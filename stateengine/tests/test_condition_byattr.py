#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-4+: SeCondition changedby / updatedby / triggeredby sub-conditions.

These three sub-conditions are central to stateengine's suspend-detection
logic: when an item changes due to a KNX telegram the "changedby=knx" condition
becomes True, allowing a transition into a Suspend state.

The conditions read meta-properties from the target item:
  • changedby  → item.property.last_change_by
  • updatedby  → item.property.last_update_by
  • triggeredby→ item.property.last_trigger_by

The comparand is stored in a SeValue and compared against the current
meta-property value using the same __change_update_value() logic used for
ordinary value checks.

Test strategy
-------------
Inject the target item (MockItem), configure the by-attr SeValue directly via
name-mangling, set the item's property attribute, and call check().  The
_SeCondition__state stub is needed so __webif_key() doesn't crash.

Combinations tested:
  • exact match → True
  • mismatch → False
  • negate=True with match → False
  • negate=True without match → True
  • all three attribute types (changedby, updatedby, triggeredby)
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


def _make_byattr_cond(SeCondition, abitem, name, item, by_type, by_value, negate=None):
    """
    Build a SeCondition whose current-value path reads item.property.<by_type>.

    by_type: 'changedby' | 'updatedby' | 'triggeredby'
    by_value: the comparand stored in the SeValue
    """
    cond = SeCondition(abitem, name)
    cond._SeCondition__item = item
    cond._SeCondition__state = _MockState()

    if by_type == 'changedby':
        cond._SeCondition__changedby._SeValue__value = by_value
    elif by_type == 'updatedby':
        cond._SeCondition__updatedby._SeValue__value = by_value
    elif by_type == 'triggeredby':
        cond._SeCondition__triggeredby._SeValue__value = by_value
    else:
        raise ValueError(f'unknown by_type: {by_type!r}')

    if negate is not None:
        if by_type == 'changedby':
            cond._SeCondition__changedbynegate = negate
        elif by_type == 'updatedby':
            cond._SeCondition__updatedbynegate = negate
        elif by_type == 'triggeredby':
            cond._SeCondition__triggeredbynegate = negate

    return cond


# ═══════════════════════════════════════════════════════════════════════════
# changedby
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionChangedBy(unittest.TestCase):
    """last_change_by metadata matching."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def _item(self, last_change_by):
        item = MockItem('test.changedby', value=True)
        item.property.last_change_by = last_change_by
        return item

    def test_exact_match_returns_true(self):
        """last_change_by='knx', changedby='knx' → True."""
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'light', item, 'changedby', 'knx')
        self.assertTrue(cond.check(None))

    def test_mismatch_returns_false(self):
        """last_change_by='mqtt', changedby='knx' → False."""
        item = self._item('mqtt')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'light', item, 'changedby', 'knx')
        self.assertFalse(cond.check(None))

    def test_negate_with_match_returns_false(self):
        """negate=True + match → False."""
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'light', item, 'changedby', 'knx', negate=True)
        self.assertFalse(cond.check(None))

    def test_negate_without_match_returns_true(self):
        """negate=True + mismatch → True."""
        item = self._item('mqtt')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'light', item, 'changedby', 'knx', negate=True)
        self.assertTrue(cond.check(None))

    def test_stateengine_plugin_caller_matches(self):
        """StateEngine Plugin name in last_change_by matches correctly."""
        item = self._item('StateEngine Plugin')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'light', item, 'changedby', 'StateEngine Plugin')
        self.assertTrue(cond.check(None))


# ═══════════════════════════════════════════════════════════════════════════
# updatedby
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionUpdatedBy(unittest.TestCase):
    """last_update_by metadata matching."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def _item(self, last_update_by):
        item = MockItem('test.updatedby', value=True)
        item.property.last_update_by = last_update_by
        return item

    def test_exact_match(self):
        item = self._item('mqtt')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'sensor', item, 'updatedby', 'mqtt')
        self.assertTrue(cond.check(None))

    def test_mismatch(self):
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'sensor', item, 'updatedby', 'mqtt')
        self.assertFalse(cond.check(None))

    def test_negate_inverts_match(self):
        """updatedby='knx', cond=knx, negate=True → False."""
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'sensor', item, 'updatedby', 'knx', negate=True)
        self.assertFalse(cond.check(None))

    def test_negate_inverts_non_match(self):
        """updatedby='mqtt', cond=knx, negate=True → True."""
        item = self._item('mqtt')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'sensor', item, 'updatedby', 'knx', negate=True)
        self.assertTrue(cond.check(None))

    def test_empty_string_no_match(self):
        """Item with empty last_update_by doesn't match 'knx'."""
        item = self._item('')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'sensor', item, 'updatedby', 'knx')
        self.assertFalse(cond.check(None))


# ═══════════════════════════════════════════════════════════════════════════
# triggeredby
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionTriggeredBy(unittest.TestCase):
    """last_trigger_by metadata matching."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def _item(self, last_trigger_by):
        item = MockItem('test.triggeredby', value=True)
        item.property.last_trigger_by = last_trigger_by
        return item

    def test_exact_match(self):
        item = self._item('Admin')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'button', item, 'triggeredby', 'Admin')
        self.assertTrue(cond.check(None))

    def test_mismatch(self):
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'button', item, 'triggeredby', 'Admin')
        self.assertFalse(cond.check(None))

    def test_negate_inverts_match(self):
        item = self._item('Admin')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'button', item, 'triggeredby', 'Admin', negate=True)
        self.assertFalse(cond.check(None))

    def test_negate_inverts_non_match(self):
        item = self._item('knx')
        cond = _make_byattr_cond(self.SeCondition, self.abitem, 'button', item, 'triggeredby', 'Admin', negate=True)
        self.assertTrue(cond.check(None))


if __name__ == '__main__':
    unittest.main()
