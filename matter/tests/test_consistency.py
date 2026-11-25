#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Cross-checks between the plugin's three sources that cannot import each
other: plugin.yaml, sidecar/bridge.js and the Python registries
(clusters.py, bridge/expose.py).
"""

import os
import re
import unittest

from plugins.matter.bridge.expose import EXPOSE_TYPES
from plugins.matter.clusters import CLUSTERS
from plugins.matter.tests.support import PLUGIN_DIR, plugin_yaml


def _walk(node, path=()):
    """Yield (path, dict) for every nested dict of a struct definition."""
    yield path, node
    for key, value in node.items():
        if isinstance(value, dict):
            yield from _walk(value, (*path, key))


def _bridge_js_expose_types() -> set[str]:
    with open(os.path.join(PLUGIN_DIR, 'sidecar', 'bridge.js')) as f:
        source = f.read()
    block = source[
        source.index('const EXPOSE_TYPES = {') : source.index('\n};', source.index('const EXPOSE_TYPES = {'))
    ]
    return set(re.findall(r'^    (\w+): \{', block, flags=re.M))


class TestExposeTypes(unittest.TestCase):
    def test_plugin_yaml_valid_list_matches_python(self):
        valid_list = plugin_yaml()['item_attributes']['matter_expose_type']['valid_list']

        self.assertEqual(set(valid_list), set(EXPOSE_TYPES))

    def test_bridge_js_matches_python(self):
        self.assertEqual(_bridge_js_expose_types(), set(EXPOSE_TYPES))


class TestStructs(unittest.TestCase):
    def setUp(self):
        self.structs = plugin_yaml()['item_structs']

    def test_every_cluster_struct_exists_in_plugin_yaml(self):
        for spec in CLUSTERS.values():
            if spec.struct is not None:
                self.assertIn(spec.struct.name, self.structs)

    def test_struct_matter_attributes_are_instance_aware(self):
        for name, struct in self.structs.items():
            for path, node in _walk(struct):
                for key in node:
                    if key.startswith('matter_'):
                        self.assertTrue(key.endswith('@instance'), f'{name}.{".".join(path)}: {key}')


if __name__ == '__main__':
    unittest.main()
