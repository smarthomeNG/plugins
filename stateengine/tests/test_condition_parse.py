#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-3: SeCondition public-API parsing tests.

The Tier-4 tests use name-mangling to inject values directly into SeCondition's
private attributes, bypassing the parsing layer.  These tests take the opposite
approach: they call SeCondition.set() with the *same attribute values* that
stateengine would receive from an item's .conf dict, then call check() and
verify the evaluation result.

This validates end-to-end compatibility: the parsing pipeline (set()) and the
evaluation pipeline (check()) must agree on how values are stored and retrieved.

Attribute forms covered:
  se_eval   → stores an eval expression; evaluated during check()
  se_value  → stores the comparand; compared against the current value
  se_min    → numeric lower bound
  se_max    → numeric upper bound
  se_negate → inverts the match result

Items are resolved via abitem.return_item(), which looks up paths in
MockSmartHome.  Register the item first with sh.items.add_item().
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


def _make_cond(abitem, name):
    from plugins.stateengine.StateEngineCondition import SeCondition

    cond = SeCondition(abitem, name)
    cond._SeCondition__state = _MockState()
    return cond


# ═══════════════════════════════════════════════════════════════════════════
# se_eval + se_value via public set()
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetEval(unittest.TestCase):
    """
    Use cond.set('se_eval', 'expr') then cond.set('se_value', v) and check().
    """

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _check(self, eval_expr, expected_value):
        cond = _make_cond(self.abitem, 'eval_cond')
        cond.set('se_eval', eval_expr)
        cond.set('se_value', expected_value)
        return cond.check(None)

    def test_eval_true_value_true_matches(self):
        """eval='True', value=True → match."""
        self.assertTrue(self._check('True', True))

    def test_eval_false_value_true_no_match(self):
        """eval='False', value=True → no match."""
        self.assertFalse(self._check('False', True))

    def test_eval_sh_available_via_public_api(self):
        """
        eval='sh is not None' configured via set() must still have sh in scope.
        This bridges Tier-3 (public API) and Tier-2 (eval namespace).
        """
        self.assertTrue(self._check('sh is not None', True))

    def test_eval_arithmetic_expression(self):
        """eval='1 + 1', value=2 → match."""
        self.assertTrue(self._check('1 + 1', 2))

    def test_eval_arithmetic_mismatch(self):
        """eval='1 + 1', value=3 → no match."""
        self.assertFalse(self._check('1 + 1', 3))


# ═══════════════════════════════════════════════════════════════════════════
# se_negate via public set()
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetNegate(unittest.TestCase):
    """se_negate=True inverts the match result through the public API."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _check(self, eval_expr, expected_value, negate):
        cond = _make_cond(self.abitem, 'negate_cond')
        cond.set('se_eval', eval_expr)
        cond.set('se_value', expected_value)
        cond.set('se_negate', negate)
        return cond.check(None)

    def test_negate_false_matching(self):
        """negate=False + match → True (unchanged)."""
        self.assertTrue(self._check('True', True, False))

    def test_negate_true_matching(self):
        """negate=True + match → False (inverted)."""
        self.assertFalse(self._check('True', True, True))

    def test_negate_true_no_match(self):
        """negate=True + no-match → True (inverted)."""
        self.assertTrue(self._check('False', True, True))


# ═══════════════════════════════════════════════════════════════════════════
# se_min / se_max via public set()
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetMinMax(unittest.TestCase):
    """
    Use cond.set('se_eval', ...) for current value and
    cond.set('se_min', ...) / cond.set('se_max', ...) for bounds.
    """

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _check(self, current_val, min_val=None, max_val=None):
        cond = _make_cond(self.abitem, 'range_cond')
        cond.set('se_eval', str(current_val))  # expression that yields current
        if min_val is not None:
            cond.set('se_min', min_val)
        if max_val is not None:
            cond.set('se_max', max_val)
        return cond.check(None)

    def test_in_range_full_bounds(self):
        """50 in [20, 80] → match."""
        self.assertTrue(self._check(50, min_val=20, max_val=80))

    def test_below_min(self):
        """5 < min(20) → no match."""
        self.assertFalse(self._check(5, min_val=20, max_val=80))

    def test_above_max(self):
        """100 > max(80) → no match."""
        self.assertFalse(self._check(100, min_val=20, max_val=80))

    def test_only_min_above(self):
        """Only min set: 60 >= 50 → match."""
        self.assertTrue(self._check(60, min_val=50))

    def test_only_min_below(self):
        """Only min set: 30 < 50 → no match."""
        self.assertFalse(self._check(30, min_val=50))

    def test_only_max_below(self):
        """Only max set: 40 <= 50 → match."""
        self.assertTrue(self._check(40, max_val=50))

    def test_only_max_above(self):
        """Only max set: 80 > 50 → no match."""
        self.assertFalse(self._check(80, max_val=50))


# ═══════════════════════════════════════════════════════════════════════════
# se_item via public set() (resolved through return_item)
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetItem(unittest.TestCase):
    """
    Use cond.set('se_item', 'path') — the item must be registered in MockSH
    so that abitem.return_item() can resolve it.
    """

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def test_item_found_and_value_checked(self):
        """Item registered in sh, value matches → True."""
        item = MockItem('room.light')
        item.property.value = True
        self.abitem._sh.items.add_item('room.light', item)

        cond = _make_cond(self.abitem, 'light')
        cond.set('se_item', 'room.light')
        cond.set('se_value', True)
        self.assertTrue(cond.check(None))

    def test_item_found_value_mismatch(self):
        """Item registered, value does not match → False."""
        item = MockItem('room.sensor')
        item.property.value = 0
        self.abitem._sh.items.add_item('room.sensor', item)

        cond = _make_cond(self.abitem, 'sensor')
        cond.set('se_item', 'room.sensor')
        cond.set('se_value', 100)
        self.assertFalse(cond.check(None))


if __name__ == '__main__':
    unittest.main()
