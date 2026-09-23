#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/matter/mapping.py - pure mapping types, dispatch keys and ItemIndex."""

import unittest

from plugins.matter.mapping import (
    AVAILABILITY,
    AliasNode,
    AttributeMapping,
    CommandMapping,
    DirectNode,
    ItemIndex,
    attribute_path,
    dispatch_key,
)


class _Item:
    def __init__(self, path):
        self.property = type('Property', (), {'path': path})()


class TestDispatchKey(unittest.TestCase):
    def test_direct_and_alias_keys_never_collide(self):
        self.assertNotEqual(dispatch_key(DirectNode(5), '1/6/0'), dispatch_key(AliasNode('5'), '1/6/0'))

    def test_availability_key_differs_from_attribute_key(self):
        self.assertNotEqual(dispatch_key(DirectNode(5), AVAILABILITY), dispatch_key(DirectNode(5), '0/0/0'))


class TestAttributeMapping(unittest.TestCase):
    def test_path(self):
        mapping = AttributeMapping(DirectNode(5), endpoint_id=1, cluster_id=6, attribute_id=0)

        self.assertEqual(mapping.path, attribute_path(1, 6, 0))
        self.assertEqual(mapping.path, '1/6/0')


class TestCommandMapping(unittest.TestCase):
    def test_value_independent_command_fires_only_on_truthy(self):
        mapping = CommandMapping(DirectNode(1), 1, 6, 'toggle')

        self.assertTrue(mapping.should_fire(True))
        self.assertFalse(mapping.should_fire(False))

    def test_on_off_pair_fires_on_every_write_and_picks_the_command(self):
        mapping = CommandMapping(DirectNode(1), 1, 6, 'on', command_name_false='off')

        self.assertTrue(mapping.should_fire(False))
        self.assertEqual(mapping.resolve_command_name(True), 'on')
        self.assertEqual(mapping.resolve_command_name(False), 'off')

    def test_value_placeholder_is_substituted(self):
        mapping = CommandMapping(DirectNode(1), 1, 8, 'moveToLevel', params={'level': '$value', 'transitionTime': 0})

        self.assertEqual(mapping.resolve_params(42), {'level': 42, 'transitionTime': 0})


class TestItemIndex(unittest.TestCase):
    def test_add_and_lookup(self):
        index = ItemIndex()
        item = _Item('a.b')
        index.add('k', item)

        self.assertEqual(index.items_for('k'), (item,))
        self.assertEqual(index.items_for('unknown'), ())

    def test_remove_drops_the_item_from_every_key(self):
        index = ItemIndex()
        item, other = _Item('a.b'), _Item('a.c')
        index.add('k1', item)
        index.add('k2', item)
        index.add('k1', other)

        self.assertTrue(index.remove('a.b'))

        self.assertEqual(index.items_for('k1'), (other,))
        self.assertEqual(index.items_for('k2'), ())
        self.assertFalse(index.remove('a.b'))


if __name__ == '__main__':
    unittest.main()
