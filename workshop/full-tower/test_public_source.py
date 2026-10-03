"""Source-only regression checks; no GRF, installed game or build fixture needed."""
import copy
import unittest
from pathlib import Path

import json_project
from editor.server import validate_project
from public_paths import BUILD, LOCAL, REPOSITORY, require_output, sanitize
import full_tower


class PublicSourceTests(unittest.TestCase):
    def test_complete_authored_content_and_editor_sample(self):
        base = json_project.chapterkit.data()
        json_project.chapterkit.validate(base)
        extension = json_project.load(json_project.HERE / 'content/floors11-20.json')
        resolved = full_tower.prepare(json_project.wave_settings.combat_content(base), extension)
        self.assertEqual([f['id'] for f in resolved['floors']], list(range(1, 21)))
        self.assertEqual(resolved['target_floor_capacity'], 200)
        self.assertEqual(len(json_project.wave_settings.catalog_monsters(resolved)), 55)
        validate_project(json_project.load(json_project.HERE / 'editor/sample-project.json'))

    def test_compiled_render_retains_save_namespace_and_has_no_app_settings_reads(self):
        base = json_project.chapterkit.data()
        extension = json_project.load(json_project.HERE / 'content/floors11-20.json')
        resolved = full_tower.prepare(json_project.wave_settings.combat_content(base), extension)
        site = json_project.load(json_project.WORKSHOP / 'chapter-one/config/site.example.json')
        site.update(npc_encoding='utf-8', evidence_note='Synthetic source-only test; no game observations.')
        site['prontera_return'] = {'x': 165, 'y': 189}
        text = json_project.chapterkit.render(base, site, installation_candidate=True,
            settings_mod_name='midgard-ascent', extension=extension, compiled_preset=resolved['wave_preset'])
        self.assertNotIn('F_ModSetting', text)
        self.assertIn('ohkt_main_clear', text)
        self.assertIn('ohkt_trial_done', text)
        self.assertIn('prontera,165,191', text)
        self.assertIn('ohkt10', text)

    def test_output_guard_allows_only_nested_artifacts(self):
        for root in (BUILD, LOCAL):
            self.assertEqual(require_output(root / 'test' / 'project.json'), (root / 'test' / 'project.json').resolve())
        for path in (REPOSITORY, BUILD, LOCAL, REPOSITORY / 'workshop' / 'project.json', BUILD / '..' / 'escape'):
            with self.assertRaises(ValueError):
                require_output(path)

    def test_evidence_sanitization_keeps_identity_and_hash(self):
        evidence = {'archive': 'D:/private/client/data.grf', 'sha256': 'abc',
                    'source_candidate': '/private/native-candidate', 'path': 'source-spawns/morocc.txt',
                    'readable': True, 'signature_matches': True, 'url': 'https://example.test/source'}
        before = copy.deepcopy(evidence)
        safe = sanitize(evidence)
        self.assertEqual(safe['archive'], 'local-source/data.grf')
        self.assertEqual(safe['source_candidate'], 'local-source/native-candidate')
        self.assertEqual(safe['sha256'], 'abc')
        self.assertEqual(safe['path'], evidence['path'])
        self.assertEqual(safe['url'], evidence['url'])
        self.assertEqual(evidence, before)

    def test_repository_data_contains_no_private_machine_paths(self):
        for path in json_project.WORKSHOP.rglob('*.json'):
            text = path.read_text(encoding='utf-8')
            self.assertNotIn('C:' + chr(92) + chr(92) + 'Users', text, str(path))
            self.assertNotIn('C:/Users/', text, str(path))
            self.assertNotIn('tower-workshop/local/', text, str(path))


if __name__ == '__main__':
    unittest.main()
