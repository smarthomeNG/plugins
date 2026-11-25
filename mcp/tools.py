"""Tool implementations; independent of the MCP SDK and the transport."""

import asyncio
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Literal, overload

from lib.item.errors import ItemWriteRejected

from .access import AccessResolver
from .logs import LogReader
from .paging import decode_cursor, encode_cursor, page_size, paginate
from .ratelimit import SlidingWindowLimiter
from .types import (
    Access,
    AccessInfo,
    DiagnosticsSource,
    ExposeGroup,
    GetItemHistoryResult,
    GetLogsResult,
    HistoryEntry,
    HistoryPoint,
    HistorySource,
    GetThreadsResult,
    ListLogicsResult,
    ListPluginsResult,
    PluginInfo,
    SchedulerInfo,
    SystemInfo,
    Entitlement,
    ItemDetail,
    ItemSource,
    ItemSummary,
    ListItemsResult,
    ReadableItem,
    ToolFailure,
    WaitResult,
    WriteResult,
)

NOT_FOUND_MESSAGE = 'item not found'
DETAIL_LEVELS = ('value', 'full')
WRITE_CALLER = 'mcp'
RATE_LIMIT_ATTRIBUTE = 'mcp_rate_limit'
GLOBAL_RATE_KEY = '*'
SECRET_ATTRIBUTE_NAME = re.compile('pass|token|secret|key', re.IGNORECASE)


def _require_group(entitlement: Entitlement, group: ExposeGroup) -> None:
    """
    Check that the entitlement exposes the group.

    :raises ToolFailure: ``not_exposed`` otherwise
    """
    if group not in entitlement.expose:
        raise ToolFailure('not_exposed', f"group '{group}' is not exposed")


def get_access_info(entitlement: Entitlement, logs: LogReader) -> AccessInfo:
    """
    Return the effective entitlement, so a caller can tell why a path is invisible or read-only.

    The logfile names the caller may read are included when the ``logs`` group is exposed.
    """
    return {
        'token_id': entitlement.token_id,
        'default_access': entitlement.default_access,
        'inherit_rw_access': entitlement.inherit_rw_access,
        'max_access': entitlement.max_access,
        'write_paths': None if entitlement.write_paths is None else list(entitlement.write_paths),
        'expose': sorted(entitlement.expose),
        'write_rate_limit': entitlement.write_rate_limit,
        'log_files': logs.list_files() if 'logs' in entitlement.expose else [],
    }


