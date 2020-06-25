#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017-2018  Martin Sinn                         m.sinn@gmx.de
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

import logging
import json

from lib.module import Modules
#from lib.model.smartplugin import *
from lib.model.mqttplugin import *
from lib.item import Items

from lib.utils import Utils


class Mqtt2(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '2.0.1'


    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
        #     self.param1 = self.get_parameter_value('param1')
            pass
        except KeyError as e:
            self.logger.critical("Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        # Initialization code goes here

        # needed because self.set_attr_value() can only set but not add attributes
        self.at_instance_name = self.get_instance_name()
        if self.at_instance_name != '':
            self.at_instance_name = '@'+self.at_instance_name

        self.inittopics = {}

        # if plugin should start even without web interface
        self.init_webinterface()

        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

        # start subscription to all topics
        self.start_subscriptions()

        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

        # stop subscription to all topics
        self.stop_subscriptions()

        return


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
        # first checking for mqtt-topic attributes 'mqtt_topic', 'mqtt_topic_in' and 'mqtt_topic_out'
        if self.has_iattr(item.conf, 'mqtt_topic'):
            item.conf['mqtt_topic_in' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic')
            item.conf['mqtt_topic_out' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic')

        if self.has_iattr(item.conf, 'mqtt_topic_init'):
            item.conf['mqtt_topic_out' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic_init')

        # check other mqtt attributes, if a topic attribute has been specified
        if self.has_iattr(item.conf, 'mqtt_topic_in') or self.has_iattr(item.conf, 'mqtt_topic_out'):
            self.logger.debug("parsing item: {0}".format(item.id()))

            # check if mqtt module has been initialized successfully
            if not self.mod_mqtt:
                self.logger.warning("MQTT module is not initialized, not parsing item '{}'".format(item.path()))
                return

            # checking attribute 'mqtt_qos'
            if self.has_iattr(item.conf, 'mqtt_qos'):
                self.logger.debug(self.get_loginstance() + "Setting QoS '{}' for item '{}'".format(
                    str(self.get_iattr_value(item.conf, 'mqtt_qos')), str(item)))
                qos = -1
                if Utils.is_int(self.get_iattr_value(item.conf, 'mqtt_qos')):
                    qos = int(self.get_iattr_value(item.conf, 'mqtt_qos'))
                if not (qos in [0, 1, 2]):
                    self.logger.warning(
                        self.get_loginstance() + "Item '{}' invalid value specified for mqtt_qos, using plugin's default".format(
                            item.id()))
                    qos = self.qos
                self.set_attr_value(item.conf, 'mqtt_qos', str(qos))

            # checking attribute 'mqtt_retain'
            if Utils.to_bool(self.get_iattr_value(item.conf, 'mqtt_retain'), default=False):
                self.set_attr_value(item.conf, 'mqtt_retain', 'True')
            else:
                self.set_attr_value(item.conf, 'mqtt_retain', 'False')

            self.logger.debug(self.get_loginstance() + "(parsing result): item.conf '{}'".format(str(item.conf)))

        # subscribe to configured topics
        if self.has_iattr(item.conf, 'mqtt_topic_in'):
            # add subscription
            topic = self.get_iattr_value(item.conf, 'mqtt_topic_in')
            payload_type = item.property.type
            bool_values = self.get_iattr_value(item.conf, 'mqtt_bool_values')
            self.add_subscription(topic, payload_type, bool_values, item)

        if self.has_iattr(item.conf, 'mqtt_topic_out'):
            # initialize topics if configured
            topic = self.get_iattr_value(item.conf, 'mqtt_topic_out')
            if self.has_iattr(item.conf, 'mqtt_topic_init'):
                self.inittopics[self.get_iattr_value(item.conf, 'mqtt_topic_init')] = item
            else:
                self.logger.info("Publishing topic '{}' (when needed) for item '{}'".format(topic, item.id()))

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
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if (self.has_iattr(item.conf, 'mqtt_topic_out')):
                topic = self.get_iattr_value(item.conf, 'mqtt_topic_out')
                retain = self.get_iattr_value(item.conf, 'mqtt_retain')
                if retain == None:
                    retain = False
                else:
                    retain = Utils.to_bool(retain)

                bool_values = self.get_iattr_value(item.conf, 'mqtt_bool_values')
                if bool_values is None or bool_values == []:
                    bool_values = None

                qos = self.get_iattr_value(item.conf, 'mqtt_qos')
                if qos:
                    qos = int(qos)
                self.publish_topic(topic, item(), item, qos, retain, bool_values)


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

    # -----------------------------------------------------------------------

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')  # try/except to handle running in a core version that does not support modules
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


# -----------------------------------------------------------------------
#    Webinterface of the plugin
# -----------------------------------------------------------------------

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
        self.plugin.get_broker_info()

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
            self.plugin.get_broker_info()
            data = {}
            data['broker_info'] = self.plugin._broker
            data['broker_uptime'] = self.plugin.broker_uptime()
            data['item_values'] = self.plugin._item_values

            # return it as json the the web page
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
                return {}

        return

