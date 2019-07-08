#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2012-2013 KNX-User-Forum e.V.       http://knx-user-forum.de/
# Copyright 2019 Bernd Meiners                      Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from lib.module import Modules
from lib.model.smartplugin import *

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory
import urllib.parse
import http.client
from datetime import datetime, timedelta


class Volkszaehler(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.6.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.info('Init Volkszaehler Plugin')

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._host = self.get_parameter_value('host')
        self._url = self.get_parameter_value('url')

        # none of the parameters may be left out
        if not self._host or not self._url:
            self._init_complete = False

        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below.
        """

        if self.has_iattr(item.conf, 'vz_uuid'):
            self.logger.debug("parse item: {}".format(item))
            return self.update_item
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        The plugin now writes the items' value to the Volkszaehler Server.
        See documentation at https://wiki.volkszaehler.org/development/api/reference#daten-kontext

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
    
        if caller != self.get_shortname():
            # code to execute, only if the item has not been changed by this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if self.has_iattr(item.conf, 'vz_uuid'):
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))

                vz_uuid = self.get_iattr_value(item.conf, 'vz_uuid')
                value = item()

                # check if the value is float (i.e. temperature, humidity...)
                # if not, then it is 1 (i.e. S0 counter for power or other energy meters)
                if isinstance(value, float):
                    vz_value = value
                else:
                    vz_value = '1'

                url = self._url.format(vz_uuid)

                self.logger.info("Try to sent '{0}' to host at '{1}' using UUID '{2}'".format(vz_value, self._host, vz_uuid))

                data = {}
                headers = {'User-Agent': "SmartHomeNG", 'Content-Type': "application/x-www-form-urlencoded"}
                data['operation'] = 'add' 
                data['value'] = vz_value 

                try:
                    conn = http.client.HTTPConnection(self._host, timeout=4)
                    conn.request("POST", url, urllib.parse.urlencode(data), headers)
                    resp = conn.getresponse()
                    if resp.status != 200:
                        raise Exception("{} {}".format(resp.status, resp.reason))
                except Exception as e:
                    self.logger.warning("Using url '{0}' at '{1}' resulted in Error: {2}".format(url, self._host, e))
                finally:
                    conn.close()
