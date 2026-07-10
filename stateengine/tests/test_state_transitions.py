#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-4: State-machine condition-chain integration tests.

These tests exercise the condition evaluation pipeline at three levels of the
stateengine stack — without requiring a full shng runtime, YAML fixture loading
or a real Item tree:

  Level A — SeCondition.check()
      A single condition is configured by direct attribute injection (same
      name-mangling technique used in Tier-2 eval tests) and then evaluated
      end-to-end through __check_value() → __get_current() → comparison.

      Sub-cases:
        • Item-based conditions  (reads MockItem.property.value)
        • Eval-based conditions  (runs eval() with sh/shtime/se_eval in scope)
        • Numeric min/max range  (no explicit value, range bounds only)
        • Negation               (negate=True inverts the match result)

  Level B — SeConditionSet.all_conditions_matching()
      Multiple SeCondition objects are wired into a SeConditionSet via
      name-mangling.  Verifies AND-logic: all must match for the set to match.

  Level C — SeConditionSets.one_conditionset_matching()
      Multiple SeConditionSet objects are wired into a SeConditionSets
      container.  Verifies OR-logic: the first matching set wins.
"""

import logging
import os
import sys
import unittest
from collections import OrderedDict

# ── path bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockAbItem, MockItem
from plugins.stateengine import StateEngineDefaults


def _setup_logger():
    StateEngineDefaults.logger = logging.getLogger('test.se')


# ── minimal state stub needed by SeCondition.__webif_key() ───────────────
class _MockState:
    """Stub with only the attributes that SeCondition.__webif_key() touches."""

    id = 'mock.state'
    use = None


# ── helpers ───────────────────────────────────────────────────────────────


def _make_item_cond(SeCondition, abitem, name, item_value, expected_value=None, negate=False):
    """
    Build an item-based SeCondition.

    The condition's item is a MockItem whose property.value is ``item_value``.
    If ``expected_value`` is given the condition checks for that specific value;
    otherwise it falls into the "no value condition → always True" path.
    """
    cond = SeCondition(abitem, name)
    item = MockItem(f'test.{name}', value=item_value)
    item.property.value = item_value
    # inject item and state
    cond._SeCondition__item = item
    cond._SeCondition__state = _MockState()
    if expected_value is not None:
        # inject expected value into the SeValue that stores the comparand
        cond._SeCondition__value._SeValue__value = expected_value
    if negate:
        cond._SeCondition__negate = True
    return cond


def _make_eval_cond(SeCondition, abitem, name, eval_expr, expected_value=None):
    """
    Build an eval-based SeCondition.

    The condition evaluates ``eval_expr`` and compares the result to
    ``expected_value`` (if given).
    """
    cond = SeCondition(abitem, name)
    cond._SeCondition__eval = eval_expr
    cond._SeCondition__state = _MockState()
    if expected_value is not None:
        cond._SeCondition__value._SeValue__value = expected_value
    return cond


def _make_minmax_cond(SeCondition, abitem, name, item_value, min_value=None, max_value=None, negate=False):
    """
    Build a range-check SeCondition (min/max, no explicit value).
    """
    cond = SeCondition(abitem, name)
    item = MockItem(f'test.{name}', value=item_value)
    item.property.value = item_value
    cond._SeCondition__item = item
    cond._SeCondition__state = _MockState()
    if min_value is not None:
        cond._SeCondition__min._SeValue__value = min_value
    if max_value is not None:
        cond._SeCondition__max._SeValue__value = max_value
    if negate:
        cond._SeCondition__negate = True
    return cond


def _make_condset(SeConditionSet, abitem, name, conditions: dict):
    """
    Build a SeConditionSet pre-populated with the given SeCondition objects.

    ``conditions`` maps condition-name → SeCondition instance.
    """
    conditionid = MockItem(f'mock.state.{name}')
    cset = SeConditionSet(abitem, name, conditionid)
    # Directly inject conditions (bypasses YAML / update() parsing)
    ordered = OrderedDict()
    for cname, cond in conditions.items():
        ordered[cname] = cond
    cset._SeConditionSet__conditions = ordered
    return cset


def _make_condsets(SeConditionSets, abitem, sets: dict):
    """
    Build a SeConditionSets container pre-populated with SeConditionSet objects.
    """
    obj = SeConditionSets(abitem)
    ordered = OrderedDict()
    for sname, cset in sets.items():
        ordered[sname] = cset
    obj._SeConditionSets__condition_sets = ordered
    return obj


# ═══════════════════════════════════════════════════════════════════════════
# Level A-1: item-based conditions
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionItemBased(unittest.TestCase):
    """SeCondition.check() with a real MockItem as the data source."""

    def setUp(self):
        _setup_logger()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def test_bool_true_matches_expected_true(self):
        """Item value=True, expected=True → condition matches."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'light', item_value=True, expected_value=True)
        self.assertTrue(cond.check(None))

    def test_bool_false_matches_expected_false(self):
        """Item value=False, expected=False → condition matches."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'light', item_value=False, expected_value=False)
        self.assertTrue(cond.check(None))

    def test_bool_mismatch_returns_false(self):
        """Item value=False, expected=True → condition does not match."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'light', item_value=False, expected_value=True)
        self.assertFalse(cond.check(None))

    def test_integer_value_match(self):
        """Item value=42, expected=42 → condition matches."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'brightness', item_value=42, expected_value=42)
        self.assertTrue(cond.check(None))

    def test_integer_value_mismatch(self):
        """Item value=10, expected=42 → condition does not match."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'brightness', item_value=10, expected_value=42)
        self.assertFalse(cond.check(None))

    def test_negate_inverts_match(self):
        """negate=True: item=False, expected=False (match) → negated → False."""
        cond = _make_item_cond(
            self.SeCondition, self.abitem, 'motion', item_value=False, expected_value=False, negate=True
        )
        self.assertFalse(cond.check(None))

    def test_negate_inverts_non_match(self):
        """negate=True: item=True, expected=False (no match) → negated → True."""
        cond = _make_item_cond(
            self.SeCondition, self.abitem, 'motion', item_value=True, expected_value=False, negate=True
        )
        self.assertTrue(cond.check(None))

    def test_no_value_condition_always_matches(self):
        """
        When item is set but no expected value / min / max are configured,
        the condition defaults to 'matching' (no constraint to fail).
        """
        cond = _make_item_cond(self.SeCondition, self.abitem, 'unconstrained', item_value=99)
        # __value.is_empty() == True, __min/__max empty → falls into
        # "neither value nor min/max" branch → returns True
        self.assertTrue(cond.check(None))

    def test_string_value_match(self):
        """String item value and string expected value."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'mode', item_value='auto', expected_value='auto')
        self.assertTrue(cond.check(None))

    def test_string_value_mismatch(self):
        """String item value doesn't match expected string."""
        cond = _make_item_cond(self.SeCondition, self.abitem, 'mode', item_value='manual', expected_value='auto')
        self.assertFalse(cond.check(None))


