#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-2+: SeActionSetItem.real_execute() tests.

SeActionSetItem is the most-used stateengine action — it sets a shng item to
a configured value when a state is entered, stayed in, or left.

The test strategy:
  • Inject item and value via name-mangling (same approach as Tier-2 tests).
  • Call real_execute() with a properly formatted actionname string.
  • Assert that the MockItem's value was updated to the expected value.
  • Also test the returnvalue=True shortcut (used internally for previews).

Because SeActionMixSetForce.real_execute() uses update_webif_actionstatus()
which tries to read self._abitem.webif_infos[state.id], that call is wrapped in
try/except inside the action and will log a warning without failing the test.
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockAbItem, MockItem
from plugins.stateengine import StateEngineDefaults


def _setup():
    StateEngineDefaults.logger = logging.getLogger('test.se')


class _MockState:
    id = 'mock.state'
    name = 'Mock State'


def _make_set_action(abitem, name='light'):
    """Build a SeActionSetItem with item and state injected."""
    from plugins.stateengine.StateEngineAction import SeActionSetItem

    action = SeActionSetItem(abitem, name)
    action._state = _MockState()
    action._action_type = 'actions_enter'
    return action


def _inject_item(action, item):
    """Inject a target item into the action (bypasses complete() parsing)."""
    action._item = item
    action._eval_item = item


def _inject_value(action, value):
    """Inject the value to set into the action's SeValue."""
    action._value._SeValue__value = value


# ═══════════════════════════════════════════════════════════════════════════


class TestSeActionSetItemExecute(unittest.TestCase):
    """real_execute() actually calls item(value, ...) on the target item."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _run(self, item_value_before, set_to, returnvalue=False):
        """
        Create action targeting a MockItem, run it, return MockItem's value.
        """
        item = MockItem('test.light', value=item_value_before)
        action = _make_set_action(self.abitem, 'light')
        _inject_item(action, item)
        _inject_value(action, set_to)
        result = action.real_execute(
            state=_MockState(), actionname="Action 'light'", namevar='light', repeat_text='', returnvalue=returnvalue
        )
        return item, result

    def test_set_bool_true(self):
        """Action sets item from False to True."""
        item, _ = self._run(item_value_before=False, set_to=True)
        self.assertIs(item._value, True)

    def test_set_bool_false(self):
        """Action sets item from True to False."""
        item, _ = self._run(item_value_before=True, set_to=False)
        self.assertIs(item._value, False)

    def test_set_integer(self):
        """Action sets item to integer value."""
        item, _ = self._run(item_value_before=0, set_to=42)
        self.assertEqual(item._value, 42)

    def test_set_string(self):
        """Action sets item to string value."""
        item, _ = self._run(item_value_before='off', set_to='on')
        self.assertEqual(item._value, 'on')

    def test_returnvalue_true_returns_value_without_setting(self):
        """
        When returnvalue=True, the action returns the value without
        actually calling item().  The item value must remain unchanged.
        """
        item = MockItem('test.bypass', value='original')
        action = _make_set_action(self.abitem, 'bypass')
        _inject_item(action, item)
        _inject_value(action, 'changed')
        result = action.real_execute(
            state=_MockState(), actionname="Action 'bypass'", namevar='bypass', returnvalue=True
        )
        self.assertEqual(result, 'changed')  # returned the value
        self.assertEqual(item._value, 'original')  # item untouched

    def test_value_none_skips_set(self):
        """
        When _value is None (empty), real_execute() should skip the item set.
        The item value must remain unchanged.
        """
        item = MockItem('test.skip', value='unchanged')
        action = _make_set_action(self.abitem, 'skip')
        _inject_item(action, item)
        # Leave _value as None (is_empty() == True)
        action.real_execute(state=_MockState(), actionname="Action 'skip'", namevar='skip', value=None)
        self.assertEqual(item._value, 'unchanged')


# ═══════════════════════════════════════════════════════════════════════════


class TestSeActionSetItemLast_run(unittest.TestCase):
    """After real_execute(), abitem.last_run is updated with the action name."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def test_last_run_recorded(self):
        import datetime

        item = MockItem('test.item', value=False)
        action = _make_set_action(self.abitem, 'myaction')
        _inject_item(action, item)
        _inject_value(action, True)
        action.real_execute(state=_MockState(), actionname="Action 'myaction'", namevar='myaction')
        self.assertIn('myaction', self.abitem.last_run)
        self.assertIsInstance(self.abitem.last_run['myaction'], datetime.datetime)


if __name__ == '__main__':
    unittest.main()
