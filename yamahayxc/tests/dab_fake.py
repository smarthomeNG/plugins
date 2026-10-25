"""A simulated DAB tuner for exercising dabstations without HTTP."""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field

from plugins.yamahayxc.dabstations import DabPlayInfo


@dataclass
class FakeDabLink:
    """Ring of (id, name) services with a current position; step() moves it like the device's setDabService."""

    services: list[tuple[int, str]]
    position: int = 0
    muted: bool = False
    mute_fails: bool = False
    mute_refused: bool = False
    down: bool = False
    stuck: bool = False
    steps: list[str] = field(default_factory=list)
    mute_calls: list[bool] = field(default_factory=list)
    on_step: Callable[['FakeDabLink'], None] | None = None

    def play_info(self) -> DabPlayInfo | None:
        if self.down:
            return None
        if not self.services:
            return DabPlayInfo(0, '', 0)
        service_id, name = self.services[self.position]
        return DabPlayInfo(service_id, name.ljust(16), len(self.services))

    def step(self, direction: str) -> bool:
        self.steps.append(direction)
        if self.stuck:
            return True
        self.position = (self.position + (1 if direction == 'next' else -1)) % len(self.services)
        if self.on_step:
            self.on_step(self)
        return True

    def mute(self) -> bool | None:
        return None if self.mute_fails else self.muted

    def set_mute(self, on: bool) -> bool:
        self.mute_calls.append(on)
        if self.mute_fails or self.mute_refused:
            return False
        self.muted = on
        return True


class FakeDabTuner:
    """The HTTP side of a DAB device: tuner play info, setDabService, main-zone mute; plug into FakeDevice.handlers."""

    def __init__(self, services: list[tuple[int, str]], position: int = 0, muted: bool = False):
        self.services = services
        self.position = position
        self.muted = muted
        self.mute_history: list[bool] = []
        self.gate: threading.Event | None = None  # while unset, setDabService blocks
        self.band = 'dab'
        self.preset_numbers: list[int] = []

    def handle(self, path: str) -> dict | None:
        if path.endswith('tuner/getPlayInfo'):
            service_id, name = self.services[self.position]
            return {
                'band': self.band,
                'dab': {
                    'id': service_id,
                    'service_label': name.ljust(16),
                    'status': 'ready',
                    'total_station_num': len(self.services),
                },
            }
        if 'tuner/setDabService' in path:
            if self.gate is not None:
                self.gate.wait(5)
            self.position = (self.position + (1 if path.endswith('dir=next') else -1)) % len(self.services)
            return {}
        if path.endswith('tuner/getPresetInfo?band=dab'):
            return {
                'preset_info': [{'band': 'dab', 'number': n, 'hd_program': 0, 'text': ''} for n in self.preset_numbers]
            }
        if path.endswith('main/getStatus'):
            return {'power': 'on', 'mute': self.muted}
        if 'main/setMute' in path:
            self.muted = path.endswith('enable=true')
            self.mute_history.append(self.muted)
            return {}
        return None
