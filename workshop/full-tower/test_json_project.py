import copy
import os
import json
import tempfile
import unittest
from pathlib import Path
import json_project as project

SOURCE = Path(os.environ.get('MIDGARD_TEST_SOURCE', str(project.BUILD / 'full/midgard-ascent')))


@unittest.skipUnless(SOURCE.exists(), 'Verified local candidate required')
class JsonCompilationTests(unittest.TestCase):
    def test_compiled_settings_ignore_legacy_and_keep_hidden_values(self):
        content = project.load(SOURCE / 'FULL-TOWER-CONTENT.json')
        content['wave_preset']['floors'][11]['wave_count'] = 2
        hidden = content['wave_preset']['floors'][11]['waves'][19]['groups'][3]
        hidden.update(mob_id=1002, count=7)
        before = copy.deepcopy(content)
        text = project.wave_settings.runtime(content, 'midgard-ascent', compiled=True)
        self.assertNotIn('F_ModSetting', text)
        self.assertIn('return getarg(1);', text)
        self.assertIn(project.wave_settings.encode_floor(content, 12), text)
        self.assertIn('0010027', text)
        self.assertEqual(content, before)
        self.assertIn('F_ModSetting', project.wave_settings.runtime(content, 'midgard-ascent'))

    def test_packaged_project_preserves_all_twenty_waves(self):
        project.BUILD.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=project.BUILD) as folder:
            output = Path(folder) / 'project.json'
            project.seed(SOURCE, output)
            value = project.load(output)
            original = project.load(SOURCE / 'FULL-TOWER-CONTENT.json')
            self.assertEqual(value['wave_preset'], original['wave_preset'])
            self.assertEqual(len(value['wave_preset']['floors']), 20)
            with self.assertRaises(ValueError):
                project.seed(SOURCE, output)


if __name__ == '__main__':
    unittest.main()
