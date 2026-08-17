#!/usr/bin/env python3
"""
Behavioral contract tests for JSONREAD.evaluate_filter().

Unlike test_jq_engine.py, these tests don't care *how* a filter string is
turned into a value — they pin "given this exact jsonread_filter string
(as it appears in a real items.yaml) and this exact JSON document, the
item ends up with this exact value." That's the part of the plugin's
behavior users actually depend on, and the part that must not regress.

Why this matters for a future jq -> jmespath (or any other engine) swap:
when that happens, the *filter syntax* in items.yaml will necessarily
change (jmespath doesn't speak jq's dialect) — but the JSON fixtures and
expected output values below do not need to change at all, because
they're describing the data, not the engine. The intended workflow for
that migration:

  1. Keep FRONIUS_FIXTURE and the expected-value assertions exactly as is.
  2. Replace only the left-hand filter-string literals with their
     jmespath equivalents.
  3. Re-run this file. Any genuine behavior regression (wrong value,
     wrong type, item not resolved) shows up here immediately, without
     needing to also re-derive "what should this have produced" from
     scratch.

If a translated expression can't be made to produce the same expected
value, that's a real semantic gap between the two engines worth a
deliberate decision — not something to discover via a user bug report,
which is how the bug this branch fixes was originally found.
"""

import json
import os
import unittest

from .base import JsonreadTestBase

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), 'fixtures', 'fronius.json')


class TestFilterContractAgainstFroniusFixture(JsonreadTestBase, unittest.TestCase):
    """
    Filter strings below are copied verbatim from
    etc/items/fronius_smartmeter.yaml — this is the actual configuration
    a real user runs, not a simplified stand-in.
    """

    @classmethod
    def setUpClass(cls):
        with open(FIXTURE_PATH) as f:
            cls.data = json.load(f)

    def setUp(self):
        self.plg = self.plugin()

    def test_current_phase_1(self):
        self.assertEqual(self.plg.evaluate_filter('.Body.Data["0"].Current_AC_Phase_1', self.data), 0.455)

    def test_current_sum(self):
        self.assertEqual(self.plg.evaluate_filter('.Body.Data["0"].Current_AC_Sum', self.data), 2.362)

    def test_nested_details_manufacturer(self):
        self.assertEqual(self.plg.evaluate_filter('.Body.Data["0"].Details.Manufacturer', self.data), 'Fronius')

    def test_nested_details_serial_is_a_string(self):
        # Serial looks numeric but is a JSON string in the source data —
        # a filter must not coerce it.
        value = self.plg.evaluate_filter('.Body.Data["0"].Details.Serial', self.data)
        self.assertEqual(value, '2099316145')
        self.assertIsInstance(value, str)

    def test_voltage_phase_3(self):
        self.assertEqual(self.plg.evaluate_filter('.Body.Data["0"].Voltage_AC_Phase_3', self.data), 236.5)

    def test_second_array_element(self):
        # Body.Data[1] only has a handful of fields populated in real
        # Fronius responses — this is the case that most clearly proves
        # array indexing (not just "first element") works.
        self.assertEqual(self.plg.evaluate_filter('.Body.Data["1"].Current_AC_Phase_1', self.data), 0.073)

    def test_field_absent_on_second_element_resolves_to_none(self):
        # Body.Data[1] has no Details key at all in real responses.
        self.assertIsNone(self.plg.evaluate_filter('.Body.Data["1"].Details.Manufacturer', self.data))

    def test_unknown_path_resolves_to_none_not_an_error(self):
        self.assertIsNone(self.plg.evaluate_filter('.Body.Data["0"].DoesNotExist', self.data))


if __name__ == '__main__':
    unittest.main(verbosity=2)
