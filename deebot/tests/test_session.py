#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

"""
Event wiring between a deebot-client event bus and the plugin's feature registry.

The bus is the real deebot-client ``EventBus`` for the N20 Pro Plus capabilities; only the command executor, which
would talk to the Ecovacs cloud, is replaced by a recorder.
"""

import asyncio
from contextlib import suppress

import pytest
from deebot_client.capabilities import Capabilities
from deebot_client.command import Command
from deebot_client.event_bus import EventBus
from deebot_client.events import BatteryEvent, LifeSpan, LifeSpanEvent, MapChangedEvent, StateEvent
from deebot_client.hardware import get_static_device_info
from deebot_client.models import State
from datetime import UTC, datetime

from plugins.deebot.credentials import CredentialStore
from plugins.deebot.features import FEATURES
from plugins.deebot.session import DeebotSession, SessionStatus, keep_listening, subscribe_features


@pytest.fixture(scope='module')
def caps() -> Capabilities:
    info = asyncio.run(get_static_device_info('qhe2o2'))
    assert info is not None
    return info.capabilities


class Harness:
    """Runs a scenario on a fresh event bus and collects what the plugin would publish."""

    def __init__(self, caps: Capabilities, feature_names: list[str]):
        self.caps = caps
        self.feature_names = feature_names
        self.published: list[tuple[str, object]] = []
        self.rendered: list[str] = []
        self.refresh_commands: list[Command] = []

    def run(self, scenario) -> None:
        async def main():
            async def execute(command: Command) -> dict:
                self.refresh_commands.append(command)
                return {}

            bus = EventBus(execute, self.caps)
            unsubscribe = subscribe_features(
                bus,
                self.caps,
                lambda name, value: self.published.append((name, value)),
                [FEATURES[name] for name in self.feature_names],
                lambda feature: self.rendered.append(feature.name),
            )
            await scenario(bus)
            await asyncio.sleep(0)
            for fn in unsubscribe:
                fn()

        asyncio.run(main())


def test_event_values_are_published_per_feature(caps):
    harness = Harness(caps, ['state', 'active', 'battery'])

    async def scenario(bus):
        bus.notify(StateEvent(State.CLEANING))
        bus.notify(BatteryEvent(64))

    harness.run(scenario)

    assert ('state', 'cleaning') in harness.published
    assert ('active', True) in harness.published
    assert ('battery', 64) in harness.published


def test_features_not_asked_for_are_not_published(caps):
    harness = Harness(caps, ['battery'])

    async def scenario(bus):
        bus.notify(StateEvent(State.CLEANING))

    harness.run(scenario)

    assert harness.published == []


def test_lifespan_events_only_reach_matching_feature(caps):
    harness = Harness(caps, ['lifespan_brush', 'lifespan_side_brush'])

    async def scenario(bus):
        bus.notify(LifeSpanEvent(LifeSpan.SIDE_BRUSH, 40.0, 100))

    harness.run(scenario)

    assert harness.published == [('lifespan_side_brush', 40.0)]


def test_unsupported_features_are_not_subscribed(caps):
    harness = Harness(caps, ['lifespan_dust_bag'])

    async def scenario(bus):
        bus.notify(LifeSpanEvent(LifeSpan.DUST_BAG, 10.0, 100))

    harness.run(scenario)

    assert harness.published == []
    assert harness.refresh_commands == []


def test_subscribing_requests_the_current_value_from_the_device(caps):
    harness = Harness(caps, ['battery'])

    async def scenario(bus):
        await asyncio.sleep(0.01)

    harness.run(scenario)

    assert harness.refresh_commands


def test_map_changes_are_reported_for_rendering_not_extracted(caps):
    harness = Harness(caps, ['map_svg'])

    async def scenario(bus):
        bus.notify(MapChangedEvent(datetime.now(UTC)))

    harness.run(scenario)

    assert harness.rendered == ['map_svg']
    assert harness.published == []


class Listener:
    """MQTT side of a connection: ``connect()`` restarts the listener if it has ended."""

    def __init__(self, error: Exception | None = None):
        self.connects = 0
        self.error = error

    async def connect(self) -> None:
        self.connects += 1
        if self.error is not None:
            raise self.error


class TestKeepListening:
    def watch(self, listener: Listener, duration: float) -> None:
        async def main():
            await asyncio.wait_for(keep_listening(listener, 0.01), duration)

        with suppress(TimeoutError):
            asyncio.run(main())

    def test_listener_is_checked_repeatedly(self):
        listener = Listener()

        self.watch(listener, 0.1)

        assert listener.connects >= 3

    def test_listener_that_cannot_be_restarted_ends_the_watch(self):
        listener = Listener(ConnectionError('broker unreachable'))

        with pytest.raises(ConnectionError):
            self.watch(listener, 1)

        assert listener.connects == 1


class TestDisconnectedSession:
    @pytest.fixture
    def session(self, tmp_path):
        return DeebotSession(CredentialStore(tmp_path / 'deebot.json'), 'a', 'b', 'DE', '', lambda *_: None, True)

    def test_write_requires_connection(self, session):
        with pytest.raises(RuntimeError, match='not connected'):
            asyncio.run(session.write(FEATURES['cmd_start'], True))

    def test_clean_rooms_requires_connection(self, session):
        with pytest.raises(RuntimeError, match='not connected'):
            asyncio.run(session.clean_rooms([1], 1))

    def test_verification_requires_pending_request(self, session):
        with pytest.raises(RuntimeError, match='verification'):
            asyncio.run(session.verify('123456'))

    def test_empty_verification_code_is_rejected(self, session):
        session.status = SessionStatus.VERIFICATION_REQUIRED

        with pytest.raises(ValueError, match='code'):
            asyncio.run(session.verify('  '))

    def test_map_feature_is_not_wanted_when_map_disabled(self, tmp_path):
        session = DeebotSession(CredentialStore(tmp_path / 'deebot.json'), 'a', 'b', 'DE', '', lambda *_: None, False)

        assert 'map_svg' not in {f.name for f in session._wanted_features()}
