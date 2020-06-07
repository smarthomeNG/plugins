#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020        René Frieß               rene.friess(a)gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
from lib.item import Items
from requests.auth import HTTPBasicAuth
import requests


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Robonect(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    PLUGIN_VERSION = '1.0.0'  # (must match the version specified in plugin.yaml)

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

        self._ip = self.get_parameter_value('ip')
        self._user = self.get_parameter_value('user')
        self._password = self.get_parameter_value('password')
        self._base_url = 'http://%s/json?cmd=' % self.get_ip()
        self._cycle = 60
        self._items = {}
        self._battery_items = {}
        self._session = requests.Session()
        self.init_webinterface()
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # overwrite base url in case of a restart
        self._base_url = 'http://%s/json?cmd=' % self.get_ip()
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

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
        if self.has_iattr(item.conf, 'robonect_data_type'):
            self.logger.debug("parse item: {}".format(item))
            if not self.get_iattr_value(item.conf, 'robonect_data_type') in self._battery_items and \
                    self.has_iattr(item.conf, 'robonect_battery_index'):
                self._battery_items[self.get_iattr_value(item.conf, 'robonect_data_type')] = []
            if self.get_iattr_value(item.conf, 'robonect_data_type') in self._battery_items:
                self._battery_items[self.get_iattr_value(item.conf, 'robonect_data_type')].append(item)
            else:
                self._items[self.get_iattr_value(item.conf, 'robonect_data_type')] = item
        # todo
        # if interesting item for sending values:
        #   return self.update_item
        return

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
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))
            pass

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        self.get_mower_information()
        self.get_status()
        self.get_battery_data()
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
        return

    def get_battery_data(self):
        try:
            response = self._session.get(self._base_url + 'battery', auth=HTTPBasicAuth(self._user, self._password))
        except Exception as e:
            self.logger.error(
                "Plugin '{}': Exception when sending GET request for get_status: {}".format(
                    self.get_fullname(), str(e)))
            return

        json_obj = response.json()

        if 'battery_id' in self._battery_items:
            for item in self._battery_items['battery_id']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['id'])
        if 'battery_charge' in self._battery_items:
            for item in self._battery_items['battery_charge']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['charge'])
        if 'battery_voltage' in self._battery_items:
            for item in self._battery_items['battery_voltage']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['voltage'])
        if 'battery_current' in self._battery_items:
            for item in self._battery_items['battery_current']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['current'])
        if 'battery_temperature' in self._battery_items:
            for item in self._battery_items['battery_temperature']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['temperature'])
        if 'battery_capacity_full' in self._battery_items:
            for item in self._battery_items['battery_capacity_full']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['capacity'][
                         'full'])
        if 'battery_capacity_remaining' in self._battery_items:
            for item in self._battery_items['battery_capacity_remaining']:
                item(json_obj['batteries'][int(self.get_iattr_value(item.conf, 'robonect_battery_index'))]['capacity'][
                         'remaining'])
        return

    def get_mower_information(self):
        try:
            response = self._session.get(self._base_url + 'version', auth=HTTPBasicAuth(self._user, self._password))
        except Exception as e:
            self.logger.error(
                "Plugin '{}': Exception when sending GET request for get_status: {}".format(
                    self.get_fullname(), str(e)))
            return

        json_obj = response.json()

        if 'hardware_serial' in self._items:
            self._items['hardware_serial'](str(json_obj['mower']['hardware']['serial']))

        if 'production_date' in self._items:
            self._items['production_date'](json_obj['mower']['hardware']['production'])

        if 'msw_title' in self._items:
            self._items['msw_title'](json_obj['mower']['msw']['title'])
        if 'msw_version' in self._items:
            self._items['msw_version'](json_obj['mower']['msw']['version'])
        if 'msw_compiled' in self._items:
            self._items['msw_compiled'](json_obj['mower']['msw']['compiled'])

        if 'serial' in self._items:
            self._items['serial'](json_obj['serial'])

        if 'wlan_sdk-version' in self._items:
            self._items['wlan_sdk-version'](json_obj['wlan']['sdk-version'])
        if 'wlan_at-version' in self._items:
            self._items['wlan_at-version'](json_obj['wlan']['at-version'])

        if 'robonect_version' in self._items:
            self._items['robonect_version'](json_obj['application']['version'])
        if 'robonect_version_comment' in self._items:
            self._items['robonect_version_comment'](json_obj['application']['comment'])
        if 'robonect_version_compiled' in self._items:
            self._items['robonect_version_compiled'](json_obj['application']['compiled'])
        return

    def get_status(self):
        try:
            response = self._session.get(self._base_url + 'status', auth=HTTPBasicAuth(self._user, self._password))
        except Exception as e:
            self.logger.error(
                "Plugin '{}': Exception when sending GET request for get_status: {}".format(
                    self.get_fullname(), str(e)))
            return

        json_obj = response.json()

        if 'robonect_name' in self._items:
            self._items['robonect_name'](json_obj['name'])
        if 'robonect_id' in self._items:
            self._items['robonect_id'](json_obj['id'])
        if 'status_code' in self._items:
            self._items['status_code'](json_obj['status']['status'])
        if 'status_distance' in self._items:
            self._items['status_distance'](json_obj['status']['distance'])
        if 'status_stopped' in self._items:
            self._items['status_stopped'](json_obj['status']['stopped'])
        if 'status_duration' in self._items:
            self._items['status_duration'](json_obj['status']['duration'])
        if 'status_mode' in self._items:
            self._items['status_mode'](json_obj['status']['mode'])
        if 'status_battery' in self._items:
            self._items['status_battery'](json_obj['status']['battery'])
        if 'status_hours' in self._items:
            self._items['status_hours'](json_obj['status']['hours'])
        if 'wlan_signal' in self._items:
            self._items['wlan_signal'](json_obj['wlan']['signal'])
        if 'health_temperature' in self._items:
            self._items['health_temperature'](json_obj['health']['temperature'])
        if 'health_humidity' in self._items:
            self._items['health_humidity'](json_obj['health']['humidity'])
        if 'date' in self._items:
            self._items['date'](json_obj['clock']['date'])
        if 'time' in self._items:
            self._items['time'](json_obj['clock']['time'])
        if 'unix' in self._items:
            self._items['unix'](json_obj['clock']['unix'])
        return

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

    def get_ip(self):
        return self._ip

    def get_user(self):
        return self._user

    def get_password(self):
        return self._password

    def get_items(self):
        return self._items

    def get_battery_items(self):
        return self._battery_items


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}
