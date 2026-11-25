"""Item change events for ``subscriptions/listen`` streams."""

import asyncio
import threading
from collections.abc import Callable

from mcp.server.subscriptions import InMemorySubscriptionBus, ServerEvent
from mcp.shared.subscriptions import ResourceUpdated

from .access import AccessResolver
from .identity import current_client
from .types import Entitlement, EntitlementProvider, ItemSource

ITEM_URI_PREFIX = 'shng://item/'
DEFAULT_COALESCE_SECONDS = 0.25


def item_uri(path: str) -> str:
    """Return the resource URI of the item with the path."""
    return f'{ITEM_URI_PREFIX}{path}'


def item_path(uri: str) -> str | None:
    """Return the item path a resource URI names, None if it is no item URI."""
    return uri[len(ITEM_URI_PREFIX) :] if uri.startswith(ITEM_URI_PREFIX) else None


class ItemEvents:
    """
    Fans item changes out to the open ``subscriptions/listen`` streams; it is the server's subscription bus.

    A client is told about an item only while its own entitlement shows it. Changes of one item that follow each
    other within ``coalesce_seconds`` are announced once, because the event only says that the item has to be read
    again. Changes are reported with :meth:`item_changed` from any thread and ignored while no stream is open.
    """

    def __init__(
        self,
        items: ItemSource,
        access: Entitlement | EntitlementProvider,
        coalesce_seconds: float = DEFAULT_COALESCE_SECONDS,
    ):
        """
        :param access: the entitlement of every listener, or the provider that maps a client to its own
        """
        self._items = items
        self._access = access
        self._coalesce_seconds = coalesce_seconds
        self._bus = InMemorySubscriptionBus()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._streams = 0
        self._pending: set[str] = set()
        self._tasks: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()

    async def publish(self, event: ServerEvent) -> None:
        """Deliver the event to every listener that may see it."""
        await self._bus.publish(event)

    def subscribe(self, listener: Callable[[ServerEvent], None]) -> Callable[[], None]:
        """Register a listen stream of the calling client; it only gets the events of items that client can see."""
        client = current_client()
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._streams += 1
        unsubscribe = self._bus.subscribe(lambda event: self._deliver(client, listener, event))

        def end() -> None:
            unsubscribe()
            with self._lock:
                self._streams -= 1

        return end

    def item_changed(self, path: str) -> None:
        """Announce that the item changed; may be called from any thread."""
        loop = self._loop
        if loop is not None and self._streams > 0 and not loop.is_closed():
            loop.call_soon_threadsafe(self._schedule, path)

    def _schedule(self, path: str) -> None:
        """Announce the item after the coalescing delay unless that is already scheduled."""
        if path in self._pending:
            return
        self._pending.add(path)
        assert self._loop is not None
        self._loop.call_later(self._coalesce_seconds, self._announce, path)

    def _announce(self, path: str) -> None:
        """Publish the item's event on the event loop."""
        self._pending.discard(path)
        task = asyncio.get_running_loop().create_task(self.publish(ResourceUpdated(item_uri(path))))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _deliver(self, client: str | None, listener: Callable[[ServerEvent], None], event: ServerEvent) -> None:
        """Pass the event on if the client may see the item it names; fail closed for anything unclear."""
        if isinstance(event, ResourceUpdated):
            path = item_path(event.uri)
            if path is None or not self._visible(client, path):
                return
        listener(event)

    def _visible(self, client: str | None, path: str) -> bool:
        """Return True if the client's current entitlement shows the item."""
        if isinstance(self._access, Entitlement):
            entitlement: Entitlement | None = self._access
        else:
            entitlement = self._access.entitlement_for(client) if client is not None else None
        item = self._items.return_item(path)
        if entitlement is None or item is None:
            return False
        return AccessResolver(entitlement).effective_access(item) != 'none'
