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

"""Connection of the deebot plugin to the Ecovacs cloud, built on deebot-client."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterable, Sequence
from contextlib import suppress
from enum import StrEnum
from typing import Protocol

import aiohttp
from deebot_client.api_client import ApiClient
from deebot_client.authentication import Authenticator, create_rest_config
from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.event_bus import EventBus
from deebot_client.events import Event
from deebot_client.exceptions import DeebotError, DeviceVerificationRequiredError, InvalidAuthenticationError
from deebot_client.models import AccountCredentials, DeviceInfo
from deebot_client.mqtt_client import MqttClient, create_mqtt_config
from deebot_client.util import md5

from .credentials import CredentialStore
from .features import FEATURES, SKIP, Feature, clean_rooms_command

# receives the name of a feature and its new value
Publish = Callable[[str, object], None]

# seconds map changes are collected before the SVG is rendered once
MAP_RENDER_DELAY = 3.0

RETRY_MIN_DELAY = 30.0
RETRY_MAX_DELAY = 600.0

# seconds between checks that the MQTT listener of deebot-client is still running
LISTENER_CHECK_INTERVAL = 60.0

_log = logging.getLogger(__name__)


class SessionStatus(StrEnum):
    """Connection state shown in the web interface."""

    CONNECTING = 'connecting'
    CONNECTED = 'connected'
    VERIFICATION_REQUIRED = 'verification_required'
    AUTH_FAILED = 'auth_failed'
    DEVICE_NOT_FOUND = 'device_not_found'
    RETRYING = 'retrying'


class DeviceNotFoundError(DeebotError):
    """The account has no supported device matching the configuration."""


class Listener(Protocol):
    """MQTT side of the connection, as offered by ``deebot_client.mqtt_client.MqttClient``."""

    async def connect(self) -> None:
        """Start the listener unless it is running; it subscribes to all devices subscribed before."""
        ...


async def keep_listening(listener: Listener, interval: float) -> None:
    """
    Restart the MQTT listener whenever it has ended.

    deebot-client reconnects the listener after broker connection errors itself, but ends it for good on any other
    error; without a restart no device events would arrive anymore while commands still work.

    :param listener: MQTT client of the session
    :param interval: seconds between two checks
    :raises Exception: whatever restarting the listener raises; the session then reconnects from scratch
    """
    while True:
        await asyncio.sleep(interval)
        await listener.connect()


def subscribe_features(
    events: EventBus,
    caps: Capabilities,
    publish: Publish,
    features: Iterable[Feature],
    on_rendered: Callable[[Feature], None],
) -> list[Callable[[], None]]:
    """
    Publish the values of all given features the device supports, whenever the device reports them.

    Features without extractor are not read from the event; ``on_rendered`` is called for them instead.

    :param events: event bus of the device
    :param caps: capabilities of the device
    :param publish: receives ``(feature name, value)``
    :param on_rendered: receives features whose value the caller renders itself
    :param features: features to subscribe, those the device does not support are skipped
    :return: functions that cancel the subscriptions
    """
    by_event: dict[type[Event], list[Feature]] = defaultdict(list)
    for feature in features:
        if feature.event is not None and feature.capability(caps) is not None:
            by_event[feature.event].append(feature)

    def handler(group: list[Feature]) -> Callable[[Event], Coroutine[None, None, None]]:
        async def handle(event: Event) -> None:
            for feature in group:
                if feature.extract is None:
                    on_rendered(feature)
                    continue
                try:
                    value = feature.extract(event)
                except Exception:
                    _log.exception("Cannot read '%s' from %r", feature.name, event)
                    continue
                if value is not SKIP:
                    publish(feature.name, value)

        return handle

    return [events.subscribe(event_type, handler(group)) for event_type, group in by_event.items()]


class DeebotSession:
    """
    Keeps one Ecovacs vacuum connected and feeds its values to ``publish``.

    All methods run in the asyncio loop of the plugin. ``run()`` connects, reconnects with growing delays on
    transient errors and returns only when cancelled.

    :param store: persistent device id and login token
    :param account: Ecovacs account (e-mail)
    :param password: Ecovacs account password
    :param country: ISO 3166 alpha-2 code of the account's country
    :param device_name: nickname, device name or id of the vacuum to use, empty for the first one of the account
    :param publish: receives ``(feature name, value)`` for each value change
    :param enable_map: render the map as SVG
    """

    def __init__(
        self,
        store: CredentialStore,
        account: str,
        password: str,
        country: str,
        device_name: str,
        publish: Publish,
        enable_map: bool,
    ) -> None:
        self._store = store
        self._account = account
        self._password_hash = md5(password)
        self._country = country.upper()
        self._device_name = device_name
        self._publish = publish
        self._enable_map = enable_map

        self.status = SessionStatus.CONNECTING
        self.status_text = ''
        self.device_info: dict[str, str] = {}

        self._device: Device | None = None
        self._authenticator: Authenticator | None = None
        self._verified = asyncio.Event()
        self._map_task: asyncio.Task[None] | None = None

    # ------------------------------------------------------------------ lifecycle

    async def run(self) -> None:
        """Connect and stay connected until cancelled; the retry delay starts over after a successful connection."""
        delay = RETRY_MIN_DELAY
        while True:
            try:
                await self._connect()
            except asyncio.CancelledError:
                raise
            except InvalidAuthenticationError as err:
                self._set_status(SessionStatus.AUTH_FAILED, str(err))
                _log.error('Ecovacs login rejected, check account and password: %s', err)
                await self._park()
            except DeviceNotFoundError as err:
                self._set_status(SessionStatus.DEVICE_NOT_FOUND, str(err))
                _log.error('%s', err)
                await self._park()
            except Exception as err:
                if self.status == SessionStatus.CONNECTED:
                    delay = RETRY_MIN_DELAY
                self._set_status(SessionStatus.RETRYING, f'{err!r}, next attempt in {delay:.0f}s')
                _log.warning('Connection to Ecovacs failed, retrying in %.0fs: %r', delay, err, exc_info=True)
                await asyncio.sleep(delay)
                delay = min(delay * 2, RETRY_MAX_DELAY)

    async def _connect(self) -> None:
        self._set_status(SessionStatus.CONNECTING)
        async with aiohttp.ClientSession() as http:
            rest = create_rest_config(http, device_id=self._store.device_id, alpha_2_country=self._country)
            authenticator = Authenticator(
                rest, self._account, self._password_hash, account_credentials=self._store.account_credentials
            )
            authenticator.subscribe_account_credentials(self._save_account_credentials)
            self._authenticator = authenticator
            mqtt = MqttClient(create_mqtt_config(device_id=self._store.device_id, country=self._country), authenticator)
            device: Device | None = None
            unsubscribe: list[Callable[[], None]] = []
            try:
                await self._authenticate(authenticator)
                info = await self._select_device(authenticator)
                device = Device(info, authenticator)
                await device.initialize(mqtt)
                self._device = device
                self.device_info = {
                    'name': info.api.get('nick') or info.api.get('name', ''),
                    'did': info.api['did'],
                    'class': info.api['class'],
                }
                unsubscribe = subscribe_features(
                    device.events,
                    device.capabilities,
                    self._publish,
                    self._wanted_features(),
                    self._schedule_map_render,
                )
                self._set_status(SessionStatus.CONNECTED)
                _log.info("Connected to '%s' (%s)", self.device_info['name'], self.device_info['class'])
                await keep_listening(mqtt, LISTENER_CHECK_INTERVAL)
            finally:
                self._device = None
                self._authenticator = None
                await self._cancel_map_task()
                for cancel in unsubscribe:
                    cancel()
                if device is not None:
                    await device.teardown()
                await mqtt.disconnect()
                await authenticator.teardown()

    async def _authenticate(self, authenticator: Authenticator) -> None:
        """Log in; while Ecovacs demands a device verification, wait until ``verify()`` has completed it."""
        while True:
            try:
                await authenticator.authenticate()
                return
            except DeviceVerificationRequiredError:
                self._set_status(SessionStatus.VERIFICATION_REQUIRED)
                _log.warning(
                    'Ecovacs requires a verification of this installation: request and enter the e-mailed code '
                    'in the web interface of the plugin'
                )
                self._verified.clear()
                await self._verified.wait()

    async def _select_device(self, authenticator: Authenticator) -> DeviceInfo:
        devices = await ApiClient(authenticator).get_devices()
        if not devices.mqtt:
            unsupported = [d.get('class', '?') for d in devices.not_supported + devices.xmpp]
            raise DeviceNotFoundError(f'No supported vacuum in the account (unsupported device classes: {unsupported})')
        if not self._device_name:
            return devices.mqtt[0]
        wanted = self._device_name.lower()
        for info in devices.mqtt:
            if wanted in (info.api.get('nick', '').lower(), info.api.get('name', '').lower(), info.api['did'].lower()):
                return info
        names = [d.api.get('nick') or d.api['did'] for d in devices.mqtt]
        raise DeviceNotFoundError(f"No vacuum '{self._device_name}' in the account, available: {names}")

    async def _park(self) -> None:
        """Stop retrying after an error only a change of the configuration can fix."""
        await asyncio.Event().wait()

    def _set_status(self, status: SessionStatus, text: str = '') -> None:
        self.status = status
        self.status_text = text

    async def _save_account_credentials(self, account: AccountCredentials) -> None:
        self._store.save_account_credentials(account)

    # ------------------------------------------------------------------ verification

    async def request_verification_code(self) -> None:
        """Have Ecovacs e-mail a verification code to the account."""
        await self._pending_authenticator().request_device_verification_code()

    async def verify(self, code: str) -> None:
        """
        Complete the device verification with the e-mailed code.

        :raises ValueError: if the code is empty
        :raises InvalidVerificationCodeError: if the code is wrong or expired
        """
        code = code.strip()
        if not code:
            raise ValueError('Enter the verification code from the e-mail')
        await self._pending_authenticator().verify_device(code)
        self._verified.set()

    def _pending_authenticator(self) -> Authenticator:
        if self.status != SessionStatus.VERIFICATION_REQUIRED or self._authenticator is None:
            raise RuntimeError('No device verification is pending')
        return self._authenticator

    # ------------------------------------------------------------------ control

    async def write(self, feature: Feature, value: object) -> None:
        """
        Send the command behind an item write to the vacuum.

        :raises ValueError: if the value is not valid for the feature or the device lacks the function
        :raises RuntimeError: if the vacuum is not connected
        """
        device = self._connected_device()
        if feature.command is None or feature.capability(device.capabilities) is None:
            raise ValueError(f"'{feature.name}' is not supported by this device")
        command = feature.command(device.capabilities, value)
        if command is not None:
            await device.execute_command(command)

    async def clean_rooms(self, rooms: Sequence[int], count: int = 1) -> None:
        """
        Clean the given rooms.

        :raises ValueError: see ``clean_rooms_command``
        :raises RuntimeError: if the vacuum is not connected
        """
        device = self._connected_device()
        await device.execute_command(clean_rooms_command(device.capabilities, rooms, count))

    def _connected_device(self) -> Device:
        if self._device is None:
            raise RuntimeError('Vacuum is not connected')
        return self._device

    # ------------------------------------------------------------------ map

    def _wanted_features(self) -> list[Feature]:
        return [f for f in FEATURES.values() if self._enable_map or f.name != 'map_svg']

    def _schedule_map_render(self, _: Feature) -> None:
        """Render the map once after the changes of the last ``MAP_RENDER_DELAY`` seconds."""
        if self._map_task is None or self._map_task.done():
            self._map_task = asyncio.create_task(self._render_map())

    async def _render_map(self) -> None:
        await asyncio.sleep(MAP_RENDER_DELAY)
        device = self._device
        if device is None or device.map is None:
            return
        try:
            svg = device.map.get_svg_map()
        except Exception:
            _log.exception('Cannot render the map')
            return
        if svg:
            self._publish('map_svg', svg)

    async def _cancel_map_task(self) -> None:
        if self._map_task is not None and self._map_task.cancel():
            with suppress(asyncio.CancelledError):
                await self._map_task
