#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tier-2: Eval namespace regression tests.

Guards against the regression introduced by b0f64e67 (plugins ruff star-import
cleanup), which removed the local variable assignments that served as the
implicit eval() scope in three stateengine files:

    sh = self._sh          # noqa: F841
    shtime = self._shtime  # noqa: F841
    stateengine_eval = se_eval = StateEngineEval.SeEval(self._abitem)

Without these, any eval expression using ``sh.``, ``shtime.``, or
``stateengine_eval.`` would raise NameError — caught internally and turned
into "condition not matching", causing stateengine to fall through to the
suspend state.

Test strategy
-------------
For each eval site we inject a minimal expression that uses the name under
test and assert it resolves without NameError.  The expressions are
deliberately simple so the test doesn't depend on a full running shng:

  ``sh is not None``         → True when sh is in scope
  ``shtime is not None``     → True when shtime is in scope
  ``stateengine_eval is not None``  → True when stateengine_eval is in scope

Sites covered:
  1. SeValue.__get_eval          (StateEngineValue.py)
  2. SeCondition check_eval      (nested in __get_current, StateEngineCondition.py)
  3. SeActionRun.__execute       (StateEngineAction.py)
"""

import logging
import os
import sys
import unittest

# ── path bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import make_sh, MockAbItem
from plugins.stateengine import StateEngineDefaults


def _setup():
    StateEngineDefaults.logger = logging.getLogger('test.se')


# ═══════════════════════════════════════════════════════════════════════════
# Tier 2a — SeValue.__get_eval
# ═══════════════════════════════════════════════════════════════════════════


class TestSeValueEvalNamespace(unittest.TestCase):
    """SeValue.__get_eval must expose sh, shtime, stateengine_eval."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineValue import SeValue

        self.abitem = MockAbItem()
        self.SeValue = SeValue

    def _make_value(self):
        return self.SeValue(self.abitem, 'test_value')

    def _eval_expr(self, expr):
        """Set a raw eval expression on a fresh SeValue and call get()."""
        v = self._make_value()
        # Bypass the complex set() parser: inject __eval directly
        v._SeValue__eval = expr
        # get() will call __get_eval() for non-None __eval
        result = v.get()
        return result

    # ── sh ──────────────────────────────────────────────────────────────

    def test_sh_is_available(self):
        """``sh is not None`` must evaluate to True (sh in eval scope)."""
        result = self._eval_expr('sh is not None')
        self.assertIs(result, True)

    def test_sh_is_the_smarthome_instance(self):
        """``sh`` must be the MockSmartHome, not an arbitrary object."""
        result = self._eval_expr('sh')
        self.assertIs(result, self.abitem._sh)

    # ── shtime ──────────────────────────────────────────────────────────

    def test_shtime_is_available(self):
        """``shtime is not None`` must evaluate to True."""
        result = self._eval_expr('shtime is not None')
        self.assertIs(result, True)

    # ── stateengine_eval / se_eval ───────────────────────────────────────

    def test_stateengine_eval_is_available(self):
        """``stateengine_eval is not None`` must evaluate True."""
        result = self._eval_expr('stateengine_eval is not None')
        self.assertIs(result, True)

    def test_se_eval_alias_available(self):
        """``se_eval`` is the same alias as ``stateengine_eval``."""
        result = self._eval_expr('se_eval is not None')
        self.assertIs(result, True)

    def test_stateengine_eval_and_se_eval_same_object(self):
        """Both names should point to the same SeEval instance."""
        result = self._eval_expr('stateengine_eval is se_eval')
        self.assertIs(result, True)

    # ── NameError regression ─────────────────────────────────────────────

    def test_missing_sh_raises_name_error(self):
        """
        Sanity: verify the test harness actually catches a NameError if an
        undefined name is used — confirming the regression would be caught.
        """
        v = self._make_value()
        v._SeValue__eval = 'undefined_name_xyz is not None'
        # get() swallows the exception into __get_issues, returning None
        result = v.get()
        # Result is None (exception path), NOT True
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════
# Tier 2b — SeCondition check_eval (nested in __get_current)
# ═══════════════════════════════════════════════════════════════════════════


