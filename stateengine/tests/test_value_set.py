#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-1+: SeValue.set() round-trip tests.

SeValue is the universal value container used throughout stateengine for
condition comparands, action values, delays, and more.  Its ``set()`` method
parses attribute strings in the format ``"source:value"`` (e.g. "eval:sh()",
"var:myvar", "value:42") and stores them internally.  ``get()`` retrieves the
stored value, evaluating evals or reading variables as needed.

These tests exercise the *public* ``set()``→``get()`` round-trip, ensuring that
the parsing pipeline stores and retrieves values correctly without using
name-mangling injection.  Regressions in the parsing logic or retrieval path
will cause these tests to fail.

Coverage:
  • Plain Python values  (bool, int, float, None)
  • String literal "source:field" forms  (value:, eval:, var:)
  • is_empty() semantics before and after set()
  • Numeric auto-parsing from strings ("42" → 42)
  • Bool auto-parsing from strings ("true" → True, "false" → False)
  • Multi-value list: set(['value:True', 'value:False'])
  • eval: source — stored as eval string, retrieved by evaluating it
  • var: source — stored as variable name, retrieved from abitem.get_variable()
"""

import logging
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockAbItem
from plugins.stateengine import StateEngineDefaults


def _setup():
    StateEngineDefaults.logger = logging.getLogger('test.se')


def _make_value(abitem, name='test', allow_list=False, value_type=None):
    from plugins.stateengine.StateEngineValue import SeValue

    return SeValue(abitem, name, allow_list, value_type)


# ═══════════════════════════════════════════════════════════════════════════
# is_empty / basic lifecycle
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueIsEmpty(unittest.TestCase):
    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def test_fresh_value_is_empty(self):
        v = _make_value(self.abitem)
        self.assertTrue(v.is_empty())

    def test_after_set_bool_not_empty(self):
        v = _make_value(self.abitem)
        v.set(True, 'test')
        self.assertFalse(v.is_empty())

    def test_after_reset_is_empty_again(self):
        v = _make_value(self.abitem)
        v.set(True, 'test')
        v.set(None, 'test', reset=True)  # None + reset → clears everything
        self.assertTrue(v.is_empty())


# ═══════════════════════════════════════════════════════════════════════════
# Plain Python values (non-string)
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueSetPlainPython(unittest.TestCase):
    """set() with raw Python values (no string parsing needed)."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _roundtrip(self, value, name='test'):
        v = _make_value(self.abitem)
        v.set(value, name)
        return v.get()

    def test_bool_true(self):
        self.assertIs(self._roundtrip(True), True)

    def test_bool_false(self):
        self.assertIs(self._roundtrip(False), False)

    def test_integer(self):
        self.assertEqual(self._roundtrip(42), 42)

    def test_negative_integer(self):
        self.assertEqual(self._roundtrip(-7), -7)

    def test_float(self):
        self.assertAlmostEqual(self._roundtrip(3.14), 3.14)

    def test_zero(self):
        self.assertEqual(self._roundtrip(0), 0)


