#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2011 KNX-User-Forum e.V.           http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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

import logging
import sys
import json
import requests
import magic
import os
import re
from lib.model.smartplugin import SmartPlugin


class Pushbullet(SmartPlugin):
    _apiurl = "https://api.pushbullet.com/v2/pushes"
    _upload_apiurl = "https://api.pushbullet.com/v2/upload-request"
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.5.2"

    def __init__(self, sh, *args, **kwargs):
        logging.getLogger("requests").setLevel(logging.WARNING)
        self._apikey = self.get_parameter_value('apikey')
        self._deviceid = self.get_parameter_value('deviceid')
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def delete(self, pushid, apikey=None):
        if apikey is None:
            apikey = self._apikey

        try:
            response = requests.delete(self._apiurl + "/" + pushid,
                                       headers={"User-Agent": "SmartHomeNG", "Content-Type": "application/json"},
                                       auth=(apikey, ""))
            if self._is_response_ok(response):
                return response.json()

            self.logger.error(
                "Plugin '{}': Could not delete Pushbullet notification. Error: {}".format(self.get_fullname(),
                                                                                          response.text))
        except Exception as exception:
            self.logger.error(
                "Plugin '{}': Could not delete Pushbullet notification. Error: {}".format(self.get_fullname(),
                                                                                          exception))

        return False

    def note(self, title, body, deviceid=None, apikey=None):
        return self._push(data={"type": "note", "title": title, "body": body}, deviceid=deviceid, apikey=apikey)

    def link(self, title, url, deviceid=None, apikey=None, body=None):
        return self._push(data={"type": "link", "title": title, "url": url, "body": body}, deviceid=deviceid,
                          apikey=apikey)

    def address(self, name, address, deviceid=None, apikey=None):
        return self._push(data={"type": "address", "name": name, "address": address}, deviceid=deviceid, apikey=apikey)

    def list(self, title, items, deviceid=None, apikey=None):
        return self._push(data={"type": "list", "title": title, "items": items}, deviceid=deviceid, apikey=apikey)

    def file(self, filepath, deviceid=None, apikey=None, body=None):
        if not os.path.exists(filepath):
            self.logger.error(
                "Plugin '{}': Trying to push non existing file: {}".format(self.get_fullname(),
                                                                           filepath))
            return False

        return self._upload_and_push_file(filepath, body, deviceid, apikey)

    def _upload_and_push_file(self, filepath, body=None, deviceid=None, apikey=None):
        try:
            headers = {"User-Agent": "SmartHomeNG", "Content-Type": "application/json"}

            if apikey is None:
                apikey = self._apikey

            if sys.version_info < (3, 5):
                upload_request_response = requests.post(self._upload_apiurl, data=json.dumps(
                    {"file_name": os.path.basename(filepath),
                     "file_type": magic.from_file(filepath, mime=True).decode("UTF-8")}), headers=headers,
                                                        auth=(apikey, ""))
            else:
                upload_request_response = requests.post(self._upload_apiurl, data=json.dumps(
                    {"file_name": os.path.basename(filepath), "file_type": magic.from_file(filepath, mime=True)}),
                                                        headers=headers, auth=(apikey, ""))

            if self._is_response_ok(upload_request_response):
                data = upload_request_response.json()
                upload_response = requests.post(data["upload_url"], data=data["data"],
                                                headers={"User-Agent": "SmartHomeNG"},
                                                files={"file": open(filepath, "rb")})

                if self._is_response_ok(upload_response):
                    if body is None:
                        body = ""

                    return self._push(
                        data={"type": "file", "file_name": data["file_name"], "file_type": data["file_type"],
                              "file_url": data["file_url"], "body": body}, deviceid=deviceid, apikey=apikey)
                else:
                    self.logger.error(
                        "Plugin '{}': Error while uploading file: {}".format(self.get_fullname(),
                                                                             upload_response.text))
            else:
                self.logger.error(
                    "Plugin '{}': Error while requesting upload: {}".format(self.get_fullname(),
                                                                            upload_request_response.text))
        except Exception as exception:
            self.logger.error(
                "Plugin '{}': Could not send file to Pushbullet notification. Error: {}".format(self.get_fullname(),
                                                                                                exception))

        return False

    def _push(self, data, deviceid=None, apikey=None):
        if apikey is None:
            apikey = self._apikey

        if deviceid is None:
            deviceid = self._deviceid

        if re.match(r"^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$", deviceid):
            data["email"] = deviceid
        else:
            data["device_iden"] = deviceid

        try:
            response = requests.post(self._apiurl, data=json.dumps(data),
                                     headers={"User-Agent": "SmartHomeNG", "Content-Type": "application/json"},
                                     auth=(apikey, ""))
            if self._is_response_ok(response):
                return response.json()

            self.logger.error(
                "Plugin '{}': Could not send Pushbullet notification. Error: {}".format(self.get_fullname(),
                                                                                        response.text))
        except Exception as exception:
            self.logger.error(
                "Plugin '{}': Could not send Pushbullet notification. Error: {}.".format(
                    self.get_fullname(), exception))
        return False

    def _is_response_ok(self, response):
        if response.status_code == 200 or response.status_code == 204:
            self.logger.debug("Plugin '{}': Pushbullet returns: Notification submitted.".format(self.get_fullname()))

            return True
        elif response.status_code == 400:
            self.logger.warning(
                "Plugin '{}': Pushbullet returns: Bad Request - Often missing a required parameter.".format(
                    self.get_fullname()))
        elif response.status_code == 401:
            self.logger.warning(
                "Plugin '{}': Pushbullet returns: Unauthorized - No valid API key provided.".format(
                    self.get_fullname()))
        elif response.status_code == 402:
            self.logger.warning(
                "Plugin '{}': Pushbullet returns: Request Failed - Parameters were valid but the request failed.".format(
                    self.get_fullname()))
        elif response.status_code == 403:
            self.logger.warning(
                "Plugin '{}': Pushbullet returns: Forbidden - The API key is not valid for that request.".format(
                    self.get_fullname()))
        elif response.status_code == 404:
            self.logger.warning(
                "Plugin '{}': Pushbullet returns: Not Found - The requested item doesn't exist.".format(
                    self.get_fullname()))
        elif response.status_code >= 500:
            self.logger.warning(
                "Plugin '{}': Server errors - something went wrong on PushBullet's side.".format(
                    self.get_fullname()))
        else:
            self.logger.error(
                "Plugin '{}': Pushbullet returns unknown HTTP status code = {}.".format(
                    self.get_fullname(), response.status_code))

        self.logger.debug(
            "Plugin '{}': Response was: {}".format(
                self.get_fullname(), response.text))

        return False
