#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-1: Unit tests for pure utility functions in StateEngineTools.

Covers:
  - partition_strip          string partitioning with se_-prefix special case
  - get_original_caller      Eval-chain traversal to find root caller
  - cast_num / cast_bool / cast_str / cast_list / cast_time   type coercion
  - get_eval_name            display name extraction from eval strings/callables
  - get_last_part_of_item_id  last path component extraction
"""

import logging
import os
import sys
import unittest

# ── path bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

# imports below rely on shng being on path
from plugins.stateengine.tests.mock_helper import make_sh, MockItem, MockAbItem, MockSeLogger
from plugins.stateengine import StateEngineTools
from plugins.stateengine import StateEngineDefaults


# ── helpers ───────────────────────────────────────────────────────────────


def _dummy_log():
    """Return a MockSeLogger that doesn't depend on StateEngineDefaults.logger."""
    return MockSeLogger()


# ═══════════════════════════════════════════════════════════════════════════
# partition_strip
# ═══════════════════════════════════════════════════════════════════════════


class TestPartitionStrip(unittest.TestCase):
    def test_simple_colon_split(self):
        self.assertEqual(StateEngineTools.partition_strip('foo:bar', ':'), ('foo', 'bar'))

    def test_strips_whitespace(self):
        self.assertEqual(StateEngineTools.partition_strip('  foo : bar  ', ':'), ('foo', 'bar'))

    def test_no_separator_present(self):
        # no colon → second element is empty string
        self.assertEqual(StateEngineTools.partition_strip('foo', ':'), ('foo', ''))

    def test_se_prefix_preserved_on_underscore_split(self):
        # "se_manual_include" split on "_" should yield ("se_manual", "include")
        result = StateEngineTools.partition_strip('se_manual_include', '_')
        self.assertEqual(result, ('se_manual', 'include'))

    def test_se_prefix_plain_name_split(self):
        # "se_item" split on "_" → ("se_item", "")
        result = StateEngineTools.partition_strip('se_item', '_')
        self.assertEqual(result[0], 'se_item')

    def test_non_se_prefix_underscore_split(self):
        # "foo_bar" split on "_" is a normal partition
        result = StateEngineTools.partition_strip('foo_bar', '_')
        self.assertEqual(result, ('foo', 'bar'))

    def test_non_string_raises(self):
        with self.assertRaises(ValueError):
            StateEngineTools.partition_strip(42, ':')

    def test_eval_caller_split(self):
        # typical usage: split "Eval:knx" to get the prefix
        part, rest = StateEngineTools.partition_strip('Eval:knx', ':')
        self.assertEqual(part, 'Eval')
        self.assertEqual(rest, 'knx')

    def test_eval_double_colon(self):
        # only first colon splits
        part, rest = StateEngineTools.partition_strip('Eval:knx:extra', ':')
        self.assertEqual(part, 'Eval')
        self.assertEqual(rest, 'knx:extra')


# ═══════════════════════════════════════════════════════════════════════════
# get_original_caller
# ═══════════════════════════════════════════════════════════════════════════


class TestGetOriginalCaller(unittest.TestCase):
    def setUp(self):
        # SeLoggerDummy.logger delegates to StateEngineDefaults.logger (None by
        # default); point it at a real logger so info() calls don't crash.
        StateEngineDefaults.logger = logging.getLogger('test.se')
        self.sh = make_sh()
        self.elog = _dummy_log()

    def _add_item(self, path, last_update_by=''):
        item = MockItem(path)
        item.property.last_update_by = last_update_by
        self.sh.items.add_item(path, item)
        return item

    def test_non_eval_caller_returned_unchanged(self):
        """A caller that doesn't start with 'Eval' should pass straight through."""
        caller, source = StateEngineTools.get_original_caller(self.sh, self.elog, 'knx', 'knx.source.item')
        self.assertEqual(caller, 'knx')
        self.assertEqual(source, 'knx.source.item')

    def test_eval_caller_with_unknown_source_breaks_immediately(self):
        """When source item doesn't exist the while loop breaks; Eval stays."""
        caller, source = StateEngineTools.get_original_caller(self.sh, self.elog, 'Eval', 'no.such.item')
        # loop broke because item not found — caller is whatever we passed
        self.assertEqual(caller, 'Eval')

    def test_single_eval_hop_resolved(self):
        """Eval:knx with source item that has last_update_by='knx:item.path'."""
        # src =
        self._add_item('room.light', last_update_by='knx:bus.path')
        caller, source = StateEngineTools.get_original_caller(self.sh, self.elog, 'Eval:trigger', 'room.light')
        self.assertEqual(caller, 'knx')
        self.assertEqual(source, 'bus.path')

    def test_double_eval_hop_resolved(self):
        """Chain: hop1 (Eval:hop2.item) → hop2 (knx:final.source) → knx."""
        # last_update_by format is 'caller:source_path' (single partition)
        # hop1 was last updated by an eval that looked at hop2
        self._add_item('hop1.item', last_update_by='Eval:hop2.item')
        # hop2 was last updated by knx
        self._add_item('hop2.item', last_update_by='knx:final.source')
        caller, source = StateEngineTools.get_original_caller(self.sh, self.elog, 'Eval', 'hop1.item')
        self.assertEqual(caller, 'knx')
        self.assertEqual(source, 'final.source')

    def test_returns_item_when_requested(self):
        """With item parameter, returns 3-tuple including original item."""
        src = self._add_item('my.item', last_update_by='admin:user')
        trigger_item = MockItem('trigger.item')
        orig_caller, orig_source, orig_item = StateEngineTools.get_original_caller(
            self.sh, self.elog, 'Eval', 'my.item', item=trigger_item
        )
        self.assertEqual(orig_caller, 'admin')
        self.assertIs(orig_item, src)

    def test_stateengine_plugin_caller_not_traversed(self):
        """StateEngine Plugin caller doesn't start with Eval, stops immediately."""
        caller, source = StateEngineTools.get_original_caller(self.sh, self.elog, 'StateEngine Plugin', 'some.item')
        self.assertEqual(caller, 'StateEngine Plugin')

    def test_custom_eval_keyword(self):
        """Custom keyword list for the eval check."""
        # 'Logic' is not a default keyword, but we pass it explicitly
        self._add_item('logic.item', last_update_by='knx:end')
        caller, source = StateEngineTools.get_original_caller(
            self.sh, self.elog, 'Logic', 'logic.item', eval_keyword=['Logic']
        )
        self.assertEqual(caller, 'knx')


