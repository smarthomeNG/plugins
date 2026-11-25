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

import json
import os
import stat

import pytest

from deebot_client.models import AccountCredentials

from plugins.deebot.credentials import CredentialStore


def test_device_id_is_generated_once_and_kept(tmp_path):
    path = tmp_path / 'deebot' / 'deebot.json'

    first = CredentialStore(path).device_id
    second = CredentialStore(path).device_id

    assert first == second
    assert len(first) == 32


def test_different_stores_get_different_device_ids(tmp_path):
    assert CredentialStore(tmp_path / 'a.json').device_id != CredentialStore(tmp_path / 'b.json').device_id


def test_account_credentials_round_trip(tmp_path):
    path = tmp_path / 'deebot.json'
    store = CredentialStore(path)
    assert store.account_credentials is None

    store.save_account_credentials(AccountCredentials(access_token='tok', user_id='uid'))

    assert CredentialStore(path).account_credentials == AccountCredentials(access_token='tok', user_id='uid')


def test_saving_account_credentials_keeps_device_id(tmp_path):
    path = tmp_path / 'deebot.json'
    store = CredentialStore(path)
    device_id = store.device_id

    store.save_account_credentials(AccountCredentials(access_token='tok', user_id='uid'))

    assert CredentialStore(path).device_id == device_id


def test_file_is_private(tmp_path):
    path = tmp_path / 'deebot' / 'deebot.json'
    CredentialStore(path).save_account_credentials(AccountCredentials(access_token='tok', user_id='uid'))

    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_unreadable_file_starts_fresh(tmp_path):
    path = tmp_path / 'deebot.json'
    path.write_text('{not json')

    store = CredentialStore(path)

    assert store.account_credentials is None
    assert len(store.device_id) == 32
    assert json.loads(path.read_text())['device_id'] == store.device_id


def test_failed_write_keeps_the_previous_file(tmp_path, monkeypatch):
    path = tmp_path / 'deebot.json'
    store = CredentialStore(path)
    store.save_account_credentials(AccountCredentials(access_token='tok', user_id='uid'))
    before = path.read_text()

    def interrupted(*_args, **_kwargs):
        raise OSError('disk full')

    monkeypatch.setattr(json, 'dump', interrupted)
    with pytest.raises(OSError):
        store.save_account_credentials(AccountCredentials(access_token='new', user_id='uid'))

    assert path.read_text() == before
    assert os.listdir(tmp_path) == ['deebot.json']
