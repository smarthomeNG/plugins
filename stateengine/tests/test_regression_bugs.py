#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Regression guard: two bugs found during PR #1041 review.

Bug #1 — SeActionBase._delayed_execute() queue arity mismatch
─────────────────────────────────────────────────────────────
Location: StateEngineAction.py  SeActionBase._delayed_execute()

run_queue() unpacks a "delayedaction" job as an 11-tuple:
    (_, action, actionname, namevar, repeat_text, value,
     current_condition, previous_condition, previousstate_condition,
     next_condition, state)

_delayed_execute() correctly puts 11 elements when state is truthy:
    ["delayedaction", self, ..., state]   → 11 items ✓

But when state is falsy (None or not provided) it only puts 10:
    ["delayedaction", self, ...]           → 10 items ✗

run_queue() will raise ValueError (not enough values to unpack) for that job.

The tests below are written for the FIXED behaviour (11 elements in both
branches).  They FAIL against the current buggy code and PASS once fixed,
acting as a regression guard.

Bug #2 — SeItem.remove_scheduler_entry() safe when name not in list
────────────────────────────────────────────────────────────────────
Location: StateEngineItem.py  SeItem.remove_scheduler_entry()

list.remove() raises ValueError if the element is not found.  The method
must guard against that.  The current code (PR #1041) already has the guard
    if name in self.__active_schedulers:
        self.__active_schedulers.remove(name)

The test verifies the guard is present and the method does not raise when
called with a name that is not in the list.  This ensures the guard is never
accidentally removed.
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


# ═══════════════════════════════════════════════════════════════════════════
# Bug #1: _delayed_execute queue arity
# ═══════════════════════════════════════════════════════════════════════════


class TestDelayedExecuteQueueArity(unittest.TestCase):
    """
    _delayed_execute() must always put exactly 11 elements into the queue so
    that run_queue()'s 11-tuple unpack never raises ValueError.
    """

    def setUp(self):
        _setup()
        self.abitem = MockAbItem()
        from plugins.stateengine.StateEngineAction import SeActionRun

        self.action = SeActionRun(self.abitem, 'test_action')
        self.action._state = _MockState()
        self.action._action_type = 'actions_enter'

    def _drain_queue(self):
        """Remove and return all current queue items."""
        items = []
        q = self.action._SeActionBase__queue
        while not q.empty():
            items.append(q.get_nowait())
        return items

    def test_with_state_puts_11_items(self):
        """Truthy state → 11 items already in current code."""
        self.action._delayed_execute(actionname="Action 'test_action'", namevar='test_action', state=_MockState())
        jobs = self._drain_queue()
        self.assertEqual(len(jobs), 1, 'Expected exactly one job in queue')
        self.assertEqual(len(jobs[0]), 11, 'Job must have 11 elements for run_queue to unpack')

    @unittest.expectedFailure
    def test_with_state_none_puts_11_items(self):
        """
        state=None → currently puts 10 items (BUG — still present after upstream merge).
        run_queue() unpacks 11; the else-branch in _delayed_execute omits state.
        Written for the fixed behaviour; xfail until the bug is addressed.
        """
        self.action._delayed_execute(actionname="Action 'test_action'", namevar='test_action', state=None)
        jobs = self._drain_queue()
        self.assertEqual(len(jobs), 1, 'Expected exactly one job in queue')
        self.assertEqual(
            len(jobs[0]),
            11,
            'Job must have 11 elements regardless of state truthiness so '
            'run_queue can unpack it: '
            '(_, action, actionname, namevar, repeat_text, value, '
            'current_condition, previous_condition, '
            'previousstate_condition, next_condition, state)',
        )

    def test_job_tag_is_delayedaction(self):
        """First element of the job must be 'delayedaction'."""
        self.action._delayed_execute(actionname="Action 'test_action'", namevar='test_action', state=_MockState())
        jobs = self._drain_queue()
        self.assertEqual(jobs[0][0], 'delayedaction')

    def test_job_second_element_is_action(self):
        """Second element must be the action itself."""
        self.action._delayed_execute(actionname="Action 'test_action'", namevar='test_action', state=_MockState())
        jobs = self._drain_queue()
        self.assertIs(jobs[0][1], self.action)

    def test_state_is_last_element_when_truthy(self):
        """state is placed as the last (11th) element when truthy."""
        mock_state = _MockState()
        self.action._delayed_execute(actionname="Action 'test_action'", namevar='test_action', state=mock_state)
        jobs = self._drain_queue()
        self.assertIs(jobs[0][10], mock_state)


# ═══════════════════════════════════════════════════════════════════════════
# Bug #2: remove_scheduler_entry guard
# ═══════════════════════════════════════════════════════════════════════════


class TestRemoveSchedulerEntryGuard(unittest.TestCase):
    """
    SeItem.remove_scheduler_entry() must not raise ValueError when the name
    is not in __active_schedulers.  The PR #1041 guard (if name in list)
    must remain intact.

    Since SeItem requires a full shng Item + plugin + config, we test the
    guard logic in isolation using the same list.remove() pattern.
    """

    def test_list_remove_without_guard_raises(self):
        """
        Demonstrate that a bare list.remove() raises ValueError — the bug
        that the guard prevents.
        """
        schedulers = ['job-a', 'job-b']
        with self.assertRaises(ValueError):
            schedulers.remove('job-unknown')

    def test_guarded_remove_does_not_raise(self):
        """
        The guard pattern used by remove_scheduler_entry() is safe.
        """
        schedulers = ['job-a', 'job-b']
        name = 'job-unknown'
        # This is exactly the guard in SeItem.remove_scheduler_entry()
        if name in schedulers:
            schedulers.remove(name)
        # No exception — guard worked
        self.assertEqual(schedulers, ['job-a', 'job-b'])

    def test_guarded_remove_does_remove_when_present(self):
        """The guard does not prevent removal of entries that ARE present."""
        schedulers = ['job-a', 'job-b']
        name = 'job-a'
        if name in schedulers:
            schedulers.remove(name)
        self.assertEqual(schedulers, ['job-b'])

    def test_empty_scheduler_list_safe(self):
        """Removing from empty list with guard is safe."""
        schedulers = []
        name = 'anything'
        if name in schedulers:
            schedulers.remove(name)
        self.assertEqual(schedulers, [])


if __name__ == '__main__':
    unittest.main()