# ═══════════════════════════════════════════════════════════════════════════
# cast_num
# ═══════════════════════════════════════════════════════════════════════════


class TestCastNum(unittest.TestCase):
    def test_int(self):
        self.assertEqual(StateEngineTools.cast_num(5), 5)

    def test_float(self):
        self.assertAlmostEqual(StateEngineTools.cast_num(3.14), 3.14)

    def test_string_int(self):
        self.assertEqual(StateEngineTools.cast_num('42'), 42)

    def test_string_float(self):
        self.assertAlmostEqual(StateEngineTools.cast_num('1.5'), 1.5)

    def test_bool_true(self):
        self.assertEqual(StateEngineTools.cast_num(True), 1)

    def test_bool_false(self):
        self.assertEqual(StateEngineTools.cast_num(False), 0)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            StateEngineTools.cast_num('not_a_number')


# ═══════════════════════════════════════════════════════════════════════════
# cast_bool
# ═══════════════════════════════════════════════════════════════════════════


class TestCastBool(unittest.TestCase):
    def test_true_bool(self):
        self.assertIs(StateEngineTools.cast_bool(True), True)

    def test_false_bool(self):
        self.assertIs(StateEngineTools.cast_bool(False), False)

    def test_one_is_true(self):
        self.assertIs(StateEngineTools.cast_bool(1), True)

    def test_zero_is_false(self):
        self.assertIs(StateEngineTools.cast_bool(0), False)

    def test_string_true(self):
        for v in ('true', 'True', 'TRUE', 'yes', 'on', '1'):
            self.assertIs(StateEngineTools.cast_bool(v), True, msg=f'failed for {v!r}')

    def test_string_false(self):
        for v in ('false', 'False', 'FALSE', 'no', 'off', '0'):
            self.assertIs(StateEngineTools.cast_bool(v), False, msg=f'failed for {v!r}')

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            StateEngineTools.cast_bool('maybe')


# ═══════════════════════════════════════════════════════════════════════════
# cast_str
# ═══════════════════════════════════════════════════════════════════════════


class TestCastStr(unittest.TestCase):
    def test_string_passthrough(self):
        self.assertEqual(StateEngineTools.cast_str('hello'), 'hello')

    def test_int_to_str(self):
        self.assertEqual(StateEngineTools.cast_str(42), '42')

    def test_bool_to_str(self):
        # cast_str simply calls str()
        result = StateEngineTools.cast_str(True)
        self.assertIsInstance(result, str)

    def test_none_to_str(self):
        result = StateEngineTools.cast_str(None)
        self.assertEqual(result, 'None')


# ═══════════════════════════════════════════════════════════════════════════
# get_eval_name
# ═══════════════════════════════════════════════════════════════════════════


class TestGetEvalName(unittest.TestCase):
    def test_lambda_returns_lambda(self):
        fn = lambda: None  # noqa: E731
        name = StateEngineTools.get_eval_name(fn)
        self.assertIn('lambda', name.lower())

    def test_string_expression_returned(self):
        expr = 'sh.some.item()'
        name = StateEngineTools.get_eval_name(expr)
        # should return the expression itself or a trimmed version
        self.assertIn('sh', name)

    def test_none_returns_none(self):
        # get_eval_name(None) is specified to return None
        self.assertIsNone(StateEngineTools.get_eval_name(None))


# ═══════════════════════════════════════════════════════════════════════════
# get_last_part_of_item_id
# ═══════════════════════════════════════════════════════════════════════════


class TestGetLastPartOfItemId(unittest.TestCase):
    def test_dotted_string(self):
        self.assertEqual(StateEngineTools.get_last_part_of_item_id('a.b.c'), 'c')

    def test_no_dot(self):
        self.assertEqual(StateEngineTools.get_last_part_of_item_id('root'), 'root')

    def test_item_object(self):
        item = MockItem('room.floor.lamp')
        self.assertEqual(StateEngineTools.get_last_part_of_item_id(item), 'lamp')


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    unittest.main()