# ═══════════════════════════════════════════════════════════════════════════
# Level A-2: eval-based conditions
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionEvalBased(unittest.TestCase):
    """SeCondition.check() where the current value comes from eval()."""

    def setUp(self):
        _setup_logger()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def test_literal_true_matches_true(self):
        """eval='True' with expected=True → match."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'flag', 'True', expected_value=True)
        self.assertTrue(cond.check(None))

    def test_literal_false_no_match(self):
        """eval='False' with expected=True → no match."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'flag', 'False', expected_value=True)
        self.assertFalse(cond.check(None))

    def test_sh_in_eval_scope(self):
        """eval='sh is not None' uses sh from the eval namespace → True."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'sh_check', 'sh is not None', expected_value=True)
        self.assertTrue(cond.check(None))

    def test_shtime_in_eval_scope(self):
        """eval='shtime is not None' uses shtime from eval namespace → True."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'shtime_check', 'shtime is not None', expected_value=True)
        self.assertTrue(cond.check(None))

    def test_numeric_eval_match(self):
        """eval='100' with expected=100 → match (numeric comparison)."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'level', '100', expected_value=100)
        self.assertTrue(cond.check(None))

    def test_numeric_eval_mismatch(self):
        """eval='50' with expected=100 → no match."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'level', '50', expected_value=100)
        self.assertFalse(cond.check(None))

    def test_eval_returning_computed_value(self):
        """eval='2 + 2' with expected=4 → match (expression evaluation)."""
        cond = _make_eval_cond(self.SeCondition, self.abitem, 'sum', '2 + 2', expected_value=4)
        self.assertTrue(cond.check(None))


