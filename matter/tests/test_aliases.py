#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/matter/aliases.py - AliasRegistry."""

import unittest

from plugins.matter.aliases import AliasRegistry
from plugins.matter.mapping import AliasNode, DirectNode


class TestAliasRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = AliasRegistry()

    def test_resolve_direct_node_is_its_own_id(self):
        self.assertEqual(self.registry.resolve(DirectNode(7)), 7)

    def test_resolve_unknown_alias_is_none_not_a_placeholder(self):
        self.assertIsNone(self.registry.resolve(AliasNode('kitchen')))

    def test_set_and_resolve(self):
        self.assertTrue(self.registry.set('kitchen', 3))

        self.assertEqual(self.registry.resolve(AliasNode('kitchen')), 3)
        self.assertEqual(self.registry.snapshot(), {'kitchen': 3})

    def test_setting_the_same_target_again_is_no_change(self):
        self.registry.set('kitchen', 3)

        self.assertFalse(self.registry.set('kitchen', 3))

    def test_repoint_moves_the_reverse_mapping(self):
        self.registry.set('kitchen', 3)
        self.registry.set('kitchen', 4)

        self.assertEqual(self.registry.targets_for(3), (DirectNode(3),))
        self.assertEqual(self.registry.targets_for(4), (DirectNode(4), AliasNode('kitchen')))

    def test_remove(self):
        self.registry.set('kitchen', 3)

        self.assertEqual(self.registry.remove('kitchen'), 3)
        self.assertIsNone(self.registry.resolve(AliasNode('kitchen')))
        self.assertEqual(self.registry.targets_for(3), (DirectNode(3),))
        self.assertIsNone(self.registry.remove('kitchen'))

    def test_bound_items_are_reported_as_dependents_and_unknown_references(self):
        self.registry.bind_item('dev.switch', 'kitchen')
        self.registry.bind_item('dev.power', 'kitchen')

        self.assertEqual(self.registry.dependents('kitchen'), ['dev.power', 'dev.switch'])
        self.assertEqual(self.registry.unknown_references(), [('dev.power', 'kitchen'), ('dev.switch', 'kitchen')])

        self.registry.set('kitchen', 3)
        self.assertEqual(self.registry.unknown_references(), [])

    def test_unbind_item(self):
        self.registry.bind_item('dev.switch', 'kitchen')

        self.assertEqual(self.registry.unbind_item('dev.switch'), 'kitchen')
        self.assertIsNone(self.registry.unbind_item('dev.switch'))
        self.assertEqual(self.registry.dependents('kitchen'), [])


if __name__ == '__main__':
    unittest.main()
