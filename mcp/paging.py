"""Opaque cursors and page-size handling shared by the paged tools."""

import base64
import binascii
from collections.abc import Callable, Iterable
from typing import TypeVar

from .types import ToolFailure

T = TypeVar('T')


def encode_cursor(key: str) -> str:
    """Return an opaque cursor that resumes after the given key."""
    return base64.urlsafe_b64encode(key.encode()).decode()


def decode_cursor(cursor: str) -> str:
    """
    Return the key an opaque cursor resumes after.

    :raises ToolFailure: ``bad_request`` if the cursor was not produced by :func:`encode_cursor`
    """
    try:
        key = base64.urlsafe_b64decode(cursor.encode()).decode()
    except (binascii.Error, UnicodeError) as e:
        raise ToolFailure('bad_request', 'invalid cursor') from e
    if encode_cursor(key) != cursor:
        raise ToolFailure('bad_request', 'invalid cursor')
    return key


def page_size(limit: int | None, default: int, maximum: int) -> int:
    """
    Return the effective page size.

    :param limit: requested size, None for the default
    :param default: size used when no limit is given
    :param maximum: hard cap
    :raises ToolFailure: ``bad_request`` if the limit is not positive
    """
    if limit is None:
        return min(default, maximum)
    if limit < 1:
        raise ToolFailure('bad_request', 'limit must be at least 1')
    return min(limit, maximum)


def paginate(
    entries: Iterable[T], key: Callable[[T], str], limit: int | None, cursor: str | None, default: int, maximum: int
) -> tuple[list[T], str | None]:
    """
    Return one page of the entries ordered by key, and the cursor of the next page (None on the last).

    :raises ToolFailure: ``bad_request`` for a non-positive limit or an invalid cursor
    """
    size = page_size(limit, default, maximum)
    after = decode_cursor(cursor) if cursor is not None else None
    remaining = [entry for entry in sorted(entries, key=key) if after is None or key(entry) > after]
    page = remaining[:size]
    return page, encode_cursor(key(page[-1])) if len(remaining) > size else None
