from datetime import datetime

import pytest
from tests import common

from plugins.mcp.logformat import LogFormat

common.register_shng_log_levels()

COMPACT = (
    '%(levelname).1s %(asctime)s %(name)-19s | %(funcName)-25s ln:%(lineno)-4d %(message)s  ----  %(threadName)-12s '
)
COMPACT_DATE = '%m%d %H%M%S'
SIMPLE = '%(asctime)s %(levelname)-8s %(name)-19s %(message)s'
SIMPLE_DATE = '%Y-%m-%d  %H:%M:%S'

REFERENCE = datetime(2026, 11, 10, 21, 0, 0)


def parse(fmt, datefmt, line, reference=REFERENCE):
    log_format = LogFormat.from_logging(fmt, datefmt)
    assert log_format is not None
    entry = log_format.parse(line, reference)
    assert entry is not None
    return entry


class TestParse:
    def test_a_compact_single_letter_format_yields_timestamp_level_logger_and_message(self):
        line = 'W 1110 205405 logics.mcp_ticker   | <module>                  ln:6    login failed  ----  logics.mcp_ticker '
        entry = parse(COMPACT, COMPACT_DATE, line)
        assert entry == {
            'ts': datetime(2026, 11, 10, 20, 54, 5),
            'level': 'WARNING',
            'logger': 'logics.mcp_ticker',
            'message': 'login failed',
        }

    def test_the_default_format_is_parsed_with_the_four_digit_year_of_its_date_format(self):
        line = '2026-11-10  10:01:00 WARNING  items.house.light   slow update'
        assert parse(SIMPLE, SIMPLE_DATE, line) == {
            'ts': datetime(2026, 11, 10, 10, 1, 0),
            'level': 'WARNING',
            'logger': 'items.house.light',
            'message': 'slow update',
        }

    def test_a_line_not_in_the_format_is_not_parsed(self):
        log_format = LogFormat.from_logging(SIMPLE, SIMPLE_DATE)
        assert log_format is not None
        assert log_format.parse('free text', REFERENCE) is None

    def test_a_year_less_date_takes_the_latest_year_not_after_the_reference(self):
        line = 'I 1231 235900 lib.x   | f  ln:1    old  ----  Main '
        assert parse(COMPACT, COMPACT_DATE, line, datetime(2027, 1, 2))['ts'] == datetime(2026, 12, 31, 23, 59, 0)

    def test_a_leap_day_without_a_year_lands_in_a_leap_year(self):
        line = 'I 0229 120000 lib.x   | f  ln:1    old  ----  Main '
        assert parse(COMPACT, COMPACT_DATE, line, datetime(2026, 11, 10))['ts'] == datetime(2024, 2, 29, 12, 0, 0)

    def test_a_date_format_without_a_day_leaves_the_timestamp_out(self):
        entry = parse('%(asctime)s %(levelname)s %(message)s', '%H:%M:%S', '10:00:00 ERROR boom')
        assert (entry['ts'], entry['level'], entry['message']) == (None, 'ERROR', 'boom')

    def test_the_logging_default_date_format_is_parsed(self):
        entry = parse('%(asctime)s %(levelname)s %(message)s', None, '2026-11-10 10:00:00,123 INFO hello')
        assert entry['ts'] == datetime(2026, 11, 10, 10, 0, 0, 123000)

    def test_a_format_without_asctime_still_yields_level_and_message(self):
        entry = parse('%(levelname)-8s %(name)s: %(message)s', None, 'ERROR    logics.x: boom')
        assert entry == {'ts': None, 'level': 'ERROR', 'logger': 'logics.x', 'message': 'boom'}

    @pytest.mark.parametrize(
        ('letter', 'level'),
        [('D', 'DEBUG'), ('I', 'INFO'), ('N', 'NOTICE'), ('W', 'WARNING'), ('E', 'ERROR'), ('C', 'CRITICAL')],
    )
    def test_a_level_letter_names_the_standard_level_even_if_custom_levels_share_it(self, letter, level):
        line = f'{letter} 1110 205405 lib.x   | f  ln:1    m  ----  Main '
        assert parse(COMPACT, COMPACT_DATE, line)['level'] == level

    def test_a_level_letter_unknown_to_logging_is_not_parsed(self):
        log_format = LogFormat.from_logging(COMPACT, COMPACT_DATE)
        assert log_format is not None
        assert log_format.parse('X 1110 205405 a | f  ln:1    m  ----  Main ', REFERENCE) is None

    def test_a_literal_percent_is_matched(self):
        entry = parse('%(levelname)s 100%% %(message)s', None, 'INFO 100% done')
        assert entry['message'] == 'done'


@pytest.mark.parametrize(
    ('fmt', 'datefmt'),
    [
        ('%(asctime)s %(message)s', SIMPLE_DATE),  # no level
        ('{levelname} {message}', None),  # another style
        ('%(levelname)s %(message)s %s', None),  # positional placeholder
        ('%(asctime)s %(levelname)s %(message)s', '%Y-%m-%d %H:%M:%S %Z'),  # unsupported date directive
        ('%(levelname)s %(levelname)s %(message)s', None),  # repeated reported field
    ],
)
def test_a_format_that_cannot_be_matched_has_no_parser(fmt, datefmt):
    assert LogFormat.from_logging(fmt, datefmt) is None
