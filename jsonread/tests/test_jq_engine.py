#!/usr/bin/env python3
"""
Tests for the jq-subset engine internals (jq_compile/_traverse/jq_step/
jq_full/jq_condition/jq_unwrap) in plugins/jsonread/__init__.py.

These pin down the *current* hand-rolled implementation's specific
mechanics (how a path token is split, how brackets are parsed, ...). They
are expected to be thrown away or substantially rewritten if/when the
engine is swapped for a real library (jmespath, pyjq, ...) — that's fine,
that's what they're for. The behavior that needs to survive a swap lives
in test_filter_contract.py instead; see that file's module docstring.
"""

import unittest

from .base import JsonreadTestBase


class _EngineBase(JsonreadTestBase, unittest.TestCase):
    def setUp(self):
        self.plg = self.plugin()


class TestJqCompile(_EngineBase):
    def test_single_path_no_pipe(self):
        self.assertEqual(self.plg.jq_compile('.a.b'), ('.a.b',))

    def test_splits_on_pipe(self):
        self.assertEqual(self.plg.jq_compile('.a | .b'), ('.a', '.b'))

    def test_respects_parens_around_pipe(self):
        self.assertEqual(self.plg.jq_compile('(.a | .b)'), ('.a', '.b'))

    def test_splits_select_from_following_path(self):
        compiled = self.plg.jq_compile('.items[] | select(.id==1).name')
        self.assertEqual(compiled, ('.items[]', 'select(.id==1)', '.name'))


class TestTraversePlainKeys(_EngineBase):
    def test_resolves_nested_dict_path(self):
        data = {'a': {'b': 5}}
        self.assertEqual(self.plg._traverse(data, '.a.b'), [5])

    def test_missing_key_returns_empty(self):
        data = {'a': {}}
        self.assertEqual(self.plg._traverse(data, '.a.b'), [])

    def test_broadcasts_over_list_obj(self):
        data = [{'a': 1}, {'a': 2}]
        self.assertEqual(self.plg._traverse(data, '.a'), [1, 2])


class TestTraverseBracketIndices(_EngineBase):
    """
    Regression coverage for the bug fixed in this branch: .Data["0"] and
    .Data[0] were being treated as one literal (and always-missing) key
    name, so every filter using array indexing silently resolved to
    nothing.
    """

    def setUp(self):
        super().setUp()
        self.data = {'Data': [{'x': 'first'}, {'x': 'second'}]}

    def test_quoted_string_index(self):
        self.assertEqual(self.plg._traverse(self.data, '.Data["0"].x'), ['first'])

    def test_unquoted_numeric_index(self):
        self.assertEqual(self.plg._traverse(self.data, '.Data[0].x'), ['first'])

    def test_second_element_index(self):
        self.assertEqual(self.plg._traverse(self.data, '.Data["1"].x'), ['second'])

    def test_out_of_range_index_returns_empty(self):
        self.assertEqual(self.plg._traverse(self.data, '.Data["5"].x'), [])

    def test_empty_brackets_still_flattens(self):
        self.assertEqual(sorted(self.plg._traverse(self.data, '.Data[].x')), ['first', 'second'])


class TestJqCondition(_EngineBase):
    def test_equals_numeric(self):
        self.assertTrue(self.plg.jq_condition('.id==1', {'id': 1}))

    def test_equals_string(self):
        self.assertTrue(self.plg.jq_condition('.name=="a"', {'name': 'a'}))

    def test_not_equal(self):
        self.assertTrue(self.plg.jq_condition('.id!=2', {'id': 1}))

    def test_greater_than(self):
        self.assertTrue(self.plg.jq_condition('.id>1', {'id': 2}))
        self.assertFalse(self.plg.jq_condition('.id>1', {'id': 1}))


class TestJqFullWithSelect(_EngineBase):
    def test_select_filters_list_then_extracts_field(self):
        data = {'items': [{'id': 1, 'name': 'a'}, {'id': 2, 'name': 'b'}]}
        compiled = self.plg.jq_compile('.items[] | select(.id==2).name')
        self.assertEqual(self.plg.jq_full(compiled, data), ['b'])


class TestJqUnwrap(_EngineBase):
    def test_empty_list_becomes_none(self):
        self.assertIsNone(self.plg.jq_unwrap([]))

    def test_single_item_list_unwraps(self):
        self.assertEqual(self.plg.jq_unwrap([42]), 42)

    def test_multi_item_list_stays_a_list(self):
        self.assertEqual(self.plg.jq_unwrap([1, 2]), [1, 2])


if __name__ == '__main__':
    unittest.main(verbosity=2)
