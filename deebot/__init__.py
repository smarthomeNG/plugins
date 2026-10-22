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

import asyncio
import copy
import os
from collections.abc import Sequence
from contextlib import suppress
from functools import partial

from lib.model.smartplugin import SmartPlugin

from .credentials import CredentialStore
from .features import FEATURES, SKIP, apply_room_settings, parse_room_names, parse_room_preselect
from .mapsvg import parse_map_css, process_map_svg
from .session import DeebotSession
from .webif import WebInterface


class Deebot(SmartPlugin):
    """
    Interface to Ecovacs Deebot vacuums through the Ecovacs cloud.

    Items are connected with the attribute ``deebot: <feature>``, see ``features.FEATURES``. Values arrive as events
    from the device; item writes are sent as commands.
    """

    PLUGIN_VERSION = '0.4.0'  # (must match the version specified in plugin.yaml)

    def __init__(self, sh):
        super().__init__()

        self._account = self.get_parameter_value('account')
        self._password = self.get_parameter_value('password')
        self._country = self.get_parameter_value('country')
        self._device_name = self.get_parameter_value('device')
        self._enable_map = self.get_parameter_value('enable_map')
        self._map_trace = self.get_parameter_value('map_trace')
        try:
            self._room_names = parse_room_names(self.get_parameter_value('room_names'))
            self._room_preselect = parse_room_preselect(self.get_parameter_value('room_preselect'))
            self._map_css = parse_map_css(self.get_parameter_value('map_css'))
        except ValueError as err:
            self.logger.error(f'Invalid configuration: {err}')
            self._init_complete = False
            return

        self._forget_device()
        store_path = os.path.join(sh.get_vardir(), 'deebot', f'{self.get_fullname()}.json')
        try:
            self._store = CredentialStore(store_path)
        except OSError as err:
            self.logger.error(f'Cannot write the credential file {store_path}: {err}')
            self._init_complete = False
            return

        if not self.init_webinterface(WebInterface):
            self._init_complete = False

    # ------------------------------------------------------------------ plugin life cycle

    def _forget_device(self) -> None:
        """Drop the session and everything learned from the device, items keep their values."""
        # last published value per feature name
        self.values: dict[str, object] = {}
        # rooms as reported by the device and the names of the known maps, to apply the room settings again later
        self._device_rooms: list = []
        self._map_names: dict[str, str] = {}
        self.session: DeebotSession | None = None
        # outcome of the last device verification step, shown while a verification is pending
        self.verification_message = ''

    def run(self):
        """Start the asyncio thread that holds the connection to the Ecovacs cloud."""
        self.logger.debug('Run method called')
        self.session = DeebotSession(
            self._store,
            self._account,
            self._password,
            self._country,
            self._device_name,
            self._publish,
            self._enable_map,
        )
        self.start_asyncio(self.plugin_coro())

    def stop(self):
        """Stop the asyncio thread."""
        self.logger.debug('Stop method called')
        self.stop_asyncio()
        self._forget_device()

    async def plugin_coro(self):
        """Run the session until the plugin is stopped."""
        self.alive = True
        task = asyncio.create_task(self._running_session().run(), name='DeebotSession')
        task.add_done_callback(self._log_session_end)
        await self.wait_for_asyncio_termination()
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
        self.alive = False

    def _running_session(self) -> DeebotSession:
        if self.session is None:
            raise RuntimeError('Plugin is not running')
        return self.session

    def _log_session_end(self, task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            self.logger.error(f'Session ended unexpectedly: {task.exception()!r}', exc_info=task.exception())

    # ------------------------------------------------------------------ items

    def parse_item(self, item):
        """Register items that carry the ``deebot`` attribute; items of writable features get ``update_item``."""
        if not self.has_iattr(item.conf, 'deebot'):
            return None
        name = self.get_iattr_value(item.conf, 'deebot')
        feature = FEATURES.get(name)
        if feature is None:
            self.logger.warning(f"{item.property.path}: unknown deebot feature '{name}'")
            return None
        if item.type() != feature.item_type:
            self.logger.warning(f"{item.property.path}: feature '{name}' delivers type '{feature.item_type}'")
        self.add_item(item, mapping=name)
        return self.update_item if feature.writable else None

    def update_item(self, item, caller=None, source=None, dest=None):
        """Send the command behind a changed item to the vacuum."""
        if self._handle_pause_item(item, caller) or caller == self.get_fullname():
            return
        if not self.alive:
            self.logger.warning(f'{item.property.path}: plugin is not running, ignoring update')
            return
        feature = FEATURES[self.get_item_mapping(item)]
        self._submit(feature.name, self._running_session().write(feature, item()))
        if feature.reset_to is not SKIP:
            item(copy.copy(feature.reset_to), self.get_fullname())

    def _publish(self, name: str, value: object) -> None:
        """Hand a value from the device to the items of the feature, adapted to the configuration."""
        if name == 'maps' and isinstance(value, list):
            self._learn_map_names(value)
        elif name == 'rooms' and isinstance(value, list):
            self._device_rooms = value
        value = self._configured(name, value)
        self.values[name] = value
        for item in self.get_items_for_mapping(name):
            item(value, self.get_fullname())

    def _learn_map_names(self, maps: list) -> None:
        """Remember the map names, which the room settings may refer to, and apply them to the rooms already known."""
        names = {str(m['id']): str(m['name']) for m in maps if m.get('name')}
        if names == self._map_names:
            return
        self._map_names = names
        if self._device_rooms:
            self._publish('rooms', self._device_rooms)

    def _configured(self, name: str, value: object) -> object:
        """Apply the room and map settings of the configuration to a device value."""
        if name == 'rooms' and isinstance(value, list):
            return apply_room_settings(value, self._room_names, self._room_preselect, self._map_names)
        if name == 'map_svg' and isinstance(value, str):
            return process_map_svg(value, self._map_css, self._map_trace)
        return value

    # ------------------------------------------------------------------ plugin functions

    def clean_rooms(self, rooms: Sequence[int], count: int = 1) -> bool:
        """
        Clean the given rooms.

        :param rooms: room ids, as published by the ``rooms`` feature
        :param count: number of cleaning passes
        :return: False if the plugin is not running; command errors are logged
        """
        if not self.alive:
            self.logger.warning('clean_rooms: plugin is not running')
            return False
        return self._submit('clean_rooms', self._running_session().clean_rooms(rooms, count))

    def _submit(self, what: str, coro) -> bool:
        """Run the command coroutine ``coro`` for feature or function ``what``; False if the loop is not running."""
        return self.submit_asyncio_coro(coro, on_error=partial(self._command_failed, what)) is not None

    def _command_failed(self, what: str, error: BaseException) -> None:
        """Log a command that was not carried out; the items of feature ``what`` get the last device value back."""
        if isinstance(error, (ValueError, RuntimeError)):
            self.logger.warning(f"Command '{what}' not sent: {error}")
        else:
            self.logger.error(f"Command '{what}' failed: {error!r}", exc_info=error)
        if what in self.values:
            for item in self.get_items_for_mapping(what):
                item(self.values[what], self.get_fullname())

    # ------------------------------------------------------------------ web interface

    def request_verification_code(self) -> None:
        """Ask Ecovacs to e-mail a device verification code; the outcome is shown in ``verification_message``."""
        self._run_verification(lambda session: session.request_verification_code(), 'code requested')

    def verify_device(self, code: str) -> None:
        """Complete the device verification with the e-mailed code; the outcome is shown in ``verification_message``."""
        self._run_verification(lambda session: session.verify(code), 'code accepted')

    def _run_verification(self, step, success_message: str) -> None:
        if self.session is None:
            self.verification_message = 'Plugin is not running'
            return
        try:
            self.run_asyncio_coro(step(self.session), timeout=30)
        except Exception as err:
            self.logger.warning(f'Device verification failed: {err!r}')
            self.verification_message = str(err) or repr(err)
            return
        self.verification_message = success_message
