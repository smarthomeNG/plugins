"""
Tests for the plugin selection of plugins/conftest.py's pytest_ignore_collect.

Each test runs a real `pytest --collect-only` over a temporary plugins tree that holds a copy of
conftest.py, so the hook is exercised exactly as pytest calls it.

Coverage
--------
- a plugin without version bounds is collected
- a plugin whose py_minversion is above the running Python is not collected
- a plugin whose py_maxversion is below the running Python is not collected
- a plugin whose plugin.yaml cannot be parsed is still collected
"""

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

PLUGINS_DIR = pathlib.Path(__file__).resolve().parents[1]
CORE_DIR = PLUGINS_DIR.parent


class TestVersionBoundsCollection(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = pathlib.Path(self._tmp.name)
        shutil.copy(PLUGINS_DIR / 'conftest.py', self.root / 'conftest.py')

    def _make_plugin(self, name, plugin_yaml):
        tests_dir = self.root / name / 'tests'
        tests_dir.mkdir(parents=True)
        (self.root / name / 'plugin.yaml').write_text(plugin_yaml)
        (tests_dir / 'test_x.py').write_text('def test_x():\n    pass\n')

    def _collected_plugins(self):
        env = {**os.environ, 'PYTHONPATH': str(CORE_DIR)}
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', '--collect-only', '-q', '-p', 'no:cacheprovider', str(self.root)],
            capture_output=True,
            text=True,
            env=env,
            cwd=self.root,
        )
        return sorted({line.split('/')[0] for line in result.stdout.splitlines() if '::' in line})

    def test_plugin_without_bounds_is_collected(self):
        self._make_plugin('plain', 'plugin:\n    version: 1.0.0\n')
        self.assertEqual(self._collected_plugins(), ['plain'])

    def test_plugin_requiring_newer_python_is_not_collected(self):
        self._make_plugin('future', "plugin:\n    version: 1.0.0\n    py_minversion: '99.0'\n")
        self.assertEqual(self._collected_plugins(), [])

    def test_plugin_limited_to_older_python_is_not_collected(self):
        self._make_plugin('past', "plugin:\n    version: 1.0.0\n    py_maxversion: '1.0'\n")
        self.assertEqual(self._collected_plugins(), [])

    def test_plugin_with_unparsable_plugin_yaml_is_still_collected(self):
        self._make_plugin('broken', 'plugin: [unclosed\n')
        self.assertEqual(self._collected_plugins(), ['broken'])


if __name__ == '__main__':
    unittest.main()
