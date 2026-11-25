"""HTTP transport: bearer-token authenticated ASGI app served by uvicorn in a background thread."""

import asyncio
import logging
import math
import threading
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

from .identity import acting_as
from .ratelimit import SlidingWindowLimiter
from .types import TokenAuthenticator

logger = logging.getLogger(__name__)

STARTUP_TIMEOUT = 10.0
GRACEFUL_SHUTDOWN_TIMEOUT = 2
SHUTDOWN_TIMEOUT = 10.0
DEFAULT_AUTH_FAILURE_LIMIT = 20
LOOPBACK_HOSTS = ('127.0.0.1:*', 'localhost:*', '[::1]:*')
LOOPBACK_ORIGINS = ('http://127.0.0.1:*', 'http://localhost:*', 'http://[::1]:*')


@dataclass(frozen=True)
class TransportSettings:
    """How the server is exposed beyond a plain loopback listener."""

    tls_certfile: str | None = None
    tls_keyfile: str | None = None
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()
    auth_failure_limit: int = DEFAULT_AUTH_FAILURE_LIMIT

    def security(self) -> TransportSecuritySettings | None:
        """
        Return the Host/Origin validation to apply, None to leave it to the SDK's default for the bind address.

        Configured hosts and origins are accepted in addition to the loopback ones.
        """
        if not self.allowed_hosts and not self.allowed_origins:
            return None
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[*LOOPBACK_HOSTS, *self.allowed_hosts],
            allowed_origins=[*LOOPBACK_ORIGINS, *self.allowed_origins],
        )


def _respond(status: int, text: str, headers: list[tuple[bytes, bytes]] | None = None):
    """Return the two ASGI messages of a short plain-text response."""
    return (
        {
            'type': 'http.response.start',
            'status': status,
            'headers': [(b'content-type', b'text/plain'), *(headers or [])],
        },
        {'type': 'http.response.body', 'body': text.encode()},
    )


class ClientAuth:
    """
    ASGI middleware that lets only authenticated clients through.

    A request without a bearer token a client owns gets 401; such failures are logged with the peer address and,
    beyond ``failure_limit`` per minute and address, answered with 429 (a valid token is never throttled). A client
    that connects from an address outside its allowed networks gets 403. The wrapped app runs as the client that
    owns the token (see :func:`identity.current_client`).
    """

    def __init__(
        self,
        app: ASGIApp,
        authenticator: TokenAuthenticator,
        failure_limit: int = DEFAULT_AUTH_FAILURE_LIMIT,
        failures: SlidingWindowLimiter | None = None,
    ):
        """
        :param failure_limit: failed authentications per minute and peer address before 429; 0 disables throttling
        :param failures: the counter of failed authentications
        """
        self._app = app
        self._authenticator = authenticator
        self._failure_limit = failure_limit
        self._failures = failures or SlidingWindowLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self._app(scope, receive, send)
            return
        peer = scope['client'][0] if scope.get('client') else None
        client = self._authenticate(scope)
        if client is None:
            await self._refuse_unauthenticated(peer, send)
            return
        if not self._authenticator.permits(client, peer):
            logger.warning(f'client {client!r} refused: it may not connect from {peer}')
            for message in _respond(403, 'forbidden'):
                await send(message)
            return
        with acting_as(client):
            await self._app(scope, receive, send)

    async def _refuse_unauthenticated(self, peer: str | None, send: Send) -> None:
        """Answer a request without a valid token: 401, or 429 once the peer has failed too often."""
        retry_after = self._failures.acquire(peer or '-', self._failure_limit)
        if retry_after is None:
            logger.warning(f'request from {peer} refused: no valid bearer token')
            messages = _respond(401, 'unauthorized')
        else:
            messages = _respond(
                429, 'too many failed attempts', [(b'retry-after', str(math.ceil(retry_after)).encode())]
            )
        for message in messages:
            await send(message)

    def _authenticate(self, scope: Scope) -> str | None:
        """Return the client owning the request's bearer token, None if there is none or nobody owns it."""
        for name, value in scope['headers']:
            if name == b'authorization':
                scheme, _, token = value.partition(b' ')
                if scheme.lower() != b'bearer':
                    return None
                try:
                    return self._authenticator.authenticate(token.decode('ascii'))
                except UnicodeDecodeError:
                    return None
        return None


