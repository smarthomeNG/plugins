#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-     Sebastian Helms                  Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
#########################################################################
"""
SmartHomeNG plugin sending push notifications through a Bark server.
"""

import json
import urllib.request
from collections.abc import Callable, Hashable
from http.client import HTTPException

from lib.item.item import Item
from lib.model.smartplugin import SmartPlugin

from .message import BarkMessage, BarkTemplate


class Bark(SmartPlugin):
    """
    Send push notifications to the Bark app through a Bark server.

    Items with a ``bark_text`` or ``bark_values`` attribute send a notification when their value changes,
    logics and eval expressions call :meth:`notify`.
    """

    PLUGIN_VERSION = '1.0.0'
    ALLOW_MULTIINSTANCE = True

    _TIMEOUT = 5

    def __init__(self, sh=None, **kwargs: object) -> None:
        """Read the plugin parameters."""
        super().__init__()

        self._push_url = self.get_parameter_value('server_url').rstrip('/') + '/push'
        self._device_key = self.get_parameter_value('device_key')
        self._pause_item_path = self.get_parameter_value('pause_item')

    def run(self) -> None:
        """Start the plugin."""
        self.alive = True
        if self._pause_item is not None:
            self._pause_item(False, self.get_fullname())

    def stop(self) -> None:
        """Stop the plugin."""
        self.alive = False
        if self._pause_item is not None:
            self._pause_item(True, self.get_fullname())

    def parse_item(self, item: Item) -> Callable[..., None] | None:
        """
        Register an item having a ``bark_text`` or ``bark_values`` attribute.

        :param item: item to check
        :return: :meth:`update_item` for a registered item
        """
        if item.property.path == self._pause_item_path:
            return super().parse_item(item)
        if not (self.has_iattr(item.conf, 'bark_text') or self.has_iattr(item.conf, 'bark_values')):
            return None

        template = BarkTemplate(
            values=self._parse_values(item),
            text=self.get_iattr_value(item.conf, 'bark_text'),
            title=self.get_iattr_value(item.conf, 'bark_title'),
            url=self.get_iattr_value(item.conf, 'bark_url'),
        )
        self.add_item(item, config_data_dict={'template': template}, updating=True)
        return self.update_item

    def _parse_values(self, item: Item) -> dict[Hashable, str]:
        """
        Read the ``bark_values`` attribute, a list of ``value: text`` entries.

        :param item: item carrying the attribute
        :return: text per item value, empty if the attribute is missing or not a list of entries
        """
        entries = self.get_iattr_value(item.conf, 'bark_values') or []
        return {value: str(text) for entry in entries for value, text in entry.items()}

    def update_item(
        self, item: Item, caller: str | None = None, source: str | None = None, dest: str | None = None
    ) -> None:
        """
        Send the notification configured for the new value of *item*.

        SmartHomeNG calls this for a changed value, and for every update of an item with ``enforce_updates``.
        """
        if self._handle_pause_item(item, caller) or not self.alive:
            return

        value = item()
        message = self.get_item_config(item)['template'].message_for(value)
        if message is None:
            self.logger.debug(f'Item {item}: no notification text for value "{value}"')
            return
        self.logger.info(f'Notification for item {item}: "{message.body}"')
        self.notify(message.body, message.title, message.url)

    def notify(self, body: str, title: str | None = None, url: str | None = None) -> bool:
        """
        Send a push notification.

        The call blocks until the server has answered, at most :attr:`_TIMEOUT` seconds per network operation.

        :param body: text of the notification, must not be empty
        :param title: headline above the text
        :param url: URL opened when the notification is tapped
        :return: True, if the server accepted the notification
        """
        if not self.alive:
            self.logger.warning(f'Notification "{body}" not sent: plugin is not running')
            return False
        if not body:
            self.logger.warning(f'Notification with title "{title}" not sent: it has no text')
            return False
        return self._send(BarkMessage(body, title, url))

    def _send(self, message: BarkMessage) -> bool:
        """
        Post *message* to the push endpoint of the server, logging a warning on failure.

        :return: True, if the server answered with HTTP 200
        """
        try:
            request = urllib.request.Request(
                self._push_url,
                data=json.dumps(message.payload(self._device_key)).encode(),
                headers={'Content-Type': 'application/json; charset=utf-8'},
            )
            with urllib.request.urlopen(request, timeout=self._TIMEOUT) as response:
                if response.status == 200:
                    return True
                error = f'HTTP status {response.status}'
        except (OSError, HTTPException, ValueError) as e:
            error = str(e)
        self.logger.warning(f'Notification "{message.body}" not sent to {self._push_url}: {error}')
        return False
