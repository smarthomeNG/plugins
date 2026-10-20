"""Media search for the yamahayxc plugin: find a track or album on a UPnP media server and play it on the device."""

import logging
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from enum import StrEnum
from typing import TYPE_CHECKING, NamedTuple

from .cds import CdsSearchFinder
from .query import parse_query
from .replay import CursorError, Hit, ListCursor, ListEntry, ListPage, ReplayResult, replay

if TYPE_CHECKING:
    from .. import YamahaYXC

MAX_CANDIDATES = 5
logger = logging.getLogger(__name__)

INPUT = 'server'
ZONE = 'main'
WAKE_POLLS = 40
WAKE_POLL_SECONDS = 0.5


class YxcListCursor:
    """ListCursor over a YamahaYXC plugin's HTTP access to one device (main zone, server input)"""

    def __init__(self, plugin: 'YamahaYXC', host: str):
        self.plugin = plugin
        self.host = host

    def _send(self, payload: str, timeout: float | None = None) -> dict:
        """submit payload and return the response; raise CursorError if there is none or it is a rejection"""
        state = self.plugin._submit_payload(self.host, payload, timeout=timeout)
        if not isinstance(state, dict) or state.get('response_code'):
            raise CursorError(f'{payload}: no usable answer ({state})')
        return state

    def _status(self) -> dict:
        return self._send(self.plugin._build_cmd_get_state(ZONE))

    def prepare(self) -> None:
        """power the main zone on if it is in standby (waiting for it to come up) and select the server input"""
        status = self._status()
        if status.get('power') != 'on':
            self._send(self.plugin._build_cmd_power(True, ZONE))
            for _ in range(WAKE_POLLS):
                status = self._status()
                if status.get('power') == 'on':
                    break
                time.sleep(WAKE_POLL_SECONDS)
            else:
                raise CursorError('device did not power on')
        if status.get('input') != INPUT:
            self._send(self.plugin._build_cmd_input(INPUT, ZONE))

    def page(self, index: int) -> ListPage:
        state = self._send(
            self.plugin._build_cmd_browse_list(INPUT, index), timeout=self.plugin._yamaha_browse_http_timeout
        )
        entries = tuple(ListEntry(line['text'], line['attribute']) for line in state['list_info'])
        return ListPage(state['menu_layer'], state['max_line'], state['index'], entries)

    def select(self, index: int) -> None:
        self._send(self.plugin._build_cmd_browse_select(index))

    def back(self) -> None:
        self._send(self.plugin._build_cmd_browse_return(None))

    def play(self, index: int) -> None:
        self._send(self.plugin._build_cmd_browse_play(index))

    def play_now(self, index: int) -> None:
        self._send(
            self.plugin._build_cmd_manage_list('play_now', index), timeout=self.plugin._yamaha_manage_http_timeout
        )


class SearchStatus(StrEnum):
    """State of the latest search request, as published on the search.status item"""

    IDLE = 'idle'
    BUSY = 'busy'
    OK = 'ok'
    NO_MATCH = 'no_match'
    PATH_FAILED = 'path_failed'
    ERROR = 'error'
    DISABLED = 'disabled'


class SearchReport(NamedTuple):
    """Outcome of one search: its status and the hit it settled on, if any"""

    status: SearchStatus
    hit: Hit | None


def run_search(
    raw_query: str,
    finder: CdsSearchFinder,
    cursor: ListCursor,
    cursor_lock: AbstractContextManager,
    cancelled: Callable[[], bool],
) -> SearchReport:
    """
    find the best match for raw_query on the media server and play it on the device

    The device's browse cursor is held (cursor_lock) only while the hit is
    replayed. A search cancelled before it played anything reports IDLE.
    MediaServerError propagates so the caller can rediscover the server.
    """
    query = parse_query(raw_query)
    candidates = finder.find(query) if query else []
    if not candidates:
        return SearchReport(SearchStatus.NO_MATCH, None)

    hit = None
    for candidate in candidates[:MAX_CANDIDATES]:
        hit = finder.resolve(candidate)
        if hit:
            break
    if hit is None:
        return SearchReport(SearchStatus.PATH_FAILED, None)

    try:
        with cursor_lock:
            result = replay(hit, cursor, cancelled)
    except CursorError as e:
        logger.warning(f'media search: device failed while playing {hit.title!r}: {e}')
        return SearchReport(SearchStatus.ERROR, hit)
    if result is ReplayResult.CANCELLED:
        return SearchReport(SearchStatus.IDLE, None)
    return SearchReport(SearchStatus.OK if result is ReplayResult.OK else SearchStatus.PATH_FAILED, hit)
