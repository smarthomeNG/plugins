"""DAB service list: walk the device's services in order and tune to one of them by stepping."""

import threading
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .mediasearch.compat import StrEnum

if TYPE_CHECKING:
    from . import YamahaYXC


class WalkState(StrEnum):
    """outcome or phase of a walk/tune job"""

    IDLE = 'idle'
    WALKING = 'walking'
    TUNING = 'tuning'
    DONE = 'done'
    ABORTED = 'aborted'
    ERROR = 'error'


@dataclass(frozen=True)
class DabService:
    """one service of the device's service list"""

    id: int
    name: str


@dataclass(frozen=True)
class DabPlayInfo:
    """the tuner's current DAB service and the number of services found by the last initial scan"""

    service_id: int
    label: str
    total: int


class DabLink(Protocol):
    """a DAB tuner as the walk sees it; every method may fail by returning None/False"""

    def play_info(self) -> DabPlayInfo | None:
        """current service, None if the device did not answer"""

    def step(self, direction: str) -> bool:
        """tune to the 'next' or 'previous' service in the device's list"""

    def mute(self) -> bool | None:
        """current mute state, None if unknown"""

    def set_mute(self, on: bool) -> bool:
        """mute or unmute, False if the device refused"""


@dataclass(frozen=True)
class WalkResult:
    """final state of a walk, the services it collected and the station count the device reported (both unset unless DONE)"""

    state: WalkState
    services: tuple[DabService, ...] = ()
    total: int = 0


@dataclass(frozen=True)
class Settle:
    """how long to wait for the tuner to report a new service after a step"""

    poll_interval: float = 0.5
    timeout: float = 8.0
    sleep: Callable[[float], None] = time.sleep


def _wait_for_change(link: DabLink, previous_id: int, settle: Settle) -> DabPlayInfo | None:
    """poll until the current service differs from previous_id; None if it does not within settle.timeout"""
    deadline = time.monotonic() + settle.timeout
    while True:
        info = link.play_info()
        if info is not None and info.service_id != previous_id:
            return info
        if time.monotonic() >= deadline:
            return None
        settle.sleep(settle.poll_interval)


@contextmanager
def _muted(link: DabLink) -> Iterator[None]:
    """mute the device for the block if it is known to be unmuted, restoring that afterwards; a refused mute is ignored"""
    mute_it = link.mute() is False and link.set_mute(True)
    try:
        yield
    finally:
        if mute_it:
            link.set_mute(False)


def walk(
    link: DabLink,
    cancel: threading.Event,
    progress: Callable[[int], None] = lambda percent: None,
    settle: Settle = Settle(),
) -> WalkResult:
    """step once around the whole service list, collecting each service; ends back on the starting service"""
    first = link.play_info()
    if first is None or first.total < 1:
        return WalkResult(WalkState.ERROR)
    services = [DabService(first.service_id, first.label.strip())]
    current = first
    progress(min(100, 100 // first.total))
    with _muted(link):
        while not cancel.is_set():
            link.step('next')
            current = _wait_for_change(link, current.service_id, settle)
            if current is None:
                return WalkResult(WalkState.ERROR)
            if current.service_id == first.service_id:
                return WalkResult(WalkState.DONE, tuple(services), first.total)
            services.append(DabService(current.service_id, current.label.strip()))
            progress(min(100, len(services) * 100 // first.total))
    return WalkResult(WalkState.ABORTED)


def tune(
    link: DabLink,
    services: Sequence[DabService],
    index: int,
    cancel: threading.Event,
    progress: Callable[[int], None] = lambda percent: None,
    settle: Settle = Settle(),
) -> WalkState:
    """step the tuner from its current service to services[index], taking the shorter way around the list"""
    current = link.play_info()
    ids = [service.id for service in services]
    if current is None or current.service_id not in ids:
        return WalkState.ERROR
    ahead = (index - ids.index(current.service_id)) % len(services)
    behind = len(services) - ahead
    direction, count = ('next', ahead) if ahead <= behind else ('previous', behind)
    with _muted(link):
        for done in range(count):
            if cancel.is_set():
                return WalkState.ABORTED
            link.step(direction)
            current = _wait_for_change(link, current.service_id, settle)
            if current is None:
                return WalkState.ERROR
            progress((done + 1) * 100 // count)
    return WalkState.DONE if current.service_id == services[index].id else WalkState.ERROR


class StationCache:
    """
    Per-device memory of DAB service names and of the last walked service list.

    Service ids are only valid until the next initial scan, which changes the
    device's station count; so everything is dropped once the observed count
    differs from the one the cache was filled under.
    """

    def __init__(self) -> None:
        self._names: dict[int, str] = {}
        self._services: tuple[DabService, ...] = ()
        self._total: int | None = None

    @property
    def services(self) -> tuple[DabService, ...]:
        """the walked service list in device order, empty if none is valid"""
        return self._services

    def name_of(self, service_id: int) -> str:
        """the remembered name of a service, '' if it was never seen"""
        return self._names.get(service_id, '')

    def invalidate(self) -> None:
        """forget the list and all names, e.g. when an initial scan starts"""
        self._names.clear()
        self._services = ()
        self._total = None

    def observe(self, info: DabPlayInfo) -> None:
        """learn the current service's name from a tuner status, dropping everything first if the station count changed"""
        if self._total is not None and info.total != self._total:
            self.invalidate()
        self._total = info.total
        label = info.label.strip()
        if label:
            self._names[info.service_id] = label

    def publish(self, services: tuple[DabService, ...], total: int) -> None:
        """store a completed walk made while the device reported total stations"""
        self._services = services
        self._total = total
        for service in services:
            self._names[service.id] = service.name


class YxcDabLink:
    """DabLink over a YamahaYXC plugin's HTTP access to one device (tuner calls plus the main zone's mute)"""

    ZONE = 'main'

    def __init__(self, plugin: 'YamahaYXC', host: str):
        self.plugin = plugin
        self.host = host

    def _send(self, payload: str) -> dict | None:
        """submit payload; the response if the device answered with response_code 0, else None"""
        response = self.plugin._submit_payload(self.host, payload)
        return response if isinstance(response, dict) and not response.get('response_code') else None

    def play_info(self) -> DabPlayInfo | None:
        state = self._send(self.plugin._build_cmd_get_tuner_state())
        dab = state.get('dab') if state and state.get('band') == 'dab' else None
        if not dab or 'id' not in dab:
            return None
        return DabPlayInfo(dab['id'], dab.get('service_label', ''), dab.get('total_station_num', 0))

    def step(self, direction: str) -> bool:
        return self._send(self.plugin._build_cmd_tuner_dab_service(direction)) is not None

    def mute(self) -> bool | None:
        state = self._send(self.plugin._build_cmd_get_state(self.ZONE))
        return state.get('mute') if state else None

    def set_mute(self, on: bool) -> bool:
        return self._send(self.plugin._build_cmd_mute(on, self.ZONE)) is not None
