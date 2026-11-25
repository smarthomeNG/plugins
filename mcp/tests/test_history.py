import asyncio
import os
from datetime import datetime, timedelta, timezone

import pytest
from mcp.client.client import Client

from plugins.mcp.history import DatabaseHistory
from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.tools import HistoryTools
from plugins.mcp.types import Entitlement, ToolFailure
from tests.mock.core import MockSmartHome

from .support import StaticSource

FIXTURE = os.path.join(os.path.dirname(__file__), 'fixtures', 'access_items.yaml')
NOW = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
HOUR = 3600_000


def at(hours_ago: float) -> int:
    """Milliseconds since the epoch of the moment ``hours_ago`` hours before NOW."""
    return int((NOW - timedelta(hours=hours_ago)).timestamp() * 1000)


def row(time_ms, num=None, boolean=None, text=None, quality=0):
    """A log row as the database plugin returns it: time, item id, duration, str, num, bool, changed, quality."""
    return (time_ms, 1, 1000, text, num, boolean, time_ms, quality)


class FakeDatabase:
    """Behaves like the database plugin for the two calls the history uses, over a fixed set of rows."""

    alive = True

    def __init__(self, rows: dict[str, list[tuple]], configname: str = 'database'):
        self._configname = configname
        self._rows = rows
        self._ids = {path: number for number, path in enumerate(rows, start=1)}

    def id(self, item, create=True, cur=None):
        return self._ids.get(item.property.path)

    def readLogs(self, id, time=None, time_start=None, time_end=None, **_ignored):
        path = next(path for path, number in self._ids.items() if number == id)
        return [
            r
            for r in self._rows[path]
            if (time_start is None or r[0] > time_start) and (time_end is None or r[0] < time_end)
        ]

    def get_configname(self):
        return self._configname

    def get_shortname(self):
        return 'database'


class Plugins:
    def __init__(self, *plugins):
        self._plugins = plugins

    def return_plugins(self):
        return self._plugins


LAMP = [row(at(5), boolean=True), row(at(3), boolean=False), row(at(1), boolean=True, quality=2)]
TEMP = [row(at(h), num=20.0 + h) for h in range(1, 11)]


@pytest.fixture
def items():
    sh = MockSmartHome()
    sh.with_items_from(FIXTURE)
    assert sh.items is not None
    return sh.items


def history_tools(items, expose=('history',), rows=None, max_days=7, **kwargs):
    database = FakeDatabase(rows or {'house.living.lamp': LAMP, 'house.living.temp': TEMP})
    source = DatabaseHistory(Plugins(database), items, None)
    entitlement = Entitlement('local', 'ro', False, frozenset(expose), 30)
    return HistoryTools(source, items, entitlement, max_window_days=max_days, now=lambda: NOW, **kwargs)


class TestEntries:
    def test_entries_come_newest_first_with_their_value_and_validity(self, items):
        result = history_tools(items).get_item_history('house.living.lamp')
        assert [(e['time'], e['value'], e['valid']) for e in result['entries']] == [
            ('2026-11-11T11:00:00+00:00', True, False),
            ('2026-11-11T09:00:00+00:00', False, True),
            ('2026-11-11T07:00:00+00:00', True, True),
        ]
        assert result['path'] == 'house.living.lamp'

    def test_a_numeric_value_is_read_from_the_numeric_column(self, items):
        entry = history_tools(items).get_item_history('house.living.temp')['entries'][0]
        assert entry['value'] == 21.0

    def test_an_untyped_item_takes_the_column_that_holds_a_value(self, items):
        rows = {'house': [row(at(1), text='auto')]}
        assert history_tools(items, rows=rows).get_item_history('house')['entries'][0]['value'] == 'auto'

    def test_a_typed_item_ignores_the_columns_of_other_types(self, items):
        rows = {'house.living.temp': [row(at(1), text='auto')]}
        assert history_tools(items, rows=rows).get_item_history('house.living.temp')['entries'][0]['value'] is None

    def test_a_gap_has_no_value(self, items):
        rows = {'house.living.temp': [row(at(1), quality=1)]}
        entry = history_tools(items, rows=rows).get_item_history('house.living.temp')['entries'][0]
        assert (entry['value'], entry['valid']) == (None, False)


class TestWindow:
    def test_without_a_window_the_last_day_is_read(self, items):
        rows = {'house.living.temp': [row(at(2)), row(at(23)), row(at(25))]}
        entries = history_tools(items, rows=rows).get_item_history('house.living.temp')['entries']
        assert len(entries) == 2

    def test_since_is_inclusive_and_until_exclusive(self, items):
        since, until = '2026-11-11T08:00:00+00:00', '2026-11-11T10:00:00+00:00'
        rows = {'house.living.temp': [row(at(4)), row(at(3)), row(at(2)), row(at(1))]}
        entries = history_tools(items, rows=rows).get_item_history('house.living.temp', since, until)['entries']
        assert [e['time'] for e in entries] == ['2026-11-11T09:00:00+00:00', '2026-11-11T08:00:00+00:00']

    @pytest.mark.parametrize(
        ('since', 'until'),
        [
            ('yesterday', None),
            ('2026-11-11T10:00:00+00:00', '2026-11-11T09:00:00+00:00'),
            ('2026-11-01T00:00:00+00:00', '2026-11-11T09:00:00+00:00'),
        ],
    )
    def test_an_invalid_window_is_a_bad_request(self, items, since, until):
        with pytest.raises(ToolFailure) as failure:
            history_tools(items).get_item_history('house.living.temp', since, until)
        assert failure.value.code == 'bad_request'

    def test_a_time_without_an_offset_is_the_local_time_of_the_instance(self, items):
        rows = {'house.living.temp': [row(at(2))]}
        since = (NOW - timedelta(hours=3)).astimezone().replace(tzinfo=None).isoformat()
        entries = history_tools(items, rows=rows).get_item_history('house.living.temp', since)['entries']
        assert len(entries) == 1


