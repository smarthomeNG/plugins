"""The tokens the server accepts and what each client behind a token may do."""

import hmac
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from typing import TypeGuard, TypeVar

from .elevation import DEFAULT_ELEVATE_MINUTES, MAX_ELEVATE_MINUTES, Elevation, ElevationTimer
from .entitlement import LOCAL_TOKEN_ID
from .types import (
    ACCESS_VALUES,
    Access,
    ClientStatus,
    DefaultAccess,
    Entitlement,
    ExposeGroup,
    is_access,
    is_default_access,
    is_expose_group,
)

T = TypeVar('T')

MIN_TOKEN_LENGTH = 16
DEFAULT_CLIENT_MAX_ACCESS: Access = 'ro'
CLIENT_SETTINGS = frozenset(
    {
        'token',
        'default_access',
        'inherit_rw_access',
        'expose',
        'max_access',
        'write_rate_limit',
        'write_paths',
        'elevate_to',
        'elevate_minutes',
        'allowed_networks',
    }
)

Network = IPv4Network | IPv6Network


@dataclass(frozen=True)
class ClientDefinition:
    """A token, the entitlement of the client that presents it and the elevation an administrator may grant it."""

    token: str
    entitlement: Entitlement
    elevation: Elevation | None = None
    networks: tuple[Network, ...] | None = None


def parse_clients(raw: Mapping[str, object], default_rate_limit: int) -> list[ClientDefinition]:
    """
    Build the client definitions from the ``clients`` plugin parameter.

    A client that leaves a setting out gets the most restrictive value: it sees no item without ``mcp_access``,
    exposes no diagnostic group and may not write (``max_access`` ``ro``).

    :param raw: client name -> settings (``token`` and any of ``default_access``, ``inherit_rw_access``,
        ``expose``, ``max_access``, ``write_rate_limit``, ``write_paths``, ``elevate_to``, ``elevate_minutes``,
        ``allowed_networks``)
    :param default_rate_limit: ``write_rate_limit`` of a client that sets none
    :raises ValueError: a client has a missing or weak token, an unknown setting or an invalid value
    """
    definitions: list[ClientDefinition] = []
    for name, settings in raw.items():
        try:
            definitions.append(_parse_client(str(name), settings, default_rate_limit))
        except ValueError as e:
            raise ValueError(f'client {name!r}: {e}') from e
    return definitions


def _parse_client(name: str, settings: object, default_rate_limit: int) -> ClientDefinition:
    """Build one client definition."""
    if name == LOCAL_TOKEN_ID:
        raise ValueError(f'the name {LOCAL_TOKEN_ID!r} is reserved for the token parameter')
    if not isinstance(settings, Mapping):
        raise ValueError('settings must be a mapping')
    unknown = sorted(set(settings) - CLIENT_SETTINGS)
    if unknown:
        raise ValueError(f'unknown settings {unknown}')
    token = settings.get('token')
    if not isinstance(token, str) or len(token) < MIN_TOKEN_LENGTH:
        raise ValueError(f'token must be a text of at least {MIN_TOKEN_LENGTH} characters')
    default_access: DefaultAccess = _choice(settings, 'default_access', is_default_access, 'none')
    max_access: Access = _choice(settings, 'max_access', is_access, DEFAULT_CLIENT_MAX_ACCESS)
    inherit = _as_bool(settings.get('inherit_rw_access', False), 'inherit_rw_access')
    rate_limit = _as_int(settings.get('write_rate_limit', default_rate_limit), 'write_rate_limit')
    return ClientDefinition(
        token,
        Entitlement(
            name,
            default_access,
            inherit,
            _groups(settings.get('expose', ())),
            rate_limit,
            max_access,
            _write_paths(settings.get('write_paths')),
        ),
        _elevation(settings, max_access),
        _networks(settings.get('allowed_networks')),
    )


