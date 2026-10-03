import copy
import http.client
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import server


def sample():
    floor = {'floor': 1, 'wave_count': 2, 'extra_floor': 'retain', 'waves': [
        {'wave': w, 'group_count': 1, 'extra_wave': [w], 'groups': [
            {'mob_id': 1002 + g, 'count': 2 if g == 0 else 0, 'extra_group': 'keep'} for g in range(4)]}
        for w in range(1, 21)]}
    other = copy.deepcopy(floor)
    other['floor'] = 2
    return {'project_schema': 1, 'extra': {'untouched': True},
            'monsters': [{'id': mid} for mid in range(1002, 1007)],
            'wave_preset': {'schema_version': 3, 'extra_preset': 'keep', 'floors': [floor, other]}}


def change(path, expected, value):
    return {'changes': [{'path': path, 'expected': expected, 'value': value}]}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'project.json'
        self.original = sample()
        self.path.write_text(json.dumps(self.original), encoding='utf-8')
        self.store = server.ProjectStore(self.path)

    def tearDown(self):
        self.store.close()
        self.directory.cleanup()

    def read(self):
        return json.loads(self.path.read_text(encoding='utf-8'))

    def test_floor_only_and_metadata(self):
        self.assertEqual(set(self.store.floor(1)['floor']), set(self.original['wave_preset']['floors'][0]))
        self.assertNotIn('waves', self.store.metadata()['floors'][0])
        self.assertEqual(len(self.store.metadata()['floors']), 2)

    def test_unrelated_stale_edits_merge(self):
        self.store.patch(1, change('wave_count', 2, 3))
        self.store.patch(1, change('waves/1/groups/1/count', 2, 4))
        floor = self.store.floor(1)['floor']
        self.assertEqual(floor['wave_count'], 3)
        self.assertEqual(floor['waves'][0]['groups'][0]['count'], 4)

    def test_same_field_conflict_preserves_file(self):
        self.store.patch(1, change('wave_count', 2, 3))
        before = self.path.read_bytes()
        with self.assertRaises(server.EditError) as caught:
            self.store.patch(1, change('wave_count', 2, 4))
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(caught.exception.conflicts[0]['current'], 3)
        self.assertEqual(self.path.read_bytes(), before)

    def test_invalid_batch_is_atomic(self):
        before = self.path.read_bytes()
        with self.assertRaises(server.EditError):
            self.store.patch(1, {'changes': [change('wave_count', 2, 3)['changes'][0], change('waves/1/groups/1/count', 2, 9)['changes'][0]]})
        self.assertEqual(before, self.path.read_bytes())

    def test_unknown_fields_and_hidden_data_retained(self):
        self.store.patch(1, change('wave_count', 2, 1))
        expected = copy.deepcopy(self.original)
        expected['wave_preset']['floors'][0]['wave_count'] = 1
        self.assertEqual(self.read(), expected)
        self.store.patch(1, change('waves/20/groups/4/count', 0, 7))
        self.assertEqual(self.store.floor(1)['floor']['waves'][19]['groups'][3]['count'], 7)

    def test_backup_exact_original(self):
        before = self.path.read_bytes()
        self.store.patch(1, change('wave_count', 2, 3))
        self.assertEqual(next((self.path.parent / 'project.json.backups').glob('*.json')).read_bytes(), before)

    def test_paths_and_duplicate_rejected(self):
        for path in ('../floor', 'waves/0/group_count', 'waves/21/group_count', 'waves/1/groups/5/count', 'extra'):
            with self.subTest(path=path), self.assertRaises(server.EditError):
                self.store.patch(1, change(path, 2, 3))
        item = change('wave_count', 2, 3)['changes'][0]
        with self.assertRaises(server.EditError):
            self.store.patch(1, {'changes': [item, item]})

    def test_invalid_integer_and_catalog(self):
        for path, expected, value in [('wave_count', 2, True), ('wave_count', 2, 2.5), ('wave_count', 2, 21), ('waves/1/groups/1/count', 2, 0), ('waves/1/groups/1/mob_id', 1002, 9999)]:
            with self.subTest(value=value), self.assertRaises(server.EditError):
                self.store.patch(1, change(path, expected, value))

    def test_second_writer_refused_and_lock_released(self):
        with self.assertRaises(server.EditError):
            server.ProjectStore(self.path)
        self.store.close()
        other = server.ProjectStore(self.path)
        other.close()

    def test_separate_process_writer_refused(self):
        script = 'import server,sys; server.ProjectStore(sys.argv[1])'
        result = subprocess.run([sys.executable, '-c', script, str(self.path)], cwd=Path(server.__file__).parent,
                                capture_output=True, text=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('already owns this project', result.stderr)

    def test_concurrent_threads_merge(self):
        errors = []
        def edit(fid):
            try:
                self.store.patch(fid, change('wave_count', 2, 3))
            except Exception as error:
                errors.append(error)
        threads = [threading.Thread(target=edit, args=(fid,)) for fid in (1, 2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual([f['wave_count'] for f in self.read()['wave_preset']['floors']], [3, 3])

    def test_replace_failure_keeps_project(self):
        self.store.patch(1, change('wave_count', 2, 3))
        before = self.path.read_bytes()
        real_replace = server.os.replace
        def fail_project(src, dst):
            if Path(dst) == self.path:
                raise OSError('simulated replace failure')
            return real_replace(src, dst)
        with patch.object(server.os, 'replace', fail_project), self.assertRaises(OSError):
            self.store.patch(1, change('wave_count', 3, 4))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])


class HTTPTests(unittest.TestCase):
    setUp = StoreTests.setUp
    tearDown = StoreTests.tearDown

    def test_http_guards_and_round_trip(self):
        with server.EditorServer(('127.0.0.1', 0), self.store) as app:
            thread = threading.Thread(target=app.serve_forever)
            thread.start()
            try:
                def req(method, path, payload=None, **headers):
                    connection = http.client.HTTPConnection('127.0.0.1', app.server_port, timeout=3)
                    connection.request(method, path, body=None if payload is None else json.dumps(payload), headers=headers)
                    response = connection.getresponse()
                    result = response.status, response.read()
                    connection.close()
                    return result
                self.assertEqual(req('GET', '/api/floors/1')[0], 200)
                self.assertEqual(req('GET', '/api/floors/1', Host='evil.example')[0], 403)
                self.assertEqual(req('GET', '/api/floors/1', Origin='https://evil.example')[0], 403)
                self.assertEqual(req('GET', '/../server.py')[0], 404)
                self.assertEqual(req('GET', '/?mode=file')[0], 200)
                for name in ('browser-store.js', 'monster-names.ko.json', 'sample-project.json'):
                    self.assertEqual(req('GET', '/' + name)[0], 200)
                self.assertEqual(req('GET', '/server.py')[0], 404)
                self.assertEqual(req('PATCH', '/api/floors/1', change('wave_count', 2, 3))[0], 403)
                headers = {'Origin': app.origin, 'X-Tower-Token': app.token, 'Content-Type': 'application/json'}
                self.assertEqual(req('PATCH', '/api/floors/1', change('wave_count', 2, 3), **headers)[0], 200)
                self.assertEqual(req('PATCH', '/api/floors/1', change('wave_count', 2, 4), **headers)[0], 409)
                self.assertEqual(req('PATCH', '/api/floors/1', {'changes': []}, **dict(headers, **{'Content-Length': '100001'}))[0], 413)
            finally:
                app.shutdown()
                thread.join()


if __name__ == '__main__':
    unittest.main()
