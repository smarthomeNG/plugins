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

"""Persistent client identity and login token of one plugin instance."""

import json
import os
import secrets
import tempfile
from contextlib import suppress
from pathlib import Path

from deebot_client.models import AccountCredentials


class CredentialStore:
    """
    JSON file holding what has to survive a restart to avoid a new device verification at Ecovacs.

    The client ``device_id`` identifies this installation towards the Ecovacs cloud; the account token lets
    the library log in without the password. The file is readable by the owner only.

    :param path: location of the JSON file; its directory is created on first write
    :raises OSError: if a new device id cannot be written
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        data = self._read()
        self._device_id: str = data.get('device_id') or secrets.token_hex(16)
        self._account: AccountCredentials | None = None
        if data.get('access_token') and data.get('user_id'):
            self._account = AccountCredentials(access_token=data['access_token'], user_id=data['user_id'])
        if data.get('device_id') != self._device_id:
            self._write()

    @property
    def device_id(self) -> str:
        """Client identifier sent to the Ecovacs cloud."""
        return self._device_id

    @property
    def account_credentials(self) -> AccountCredentials | None:
        """Token from the last successful login, ``None`` before the first one."""
        return self._account

    def save_account_credentials(self, account: AccountCredentials) -> None:
        """Persist the token of a successful login."""
        self._account = account
        self._write()

    def _read(self) -> dict[str, str]:
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self) -> None:
        """
        Persist device id and token, readable by the owner only.

        :raises OSError: if the file cannot be written
        """
        data = {'device_id': self._device_id}
        if self._account is not None:
            data.update(access_token=self._account.access_token, user_id=self._account.user_id)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # written next to the target and renamed, so the file is always either the old or the new version
        fd, tmp = tempfile.mkstemp(dir=self._path.parent, prefix=f'.{self._path.name}.')
        try:
            with os.fdopen(fd, 'w') as file:
                json.dump(data, file)
            os.replace(tmp, self._path)
        except BaseException:
            with suppress(OSError):
                os.unlink(tmp)
            raise