class TestSeConditionEvalNamespace(unittest.TestCase):
    """SeCondition.__get_current / check_eval must expose sh, shtime, stateengine_eval."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineCondition import SeCondition

        self.abitem = MockAbItem()
        self.SeCondition = SeCondition

    def _make_condition(self, eval_expr):
        """Return a SeCondition with __eval set to eval_expr."""
        cond = self.SeCondition(self.abitem, 'test_cond')
        cond._SeCondition__eval = eval_expr
        return cond

    def _get_current(self, eval_expr):
        """Call __get_current() on a condition configured with eval_expr."""
        cond = self._make_condition(eval_expr)
        # Call the private method via name-mangling
        return cond._SeCondition__get_current()

    # ── sh ──────────────────────────────────────────────────────────────

    def test_sh_is_available(self):
        result = self._get_current('sh is not None')
        self.assertIs(result, True)

    def test_sh_is_smarthome_instance(self):
        result = self._get_current('sh')
        self.assertIs(result, self.abitem._sh)

    # ── shtime ──────────────────────────────────────────────────────────

    def test_shtime_is_available(self):
        result = self._get_current('shtime is not None')
        self.assertIs(result, True)

    # ── stateengine_eval / se_eval ───────────────────────────────────────

    def test_stateengine_eval_available(self):
        result = self._get_current('stateengine_eval is not None')
        self.assertIs(result, True)

    def test_se_eval_alias_available(self):
        result = self._get_current('se_eval is not None')
        self.assertIs(result, True)

    # ── NameError regression ─────────────────────────────────────────────

    def test_undefined_name_raises_value_error(self):
        """
        check_eval wraps NameError into ValueError with a message; verify that
        using an unknown name raises rather than silently returning True.
        """
        cond = self._make_condition('undefined_xyz_name is not None')
        with self.assertRaises((ValueError, NameError)):
            cond._SeCondition__get_current()


# ═══════════════════════════════════════════════════════════════════════════
# Tier 2c — SeActionRun.__execute
# ═══════════════════════════════════════════════════════════════════════════


class TestSeActionRunEvalNamespace(unittest.TestCase):
    """SeActionRun.__execute must expose sh, shtime, stateengine_eval."""

    def setUp(self):
        _setup()
        from plugins.stateengine.StateEngineAction import SeActionRun

        self.abitem = MockAbItem()
        self.SeActionRun = SeActionRun

    def _make_action(self, eval_expr):
        """Return a SeActionRun with __eval set to eval_expr."""
        action = self.SeActionRun(self.abitem, 'test_action')
        # SeActionRun stores the eval as _SeActionRun__eval
        action._SeActionRun__eval = eval_expr
        return action

    def _call_execute(self, eval_expr, returnvalue=True):
        """
        Call real_execute with returnvalue=True so the eval result is returned
        directly without side-effecting any shng items.
        """
        action = self._make_action(eval_expr)
        return action.real_execute(state=None, actionname='test_action', returnvalue=returnvalue)

    # ── sh ──────────────────────────────────────────────────────────────

    def test_sh_is_available(self):
        result = self._call_execute('sh is not None')
        self.assertIs(result, True)

    def test_sh_is_smarthome_instance(self):
        result = self._call_execute('sh')
        self.assertIs(result, self.abitem._sh)

    # ── shtime ──────────────────────────────────────────────────────────

    def test_shtime_is_available(self):
        result = self._call_execute('shtime is not None')
        self.assertIs(result, True)

    # ── stateengine_eval / se_eval ───────────────────────────────────────

    def test_stateengine_eval_available(self):
        result = self._call_execute('stateengine_eval is not None')
        self.assertIs(result, True)

    def test_se_eval_alias_available(self):
        result = self._call_execute('se_eval is not None')
        self.assertIs(result, True)


if __name__ == '__main__':
    unittest.main()