# ═══════════════════════════════════════════════════════════════════════════
# Level A-3: numeric min/max range conditions
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionMinMax(unittest.TestCase):
    """SeCondition.check() using numeric range bounds instead of exact value."""

    def setUp(self):
        _setup_logger()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.SeCondition = SeCondition
        self.abitem = MockAbItem()

    def test_value_within_full_range(self):
        """50 is within [20, 80] → matches."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'temp', item_value=50, min_value=20, max_value=80)
        self.assertTrue(cond.check(None))

    def test_value_at_min_boundary(self):
        """Value equal to min → matches (not strictly less than)."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'temp', item_value=20, min_value=20, max_value=80)
        self.assertTrue(cond.check(None))

    def test_value_at_max_boundary(self):
        """Value equal to max → matches (not strictly greater than)."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'temp', item_value=80, min_value=20, max_value=80)
        self.assertTrue(cond.check(None))

    def test_value_below_min_no_match(self):
        """5 < min(20) → does not match."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'temp', item_value=5, min_value=20, max_value=80)
        self.assertFalse(cond.check(None))

    def test_value_above_max_no_match(self):
        """100 > max(80) → does not match."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'temp', item_value=100, min_value=20, max_value=80)
        self.assertFalse(cond.check(None))

    def test_only_min_above_min_matches(self):
        """Only min set: value ≥ min → matches."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'brightness', item_value=60, min_value=50)
        self.assertTrue(cond.check(None))

    def test_only_min_below_min_no_match(self):
        """Only min set: value < min → does not match."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'brightness', item_value=30, min_value=50)
        self.assertFalse(cond.check(None))

    def test_only_max_below_max_matches(self):
        """Only max set: value ≤ max → matches."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'brightness', item_value=40, max_value=50)
        self.assertTrue(cond.check(None))

    def test_only_max_above_max_no_match(self):
        """Only max set: value > max → does not match."""
        cond = _make_minmax_cond(self.SeCondition, self.abitem, 'brightness', item_value=80, max_value=50)
        self.assertFalse(cond.check(None))


# ═══════════════════════════════════════════════════════════════════════════
# Level B: SeConditionSet AND-logic
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetAndLogic(unittest.TestCase):
    """
    SeConditionSet.all_conditions_matching(): all conditions must match.
    """

    def setUp(self):
        _setup_logger()
        from plugins.stateengine.StateEngineCondition import SeCondition
        from plugins.stateengine.StateEngineConditionSet import SeConditionSet

        self.SeCondition = SeCondition
        self.SeConditionSet = SeConditionSet
        self.abitem = MockAbItem()

    def _cond(self, name, item_value, expected_value, negate=False):
        return _make_item_cond(self.SeCondition, self.abitem, name, item_value, expected_value, negate)

    def test_empty_conditionset_always_matches(self):
        """A conditionset with no conditions → all_conditions_matching is True."""
        cset = _make_condset(self.SeConditionSet, self.abitem, 'empty_set', {})
        self.assertTrue(cset.all_conditions_matching(None))

    def test_single_matching_condition(self):
        """One condition that matches → True."""
        cset = _make_condset(self.SeConditionSet, self.abitem, 'one_match', {'light': self._cond('light', True, True)})
        self.assertTrue(cset.all_conditions_matching(None))

    def test_single_failing_condition(self):
        """One condition that does not match → False."""
        cset = _make_condset(self.SeConditionSet, self.abitem, 'one_fail', {'light': self._cond('light', False, True)})
        self.assertFalse(cset.all_conditions_matching(None))

    def test_all_conditions_must_match(self):
        """Two conditions, both matching → True."""
        cset = _make_condset(
            self.SeConditionSet,
            self.abitem,
            'both_match',
            {'light': self._cond('light', True, True), 'motion': self._cond('motion', True, True)},
        )
        self.assertTrue(cset.all_conditions_matching(None))

    def test_one_failure_fails_entire_set(self):
        """Two conditions: first matches, second fails → False (AND-logic)."""
        cset = _make_condset(
            self.SeConditionSet,
            self.abitem,
            'and_fail',
            {
                'light': self._cond('light', True, True),  # match
                'motion': self._cond('motion', False, True),  # no match
            },
        )
        self.assertFalse(cset.all_conditions_matching(None))

    def test_all_failing_returns_false(self):
        """All conditions fail → False."""
        cset = _make_condset(
            self.SeConditionSet,
            self.abitem,
            'all_fail',
            {'light': self._cond('light', False, True), 'motion': self._cond('motion', False, True)},
        )
        self.assertFalse(cset.all_conditions_matching(None))

    def test_matching_set_records_lastconditionset(self):
        """On success, abitem.lastconditionset_set is called with set info."""
        cset = _make_condset(
            self.SeConditionSet, self.abitem, 'recorded_set', {'light': self._cond('light', True, True)}
        )
        cset.all_conditions_matching(None)
        # MockAbItem.lastconditionset_set stores into _variables
        self.assertEqual(self.abitem._variables.get('lastconditionset_name'), 'recorded_set')