class TestPaging:
    def test_pages_cover_the_window_without_gaps_or_repeats(self, items):
        tools = history_tools(items, default_page_size=4)
        seen: list[str] = []
        cursor = None
        while True:
            page = tools.get_item_history('house.living.temp', limit=4, cursor=cursor)
            seen.extend(e['time'] for e in page['entries'])
            cursor = page['cursor']
            if cursor is None:
                break
        assert len(seen) == 10
        assert seen == sorted(seen, reverse=True)
        assert len(set(seen)) == 10

    def test_the_last_page_has_no_cursor(self, items):
        assert history_tools(items).get_item_history('house.living.temp', limit=10)['cursor'] is None

    def test_an_invalid_cursor_or_limit_is_a_bad_request(self, items):
        tools = history_tools(items)
        with pytest.raises(ToolFailure) as bad_cursor:
            tools.get_item_history('house.living.temp', cursor='!!')
        with pytest.raises(ToolFailure) as bad_limit:
            tools.get_item_history('house.living.temp', limit=0)
        assert (bad_cursor.value.code, bad_limit.value.code) == ('bad_request', 'bad_request')


class TestAccess:
    def test_the_group_must_be_exposed(self, items):
        with pytest.raises(ToolFailure) as failure:
            history_tools(items, expose=()).get_item_history('house.living.temp')
        assert failure.value.code == 'not_exposed'

    @pytest.mark.parametrize('path', ['house.alarm', 'nowhere', 'house.living.lamp.dimmer'])
    def test_an_item_the_client_cannot_see_or_that_has_no_history_is_not_found(self, items, path):
        with pytest.raises(ToolFailure) as failure:
            history_tools(items, rows={'house.alarm': LAMP}).get_item_history(path)
        assert failure.value.code == 'not_found'


class TestSource:
    def test_the_database_plugin_is_found_by_its_short_name(self, items):
        assert DatabaseHistory(Plugins(FakeDatabase({})), items, None).available()

    def test_a_configured_name_selects_the_instance(self, items):
        other = FakeDatabase({}, configname='archive')
        wanted = DatabaseHistory(Plugins(FakeDatabase({}), other), items, 'archive')
        assert wanted.available()
        assert not DatabaseHistory(Plugins(FakeDatabase({})), items, 'archive').available()

    def test_without_a_database_plugin_there_is_no_history(self, items):
        assert not DatabaseHistory(Plugins(), items, None).available()

    def test_a_plugin_without_the_calls_or_not_running_does_not_count(self, items):
        class Other:
            alive = True

            def get_configname(self):
                return 'database'

            def get_shortname(self):
                return 'database'

        stopped = FakeDatabase({})
        stopped.alive = False
        assert not DatabaseHistory(Plugins(Other()), items, None).available()
        assert not DatabaseHistory(Plugins(stopped), items, None).available()

    def test_a_database_that_went_away_is_reported_as_unavailable(self, items):
        database = FakeDatabase({'house.living.temp': TEMP})
        tools = HistoryTools(
            DatabaseHistory(Plugins(database), items, None),
            items,
            Entitlement('local', 'ro', False, frozenset({'history'}), 30),
            now=lambda: NOW,
        )
        database.alive = False
        with pytest.raises(ToolFailure) as failure:
            tools.get_item_history('house.living.temp')
        assert failure.value.code == 'unavailable'


class TestServer:
    """The tool through the MCP protocol."""

    def server(self, items, with_history=True):
        database = FakeDatabase({'house.living.temp': TEMP})
        history = DatabaseHistory(Plugins(database), items, None) if with_history else None
        entitlement = Entitlement('local', 'ro', False, frozenset({'history'}), 30)
        return create_mcp_server(items, entitlement, StaticSource(), LogReader('/nonexistent'), history=history)

    def tools(self, server):
        async def run():
            async with Client(server) as client:
                return {tool.name for tool in (await client.list_tools()).tools}

        return asyncio.run(run())

    def test_the_tool_is_offered_only_with_a_history_source(self, items):
        assert 'get_item_history' in self.tools(self.server(items))
        assert 'get_item_history' not in self.tools(self.server(items, with_history=False))

    def test_the_tool_answers_a_call(self, items):
        async def run():
            async with Client(self.server(items)) as client:
                return await client.call_tool(
                    'get_item_history', {'path': 'house.living.temp', 'until': '2026-11-11T12:00:00+00:00', 'limit': 2}
                )

        result = asyncio.run(run())
        assert result.structured_content is not None
        assert [e['value'] for e in result.structured_content['entries']] == [21.0, 22.0]
        assert result.structured_content['cursor'] is not None