def _elevation(settings: Mapping[str, object], max_access: Access) -> Elevation | None:
    """Validate the elevation settings; absent ``elevate_to`` means the client cannot be elevated."""
    target = settings.get('elevate_to')
    if target is None:
        if 'elevate_minutes' in settings:
            raise ValueError('elevate_minutes needs elevate_to')
        return None
    if not is_access(target) or ACCESS_VALUES.index(target) <= ACCESS_VALUES.index(max_access):
        raise ValueError(f'elevate_to must be an access level above max_access {max_access!r}, got {target!r}')
    minutes = _as_int(settings.get('elevate_minutes', DEFAULT_ELEVATE_MINUTES), 'elevate_minutes')
    if not 1 <= minutes <= MAX_ELEVATE_MINUTES:
        raise ValueError(f'elevate_minutes must be a number from 1 to {MAX_ELEVATE_MINUTES}')
    return Elevation(target, minutes)


def _networks(value: object) -> tuple[Network, ...] | None:
    """Validate an ``allowed_networks`` list of addresses or CIDR networks; absent means from anywhere."""
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValueError('allowed_networks must be a list')
    networks: list[Network] = []
    for entry in value:
        try:
            if not isinstance(entry, str):
                raise ValueError('not text')
            networks.append(ip_network(entry, strict=False))
        except ValueError as e:
            raise ValueError(f'allowed_networks contains {entry!r}, which is no address or network') from e
    return tuple(networks)


def _as_bool(value: object, key: str) -> bool:
    """Read a flag; shng's config loader delivers nested scalars as text, so ``'True'`` and ``'false'`` count too."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ('true', 'false'):
        return value.strip().lower() == 'true'
    raise ValueError(f'{key} must be true or false')


def _as_int(value: object, key: str) -> int:
    """Read a whole number; shng's config loader delivers nested scalars as text, so ``'5'`` counts too."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            pass
    raise ValueError(f'{key} must be a number')


def _choice(settings: Mapping[str, object], key: str, valid: Callable[[object], TypeGuard[T]], default: T) -> T:
    """Return the setting if ``valid`` accepts it, ``default`` if it is absent."""
    value = settings.get(key, default)
    if not valid(value):
        raise ValueError(f'{key} has an invalid value {value!r}')
    return value


def _write_paths(value: object) -> tuple[str, ...] | None:
    """Validate a ``write_paths`` list; absent means no restriction."""
    if value is None:
        return None
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValueError('write_paths must be a list')
    patterns = tuple(value)
    if not all(isinstance(pattern, str) and pattern for pattern in patterns):
        raise ValueError('write_paths must contain item path patterns')
    return patterns


def _groups(value: object) -> frozenset[ExposeGroup]:
    """Validate an ``expose`` list."""
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise ValueError('expose must be a list')
    groups: set[ExposeGroup] = set()
    for name in value:
        if not is_expose_group(name):
            raise ValueError(f'expose contains unknown group {name!r}')
        groups.add(name)
    return frozenset(groups)


