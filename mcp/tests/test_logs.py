import logging
import logging.handlers
import os
import time
from contextlib import contextmanager
from datetime import datetime

import pytest
from tests import common

from plugins.mcp.logs import LogReader
from plugins.mcp.types import ToolFailure

common.register_shng_log_levels()

DEFAULT_LOG = """\
2026-11-10  10:00:00 NOTICE   lib.smarthome       started
2026-11-10  10:00:05 INFO     plugins.knx         connected to gateway
2026-11-10  10:01:00 WARNING  items.house.light   slow update
2026-11-10  10:02:00 ERROR    logics.heating      failed
Traceback (most recent call last):
  File "heating.py", line 3, in <module>
ValueError: boom
2026-11-10  10:03:00 DEBUG    lib.scheduler       tick
"""


def reader(tmp_path, content=DEFAULT_LOG, name='shng.log', **kwargs):
    (tmp_path / name).write_text(content, encoding='UTF-8')
    return LogReader(str(tmp_path), **kwargs)


@contextmanager
def written_with(tmp_path, fmt, datefmt=None, name='shng.log', handler_class=logging.FileHandler):
    """Attach a real file handler for ``tmp_path/name`` with the given format to a named logger."""
    logger = logging.getLogger('mcp_test_logs')
    handler = handler_class(str(tmp_path / name), delay=True)
    handler.setFormatter(logging.Formatter(fmt, datefmt))
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()


COMPACT = (
    '%(levelname).1s %(asctime)s %(name)-19s | %(funcName)-25s ln:%(lineno)-4d %(message)s  ----  %(threadName)-12s '
)
COMPACT_LOG = """\
N 1110 100000 lib.smarthome       | __init__                  ln:428  started  ----  Main         
W 1110 100100 items.house.light   | update                    ln:12   slow update  ----  Main         
E 1110 100200 logics.heating      | <module>                  ln:3    failed  ----  logics.heating
Traceback (most recent call last):
ValueError: boom
D 1110 100300 lib.scheduler       | tick                      ln:9    tick  ----  Scheduler    
"""


def messages(page):
    return [entry['message'].splitlines()[0].strip() for entry in page['entries']]


class TestFiles:
    def test_only_regular_log_files_are_listed_in_order(self, tmp_path):
        for name in ('b.log', 'a.log', 'a.2026-10-27.log', '.hidden.log', 'notes.txt'):
            (tmp_path / name).write_text('x\n')
        (tmp_path / 'dir.log').mkdir()
        assert LogReader(str(tmp_path)).list_files() == ['a.2026-10-27.log', 'a.log', 'b.log']

    def test_a_missing_log_directory_has_no_files(self, tmp_path):
        assert LogReader(str(tmp_path / 'absent')).list_files() == []

    @pytest.mark.parametrize('name', ['nope.log', '../shng.log', '/etc/passwd', 'sub/shng.log', '.hidden.log'])
    def test_an_unlisted_file_is_not_found(self, tmp_path, name):
        with pytest.raises(ToolFailure) as failure:
            reader(tmp_path).read(name)
        assert failure.value.code == 'not_found'


class TestEntries:
    def test_entries_are_returned_newest_first_with_parsed_fields(self, tmp_path):
        page = reader(tmp_path).read('shng.log', limit=2)
        assert page['entries'] == [
            {'line': 8, 'ts': '2026-11-10T10:03:00', 'level': 'DEBUG', 'logger': 'lib.scheduler', 'message': 'tick'},
            {
                'line': 7,
                'ts': '2026-11-10T10:02:00',
                'level': 'ERROR',
                'logger': 'logics.heating',
                'message': 'failed\n'
                'Traceback (most recent call last):\n'
                '  File "heating.py", line 3, in <module>\n'
                'ValueError: boom',
            },
        ]

    def test_a_timezone_name_before_the_level_is_skipped(self, tmp_path):
        content = '2026-11-10 10:00:00 CET      INFO     plugins.knx         hello\n'
        (entry,) = reader(tmp_path, content).read('shng.log')['entries']
        assert (entry['ts'], entry['level'], entry['logger'], entry['message']) == (
            '2026-11-10T10:00:00',
            'INFO',
            'plugins.knx',
            'hello',
        )

    def test_a_line_in_another_format_is_returned_whole_without_fields(self, tmp_path):
        (entry,) = reader(tmp_path, '2026-11-10;10:00:00;busmonitor 1/2/3;\n').read('shng.log')['entries']
        assert entry == {
            'line': 1,
            'ts': None,
            'level': None,
            'logger': None,
            'message': '2026-11-10;10:00:00;busmonitor 1/2/3;',
        }

    def test_an_overlong_message_is_cut(self, tmp_path):
        content = '2026-11-10 10:00:00 INFO     x   ' + 'y' * 10_000 + '\n'
        (entry,) = reader(tmp_path, content).read('shng.log')['entries']
        assert len(entry['message']) < 5000
        assert entry['message'].endswith('[truncated]')


