"""
Checks the version bounds (sh_/py_/sdp_ min/max version) of every current plugin's plugin.yaml.

An unquoted bound is a YAML number: ``py_minversion: 3.10`` is read as 3.1. The detection is
tools/check_versions.py's misread_version_bounds(); unquoted bounds that read back as written
(``3.11``) pass.
"""

import importlib.util
import pathlib

PLUGINS_DIR = pathlib.Path(__file__).resolve().parents[1]
CHECK_VERSIONS = PLUGINS_DIR.parent / 'tools' / 'check_versions.py'


def _check_versions():
    spec = importlib.util.spec_from_file_location('check_versions', CHECK_VERSIONS)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _current_plugin_yamls() -> list[pathlib.Path]:
    """plugin.yaml of every plugin directory, without superseded versions (_pv_*) and local variants (priv_*)."""
    return sorted(
        path for path in PLUGINS_DIR.glob('*/plugin.yaml') if not path.parent.name.startswith(('_', '.', 'priv_'))
    )


def test_version_bounds_are_read_as_written():
    misread_version_bounds = _check_versions().misread_version_bounds
    plugin_yamls = _current_plugin_yamls()
    assert plugin_yamls, f'no plugin.yaml found below {PLUGINS_DIR}'

    misread = [
        f'{path.parent.name}: {bound}'
        for path in plugin_yamls
        for bound in misread_version_bounds(path.read_text(encoding='utf-8'))
    ]
    assert misread == []
