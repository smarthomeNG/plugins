import datetime

from holidays import HolidayBase

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
    """Entry key ``holidays`` combines the rrule weekdays with the core holiday calendar."""

    def test_exclude_skips_holiday(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)

        self.entry['holidays'] = 'exclude'

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_include_adds_holiday_to_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=3), today + datetime.timedelta(days=2)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)

        self.assertEqual(self.next_date(), weekday)
        self.entry['holidays'] = 'include'

        self.assertEqual(self.next_date(), holiday)

    def test_only_fires_on_holidays_regardless_of_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=2), today + datetime.timedelta(days=3)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)

        self.entry['holidays'] = 'include'
        self.assertEqual(self.next_date(), weekday)
        self.entry['holidays'] = 'only'

        self.assertEqual(self.next_date(), holiday)

    def test_public_scope_ignores_custom_holidays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)
        self.entry['holidays'] = 'exclude'
        self.entry['holidays_scope'] = 'public'

        self.assertEqual(self.next_date(), baseline)

        self.sh.shtime.public_holidays.append({baseline: 'public holiday'})

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_entry_without_rrule_honours_holidays(self):
        baseline = self.next_date()
        self.sh.shtime.add_custom_holiday_range(baseline)
        del self.entry['rrule']
        self.entry['holidays'] = 'exclude'

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

        self.entry['holidays'] = 'exclude'

        self.assertEqual(self.next_date(), baseline + datetime.timedelta(days=1))

    def test_include_adds_holiday_to_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=3), today + datetime.timedelta(days=2)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)
        self.entry['holidays'] = 'include'

        self.assertEqual(self.next_date(), holiday)

    def test_only_fires_on_holidays_regardless_of_rrule_weekdays(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        weekday, holiday = today + datetime.timedelta(days=2), today + datetime.timedelta(days=3)
        self.entry['rrule'] = f'FREQ=WEEKLY;BYDAY={WEEKDAYS[weekday.weekday()]}'
        self.sh.shtime.add_custom_holiday_range(holiday)
        self.entry['holidays'] = 'only'

        self.assertEqual(self.next_date(), holiday)

    def test_no_previous_time_without_holiday_in_the_past(self):
        today = datetime.datetime.now(self.plugin._timezone).date()
        self.sh.shtime.add_custom_holiday_range(today + datetime.timedelta(days=3))
        self.entry['holidays'] = 'only'

        self.assertIsNone(self.plugin._series_get_time(self.entry, 'previous'))