class TestFilters:
    def test_level_is_a_minimum(self, tmp_path):
        page = reader(tmp_path).read('shng.log', level='WARNING')
        assert messages(page) == ['failed', 'slow update']

    def test_the_shng_level_notice_is_a_filter_level(self, tmp_path):
        kept = messages(reader(tmp_path).read('shng.log', level='NOTICE'))
        assert 'started' in kept
        assert 'connected to gateway' not in kept

    def test_unparsed_entries_are_dropped_by_a_level_filter(self, tmp_path):
        content = 'free text\n2026-11-10 10:00:00 ERROR    x   bad\n'
        assert messages(reader(tmp_path, content).read('shng.log', level='ERROR')) == ['bad']

    def test_an_unknown_level_is_a_bad_request(self, tmp_path):
        with pytest.raises(ToolFailure) as failure:
            reader(tmp_path).read('shng.log', level='LOUD')
        assert failure.value.code == 'bad_request'

    def test_since_keeps_entries_from_that_time_on(self, tmp_path):
        page = reader(tmp_path).read('shng.log', since='2026-11-10T10:01:00')
        assert messages(page) == ['tick', 'failed', 'slow update']

    def test_an_invalid_since_is_a_bad_request(self, tmp_path):
        with pytest.raises(ToolFailure) as failure:
            reader(tmp_path).read('shng.log', since='yesterday')
        assert failure.value.code == 'bad_request'

    def test_contains_ignores_case_and_looks_into_tracebacks(self, tmp_path):
        assert messages(reader(tmp_path).read('shng.log', contains='VALUEERROR')) == ['failed']


class TestPaging:
    def test_a_cursor_continues_with_older_entries(self, tmp_path):
        log = reader(tmp_path)
        first = log.read('shng.log', limit=2)
        assert messages(first) == ['tick', 'failed']
        assert first['cursor'] is not None
        second = log.read('shng.log', limit=2, cursor=first['cursor'])
        assert messages(second) == ['slow update', 'connected to gateway']
        third = log.read('shng.log', limit=2, cursor=second['cursor'])
        assert messages(third) == ['started']
        assert third['cursor'] is None

    def test_filters_apply_across_pages(self, tmp_path):
        log = reader(tmp_path)
        first = log.read('shng.log', level='INFO', limit=2)
        assert messages(first) == ['failed', 'slow update']
        second = log.read('shng.log', level='INFO', limit=2, cursor=first['cursor'])
        assert messages(second) == ['connected to gateway', 'started']
        assert second['cursor'] is None

    def test_an_invalid_cursor_is_a_bad_request(self, tmp_path):
        for cursor in ('!!!', 'bm90LWEtbnVtYmVy'):
            with pytest.raises(ToolFailure) as failure:
                reader(tmp_path).read('shng.log', cursor=cursor)
            assert failure.value.code == 'bad_request'