class ItemTools:
    """Item tools for one entitlement."""

    def __init__(
        self,
        items: ItemSource,
        entitlement: Entitlement,
        default_page_size: int = 50,
        max_page_size: int = 200,
        clock: Callable[[], float] = time.monotonic,
        wait_max_seconds: float = 30.0,
        poll_interval: float = 0.2,
        write_limiter: SlidingWindowLimiter | None = None,
    ):
        self._items = items
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
        self._resolver = AccessResolver(entitlement)
        self._token_id = entitlement.token_id
        self._write_rate_limit = entitlement.write_rate_limit
        self._write_limiter = write_limiter or SlidingWindowLimiter(clock)
        self._wait_max_seconds = wait_max_seconds
        self._poll_interval = poll_interval

    @overload
    def get_item(self, path: str, detail: Literal['value'] = 'value') -> ItemSummary: ...

    @overload
    def get_item(self, path: str, detail: Literal['full']) -> ItemDetail: ...

    @overload
    def get_item(self, path: str, detail: str) -> ItemSummary | ItemDetail: ...

    def get_item(self, path: str, detail: str = 'value') -> ItemSummary | ItemDetail:
        """
        Return the item's summary, or its full detail.

        :param path: item path
        :param detail: ``value`` for the summary, ``full`` for the detail view
        :raises ToolFailure: ``bad_request`` for an unknown detail level; ``not_found`` if the path does
            not exist or is invisible to the entitlement
        """
        if detail not in DETAIL_LEVELS:
            raise ToolFailure('bad_request', f'detail must be one of {DETAIL_LEVELS}')
        item, access = self._visible_item(path)
        summary = self._summary_of(item, access)
        return self._detail(item, summary) if detail == 'full' else summary

    def list_items(
        self,
        prefix: str | None = None,
        type: str | None = None,
        has_attr: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> ListItemsResult:
        """
        Return one page of the visible items, ordered by path.

        :param prefix: only the item at this path and its descendants (whole path segments)
        :param type: only items of this item type
        :param has_attr: only items that carry this attribute themselves (not inherited)
        :param limit: page size, capped at the configured maximum
        :param cursor: the ``cursor`` of the previous page
        :raises ToolFailure: ``bad_request`` for a non-positive limit or an invalid cursor
        """
        size = page_size(limit, self._default_page_size, self._max_page_size)
        after = decode_cursor(cursor) if cursor is not None else None
        entries: list[ItemSummary] = []
        for item in self._items.return_items(ordered=True):
            path = item.id()
            if after is not None and path <= after:
                continue
            if prefix is not None and path != prefix and not path.startswith(prefix + '.'):
                continue
            if has_attr is not None and has_attr not in item.conf:
                continue
            entry = self._summary(item)
            if entry is None or (type is not None and entry['type'] != type):
                continue
            if len(entries) == size:
                return {'items': entries, 'cursor': encode_cursor(entries[-1]['path'])}
            entries.append(entry)
        return {'items': entries, 'cursor': None}

    def set_item(self, path: str, value: object) -> WriteResult:
        """
        Write a value to an item the entitlement may write.

        The value is cast to the item type first, so a mismatch is refused before it uses up write budget; a value
        the item itself drops (e.g. while it fades) is reported as well. The returned ``value`` is read back right after the write; ``eval``, hysteresis, fades or a
        concurrent writer can make it differ from the written value, and ``changed`` is False when the item
        kept its value.

        :raises ToolFailure: ``not_found`` for a missing or invisible item, ``forbidden`` for a read-only item,
            ``invalid_value`` if the value is null, does not fit the item type or is dropped by the item
        """
        item, access = self._visible_item(path)
        if access != 'rw':
            raise ToolFailure('forbidden', f'item is not writable (access: {access})')
        if value is None:
            raise ToolFailure('invalid_value', 'null cannot be written')
        try:
            cast_value = item.cast(value)
        except Exception as e:
            raise ToolFailure('invalid_value', f'value does not match item type {item.type()}') from e
        self._acquire_write_budget(item)
        previous = item()
        last_change = item.property.last_change
        self._write_item(item, cast_value)
        return {'previous': previous, 'value': item(), 'changed': item.property.last_change != last_change}

    async def wait_for_change(self, path: str, timeout: float) -> WaitResult:
        """
        Wait until the item's value changes, or until the timeout passes.

        Polls the item's ``last_change``; an update that keeps the value is not a change.

        :param timeout: seconds to wait, capped at the configured maximum
        :raises ToolFailure: ``not_found`` for a missing or invisible item, ``bad_request`` for a non-positive
            timeout
        """
        item, _ = self._visible_item(path)
        if timeout <= 0:
            raise ToolFailure('bad_request', 'timeout must be positive')
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(timeout, self._wait_max_seconds)
        previous = item()
        last_change = item.property.last_change
        while item.property.last_change == last_change:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return {'changed': False, 'value': item(), 'previous': previous, 'timed_out': True}
            await asyncio.sleep(min(self._poll_interval, remaining))
        return {'changed': True, 'value': item(), 'previous': previous, 'timed_out': False}

    def _visible_item(self, path: str) -> tuple[ReadableItem, Access]:
        """
        Return the item and the access the entitlement has on it.

        :raises ToolFailure: ``not_found`` if the path does not exist or is invisible
        """
        item = self._items.return_item(path)
        if item is None:
            raise ToolFailure('not_found', NOT_FOUND_MESSAGE)
        access = self._resolver.effective_access(item)
        if access == 'none':
            raise ToolFailure('not_found', NOT_FOUND_MESSAGE)
        return item, access

    def _acquire_write_budget(self, item: ReadableItem) -> None:
        """
        Count a write against its rate limit.

        An item with its own ``mcp_rate_limit`` (0 = unlimited) is limited per item and does not use the
        global budget; every other item shares the global ``write_rate_limit``.

        :raises ToolFailure: ``rate_limited`` with the seconds until a write would be allowed
        """
        item_limit = _parse_int(item.conf.get(RATE_LIMIT_ATTRIBUTE))
        if item_limit is not None:
            retry_after = self._write_limiter.acquire(item.id(), item_limit)
        else:
            retry_after = self._write_limiter.acquire(GLOBAL_RATE_KEY, self._write_rate_limit)
        if retry_after is not None:
            raise ToolFailure('rate_limited', 'write rate limit reached', retry_after)

    def _write_item(self, item: ReadableItem, value: object) -> None:
        """
        Write through the item's regular update path, attributed to this plugin and token.

        :raises ToolFailure: ``invalid_value`` if the item drops the value (wrong type, item fading)
        """
        try:
            item(value, caller=WRITE_CALLER, source=self._token_id, strict=True)
        except ItemWriteRejected as e:
            raise ToolFailure('invalid_value', f'item rejected the value ({e.reason.value})') from e

    def _summary(self, item: ReadableItem) -> ItemSummary | None:
        """Return the item's summary, None if the entitlement cannot see it."""
        access = self._resolver.effective_access(item)
        return None if access == 'none' else self._summary_of(item, access)

    @staticmethod
    def _summary_of(item: ReadableItem, access: Access) -> ItemSummary:
        """Return the item's summary for an access level the entitlement has on it."""
        return {'path': item.id(), 'type': item.type(), 'value': item(), 'access': access}

    def _detail(self, item: ReadableItem, summary: ItemSummary) -> ItemDetail:
        """Extend the summary with the item's metadata, visible children and non-secret attributes."""
        prop = item.property
        parent = item.return_parent()
        children = sorted(child.id() for child in item.return_children() if self._summary(child) is not None)
        return {
            **summary,
            'name': prop.name,
            'description': prop.description,
            'previous_value': prop.prev_value,
            'last_update': prop.last_update.isoformat() if prop.last_update else None,
            'last_change': prop.last_change.isoformat() if prop.last_change else None,
            'last_update_by': prop.last_update_by,
            'last_change_by': prop.last_change_by,
            'parent': parent.id() if isinstance(parent, ReadableItem) else None,
            'children': children,
            'triggers': {
                'eval': [prop.eval] if prop.eval else [],
                'eval_trigger': list(prop.trigger),
                'on_update': list(prop.on_update),
                'on_change': list(prop.on_change),
            },
            'attributes': {k: v for k, v in item.conf.items() if not SECRET_ATTRIBUTE_NAME.search(k)},
        }


def _parse_int(value: object) -> int | None:
    """Return the value as an int, None if it is absent or not an integer."""
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


class DiagnosticsTools:
    """Read-only diagnostic tools; each tool belongs to a group the entitlement must expose."""

    def __init__(
        self, source: DiagnosticsSource, entitlement: Entitlement, default_page_size: int = 50, max_page_size: int = 200
    ):
        self._source = source
        self._entitlement = entitlement
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size

    def list_plugins(self, limit: int | None = None, cursor: str | None = None) -> ListPluginsResult:
        """Return one page of the loaded plugin instances, ordered by ``plugin.yaml`` section name."""
        self._require('plugins')
        page, next_cursor = self._page(self._source.list_plugins(), lambda p: p['config_name'], limit, cursor)
        return {'plugins': page, 'cursor': next_cursor}

    def get_plugin_info(self, name: str) -> PluginInfo:
        """
        Return the status of the plugin instance with the given ``plugin.yaml`` section name.

        :raises ToolFailure: ``not_found`` if no such plugin instance is loaded
        """
        self._require('plugins')
        info = self._source.get_plugin_info(name)
        if info is None:
            raise ToolFailure('not_found', 'plugin not found')
        return info

    def list_schedulers(self) -> SchedulerInfo:
        """Return the scheduler's worker counts and running tasks."""
        self._require('scheduler')
        return self._source.get_scheduler_info()

    def list_logics(self, limit: int | None = None, cursor: str | None = None) -> ListLogicsResult:
        """Return one page of the loaded logics, ordered by name."""
        self._require('logics')
        page, next_cursor = self._page(self._source.list_logics(), lambda logic: logic['name'], limit, cursor)
        return {'logics': page, 'cursor': next_cursor}

    def get_threads(self, limit: int | None = None, cursor: str | None = None) -> GetThreadsResult:
        """Return one page of the process threads, ordered by name and ident."""
        self._require('threads')
        page, next_cursor = self._page(
            self._source.get_threads(), lambda thread: f'{thread["name"]}#{thread["ident"]}', limit, cursor
        )
        return {'threads': page, 'cursor': next_cursor}

    def get_system_info(self) -> SystemInfo:
        """Return version, status, Python, platform, pid and uptime."""
        self._require('system')
        return self._source.get_system_info()

    def _require(self, group: ExposeGroup) -> None:
        _require_group(self._entitlement, group)

    def _page(self, entries, key, limit: int | None, cursor: str | None):
        return paginate(entries, key, limit, cursor, self._default_page_size, self._max_page_size)


class LogTools:
    """The ``get_logs`` tool; it belongs to the ``logs`` group."""

    def __init__(
        self, logs: LogReader, entitlement: Entitlement, default_page_size: int = 50, max_page_size: int = 200
    ):
        self._logs = logs
        self._entitlement = entitlement
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size

    def get_logs(
        self,
        file: str,
        level: str | None = None,
        since: str | None = None,
        contains: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> GetLogsResult:
        """
        Return one page of the entries of a logfile, newest first.

        :raises ToolFailure: ``not_exposed`` unless logs are exposed; ``not_found`` for an unknown file;
            ``bad_request`` for an invalid limit, level, timestamp or cursor
        """
        _require_group(self._entitlement, 'logs')
        size = page_size(limit, self._default_page_size, self._max_page_size)
        return self._logs.read(file, level, since, contains, size, cursor)


DEFAULT_HISTORY_WINDOW = timedelta(hours=24)
DEFAULT_MAX_WINDOW_DAYS = 7


class HistoryTools:
    """The ``get_item_history`` tool; it belongs to the ``history`` group and obeys the item's visibility."""

    def __init__(
        self,
        source: HistorySource,
        items: ItemSource,
        entitlement: Entitlement,
        default_page_size: int = 50,
        max_page_size: int = 200,
        max_window_days: int = DEFAULT_MAX_WINDOW_DAYS,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        """
        :param max_window_days: longest span between ``since`` and ``until`` one request may read
        :param now: the current time
        """
        self._source = source
        self._items = items
        self._entitlement = entitlement
        self._resolver = AccessResolver(entitlement)
        self._default_page_size = default_page_size
        self._max_page_size = max_page_size
        self._max_window = timedelta(days=max_window_days)
        self._now = now

    def get_item_history(
        self,
        path: str,
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> GetItemHistoryResult:
        """
        Return one page of the item's logged values, newest first.

        ``since`` is inclusive and ``until`` exclusive; without them the last 24 hours up to now are read. A time
        without an offset is the instance's local time. The cursor of a page repeats the window, so ``since`` and
        ``until`` are ignored when it is given.

        :raises ToolFailure: ``not_exposed`` unless history is exposed; ``not_found`` if the item is invisible or
            has no history; ``bad_request`` for an invalid time, window, limit or cursor; ``unavailable`` if no
            database plugin is running
        """
        _require_group(self._entitlement, 'history')
        size = page_size(limit, self._default_page_size, self._max_page_size)
        item = self._items.return_item(path)
        if item is None or self._resolver.effective_access(item) == 'none':
            raise ToolFailure('not_found', NOT_FOUND_MESSAGE)
        since_ms, until_ms = self._window(since, until, cursor)
        points = self._source.read(path, since_ms - 1, until_ms)
        if points is None:
            raise ToolFailure('not_found', 'item has no history')
        newest_first = points[::-1]
        page = newest_first[:size]
        more = len(newest_first) > size
        return {
            'path': path,
            'entries': [_entry(point) for point in page],
            'cursor': encode_cursor(f'{since_ms}:{page[-1]["time_ms"]}') if more else None,
        }

    def _window(self, since: str | None, until: str | None, cursor: str | None) -> tuple[int, int]:
        """
        Return the window as milliseconds since the epoch: ``since`` inclusive, ``until`` exclusive.

        :raises ToolFailure: ``bad_request`` if a time or the cursor is invalid or the window is empty or too long
        """
        if cursor is not None:
            try:
                first, second = decode_cursor(cursor).split(':')
                return int(first), int(second)
            except ValueError:
                raise ToolFailure('bad_request', 'invalid cursor') from None
        end = _parse_time(until) if until else self._now()
        start = _parse_time(since) if since else end - DEFAULT_HISTORY_WINDOW
        if start >= end:
            raise ToolFailure('bad_request', 'since must be before until')
        if end - start > self._max_window:
            raise ToolFailure('bad_request', f'the window may span at most {self._max_window.days} days')
        return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _parse_time(text: str) -> datetime:
    """Parse an ISO 8601 time; one without an offset is the instance's local time."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise ToolFailure('bad_request', 'times must be ISO 8601') from None
    return moment.astimezone() if moment.tzinfo is None else moment


def _entry(point: HistoryPoint) -> HistoryEntry:
    """Convert a history point to the entry a client reads."""
    moment = datetime.fromtimestamp(point['time_ms'] / 1000, tz=timezone.utc)
    return {'time': moment.isoformat(), 'value': point['value'], 'valid': point['valid']}