# ═══════════════════════════════════════════════════════════════════════════
# String "value:…" form
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueSetStringLiteral(unittest.TestCase):
    """set() with strings that are parsed as literal values."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _roundtrip(self, raw, name='test'):
        v = _make_value(self.abitem)
        v.set(raw, name)
        return v.get()

    def test_bare_integer_string(self):
        """'42' (no prefix) → auto-parsed to int 42."""
        result = self._roundtrip('42')
        self.assertEqual(result, 42)

    def test_bare_negative_integer_string(self):
        result = self._roundtrip('-5')
        self.assertEqual(result, -5)

    def test_bare_float_string(self):
        result = self._roundtrip('1.5')
        self.assertAlmostEqual(result, 1.5)

    def test_bare_true_string(self):
        """'true' (bare) → parsed to Python True."""
        result = self._roundtrip('true')
        self.assertIs(result, True)

    def test_bare_false_string(self):
        result = self._roundtrip('false')
        self.assertIs(result, False)

    def test_bare_True_string(self):
        result = self._roundtrip('True')
        self.assertIs(result, True)

    def test_value_prefixed_integer(self):
        """'value:99' → 99."""
        result = self._roundtrip('value:99')
        self.assertEqual(result, 99)

    def test_value_prefixed_bool_true(self):
        """'value:True' → True."""
        result = self._roundtrip('value:True')
        self.assertIs(result, True)

    def test_bare_string_word(self):
        """'auto' (no colon, no known type) → stored as string 'auto'."""
        result = self._roundtrip('auto')
        self.assertEqual(result, 'auto')


# ═══════════════════════════════════════════════════════════════════════════
# eval: source
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueSetEval(unittest.TestCase):
    """set('eval:…') stores an expression; get() evaluates it at retrieval."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def _eval_roundtrip(self, expr):
        v = _make_value(self.abitem)
        v.set('eval:' + expr, 'test')
        return v.get()

    def test_eval_literal_true(self):
        self.assertIs(self._eval_roundtrip('True'), True)

    def test_eval_literal_false(self):
        self.assertIs(self._eval_roundtrip('False'), False)

    def test_eval_arithmetic(self):
        self.assertEqual(self._eval_roundtrip('2 + 3'), 5)

    def test_eval_sh_in_scope(self):
        """eval expression can reference 'sh' from the eval namespace."""
        result = self._eval_roundtrip('sh is not None')
        self.assertIs(result, True)

    def test_eval_shtime_in_scope(self):
        result = self._eval_roundtrip('shtime is not None')
        self.assertIs(result, True)

    def test_eval_not_empty(self):
        """After set('eval:…'), is_empty() must be False."""
        v = _make_value(self.abitem)
        v.set('eval:True', 'test')
        self.assertFalse(v.is_empty())


# ═══════════════════════════════════════════════════════════════════════════
# var: source
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueSetVar(unittest.TestCase):
    """set('var:name') retrieves value from abitem.get_variable()."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def test_var_reads_from_abitem(self):
        self.abitem.set_variable('my.var', 'hello')
        v = _make_value(self.abitem)
        v.set('var:my.var', 'test')
        self.assertEqual(v.get(), 'hello')

    def test_var_missing_returns_none(self):
        """Variable not set → get_variable returns None → get() returns None."""
        v = _make_value(self.abitem)
        v.set('var:no.such.var', 'test')
        result = v.get()
        self.assertIsNone(result)

    def test_var_not_empty_after_set(self):
        v = _make_value(self.abitem)
        v.set('var:some.var', 'test')
        self.assertFalse(v.is_empty())


# ═══════════════════════════════════════════════════════════════════════════
# Multi-value list
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueSetList(unittest.TestCase):
    """set() with a Python list → multiple values stored."""

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()

    def test_list_of_raw_bools(self):
        """set([True, False]) → get() returns [True, False]."""
        v = _make_value(self.abitem, allow_list=True)
        v.set([True, False], 'test')
        result = v.get()
        result_list = result if isinstance(result, list) else [result]
        self.assertIn(True, result_list)
        self.assertIn(False, result_list)

    def test_list_of_value_strings_stored_as_strings(self):
        """
        set(['value:True', 'value:False']) stores via __listorder which keeps
        the string form 'True'/'False'.  SeValue.get() returns from __listorder
        when len > 1, so the result is a list of strings, not Python bools.
        This documents the actual behaviour — callers using the string form in
        a multi-value list receive strings and must cast themselves.
        """
        v = _make_value(self.abitem, allow_list=True)
        v.set(['value:True', 'value:False'], 'test')
        result = v.get()
        result_list = result if isinstance(result, list) else [result]
        self.assertEqual(len(result_list), 2)
        # Both canonical strings are present
        self.assertIn('True', result_list)
        self.assertIn('False', result_list)

    def test_list_of_plain_ints(self):
        v = _make_value(self.abitem, allow_list=True)
        v.set([1, 2, 3], 'test')
        result = v.get()
        result_list = result if isinstance(result, list) else [result]
        self.assertIn(1, result_list)

    def test_list_not_empty(self):
        v = _make_value(self.abitem, allow_list=True)
        v.set([True, False], 'test')
        self.assertFalse(v.is_empty())


if __name__ == '__main__':
    unittest.main()