class TestRedaction:
    @pytest.mark.parametrize(
        'text',
        [
            'login password=hunter2 ok',
            "config {'password': 'hunter2'}",
            'send Authorization: Bearer hunter2 now',
            'GET http://admin:hunter2@host/x',
            'api_key: hunter2',
            'token="hunter2"',
        ],
    )
    def test_secrets_are_replaced_in_messages(self, tmp_path, text):
        content = f'2026-11-10 10:00:00 INFO     x   {text}\n'
        (entry,) = reader(tmp_path, content).read('shng.log')['entries']
        assert 'hunter2' not in entry['message']
        assert '***' in entry['message']

    def test_text_without_secrets_is_unchanged(self, tmp_path):
        content = '2026-11-10 10:00:00 INFO     x   keyboard passes the check\n'
        (entry,) = reader(tmp_path, content).read('shng.log')['entries']
        assert entry['message'] == 'keyboard passes the check'

    def test_configured_patterns_are_applied_as_well(self, tmp_path):
        content = '2026-11-10 10:00:00 INFO     x   serial SN-12345 seen\n'
        (entry,) = reader(tmp_path, content, redact_patterns=[r'SN-\d+']).read('shng.log')['entries']
        assert entry['message'] == 'serial *** seen'

    def test_contains_cannot_probe_redacted_text(self, tmp_path):
        content = '2026-11-10 10:00:00 INFO     x   password=hunter2\n'
        assert reader(tmp_path, content).read('shng.log', contains='hunter2')['entries'] == []

    def test_an_invalid_configured_pattern_is_rejected(self, tmp_path):
        with pytest.raises(ValueError):
            LogReader(str(tmp_path), redact_patterns=['('])


class TestHandlerFormat:
    def test_a_file_is_parsed_with_the_format_of_the_handler_writing_it(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S'):
            (entry, *_) = reader(tmp_path, COMPACT_LOG).read('shng.log')['entries']
        assert ((entry['ts'] or '')[5:], entry['level'], entry['logger'], entry['message']) == (
            '11-10T10:03:00',
            'DEBUG',
            'lib.scheduler',
            'tick',
        )

    def test_level_and_since_filters_work_on_a_handler_format(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S'):
            log = reader(tmp_path, COMPACT_LOG)
            assert messages(log.read('shng.log', level='WARNING')) == ['failed', 'slow update']
            year = (log.read('shng.log')['entries'][0]['ts'] or '')[:4]
            assert messages(log.read('shng.log', since=f'{year}-11-10T10:01:00')) == ['tick', 'failed', 'slow update']

    def test_a_traceback_stays_with_its_entry(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S'):
            entries = reader(tmp_path, COMPACT_LOG).read('shng.log')['entries']
        assert entries[1]['message'] == 'failed\nTraceback (most recent call last):\nValueError: boom'

    def test_a_rotated_file_uses_the_format_of_its_handler(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S', name='shng.log'):
            page = reader(tmp_path, COMPACT_LOG, name='shng.2026-11-09.log').read('shng.2026-11-09.log')
        assert page['entries'][0]['level'] == 'DEBUG'

    def test_a_file_in_another_directory_is_not_matched(self, tmp_path):
        other = tmp_path / 'other'
        other.mkdir()
        with written_with(other, COMPACT, '%m%d %H%M%S'):
            page = reader(tmp_path, COMPACT_LOG).read('shng.log')
        assert page['entries'][0]['level'] is None

    def test_a_lines_that_does_not_fit_the_handler_format_stays_unparsed(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S'):
            (entry,) = reader(tmp_path, 'free text\n').read('shng.log')['entries']
        assert (entry['level'], entry['message']) == (None, 'free text')

    def test_a_file_without_a_handler_is_parsed_as_the_default_format(self, tmp_path):
        assert reader(tmp_path).read('shng.log')['entries'][0]['level'] == 'DEBUG'

    def test_the_year_of_a_year_less_date_follows_the_file_modification_time(self, tmp_path):
        with written_with(tmp_path, COMPACT, '%m%d %H%M%S'):
            log = reader(tmp_path, COMPACT_LOG)
            mtime = datetime(2025, 11, 12).timestamp()
            os.utime(tmp_path / 'shng.log', (mtime, mtime))
            assert (log.read('shng.log')['entries'][0]['ts'] or '').startswith('2025-11-10')

    def test_the_shng_rotating_handler_is_recognised(self, tmp_path):
        from lib.log import ShngTimedRotatingFileHandler

        with written_with(tmp_path, COMPACT, '%m%d %H%M%S', handler_class=ShngTimedRotatingFileHandler):
            assert reader(tmp_path, COMPACT_LOG).read('shng.log')['entries'][0]['level'] == 'DEBUG'
