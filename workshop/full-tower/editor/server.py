"""Offline Tower editor. Edits one explicitly selected authoring JSON, never game state."""
import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MAX_BODY = 100_000
MAX_PROJECT = 16_000_000
STATIC = Path(__file__).resolve().parent
FIELD = re.compile(r"(?:wave_count|waves/([1-9]|1[0-9]|20)/(?:group_count|groups/([1-4])/(?:mob_id|count)))\Z")


class EditError(Exception):
    def __init__(self, message, status=400, conflicts=None):
        super().__init__(message)
        self.status, self.conflicts = status, conflicts


def integer(value, low, high, label):
    if type(value) is not int or not low <= value <= high:
        raise EditError(f"{label}: integer {low}–{high} required")


def preset(document):
    value = document.get('wave_preset', document)
    if not isinstance(value, dict) or value.get('schema_version') != 3 or not isinstance(value.get('floors'), list):
        raise EditError('Expected schema_version 3 wave_preset with floors')
    return value


def validate_floor(floor):
    """Same numeric/topology bounds as wave_settings.default_preset; retain extras."""
    if not isinstance(floor, dict):
        raise EditError('Invalid floor')
    integer(floor.get('floor'), 1, 200, 'Floor')
    integer(floor.get('wave_count'), 1, 20, 'Wave count')
    waves = floor.get('waves')
    if not isinstance(waves, list) or len(waves) != 20:
        raise EditError('Every floor must retain 20 waves')
    for wid, wave in enumerate(waves, 1):
        if not isinstance(wave, dict) or type(wave.get('wave')) is not int or wave.get('wave') != wid:
            raise EditError('Wave identifiers must be ordered 1–20')
        integer(wave.get('group_count'), 1, 4, 'Group count')
        groups = wave.get('groups')
        if not isinstance(groups, list) or len(groups) != 4:
            raise EditError('Every wave must retain four groups')
        for group in groups:
            if not isinstance(group, dict):
                raise EditError('Invalid group')
            integer(group.get('mob_id'), 1, 200000, 'Monster ID')
            integer(group.get('count'), 0, 8, 'Count')
        integer(sum(g['count'] for g in groups[:wave['group_count']]), 1, 8, f'Wave {wid} active total')


