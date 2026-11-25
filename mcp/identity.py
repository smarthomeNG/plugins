"""The client a request acts for; set by the transport, read by the tools."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_CURRENT_CLIENT: ContextVar[str | None] = ContextVar('mcp_current_client', default=None)


def current_client() -> str | None:
    """Return the name of the authenticated client of the running request, None outside an authenticated request."""
    return _CURRENT_CLIENT.get()


@contextmanager
def acting_as(client: str) -> Iterator[None]:
    """Make ``client`` the current client for the tool calls made inside the block."""
    token = _CURRENT_CLIENT.set(client)
    try:
        yield
    finally:
        _CURRENT_CLIENT.reset(token)
