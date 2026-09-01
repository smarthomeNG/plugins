#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for the matter_server role's alias resolution/validation
(server.resolve_node_id, server.validate_alias_references) - exercised
directly against Matter.__new__() with only the attributes these
functions touch set, no SmartPlugin/Items framework needed since neither
uses it.
"""

import unittest

from plugins.matter import Matter, server


class _FakeItem:
    """
    Real .conf dict + ancestor-chain support (return_parent()/
    _is_top_of_item_tree()) - the exact duck-typed interface
    lib.item._internal._pathresolution.find_attribute_with_instance() needs
    from its `item` argument, so find_attribute_with_instance() below
    delegates to the real core implementation rather than reimplementing
    ancestor-walk logic in a test fake (that logic has its own real-Item
    coverage in tests/test_item_pathresolution.py - this fake only needs to
    prove server.resolve_node_id()/resolve_addressing() call it correctly).
    """

    def __init__(self, path, conf=None, parent=None):
        self._path = path
        self.conf = conf or {}
        self._parent = parent

    class _Property:
        def __init__(self, path):
            self.path = path

    @property
    def property(self):
        return self._Property(self._path)

    def _is_top_of_item_tree(self):
        return self._parent is None

    def return_parent(self):
        return self._parent

    def find_attribute_with_instance(self, attr, default=None, level=-1, strict=False, plugin=None):
        from lib.item._internal._pathresolution import find_attribute_with_instance as _core_find

        return _core_find(self, attr, default=default, level=level, strict=strict, plugin=plugin)


class _FakeLogger:
    def __init__(self):
        self.errors = []

    def error(self, msg):
        self.errors.append(msg)

    def info(self, msg):
        pass


def _make_plugin(instance=''):
    plugin = Matter.__new__(Matter)
    plugin.logger = _FakeLogger()
    plugin.server_alias_base_item = 'matter.aliases'
    plugin._server_aliases = {}
    plugin._server_node_to_alias = {}
    plugin._server_item_alias = {}
    plugin._SmartPlugin__instance = instance  # what _set_instance_name() actually sets
    return plugin


class _FakeBaseItem:
    """Stand-in for the alias_base_item Item - only what
    server.ensure_alias_base_item()/server.preserve_core_config() touch."""

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
    """Regression test: an item referencing matter_alias must not fail
    permanently (never registered for dispatch) if it parses before its
    alias definition - item tree load order across yaml files isn't
    guaranteed either way."""

    def test_unresolved_alias_at_parse_time_returns_placeholder_not_none(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1', conf={'matter_alias': 'socket16'})

        self.assertEqual(server.resolve_node_id(plugin, item), (0, 'socket16'))
        self.assertEqual(plugin.logger.errors, [])

    def test_already_resolved_alias_returns_real_node_id(self):
        plugin = _make_plugin()
        plugin._server_aliases['socket16'] = 5
        item = _FakeItem('socket1', conf={'matter_alias': 'socket16'})

        self.assertEqual(server.resolve_node_id(plugin, item), (5, 'socket16'))

    def test_matter_node_still_works_without_alias(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1', conf={'matter_node': 7})

        self.assertEqual(server.resolve_node_id(plugin, item), (7, None))

    def test_neither_matter_node_nor_matter_alias_still_fails(self):
        plugin = _make_plugin()
        item = _FakeItem('socket1')

        self.assertIsNone(server.resolve_node_id(plugin, item))
        self.assertEqual(len(plugin.logger.errors), 1)


class TestResolveAddressingMultiInstance(unittest.TestCase):
    """Regression tests: resolve_node_id()/resolve_addressing() must call
    Item.find_attribute_with_instance(), not Item.find_attribute() directly
    (which has no idea attr@instance exists) - matter_node@matter2 on a
    second-instance item must resolve, not be silently invisible, logged as
    "not set on this item or any ancestor" even though it's plainly set
    (shng core, tests/test_item_pathresolution.py has the
    ancestor-walk/attr@instance coverage at that level). These tests check
    the matter plugin's own wiring to it, at the level
    resolve_node_id()/resolve_addressing() operate, not the generic lookup
    mechanism itself."""

    def test_default_instance_still_resolves_bare_attrs(self):
        plugin = _make_plugin(instance='')
        item = _FakeItem('socket1', conf={'matter_node': 7, 'matter_endpoint': 1, 'matter_cluster': 6})

        self.assertEqual(server.resolve_addressing(plugin, item), (7, 1, 6, None))

    def test_named_instance_resolves_the_users_exact_reported_item(self):
        """m2sock, instance matter2 - the exact config that failed live."""
        plugin = _make_plugin(instance='matter2')
        item = _FakeItem(
            'm2sock', conf={'matter_node@matter2': 1, 'matter_endpoint@matter2': 1, 'matter_cluster@matter2': 6}
        )

        self.assertEqual(server.resolve_addressing(plugin, item), (1, 1, 6, None))
        self.assertEqual(plugin.logger.errors, [])

    def test_bare_attr_is_invisible_to_a_named_instance(self):
        """A bare matter_node (meant for the default instance) must NOT leak
        into a named instance's resolution - the two instances address
        completely different fabrics, this would silently cross-wire them."""
        plugin = _make_plugin(instance='matter2')
        item = _FakeItem('socket1', conf={'matter_node': 7})

        self.assertIsNone(server.resolve_node_id(plugin, item))
        self.assertEqual(len(plugin.logger.errors), 1)

    def test_ancestor_inheritance_still_works_with_an_instance_suffix(self):
        """matter_node/matter_endpoint/matter_cluster are documented to be
        set once on a device's "master" item and inherited by children -
        must keep working per-instance, not just for the default instance."""
        plugin = _make_plugin(instance='matter2')
        parent = _FakeItem(
            'device2', conf={'matter_node@matter2': 3, 'matter_endpoint@matter2': 1, 'matter_cluster@matter2': 6}
        )
        child = _FakeItem('device2.power', conf={}, parent=parent)

        self.assertEqual(server.resolve_addressing(plugin, child), (3, 1, 6, None))


class TestValidateAliasReferences(unittest.TestCase):
    def test_alias_resolved_after_the_fact_is_not_flagged(self):
        plugin = _make_plugin()
        plugin._server_aliases['socket16'] = 5
        plugin._server_item_alias['socket1'] = 'socket16'

        server.validate_alias_references(plugin)

        self.assertEqual(plugin.logger.errors, [])

    def test_genuinely_unknown_alias_is_flagged(self):
        plugin = _make_plugin()
        plugin._server_item_alias['socket1'] = 'typo_alias'

        server.validate_alias_references(plugin)

        self.assertEqual(len(plugin.logger.errors), 1)
        self.assertIn('typo_alias', plugin.logger.errors[0])


class TestStopOnItemChangeDisabled(unittest.TestCase):
    """Regression guard: STOP_ON_ITEM_CHANGE must stay False - combined with
    server.ensure_alias_base_item()'s edit_item() call on its own base item,
    True would make Matter pause itself mid-run(): edit_item() sees every
    loaded plugin (item.plugins.return_plugins() is the global registry,
    not item-filtered), including Matter, already self.alive at that
    point, calls Matter.stop() before start_asyncio() ever ran, then
    resumes via a re-entrant Matter.run() call in its finally block -
    which hits the exact same edit_item() call again, recursing forever."""

    def test_stop_on_item_change_is_false(self):
        self.assertFalse(Matter.STOP_ON_ITEM_CHANGE)


class TestEnsureAliasBaseItemRemark(unittest.TestCase):
    """server.ensure_alias_base_item() must only edit_item() the base item
    ONCE, the first time it has no remark - not on every run() (checking
    item.conf instead of item.property.remark would miss an already-set
    remark on every call, feeding the recursion above)."""

    def test_remark_already_set_never_calls_edit_item(self):
        plugin = _make_plugin()
        base_item = _FakeBaseItem(remark='already set by the user')
        plugin.items = _FakeItems(base_item)

        server.ensure_alias_base_item(plugin)

        self.assertEqual(plugin.items.edit_item_calls, [])

    def test_missing_remark_calls_edit_item_once_with_default(self):
        plugin = _make_plugin()
        base_item = _FakeBaseItem(remark=None)
        plugin.items = _FakeItems(base_item)

        server.ensure_alias_base_item(plugin)

        self.assertEqual(len(plugin.items.edit_item_calls), 1)
        item, config, notify_plugins = plugin.items.edit_item_calls[0]
        self.assertIs(item, base_item)
        self.assertIn('remark', config)
        # base item is matter's own alias container, unused by any other
        # plugin - no need to notify plugins of this edit
        self.assertFalse(notify_plugins)


if __name__ == '__main__':
    unittest.main()
