import datetime

from tests import common

from plugins.uzsu.tests.base import TestUZSUBase


class TestPlainTimeEntries(TestUZSUBase):
    """Coverage for _get_time() with a plain HH:MM entry.

    These exercise the datetime.now(self._timezone) fix in _get_time(): the
    rrule search seed and the final scheduled time must consistently be in
    shng's configured timezone.

    NOTE: a true red/green regression test (proving the OS-tz vs configured-tz
    bug specifically) isn't practical here without monkeypatching
    datetime.datetime.now() itself - the bug only manifests when the OS
    timezone and configured timezone disagree about *which calendar day it
    currently is* (i.e. right at local midnight). force_os_tz alone doesn't
    shift "now" far enough to hit that window. These tests instead confirm
    the now-fixed code produces correct, consistently-tz-aware results.
    """

    def setUp(self):
        self.plugin = self.plugin_with_entry('main.temp.uzsu', {'value': 21.5, 'time': '07:00'})
        self.item = self.sh.return_item('main.temp.uzsu')

    def test_next_time_is_aware_in_configured_tz(self):
        entry = self.plugin._items[self.item]['list'][0]
        nxt, value, _ = self.plugin._get_time(entry, 'next', self.item, 0, 'test')
        self.assertEqual(nxt.hour, 7)
        self.assertEqual(nxt.minute, 0)
        self.assertEqual(nxt.tzinfo, self.plugin._timezone)
        self.assertEqual(value, 21.5)

    def test_next_time_unaffected_by_os_tz(self):
        entry = self.plugin._items[self.item]['list'][0]
        with common.force_os_tz('Pacific/Honolulu'):
            nxt, value, _ = self.plugin._get_time(entry, 'next', self.item, 0, 'test')
        self.assertEqual(nxt.hour, 7)
        self.assertEqual(nxt.utcoffset(), datetime.timedelta(hours=2))  # CEST in June


class TestSunBoundEntries(TestUZSUBase):
    """Coverage for _get_time()/_sun() with sunrise/sunset entries — exercises
    the Orb tz fixes (lib/orb.py) through the uzsu integration path."""

    def setUp(self):
        self.plugin = self.plugin_with_entry('main.temp.uzsu', {'value': 18.0, 'time': 'sunset'})
        self.item = self.sh.return_item('main.temp.uzsu')

    def test_sunset_entry_returns_aware_datetime_in_configured_tz(self):
        entry = self.plugin._items[self.item]['list'][0]
        nxt, value, _ = self.plugin._get_time(entry, 'next', self.item, 0, 'test')
        self.assertEqual(nxt.tzinfo, self.plugin._timezone)
        self.assertEqual(value, 18.0)

    def test_get_sun4week_populates_sunrise_and_sunset_for_all_days(self):
        self.plugin._get_sun4week(self.item)
        suncalc = self.plugin._items[self.item]['SunCalculated']
        self.assertEqual(set(suncalc.keys()), {'sunrise', 'sunset'})
        self.assertEqual(len(suncalc['sunrise']), 7)
        self.assertEqual(len(suncalc['sunset']), 7)
        for day_str in suncalc['sunrise'].values():
            hour, minute = day_str.split(':')
            self.assertTrue(0 <= int(hour) <= 23)
            self.assertTrue(0 <= int(minute) <= 59)


class TestInterpolation(TestUZSUBase):
    def test_interpolation_set_and_get(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.temp.uzsu')
        result = plugin.interpolation('linear', interval=10, item=item)
        self.assertEqual(result['type'], 'linear')
        self.assertEqual(result['interval'], 10)
        self.assertEqual(plugin.interpolation(item=item), result)

    def test_invalid_interpolation_type_rejected(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.temp.uzsu')
        before = plugin.interpolation(item=item)
        result = plugin.interpolation('exponential', item=item)
        self.assertEqual(result, before)