def read_json(path):
    raw = path.read_bytes()
    if len(raw) > MAX_PROJECT:
        raise EditError('Project exceeds 16 MB')
    try:
        value = json.loads(raw.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as error:
        raise EditError(f'Invalid project JSON: {error}') from error
    if not isinstance(value, dict):
        raise EditError('Project must be an object')
    return value, raw


def validate_project(document):
    if not isinstance(document, dict):
        raise EditError('Project must be an object')
    floors = preset(document)['floors']
    if not 1 <= len(floors) <= 200:
        raise EditError('Expected 1–200 stored floors')
    seen = set()
    for floor in floors:
        validate_floor(floor)
        if floor['floor'] in seen:
            raise EditError('Duplicate floor identifier')
        seen.add(floor['floor'])
    return document


def atomic_write(path, raw):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ProjectStore:
    def __init__(self, project, catalog=None):
        self.path = Path(project).resolve(strict=True)
        if not self.path.is_file():
            raise EditError('Project must be a file')
        self.writer = open(str(self.path) + '.editor.lock', 'a+b')
        if os.fstat(self.writer.fileno()).st_size == 0:
            self.writer.write(b'0')
            self.writer.flush()
        self.writer.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.writer.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.writer.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.writer.close()
            raise EditError('Another Tower editor already owns this project', 409) from error
        self.lock = threading.RLock()
        self.catalog = {}
        self.explicit_catalog = bool(catalog)
        try:
            if catalog:
                self.catalog, _ = read_json(Path(catalog))
            document, _ = self._load()
            if not catalog:
                self.catalog = {'monsters': document.get('monsters', [])}
        except Exception:
            self.close()
            raise

    def close(self):
        if self.writer.closed:
            return
        self.writer.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(self.writer.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(self.writer.fileno(), fcntl.LOCK_UN)
        self.writer.close()

    def _load(self):
        document, raw = read_json(self.path)
        validate_project(document)
        return document, raw

    def _floor(self, document, fid):
        for floor in preset(document)['floors']:
            if floor['floor'] == fid:
                return floor
        raise EditError('Floor not found', 404)

    def metadata(self):
        with self.lock:
            document, _ = self._load()
            return {'project': self.path.name, 'floors': [
                {'floor': f['floor'], 'wave_count': f['wave_count']}
                for f in preset(document)['floors']],
                'limits': {'waves': 20, 'groups': 4, 'active_total': 8}}

    def floor(self, fid):
        with self.lock:
            document, raw = self._load()
            return {'floor': copy.deepcopy(self._floor(document, fid)), 'revision': hashlib.sha256(raw).hexdigest()}

    @staticmethod
    def target(floor, path):
        if not isinstance(path, str) or not FIELD.fullmatch(path):
            raise EditError('Unsupported field path')
        parts = path.split('/')
        if len(parts) == 1:
            return floor, parts[0]
        wave = floor['waves'][int(parts[1]) - 1]
        if len(parts) == 3:
            return wave, parts[2]
        return wave['groups'][int(parts[3]) - 1], parts[4]

    def patch(self, fid, payload):
        if not isinstance(payload, dict) or set(payload) != {'changes'}:
            raise EditError('Expected only a changes array')
        changes = payload['changes']
        if not isinstance(changes, list) or not 1 <= len(changes) <= 181:
            raise EditError('Expected 1–181 field changes')
        with self.lock:
            document, original = self._load()
            floor = self._floor(document, fid)
            seen, conflicts = set(), []
            for change in changes:
                if not isinstance(change, dict) or set(change) != {'path', 'expected', 'value'}:
                    raise EditError('Each change requires path, expected and value')
                container, key = self.target(floor, change['path'])
                if change['path'] in seen:
                    raise EditError('Duplicate field path')
                seen.add(change['path'])
                if type(change['expected']) is not int or type(change['value']) is not int:
                    raise EditError('Expected and value must be integers')
                catalog = self.catalog.get('monsters', []) if self.explicit_catalog else document.get('monsters', [])
                if key == 'mob_id' and catalog and change['value'] not in {m['id'] for m in catalog}:
                    raise EditError('Select a monster from the project catalog')
                if container[key] != change['expected']:
                    conflicts.append({'path': change['path'], 'expected': change['expected'], 'current': container[key]})
            if conflicts:
                raise EditError('Another edit changed these fields. Reload before retrying.', 409, conflicts)
            for change in changes:
                container, key = self.target(floor, change['path'])
                container[key] = change['value']
            validate_floor(floor)
            raw = (json.dumps(document, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
            # Content-addressed backup keeps every distinct prior version, without pruning.
            backups = self.path.parent / (self.path.name + '.backups')
            backups.mkdir(exist_ok=True)
            backup = backups / (hashlib.sha256(original).hexdigest() + '.json')
            if not backup.exists():
                atomic_write(backup, original)
            # Detect uncoordinated external writes during validation before replacing.
            if self.path.read_bytes() != original:
                raise EditError('Project changed outside this editor; reload and retry.', 409)
            atomic_write(self.path, raw)
            return {'floor': copy.deepcopy(floor), 'revision': hashlib.sha256(raw).hexdigest(), 'saved_fields': len(changes)}


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, store):
        super().__init__(address, Handler)
        self.store, self.token = store, secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def respond(self, status, value, content_type='application/json; charset=utf-8'):
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def guard(self, write=False):
        if self.headers.get('Host') != self.server.origin.removeprefix('http://'):
            raise EditError('Invalid localhost Host', 403)
        origin = self.headers.get('Origin')
        if origin and origin != self.server.origin:
            raise EditError('Cross-origin requests are forbidden', 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise EditError('Cross-site requests are forbidden', 403)
        if write and (origin != self.server.origin or self.headers.get('X-Tower-Token') != self.server.token):
            raise EditError('Editor token and same-origin request required', 403)

    def run_request(self, write=False):
        try:
            self.guard(write)
            if not write:
                if self.path.split('?', 1)[0] in ('/', '/index.html', '/app.js', '/style.css', '/browser-store.js', '/monster-names.ko.json', '/sample-project.json'):
                    route = self.path.split('?', 1)[0]
                    name = 'index.html' if route == '/' else route[1:]
                    types = {'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'style.css': 'text/css; charset=utf-8', 'browser-store.js': 'text/javascript; charset=utf-8', 'monster-names.ko.json': 'application/json; charset=utf-8'}
                    return self.respond(200, (STATIC / name).read_bytes(), types.get(name, 'application/json; charset=utf-8'))
                if self.path == '/api/floors':
                    return self.respond(200, dict(self.server.store.metadata(), token=self.server.token))
                if self.path == '/api/catalog':
                    return self.respond(200, self.server.store.catalog)
            match = re.fullmatch(r'/api/floors/([1-9]\d{0,2})', self.path)
            if not match:
                raise EditError('Not found', 404)
            fid = int(match[1])
            if not write:
                return self.respond(200, self.server.store.floor(fid))
            if self.headers.get('Transfer-Encoding'):
                raise EditError('Chunked requests are unsupported')
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise EditError('application/json required', 415)
            length = self.headers.get('Content-Length', '')
            if not length.isascii() or not length.isdigit() or not 1 <= int(length) <= MAX_BODY:
                raise EditError('Request body exceeds bounds', 413)
            self.connection.settimeout(5)
            raw = self.rfile.read(int(length))
            if len(raw) != int(length):
                raise EditError('Incomplete body')
            try:
                payload = json.loads(raw.decode('utf-8'))
            except (ValueError, UnicodeError) as error:
                raise EditError('Invalid JSON body') from error
            return self.respond(200, self.server.store.patch(fid, payload))
        except EditError as error:
            self.respond(error.status, {'error': str(error), 'conflicts': error.conflicts or []})
        except (OSError, ValueError, TimeoutError) as error:
            self.respond(500, {'error': f'File/request operation failed: {error}'})

    def do_GET(self):
        self.run_request()

    def do_PATCH(self):
        self.run_request(True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, type=Path)
    parser.add_argument('--catalog', type=Path)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    store = ProjectStore(args.project, args.catalog)
    try:
        with EditorServer(('127.0.0.1', args.port), store) as server:
            print(f'Tower editor: {server.origin} (Ctrl+C to stop)', flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        store.close()


if __name__ == '__main__':
    main()
