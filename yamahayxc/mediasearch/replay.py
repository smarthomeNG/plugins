"""
Replaying a media server path on the device's browse cursor.

The device has one global browse position. A hit's path is walked from layer 0
(the list of media servers) down: every layer but the last is entered with
select, the last entry is played. The path's position hints make this one
list request per layer; if a hint is missing or wrong the layer is scanned.
"""

from collections.abc import Callable
from enum import StrEnum
from typing import NamedTuple, Protocol

from .query import HitKind

PAGE_SIZE = 8
MAX_RETURNS = 16
ATTR_SELECT = 1 << 0


class CursorError(Exception):
    """The device did not answer or rejected a browse request"""


class PathStep(NamedTuple):
    """One layer on the way to a hit: the entry's text and its expected position in that layer, if known"""

    text: str
    hint: int | None


class Hit(NamedTuple):
    """A playable search result: path leads from the device's layer 0 (the media server) to the entry to play"""

    kind: HitKind
    title: str
    album: str
    path: tuple[PathStep, ...]


class ListEntry(NamedTuple):
    """One line of a device list: displayed text and the YXC attribute bit mask"""

    text: str
    attribute: int


class ListPage(NamedTuple):
    """Up to PAGE_SIZE entries of the current layer starting at index"""

    menu_layer: int
    max_line: int
    index: int
    entries: tuple[ListEntry, ...]


class ListCursor(Protocol):
    """The device's browse cursor; every method raises CursorError if the device fails"""

    def prepare(self) -> None:
        """make the device ready for browsing the server input"""

    def page(self, index: int) -> ListPage:
        """list the current layer from index (a multiple of PAGE_SIZE)"""

    def select(self, index: int) -> None:
        """enter the container at absolute index of the current layer"""

    def back(self) -> None:
        """leave the current layer"""

    def play(self, index: int) -> None:
        """play the track at index; the rest of its layer continues"""

    def play_now(self, index: int) -> None:
        """play the container or track at index immediately"""


class ReplayResult(StrEnum):
    """How a replay ended"""

    OK = 'ok'
    PATH_FAILED = 'path_failed'
    CANCELLED = 'cancelled'


def replay(hit: Hit, cursor: ListCursor, cancelled: Callable[[], bool]) -> ReplayResult:
    """
    walk hit.path on cursor and play its last entry

    cancelled is polled before every layer so a newer request can take over.
    """
    cursor.prepare()
    page: ListPage | None = cursor.page(0)
    returns = 0
    while page.menu_layer > 0:
        if returns == MAX_RETURNS:
            return ReplayResult.PATH_FAILED
        cursor.back()
        returns += 1
        page = cursor.page(0)

    last = len(hit.path) - 1
    for depth, step in enumerate(hit.path):
        if cancelled():
            return ReplayResult.CANCELLED
        aligned = (step.hint or 0) // PAGE_SIZE * PAGE_SIZE
        if page is None or page.index != aligned:
            page = cursor.page(aligned)
        index = _locate(step, page, cursor, cancelled)
        if index is None:
            return ReplayResult.CANCELLED if cancelled() else ReplayResult.PATH_FAILED
        if depth < last:
            cursor.select(index)
            page = None
        elif hit.kind is HitKind.ALBUM:
            cursor.play_now(index)
        else:
            cursor.play(index)
    return ReplayResult.OK


def _is_exact(step: PathStep, entry: ListEntry) -> bool:
    return step.text.casefold() == entry.text.casefold()


def _is_truncation(step: PathStep, entry: ListEntry) -> bool:
    """the device may cut the text of selectable entries short"""
    return bool(entry.attribute & ATTR_SELECT and entry.text and step.text.casefold().startswith(entry.text.casefold()))


def _locate(step: PathStep, page: ListPage, cursor: ListCursor, cancelled: Callable[[], bool]) -> int | None:
    """return the absolute index of step's entry in the layer page belongs to: at its hint, else by scanning"""
    if step.hint is not None:
        offset = step.hint - page.index
        if 0 <= offset < len(page.entries):
            entry = page.entries[offset]
            if _is_exact(step, entry) or _is_truncation(step, entry):
                return step.hint

    truncated = None
    for start in range(0, page.max_line, PAGE_SIZE):
        if cancelled():
            return None
        scanned = page if page.index == start else cursor.page(start)
        for offset, entry in enumerate(scanned.entries):
            if _is_exact(step, entry):
                return start + offset
            if truncated is None and _is_truncation(step, entry):
                truncated = start + offset
    return truncated