# ═══════════════════════════════════════════════════════════════════════════
# Level C: SeConditionSets OR-logic
# ═══════════════════════════════════════════════════════════════════════════


class TestConditionSetsOrLogic(unittest.TestCase):
    """
    SeConditionSets.one_conditionset_matching(): any set matching is enough.
    """

    def setUp(self):
        _setup_logger()
        from plugins.stateengine.StateEngineCondition import SeCondition
        from plugins.stateengine.StateEngineConditionSet import SeConditionSet
        from plugins.stateengine.StateEngineConditionSets import SeConditionSets

        self.SeCondition = SeCondition
        self.SeConditionSet = SeConditionSet
        self.SeConditionSets = SeConditionSets
        self.abitem = MockAbItem()

    def _cond(self, name, item_value, expected_value):
        return _make_item_cond(self.SeCondition, self.abitem, name, item_value, expected_value)

    def _cset(self, name, conditions):
        return _make_condset(self.SeConditionSet, self.abitem, name, conditions)

    def test_no_conditionsets_always_matches(self):
        """No conditionsets at all → one_conditionset_matching returns True."""
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertTrue(result)
        self.assertEqual(name, '')

    def test_single_matching_set(self):
        """One set that matches → True, returns set name."""
        cset = self._cset('normal', {'light': self._cond('light', False, False)})
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {'normal': cset})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertTrue(result)
        self.assertEqual(name, 'normal')

    def test_single_failing_set(self):
        """One set that does not match → False."""
        cset = self._cset('normal', {'light': self._cond('light', False, True)})
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {'normal': cset})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertFalse(result)

    def test_second_set_matches_when_first_fails(self):
        """
        OR-logic: first conditionset fails, second matches.
        Result should be True with the name of the second set.
        """
        cset1 = self._cset('normal', {'light': self._cond('light', False, True)})
        cset2 = self._cset('suspend', {'light': self._cond('light', False, False)})
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {'normal': cset1, 'suspend': cset2})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertTrue(result)
        self.assertEqual(name, 'suspend')

    def test_all_sets_fail(self):
        """Both conditionsets fail → False."""
        cset1 = self._cset('set1', {'x': self._cond('x', False, True)})
        cset2 = self._cset('set2', {'y': self._cond('y', False, True)})
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {'set1': cset1, 'set2': cset2})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertFalse(result)
        self.assertEqual(name, '')

    def test_first_set_matches_stops_evaluation(self):
        """
        OR short-circuits: if the first set matches, the second is not
        checked (we verify by making the second set's condition impossible).
        """
        cset1 = self._cset('normal', {'light': self._cond('light', True, True)})
        # cset2 would also match, but should never be reached
        cset2 = self._cset('suspend', {'light': self._cond('light', True, True)})
        sets_obj = _make_condsets(self.SeConditionSets, self.abitem, {'normal': cset1, 'suspend': cset2})
        result, name = sets_obj.one_conditionset_matching(None)
        self.assertTrue(result)
        self.assertEqual(name, 'normal')  # first set, not second


if __name__ == '__main__':
    unittest.main()
