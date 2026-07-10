#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-2+: Tests for SeFunctions.manual_item_update_eval.

The function is the heart of stateengine's "suspend on manual change" logic:
  - item._eval = "sh.stateengine_plugin_functions.manual_item_update_eval(
        'path', caller, source)"

Scenarios:
  NOT_ALIVE   ab_alive=False → always return current value (no flip)
  NO_INCLUDE  no se_manual_include set → flip value for any non-SE caller
  SE_CALLER   original caller is StateEngine Plugin → return current (no flip)
  EXCLUDE     se_manual_exclude list → matching caller suppressed
  INCLUDE     se_manual_include list → only listed callers trigger
  ON          se_manual_on list  → only listed callers activate (True)
"""

import logging
import os
import sys
import unittest

# ── path bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockItem
from plugins.stateengine import StateEngineDefaults
from plugins.stateengine.StateEngineFunctions import SeFunctions


# ── fixtures ──────────────────────────────────────────────────────────────


def _make_functions(sh):
    """Return a SeFunctions instance wired to sh."""
    StateEngineDefaults.logger = logging.getLogger('test.se')
    fn = SeFunctions(sh, logging.getLogger('test.se.fn'))
    return fn


def _register_item(sh, path, value=False, conf=None):
    """Create a MockItem, register it with sh.items, return it."""
    item = MockItem(path, value=value)
    if conf:
        item.conf.update(conf)
    sh.items.add_item(path, item)
    return item


# ─────────────────────────────────────────────────────────────────────────
# Helper: produce an eval call the same way stateengine does it, then call
# the function directly (since we're not running a full shng scheduler).
# ─────────────────────────────────────────────────────────────────────────


class _Base(unittest.TestCase):
    def setUp(self):
        self.sh = make_sh()
        self.fn = _make_functions(self.sh)
        # item path used across tests
        self.path = 'room.light.manual'

    def call(self, caller='knx', source='room.bus', value=False, alive=True):
        """Call manual_item_update_eval with given arguments."""
        self.fn.ab_alive = alive
        item = self.sh.items.return_item(self.path)
        if item is None:
            item = _register_item(self.sh, self.path, value=value)
        else:
            item._value = value
        return self.fn.manual_item_update_eval(self.path, caller, source)


# ═══════════════════════════════════════════════════════════════════════════
# NOT_ALIVE: plugin not yet running
# ═══════════════════════════════════════════════════════════════════════════


class TestNotAlive(_Base):
    def setUp(self):
        super().setUp()
        _register_item(self.sh, self.path, value=False)

    def test_returns_current_value_false(self):
        """When ab_alive=False the item stays False."""
        result = self.call(caller='knx', alive=False, value=False)
        self.assertIs(result, False)

    def test_returns_current_value_true(self):
        """When ab_alive=False the item stays True."""
        result = self.call(caller='knx', alive=False, value=True)
        self.assertIs(result, True)

    def test_stateengine_caller_not_alive(self):
        """Even SE caller returns current value when not alive."""
        result = self.call(caller='StateEngine Plugin', alive=False, value=False)
        self.assertIs(result, False)


# ═══════════════════════════════════════════════════════════════════════════
# NO_INCLUDE: any external caller triggers (flips) the item
# ═══════════════════════════════════════════════════════════════════════════


class TestNoIncludeLimit(_Base):
    def setUp(self):
        super().setUp()
        _register_item(self.sh, self.path, value=False)

    def test_external_caller_flips_false_to_true(self):
        """knx call flips False → True (trigger)."""
        result = self.call(caller='knx', source='bus', value=False)
        self.assertIs(result, True)

    def test_external_caller_flips_true_to_false(self):
        """knx call flips True → False (still a trigger, opposite value)."""
        result = self.call(caller='knx', source='bus', value=True)
        self.assertIs(result, False)

    def test_admin_caller_also_triggers(self):
        result = self.call(caller='Admin', source='user', value=False)
        self.assertIs(result, True)

    def test_eval_caller_resolves_to_knx_and_triggers(self):
        """Eval:knx with traceable source item also triggers."""
        src = _register_item(self.sh, 'bus.item')
        src.property.last_update_by = 'knx:end.point'
        result = self.call(caller='Eval:knx', source='bus.item', value=False)
        self.assertIs(result, True)


# ═══════════════════════════════════════════════════════════════════════════
# SE_CALLER: StateEngine Plugin must never trigger itself
# ═══════════════════════════════════════════════════════════════════════════


class TestSECallerIgnored(_Base):
    def setUp(self):
        super().setUp()
        _register_item(self.sh, self.path, value=False)

    def test_se_plugin_caller_no_trigger(self):
        """Direct StateEngine Plugin call → no flip."""
        result = self.call(caller='StateEngine Plugin', source=self.path, value=False)
        self.assertIs(result, False)

    def test_se_plugin_caller_trailing_instance(self):
        """StateEngine Plugin caller with instance suffix is also ignored."""
        result = self.call(caller='StateEngine Plugin instance1', source=self.path, value=False)
        # Should NOT trigger — se plugin identification regex must match
        # Note: actual behaviour depends on plugin_identification regex,
        # assert the result is the current value (no flip).
        self.assertIs(result, False)

    def test_eval_tracing_back_to_se_no_trigger(self):
        """Eval whose original caller is StateEngine Plugin → no trigger."""
        src = _register_item(self.sh, 'se.src.item')
        src.property.last_update_by = 'StateEngine Plugin:' + self.path
        result = self.call(caller='Eval', source='se.src.item', value=False)
        self.assertIs(result, False)


# ═══════════════════════════════════════════════════════════════════════════
# EXCLUDE list
# ═══════════════════════════════════════════════════════════════════════════


class TestExcludeList(_Base):
    def setUp(self):
        super().setUp()
        # Exclude 'autoblind' callers
        _register_item(self.sh, self.path, value=False, conf={'se_manual_exclude': 'autoblind'})

    def test_excluded_caller_no_trigger(self):
        """Caller in exclude list → no flip (returns current value)."""
        result = self.call(caller='autoblind', source='ab.source', value=False)
        self.assertIs(result, False)

    def test_non_excluded_caller_still_triggers(self):
        """Caller NOT in exclude list → still flips."""
        result = self.call(caller='knx', source='bus', value=False)
        self.assertIs(result, True)

    def test_exclude_regex_pattern(self):
        """Exclude list entries are interpreted as regexes."""
        _register_item(self.sh, 'regex.item', value=False, conf={'se_manual_exclude': 'auto.*'})
        self.fn.ab_alive = True
        result = self.fn.manual_item_update_eval('regex.item', 'autoblind', 'src')
        self.assertIs(result, False)
        result = self.fn.manual_item_update_eval('regex.item', 'knx', 'src')
        self.assertIs(result, True)

    def test_exclude_list_as_python_list(self):
        """se_manual_exclude can be a Python list."""
        _register_item(self.sh, 'list.item', value=False, conf={'se_manual_exclude': ['knx', 'zigbee']})
        self.fn.ab_alive = True
        result = self.fn.manual_item_update_eval('list.item', 'knx', 'src')
        self.assertIs(result, False)
        result = self.fn.manual_item_update_eval('list.item', 'zigbee', 'src')
        self.assertIs(result, False)
        result = self.fn.manual_item_update_eval('list.item', 'mqtt', 'src')
        self.assertIs(result, True)


# ═══════════════════════════════════════════════════════════════════════════
# INCLUDE list: only listed callers trigger
# ═══════════════════════════════════════════════════════════════════════════


class TestIncludeList(_Base):
    def setUp(self):
        super().setUp()
        # Only 'knx' callers should trigger
        _register_item(self.sh, self.path, value=False, conf={'se_manual_include': 'knx'})

    def test_included_caller_triggers(self):
        """Caller matching include list → flips the value."""
        result = self.call(caller='knx', source='bus', value=False)
        self.assertIs(result, True)

    def test_non_included_caller_no_trigger(self):
        """Caller NOT in include list → keeps current value."""
        result = self.call(caller='mqtt', source='broker', value=False)
        self.assertIs(result, False)

    def test_include_list_multiple_entries(self):
        """Include list with multiple entries."""
        _register_item(self.sh, 'multi.item', value=False, conf={'se_manual_include': ['knx', 'mqtt']})
        self.fn.ab_alive = True
        self.assertIs(self.fn.manual_item_update_eval('multi.item', 'knx', 'x'), True)
        self.assertIs(self.fn.manual_item_update_eval('multi.item', 'mqtt', 'x'), True)
        self.assertIs(self.fn.manual_item_update_eval('multi.item', 'zigbee', 'x'), False)

    def test_include_beats_exclude(self):
        """When both include and exclude are set, exclude is checked first."""
        # se_manual_exclude is checked before se_manual_include in the code.
        # A caller that is excluded should not trigger even if it would be included.
        _register_item(self.sh, 'both.item', value=False, conf={'se_manual_exclude': 'knx', 'se_manual_include': 'knx'})
        self.fn.ab_alive = True
        # excluded → no trigger (exclude checked first)
        result = self.fn.manual_item_update_eval('both.item', 'knx', 'src')
        self.assertIs(result, False)


# ═══════════════════════════════════════════════════════════════════════════
# Regression: ab_alive guard prevents false triggers during startup
# ═══════════════════════════════════════════════════════════════════════════


class TestStartupGuard(_Base):
    def test_no_flip_before_alive(self):
        """The ab_alive=False guard prevents any flip during shng startup."""
        _register_item(self.sh, self.path, value=False)
        # Simulate a sequence of calls during startup (ab_alive still False)
        for caller in ('knx', 'mqtt', 'Admin', 'Eval'):
            with self.subTest(caller=caller):
                result = self.fn.manual_item_update_eval(self.path, caller, 'some.source')
                self.assertIs(result, False, f'caller={caller!r} should not flip during startup')

    def test_flip_happens_after_alive_set(self):
        """Exactly one flip occurs after ab_alive becomes True."""
        _register_item(self.sh, self.path, value=False)
        # Before alive: no flip
        self.fn.ab_alive = False
        result_before = self.fn.manual_item_update_eval(self.path, 'knx', 'bus')
        self.assertIs(result_before, False)
        # After alive: flip
        self.fn.ab_alive = True
        result_after = self.fn.manual_item_update_eval(self.path, 'knx', 'bus')
        self.assertIs(result_after, True)


if __name__ == '__main__':
    unittest.main()
