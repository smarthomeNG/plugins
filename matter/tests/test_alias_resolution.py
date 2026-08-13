#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for Matter's alias resolution/validation (_resolve_node_id,
_validate_alias_references) - exercised directly against Matter.__new__()
with only the attributes these methods touch set, no SmartPlugin/Items
framework needed since neither method uses it.
"""

import unittest

from plugins.matter import Matter


class _FakeItem:
    def __init__(self, path, matter_alias=None, matter_node=None):
        self._path = path
        self._matter_alias = matter_alias
        self._matter_node = matter_node

    class _Property:
        def __init__(self, path):
            self.path = path

    @property
    def property(self):
        return self._Property(self._path)

    def find_attribute(self, attr, default=None):
        if attr == 'matter_alias':
            return self._matter_alias if self._matter_alias is not None else default
        if attr == 'matter_node':
            return self._matter_node if self._matter_node is not None else default
        return default


class _FakeLogger:
    def __init__(self):
        self.errors = []

    def error(self, msg):
        self.errors.append(msg)

    def info(self, msg):
        pass


def _make_plugin():
    plugin = Matter.__new__(Matter)
    plugin.logger = _FakeLogger()
    plugin.alias_base_item = 'matter.aliases'
    plugin._aliases = {}
    plugin._node_to_alias = {}
    plugin._item_alias = {}
    return plugin


class _FakeBaseItem:
    """Stand-in for the alias_base_item Item - only what
    _ensure_alias_base_item()/_preserve_core_config() touch."""

    def __init__(self, remark=None, conf=None, item_type='foo'):
        self.conf = conf or {}
        self._type = item_type

        class _Property:
            def __init__(self, remark):
                self.remark = remark

        self.property = _Property(remark)

    def __call__(self):
        return 0


class _FakeItems:
    def __init__(self, item):
        self._item = item
        self.edit_item_calls = []

    def return_item(self, path):
        return self._item

    def edit_item(self, item, config, notify_plugins=True):
        self.edit_item_calls.append((item, dict(config), notify_plugins))


class TestResolveNodeIdAliasParseOrder(unittest.TestCase):
    """Regression test: an item referencing matter_alias used to fail
    permanently (never registered for dispatch) if it parsed before its
    alias definition - item tree load order across yaml files isn't
    guaranteed either way."""

    def test_unresolved_alias_at_parse_time_returns_placeholder_not_none(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1', matter_alias='socket16')

        self.assertEqual(plugin._resolve_node_id(item), (0, 'socket16'))
        self.assertEqual(plugin.logger.errors, [])

    def test_already_resolved_alias_returns_real_node_id(self):
        plugin = _make_plugin()
        plugin._aliases['socket16'] = 5
        item = _FakeItem('socket1', matter_alias='socket16')

        self.assertEqual(plugin._resolve_node_id(item), (5, 'socket16'))

    def test_matter_node_still_works_without_alias(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1', matter_node=7)

        self.assertEqual(plugin._resolve_node_id(item), (7, None))

    def test_neither_matter_node_nor_matter_alias_still_fails(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1')

        self.assertIsNone(plugin._resolve_node_id(item))
        self.assertEqual(len(plugin.logger.errors), 1)


class TestValidateAliasReferences(unittest.TestCase):
    def test_alias_resolved_after_the_fact_is_not_flagged(self):
        plugin = _make_plugin()
        plugin._aliases['socket16'] = 5
        plugin._item_alias['socket1'] = 'socket16'

        plugin._validate_alias_references()

        self.assertEqual(plugin.logger.errors, [])

    def test_genuinely_unknown_alias_is_flagged(self):
        plugin = _make_plugin()
        plugin._item_alias['socket1'] = 'typo_alias'

        plugin._validate_alias_references()

        self.assertEqual(len(plugin.logger.errors), 1)
        self.assertIn('typo_alias', plugin.logger.errors[0])


class TestStopOnItemChangeDisabled(unittest.TestCase):
    """Regression guard: STOP_ON_ITEM_CHANGE=True (the SmartPlugin default)
    combined with _ensure_alias_base_item()'s edit_item() call on its own
    base item caused Matter to pause itself mid-run() - edit_item() sees
    every loaded plugin (item.plugins.return_plugins() is the global
    registry, not item-filtered), including Matter, already self.alive at
    that point, calls Matter.stop() before start_asyncio() ever ran, then
    resumes via a re-entrant Matter.run() call in its finally block -
    which hits the exact same edit_item() call again, recursing forever."""

    def test_stop_on_item_change_is_false(self):
        self.assertFalse(Matter.STOP_ON_ITEM_CHANGE)


class TestEnsureAliasBaseItemRemark(unittest.TestCase):
    """_ensure_alias_base_item() must only edit_item() the base item ONCE,
    the first time it has no remark - not on every run(), which is what a
    remark-detection bug (checking item.conf instead of
    item.property.remark) previously caused, and what fed the recursion
    above."""

    def test_remark_already_set_never_calls_edit_item(self):
        plugin = _make_plugin()
        base_item = _FakeBaseItem(remark='already set by the user')
        plugin.items = _FakeItems(base_item)

        plugin._ensure_alias_base_item()

        self.assertEqual(plugin.items.edit_item_calls, [])

    def test_missing_remark_calls_edit_item_once_with_default(self):
        plugin = _make_plugin()
        base_item = _FakeBaseItem(remark=None)
        plugin.items = _FakeItems(base_item)

        plugin._ensure_alias_base_item()

        self.assertEqual(len(plugin.items.edit_item_calls), 1)
        item, config, notify_plugins = plugin.items.edit_item_calls[0]
        self.assertIs(item, base_item)
        self.assertIn('remark', config)
        # base item is matter's own alias container, unused by any other
        # plugin - no need to notify plugins of this edit
        self.assertFalse(notify_plugins)


if __name__ == '__main__':
    unittest.main()
