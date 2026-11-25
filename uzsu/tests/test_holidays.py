import datetime
import unittest

from dateutil.rrule import rrulestr
from holidays import HolidayBase

from plugins.uzsu import HOLIDAY_COMBINERS, HOLIDAY_MODES, _restrict_to_holidays
from plugins.uzsu.tests.base import TestUZSUBase

ITEM_PATH = 'main.temp.uzsu'
WEEKDAYS = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']


class HolidayCase(TestUZSUBase):
    """Plugin with one list entry and an empty holiday calendar."""

    ENTRY = {'value': 21.5, 'time': '07:00'}

    def setUp(self):
        self.plugin = self.plugin_with_entry(ITEM_PATH, dict(self.ENTRY))
        self.item = self.sh.items.return_item(ITEM_PATH)
        self.entry = self.plugin._items[self.item]['list'][0]
        # Shtime is a singleton: start every test with an empty calendar
        self.sh.shtime.holidays = HolidayBase()
        self.sh.shtime.public_holidays = HolidayBase()

    def next_date(self, entry=None):
        nxt, _, _ = self.plugin._get_time(entry or self.entry, 'next', self.item, 0, 'test')
        return None if nxt is None else nxt.date()


class TestHolidays(HolidayCase):
    """Entry key ``holidays`` (``mode``, ``scope``) combines the rrule weekdays with the core holiday calendar."""

    def test_exclude_skips_holiday(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)

        self.entry['holidays'] = {'mode': 'exclude'}

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_include_adds_holiday_to_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=3), today + datetime.timedelta(days=2)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)

        self.assertEqual(self.next_date(), weekday)
        self.entry['holidays'] = {'mode': 'include'}

        self.assertEqual(self.next_date(), holiday)

    def test_only_fires_on_holidays_regardless_of_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=2), today + datetime.timedelta(days=3)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)

        self.entry['holidays'] = {'mode': 'include'}
        self.assertEqual(self.next_date(), weekday)
        self.entry['holidays'] = {'mode': 'only'}

        self.assertEqual(self.next_date(), holiday)

    def test_public_scope_ignores_custom_holidays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)
        self.entry['holidays'] = {'mode': 'exclude', 'scope': 'public'}

        self.assertEqual(self.next_date(), baseline)

        self.sh.shtime.public_holidays.append({baseline: 'public holiday'})

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_ignore_keeps_rrule_weekdays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)

        self.entry['holidays'] = {'mode': 'ignore', 'scope': 'all'}

        self.assertEqual(self.next_date(), baseline)

    def test_entry_without_rrule_honours_holidays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)
        del self.entry['rrule']
        self.entry['holidays'] = {'mode': 'exclude'}

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))