class ShutdownGuard:
    """
    ASGI middleware that can end every open HTTP request at once.

    Requests cancelled by :meth:`close` are completed with a clean end of response, so the server sees neither
    a cancelled task nor an unfinished response.
    """

    def __init__(self, app: ASGIApp):
        self._app = app
        self._loop: asyncio.AbstractEventLoop | None = None
        self._open: set[asyncio.Task[Any]] = set()
        self._closing = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self._app(scope, receive, send)
            return
        task = asyncio.current_task()
        assert task is not None
        self._loop = asyncio.get_running_loop()
        self._open.add(task)
        started = complete = False

        async def tracking_send(message: MutableMapping[str, Any]) -> None:
            nonlocal started, complete
            if message['type'] == 'http.response.start':
                started = True
            elif message['type'] == 'http.response.body' and not message.get('more_body', False):
                complete = True
            await send(message)

        try:
            await self._app(scope, receive, tracking_send)
        except asyncio.CancelledError:
            if not self._closing:
                raise
            task.uncancel()
            if not started:
                await send({'type': 'http.response.start', 'status': 503, 'headers': []})
            if not complete:
                await send({'type': 'http.response.body', 'body': b''})
        finally:
            self._open.discard(task)

    def close(self) -> None:
        """Cancel every open request; may be called from any thread."""
        self._closing = True
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._cancel_open)

    def _cancel_open(self) -> None:
        for task in list(self._open):
            task.cancel()


def _serve(server: uvicorn.Server) -> None:
    """Run the uvicorn server in the current thread; a startup failure is logged, not left as a thread traceback."""
    try:
        asyncio.run(server.serve())
    except SystemExit:
        pass
    except Exception:
        logger.exception('MCP HTTP server stopped unexpectedly')


class McpHttpServer:
    """Serves an MCP server over streamable HTTP; start() and stop() may alternate."""

    def __init__(
        self,
        mcp_server: MCPServer,
        authenticator: TokenAuthenticator,
        bind_address: str,
        port: int,
        settings: TransportSettings = TransportSettings(),
    ):
        self._mcp_server = mcp_server
        self._authenticator = authenticator
        self._bind_address = bind_address
        self._requested_port = port
        self._settings = settings
        self._uvicorn: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._guard: ShutdownGuard | None = None

    @property
    def port(self) -> int:
        """Return the bound port (the actual one if port 0 was requested); only valid while started."""
        if self._uvicorn is None or not self._uvicorn.servers:
            raise RuntimeError('server is not started')
        return self._uvicorn.servers[0].sockets[0].getsockname()[1]

    def start(self) -> None:
        """
        Start serving in a background thread and wait until the socket is bound.

        :raises RuntimeError: the server did not come up (for example the port is in use)
        """
        guard = ShutdownGuard(
            ClientAuth(
                self._mcp_server.streamable_http_app(
                    host=self._bind_address, stateless_http=True, transport_security=self._settings.security()
                ),
                self._authenticator,
                self._settings.auth_failure_limit,
            )
        )
        config = uvicorn.Config(
            guard,
            host=self._bind_address,
            port=self._requested_port,
            log_level='warning',
            log_config=None,
            ssl_certfile=self._settings.tls_certfile,
            ssl_keyfile=self._settings.tls_keyfile,
            timeout_graceful_shutdown=GRACEFUL_SHUTDOWN_TIMEOUT,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=lambda: _serve(server), name='mcp-http', daemon=True)
        thread.start()
        if not self._wait_until_started(server, thread):
            server.should_exit = True
            thread.join(SHUTDOWN_TIMEOUT)
            raise RuntimeError(f'MCP HTTP server did not start on {self._bind_address}:{self._requested_port}')
        self._uvicorn, self._thread, self._guard = server, thread, guard

    def stop(self) -> None:
        """
        Stop serving and wait for the server thread to end; does nothing if not started.

        Open requests, such as event streams, are ended first; ``GRACEFUL_SHUTDOWN_TIMEOUT`` bounds what is left.
        """
        if self._uvicorn is None or self._thread is None:
            return
        if self._guard is not None:
            self._guard.close()
        self._uvicorn.should_exit = True
        self._thread.join(SHUTDOWN_TIMEOUT)
        if self._thread.is_alive():
            raise RuntimeError('MCP HTTP server thread did not stop')
        self._uvicorn = self._thread = self._guard = None

    @staticmethod
    def _wait_until_started(server: uvicorn.Server, thread: threading.Thread) -> bool:
        """Poll until uvicorn reports started; False if the thread died or the timeout passed."""
        waited = 0.0
        while not server.started:
            if not thread.is_alive() or waited >= STARTUP_TIMEOUT:
                return False
            thread.join(0.05)
            waited += 0.05
        return True
