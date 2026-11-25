#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Regression test for StateEngineEval.insert_suspend_time()'s DST-fold bug:
it used to compute `suspend_until = shtime.now() + timedelta(seconds=...)`,
which silently gains or loses an hour when the remaining suspend time
straddles a DST transition (the same defect fixed in lib/scheduler.py and
lib/shtime.py - see Shtime.add_seconds()). Now delegates to that already
DST-safe primitive; this confirms the wiring, not add_seconds() itself.

The other four now()+timedelta sites this bug also affected
(StateEngineItem.startup()/__startup_delay_callback(),
StateEngineAction._waitforexecute()'s two next_run computations) got the
identical one-line fix but aren't separately covered here - they need a
full SeItem/SeAction construction this test suite has no existing harness
for, which is a materially bigger undertaking than the fix itself.
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import tests.common as common

common.register_shng_log_levels()

from plugins.stateengine.tests.mock_helper import MockAbItem
from plugins.stateengine import StateEngineEval


class _FakeItemProperty:
    def __init__(self, path, last_change_age):
        self.path = path
        self.last_change_age = last_change_age


class _FakeItem:
    def __init__(self, path, last_change_age):
        self.property = _FakeItemProperty(path, last_change_age)


class TestInsertSuspendTimeDstTransition(unittest.TestCase):
    """Uses the real Shtime singleton set to Europe/Berlin - the UTC
    default other stateengine tests get has no DST transition to
    reproduce the bug against."""

    def setUp(self):
        self.abitem = MockAbItem()
        self.shtime = self.abitem.shtime
        self._orig_tz = self.shtime.tz()
        self.shtime.set_tz('Europe/Berlin')
        self.addCleanup(self.shtime.set_tz, self._orig_tz)
        self.berlin = self.shtime.tzinfo()
        self.se_eval = StateEngineEval.SeEval(self.abitem)

    def _run_with_now(self, now, suspend_time, already_suspended_for):
        self.abitem.set_variable('item.suspend_time', suspend_time)
        self.abitem.return_item = lambda path: (_FakeItem(path, already_suspended_for), None)
        with patch.object(self.shtime, 'now', return_value=now):
            result = self.se_eval.insert_suspend_time('mock.suspend_item', '%Y-%m-%d %H:%M:%S %z')
        return datetime.strptime(result, '%Y-%m-%d %H:%M:%S %z')

    def test_suspend_finish_time_survives_fall_back(self):
        # 5 minutes of suspend time remain, evaluated right before the
        # 2026-10-25 Europe/Berlin fall-back.
        now = datetime(2026, 10, 25, 2, 55, 0, tzinfo=self.berlin, fold=0)
        finished = self._run_with_now(now, suspend_time=300, already_suspended_for=0)
        elapsed = (finished - now).total_seconds()
        self.assertEqual(300, elapsed)

    def test_suspend_finish_time_survives_spring_forward(self):
        now = datetime(2026, 3, 29, 1, 55, 0, tzinfo=self.berlin, fold=0)
        finished = self._run_with_now(now, suspend_time=300, already_suspended_for=0)
        elapsed = (finished - now).total_seconds()
        self.assertEqual(300, elapsed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