class TestHolidaySeries(HolidayCase):
    """``holidays`` also applies to series entries."""

    ENTRY = {
        'value': 21.5,
        'time': 'series',
        'series': {'active': True, 'timeSeriesMin': '07:00', 'timeSeriesMax': '07:30', 'timeSeriesIntervall': '00:15'},
    }

    def test_exclude_skips_holiday(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)

        self.entry['holidays'] = {'mode': 'exclude'}

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_include_adds_holiday_to_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=3), today + datetime.timedelta(days=2)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)
        self.entry['holidays'] = {'mode': 'include'}

        self.assertEqual(self.next_date(), holiday)

    def test_only_fires_on_holidays_regardless_of_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=2), today + datetime.timedelta(days=3)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)
        self.entry['holidays'] = {'mode': 'only'}

        self.assertEqual(self.next_date(), holiday)

    def test_ignore_keeps_rrule_weekdays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)

        self.entry['holidays'] = {'mode': 'ignore', 'scope': 'all'}

        self.assertEqual(self.next_date(), baseline)

    def test_no_previous_time_without_holiday_in_the_past(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        self.sh.shtime.add_custom_holiday_range(today + datetime.timedelta(days=3))
        self.entry['holidays'] = {'mode': 'only'}

        self.assertIsNone(self.plugin._series_get_time(self.entry, 'previous'))


class TestHolidayMigration(TestUZSUBase):
    """List entries get a complete nested ``holidays`` dict on load and on item update."""

    def load(self, entry):
        plugin = self.plugin()
        item = self.sh.items.return_item(ITEM_PATH)
        item({'active': True, 'list': [{'value': 1, 'active': True, 'time': '07:00', **entry}]})
        plugin.parse_item(item)
        return plugin._items[item]['list'][0], item()['list'][0]

    def test_flat_keys_written_after_start(self):
        plugin = self.plugin()
        item = self.sh.items.return_item(ITEM_PATH)
        entry = {'value': 1, 'active': True, 'time': '07:00', 'holidays': 'exclude', 'holidays_scope': 'public'}
        item({'active': True, 'list': [entry]}, 'Visu')

        plugin.update_item(item, 'Visu')

        self.assertEqual(plugin._items[item]['list'][0]['holidays'], {'mode': 'exclude', 'scope': 'public'})
        self.assertEqual(item()['list'][0]['holidays'], {'mode': 'exclude', 'scope': 'public'})
        self.assertNotIn('holidays_scope', item()['list'][0])

    def test_flat_mode_and_scope(self):
        entry, stored = self.load({'holidays': 'exclude', 'holidays_scope': 'public'})

        self.assertEqual(entry['holidays'], {'mode': 'exclude', 'scope': 'public'})
        self.assertNotIn('holidays_scope', entry)
        self.assertEqual(stored, entry)

    def test_flat_mode_without_scope(self):
        entry, _ = self.load({'holidays': 'only'})

        self.assertEqual(entry['holidays'], {'mode': 'only', 'scope': 'all'})

    def test_orphan_scope_is_dropped(self):
        entry, _ = self.load({'holidays_scope': 'public'})

        self.assertEqual(entry['holidays'], {'mode': 'ignore', 'scope': 'all'})
        self.assertNotIn('holidays_scope', entry)

    def test_missing_holidays_get_default(self):
        entry, stored = self.load({})

        self.assertEqual(entry['holidays'], {'mode': 'ignore', 'scope': 'all'})
        self.assertEqual(stored, entry)

    def test_missing_holidays_get_default_after_start(self):
        plugin = self.plugin()
        item = self.sh.items.return_item(ITEM_PATH)
        item({'active': True, 'list': [{'value': 1, 'active': True, 'time': '07:00'}]}, 'Visu')

        plugin.update_item(item, 'Visu')

        self.assertEqual(item()['list'][0]['holidays'], {'mode': 'ignore', 'scope': 'all'})

    def test_nested_without_scope_gets_default_scope(self):
        entry, _ = self.load({'holidays': {'mode': 'exclude'}})

        self.assertEqual(entry['holidays'], {'mode': 'exclude', 'scope': 'all'})

    def test_invalid_holidays_are_kept(self):
        entry, _ = self.load({'holidays': {'mode': 'sometimes'}})

        self.assertEqual(entry['holidays'], {'mode': 'sometimes'})

    def test_nested_is_kept(self):
        entry, _ = self.load({'holidays': {'mode': 'include', 'scope': 'all'}})

        self.assertEqual(entry['holidays'], {'mode': 'include', 'scope': 'all'})


class TestHolidayCombiners(unittest.TestCase):
    """Functions combining an rrule with holiday datetimes."""

    MONDAY = datetime.datetime(2026, 11, 2, 7, 0)
    RULE = 'FREQ=WEEKLY;BYDAY=MO,WE'

    def occurrences(self, combiner, holidays, days=14):
        rule = combiner(rrulestr(self.RULE, dtstart=self.MONDAY), holidays)
        return [d.date() for d in rule.between(self.MONDAY, self.MONDAY + datetime.timedelta(days=days), inc=True)]

    def test_restrict_keeps_holidays_on_rrule_days_only(self):
        holiday_monday = self.MONDAY + datetime.timedelta(days=7)
        holiday_tuesday = self.MONDAY + datetime.timedelta(days=1)

        self.assertEqual(
            self.occurrences(_restrict_to_holidays, [holiday_monday, holiday_tuesday]), [holiday_monday.date()]
        )

    def test_restrict_uses_rrule_time(self):
        holiday = datetime.datetime.combine(self.MONDAY.date(), datetime.time(0, 0))

        rule = _restrict_to_holidays(rrulestr(self.RULE, dtstart=self.MONDAY), [holiday])

        self.assertEqual(list(rule), [self.MONDAY])

    def test_restrict_respects_rrule_interval(self):
        self.RULE = 'FREQ=WEEKLY;INTERVAL=2;BYDAY=MO'
        off_week_monday = self.MONDAY + datetime.timedelta(days=7)

        self.assertEqual(self.occurrences(_restrict_to_holidays, [off_week_monday]), [])

    def test_restrict_has_no_mode_keyword(self):
        self.assertNotIn(_restrict_to_holidays, HOLIDAY_COMBINERS.values())

    def test_every_mode_but_ignore_has_a_combiner(self):
        self.assertEqual(set(HOLIDAY_MODES), {'ignore', *HOLIDAY_COMBINERS})
