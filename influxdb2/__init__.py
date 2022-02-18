#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
#  upwards.
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

import requests
import json

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class InfluxDB2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.1.0'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.host = self.get_parameter_value('host')
        self.http_port = self.get_parameter_value('http_port')
        self.api_token = self.get_parameter_value('api_token')
        self.org = self.get_parameter_value('org')
        self.bucket = self.get_parameter_value('bucket')
        self.recognize_database = self.get_parameter_value('recognize_database')'

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.recognize_database and self.has_iattr(item.conf, 'database'):
            #self.logger.debug(f"parse item: {item}")

            if item.type() not in ['num', 'bool']:
                #self.logger.error(f"Item {item.id()} has type {item.type()}, only 'num' and 'bool' are supported by influxdb2")
                return

        if self.has_iattr(item.conf, 'influxdb2'):
            #self.logger.debug(f"parse item: {item}")

            if item.type() not in ['num', 'bool']:
                self.logger.error(f"Item {item.id()} has type {item.type()}, only 'num' and 'bool' are supported by influxdb2")
                return

        # todo
        # if interesting item for sending values:
        #   self._itemlist.append(item)
        #   return self.update_item

            return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            #self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'database'):
                #self.logger.debug(f"update_item was called with item {item.property.path} (value {item()}) from caller {caller}, source {source} and dest {dest}")

                tags = {
                    'caller': caller.replace(' ', '\ '),
                    'source': source,
                    'dest': dest
                }
                tags['item_path'] = item.property.path
                if item.property.path != item.property.name:
                    tags['item_name'] = item.property.name.replace(' ', '\ ')
                    tags['item_name'] = tags['item_name'].replace('ä', 'ae')
                    tags['item_name'] = tags['item_name'].replace('ö', 'oe')
                    tags['item_name'] = tags['item_name'].replace('ü', 'ue')
                    tags['item_name'] = tags['item_name'].replace('ß', 'ss')
                    tags['item_name'] = tags['item_name'].replace('Ä', 'Ae')
                    tags['item_name'] = tags['item_name'].replace('Ö', 'Oe')
                    tags['item_name'] = tags['item_name'].replace('Ü', 'Ue')

                fields = {}
                fields['value'] = float(item())

                #line = self.create_line(name, tags, fields)
                line = self.create_line(item.id(), tags, fields)
                self.sendhttp(line)

            pass

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # # get the value from the device
        # device_value = ...
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item by calling item(value, caller, source=None, dest=None)
        #     # - value and caller must be specified, source and dest are optional
        #     #
        #     # The simple case:
        #     item(device_value, self.get_shortname())
        #     # if the plugin is a gateway plugin which may receive updates from several external sources,
        #     # the source should be included when updating the the value:
        #     item(device_value, self.get_shortname(), source=device_source_id)
        pass


# =======================================================================================================

    def create_line(self, name, tags, fields):
        # https://docs.influxdata.com/influxdb/v1.0/guides/writing_data/

        # build name & tags
        kvs = [name]
        for tag_key in sorted(tags.keys()):
            kvs.append("{k}={v}".format(k=tag_key, v=tags[tag_key]))
        lineproto_name_tags = ','.join(kvs)

        # replace ":ga=" with ",ga=" to avoid "invalid tag format" error
        lineproto_name_tags = lineproto_name_tags.replace(":ga=", ",ga=")

        # build fields (which include the actual value)
        kvs = []
        for field_key in sorted(fields.keys()):
            kvs.append("{k}={v}".format(k=field_key, v=fields[field_key]))
        lineproto_fields = ','.join(kvs)

        return lineproto_name_tags + ' ' + lineproto_fields


    def sendhttp(self, data):
        try:
            #url_string = f"http://{self.host}:{self.http_port}/api/v2/write?db={self.bucket}"
            url_string = f"http://{self.host}:{self.http_port}/api/v2/write?bucket={self.bucket}&org={self.org}"
            r = requests.post(url_string, data=data, headers={'Authorization': 'Token '+self.api_token})
            if(r.status_code != 204):
                self.logger.error(f"Request returns http {r.status_code} [{r.text}]")
        except Exception as e:
            self.logger.error(f"Failed sending HTTP datagram [{data}] to {url_string} with error: {e}")
        else:
            #self.logger.debug(f"Sent HTTP datagram [{data}] to {url_string}")
            pass


    def gethttp(self, endpoint, data=None, auth=False):
        #api_token = 'd81TQsiK0ueTs1ql53hAywwdh_coW-KOhkvqnYiEYeJ3_jBEa-QrRn3Kb7ZzyLYJflfXzzA_iVUCWM2-1K1yQg=='
        try:
            url_string = f"http://{'127.0.0.1'}:{'8086'}"
            # r = requests.get(url_string, data=data, headers={'Authorization': 'Token '+self.api_token})
            if auth:
                r = requests.get(url_string + endpoint, headers={'Authorization': 'Token ' + self.api_token})
            else:
                r = requests.get(url_string + endpoint)
            self.logger.debug(f"Sent HTTP GET request [{url_string + endpoint}]")
            if not (r.status_code in [200, 204]):
                self.logger.error(f"Request {url_string + endpoint} returns http {r.status_code} [{r.text}]")
                return json.loads(r.text)
            else:
                self.logger.debug(f"Returns http {r}]")
        except Exception as e:
            self.logger.error(f"Failed sending HTTP datagram [{data}] to {'127.0.0.1:8086'} with error: {e}")
        else:
            if r.text:
                self.logger.debug(f"Received datagram text [{r.text}]")
            try:
                self.logger.debug(f"Received datagram json: {json.loads(r.text)}")
                return json.loads(r.text)
            except Exception as e:
                pass
            self.logger.debug(f"Received datagram [{r}]")
        return


    def influx_getversion(self):
        healthdict = self.gethttp('/health', auth=False)
        return healthdict.get('version','-')
