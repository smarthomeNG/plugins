"""
Regression tests for _get_time()'s DST-fold comparison bug: cond_future/
cond_next/etc. compared two aware datetimes sharing the same tzinfo
object (self._timezone) with a bare `>`/`<` - per CPython's documented
datetime semantics that skips fold normalization entirely, giving a
wrong answer whenever `next` and `now()` straddle a DST transition. Same
defect class fixed in lib/scheduler.py, lib/shtime.py, and stateengine
(see those commits) - here the fix is `.timestamp()`-based comparison
instead of the bare operator, applied at every next/now() comparison
site in _get_time() and _schedule()'s interpolation branch.

Uses a datetime.datetime subclass to freeze "now" to an exact instant
straddling the real 2026-10-25 Europe/Berlin fall-back, since the bug
only reproduces against a real DST-observing zone and a controlled
clock (nothing else in this file drives the clock explicitly).
"""

import datetime

from unittest.mock import patch

from plugins.uzsu.tests.base import TestUZSUBase


class _FrozenDatetime(datetime.datetime):
    """datetime.datetime subclass whose now() returns a fixed instant -
    combine()/strptime()/replace()/etc. stay the real implementations
    since this is a subclass, not a bare Mock."""

    _frozen = None

    @classmethod
    def now(cls, tz=None):
        return cls._frozen


class TestGetTimeDstFallBack(TestUZSUBase):
    """A plain HH:MM entry whose today-occurrence has *just* passed
    across the fall-back must be treated as past (and _get_time() must
    roll over to tomorrow's occurrence), not as still-upcoming."""

    def setUp(self):
        self.plugin = self.plugin_with_entry('main.temp.uzsu', {'value': 21.5, 'time': '02:59'})
        self.item = self.sh.return_item('main.temp.uzsu')
        self.berlin = self.plugin._timezone

    def test_todays_occurrence_past_the_fall_back_rolls_to_tomorrow(self):
        # 02:59 combined fresh always gets fold=0 (CEST, +02:00 -> UTC
        # 00:59:00). Freezing "now" to 02:00 fold=1 (CET, +01:00 -> UTC
        # 01:00:00) puts real "now" 1 minute *after* that 02:59 instant -
        # today's occurrence has already passed by the time this runs.
        _FrozenDatetime._frozen = datetime.datetime(2026, 10, 25, 2, 0, 0, tzinfo=self.berlin, fold=1)
        entry = self.plugin._items[self.item]['list'][0]
        with patch('plugins.uzsu.datetime', _FrozenDatetime):
            nxt, value, _ = self.plugin._get_time(entry, 'next', self.item, 0, 'test')
        self.assertEqual(26, nxt.day, "today's 02:59 already passed - _get_time() must return tomorrow's")
        self.assertEqual(21.5, value)


if __name__ == '__main__':
    import unittest

    unittest.main(verbosity=2)