class ClientRegistry:
    """
    Authenticates tokens, serves the entitlement of the client behind each and keeps what the status page shows.

    Elevations and the request statistics live in memory only.
    """

    def __init__(
        self,
        definitions: Iterable[ClientDefinition],
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = datetime.now,
    ):
        """
        :param clock: monotonic seconds, for the elevation timer
        :param wall_clock: current time, for ``last_seen``
        :raises ValueError: two clients share a token or a name
        """
        self._definitions = list(definitions)
        ids = [definition.entitlement.token_id for definition in self._definitions]
        tokens = [definition.token for definition in self._definitions]
        if len(set(ids)) != len(ids):
            raise ValueError('client names must be unique')
        if len(set(tokens)) != len(tokens):
            raise ValueError('every client needs its own token')
        self._timer = ElevationTimer(clock)
        self._wall_clock = wall_clock
        self._seen: dict[str, tuple[int, datetime]] = {}
        self._lock = threading.Lock()

    @classmethod
    def build(
        cls,
        local_token: str,
        local_entitlement: Entitlement,
        clients: Mapping[str, object],
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = datetime.now,
    ) -> 'ClientRegistry':
        """
        Build the registry of the local token plus the configured clients.

        :raises ValueError: see :func:`parse_clients` and the constructor
        """
        return cls(
            [
                ClientDefinition(local_token, local_entitlement),
                *parse_clients(clients, local_entitlement.write_rate_limit),
            ],
            clock,
            wall_clock,
        )

    def authenticate(self, presented: str) -> str | None:
        """Return the client name for the token and count the request, None if no client has it."""
        candidate = presented.encode()
        match: str | None = None
        for definition in self._definitions:
            if hmac.compare_digest(candidate, definition.token.encode()):
                match = definition.entitlement.token_id
        if match is not None:
            with self._lock:
                count, _ = self._seen.get(match, (0, self._wall_clock()))
                self._seen[match] = (count + 1, self._wall_clock())
        return match

    def entitlement_for(self, token_id: str) -> Entitlement | None:
        """Return the entitlement of the client, with the raised ceiling while it is elevated; None if unknown."""
        definition = self._definition(token_id)
        if definition is None:
            return None
        if definition.elevation is not None and self._timer.remaining(token_id) is not None:
            return replace(definition.entitlement, max_access=definition.elevation.max_access)
        return definition.entitlement

    def permits(self, client: str, peer: str | None) -> bool:
        """
        Return True if the client may connect from the peer address.

        A client without ``allowed_networks`` may connect from anywhere; a client with them only from there, and an
        unknown peer address never matches.
        """
        definition = self._definition(client)
        if definition is None:
            return False
        if definition.networks is None:
            return True
        address = _address_of(peer)
        return address is not None and any(address in network for network in definition.networks)

    def elevate(self, client: str) -> None:
        """
        Raise the client's ceiling for the time its settings allow, or restart that time.

        :raises ValueError: the client is unknown or its settings do not allow an elevation
        """
        definition = self._definition(client)
        if definition is None or definition.elevation is None:
            raise ValueError(f'client {client!r} cannot be elevated')
        self._timer.start(client, definition.elevation.minutes)

    def revoke(self, client: str) -> None:
        """End the client's elevation at once; does nothing if it has none."""
        self._timer.stop(client)

    def status(self) -> list[ClientStatus]:
        """Return what the status page shows for every client, in configuration order."""
        rows: list[ClientStatus] = []
        for definition in self._definitions:
            entitlement = definition.entitlement
            effective = self.entitlement_for(entitlement.token_id)
            with self._lock:
                requests, last_seen = self._seen.get(entitlement.token_id, (0, None))
            rows.append(
                {
                    'name': entitlement.token_id,
                    'default_access': entitlement.default_access,
                    'max_access': entitlement.max_access,
                    'effective_max_access': effective.max_access if effective else entitlement.max_access,
                    'inherit_rw_access': entitlement.inherit_rw_access,
                    'expose': sorted(entitlement.expose),
                    'write_rate_limit': entitlement.write_rate_limit,
                    'write_paths': None if entitlement.write_paths is None else list(entitlement.write_paths),
                    'elevate_to': definition.elevation.max_access if definition.elevation else None,
                    'elevate_minutes': definition.elevation.minutes if definition.elevation else None,
                    'allowed_networks': None
                    if definition.networks is None
                    else [str(network) for network in definition.networks],
                    'elevated_for': self._timer.remaining(entitlement.token_id),
                    'requests': requests,
                    'last_seen': last_seen,
                }
            )
        return rows

    def _definition(self, name: str) -> ClientDefinition | None:
        """Return the definition of the named client."""
        for definition in self._definitions:
            if definition.entitlement.token_id == name:
                return definition
        return None


def _address_of(peer: str | None) -> IPv4Address | IPv6Address | None:
    """Parse a peer address, reading an IPv4-mapped IPv6 address as the IPv4 address; None if it is no address."""
    if peer is None:
        return None
    try:
        address = ip_address(peer)
    except ValueError:
        return None
    if isinstance(address, IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address
