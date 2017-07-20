#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 Pierre Scheibke                       pierre(a)scheibke.com
#########################################################################
#
#  This file is part of SmartHomeNG.
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

import logging
import requests
from lib.model.smartplugin import SmartPlugin


class Join(SmartPlugin):
    URL_PREFIX = 'https://joinjoaomgcd.appspot.com/_ah/api/'
    SEND_URL = URL_PREFIX+'messaging/v1/sendPush?apikey='
    LIST_URL = URL_PREFIX+'registration/v1/listDevices?apikey='
    PLUGIN_VERSION = "1.4.1.0"
    ALLOW_MULTIINSTANCE = True

    def __init__(self, smarthome, api_key=None, device_id=None):
        logging.getLogger("requests").setLevel(logging.WARNING)
        self.logger = logging.getLogger(__name__)
        self._api_key = api_key
        self._device_id = device_id
        self._sh = smarthome

    def run(self):
        pass

    def stop(self):
        pass

    def send(self, title=None, text=None, icon=None, find=None, smallicon=None, device_id=None, device_ids=None,
             device_names=None, url=None, image=None, sound=None, group=None, clipboard=None, file=None,
             callnumber=None, smsnumber=None, smstext=None, mmsfile=None, wallpaper=None, lockWallpaper=None,
             interruptionFilter=None, mediaVolume=None, ringVolume=None, alarmVolume=None):
        req_url = self.SEND_URL + self._api_key
        if title:
            req_url += "&title=" + title
        if text:
            req_url += "&text=" + text
        if icon:
            req_url += "&icon=" + icon
        if find:
            req_url += "&find=" + find
        if smallicon:
            req_url += "&smallicon=" + smallicon
        if device_ids:
            req_url += "&deviceIds=" + device_ids
        if device_names:
            req_url += "&deviceNames=" + device_names
        if url:
            req_url += "&url=" + url
        if image:
            req_url += "&image=" + image
        if sound:
            req_url += "&sound=" + sound
        if group:
            req_url += "&group=" + group
        if clipboard:
            req_url += "&clipboard=" + clipboard
        if file:
            req_url += "&file=" + file
        if callnumber:
            req_url += "&callnumber=" + callnumber
        if smsnumber:
            req_url += "&smsnumber=" + smsnumber
        if smstext:
            req_url += "&smstext=" + smstext
        if mmsfile:
            req_url += "&mmsfile=" + mmsfile
        if wallpaper:
            req_url += "&wallpaper=" + wallpaper
        if lockWallpaper:
            req_url += "&lockWallpaper=" + lockWallpaper
        if interruptionFilter:
            req_url += "&interruptionFilter=" + interruptionFilter
        if mediaVolume:
            req_url += "&mediaVolume=" + mediaVolume
        if ringVolume:
            req_url += "&ringVolume=" + ringVolume
        if alarmVolume:
            req_url += "&alarmVolume=" + alarmVolume
        if device_id:
            req_url += "&deviceId=" + device_id
        else:
            req_url += "&deviceId=" + self._device_id
        self.logger.debug(req_url)
        try:
            requests.get(req_url)
        except Exception as e:
            self.logger.error(
                "Exception when sending GET request towards https://joinjoaomgcd.appspot.com: %s" % str(e))
            return
        return
