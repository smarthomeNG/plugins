#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 <AUTHOR>                                        <EMAIL>
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
from lib.model.smartplugin import *
from lib.model.mqttplugin import *
from lib.item import Items

from lib.utils import Utils


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Mqtt2(SmartPlugin, MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.7.0'

    # _broker_version = '?'
    # _broker = {}
    # broker_config = {}
    # broker_monitoring = False
    #
    # _item_values = {}                    # dict of dicts


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
#        from bin.smarthome import VERSION
#        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
#            self.logger = logging.getLogger(__name__)

        # If an package import with try/except is done, handle an import error like this:

        # Exit if the required package(s) could not be imported
        # if not REQUIRED_PACKAGE_IMPORTED:
        #     self.logger.error("Unable to import Python package '<exotic package>'")
        #     self._init_complete = False
        #     return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        try:
        #     self.param1 = self.get_parameter_value('param1')
            pass
        except KeyError as e:
            self.logger.critical("Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # Initialization code goes here

        # needed because self.set_attr_value() can only set but not add attributes
        self.at_instance_name = self.get_instance_name()
        if self.at_instance_name != '':
            self.at_instance_name = '@'+self.at_instance_name

        # get instance of MQTT module
        try:
            self.mod_mqtt = Modules.get_instance().get_module('mqtt')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_mqtt = None
        if self.mod_mqtt == None:
            self.logger.error("Module MQTT could not be initialized. The plugin is not starting")
            return False

        self.inittopics = {}               # topics for items publishing initial value ('mqtt_topic_init')
        self._subscribed_topics = {}       # subscribed topics (a dict of dicts)
        self._subscribe_current_number = 0 # current number of the subscription entry

        # get broker configuration (for display in web interface)
        self.broker_config = self.mod_mqtt.get_broker_config()

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # if plugin should start even without web interface
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
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        #self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

        # start subscription to all topics
        self._start_subscriptions()

        # log structure with subscribed topic information
        from pprint import pformat
        sub = pformat(self._subscribed_topics, indent=4, width=80)
        self.logger.debug("self._subscribed_topics:\n{}\n".format(sub))

        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

        # stop subscription to all topics
        self._stop_subscriptions()

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
        if self.has_iattr(item.conf, 'mqtt2_topic'):
            item.conf['mqtt2_topic_in' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt2_topic')
            item.conf['mqtt2_topic_out' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt2_topic')

        if self.has_iattr(item.conf, 'mqtt2_topic_init'):
            item.conf['mqtt2_topic_out' + self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt2_topic_init')

        # check other mqtt attributes, if a topic attribute has been specified
        if self.has_iattr(item.conf, 'mqtt2_topic_in') or self.has_iattr(item.conf, 'mqtt2_topic_out'):
            self.logger.debug("parsing item: {0}".format(item.id()))

            # check if mqtt module has been initialized successfully
            if not self.mod_mqtt:
                self.logger.warning("MQTT module is not initialized, not parsing item '{}'".format(item.path()))
                return

            # checking attribute 'mqtt_qos'
            if self.has_iattr(item.conf, 'mqtt2_qos'):
                self.logger.debug(self.get_loginstance() + "Setting QoS '{}' for item '{}'".format(
                    str(self.get_iattr_value(item.conf, 'mqtt2_qos')), str(item)))
                qos = -1
                if Utils.is_int(self.get_iattr_value(item.conf, 'mqtt2_qos')):
                    qos = int(self.get_iattr_value(item.conf, 'mqtt2_qos'))
                if not (qos in [0, 1, 2]):
                    self.logger.warning(
                        self.get_loginstance() + "Item '{}' invalid value specified for mqtt2_qos, using plugin's default".format(
                            item.id()))
                    qos = self.qos
                self.set_attr_value(item.conf, 'mqtt2_qos', str(qos))

            # checking attribute 'mqtt_retain'
            if Utils.to_bool(self.get_iattr_value(item.conf, 'mqtt2_retain'), default=False):
                self.set_attr_value(item.conf, 'mqtt2_retain', 'True')
            else:
                self.set_attr_value(item.conf, 'mqtt2_retain', 'False')

            self.logger.debug(self.get_loginstance() + "(parsing result): item.conf '{}'".format(str(item.conf)))

        # subscribe to configured topics
        if self.has_iattr(item.conf, 'mqtt2_topic_in'):
            # add subscription
            topic = self.get_iattr_value(item.conf, 'mqtt2_topic_in')
            payload_type = item.property.type
            bool_values = self.get_iattr_value(item.conf, 'mqtt2_bool_values')
            self._add_subscription(topic, payload_type, bool_values, item)

        if self.has_iattr(item.conf, 'mqtt2_topic_out'):
            # initialize topics if configured
            topic = self.get_iattr_value(item.conf, 'mqtt2_topic_out')
            if self.has_iattr(item.conf, 'mqtt2_topic_init'):
                self.inittopics[self.get_iattr_value(item.conf, 'mqtt2_topic_init')] = item
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

            if (self.has_iattr(item.conf, 'mqtt2_topic_out')):
                topic = self.get_iattr_value(item.conf, 'mqtt2_topic_out')
                retain = self.get_iattr_value(item.conf, 'mqtt2_retain')
                if retain == None:
                    retain = False

                bool_values = self.get_iattr_value(item.conf, 'mqtt2_bool_values')
                if bool_values is None or bool_values == []:
                    bool_values = None

                qos = self.get_iattr_value(item.conf, 'mqtt2_qos')
                if qos:
                    qos = int(qos)
                self._publish_topic(item, topic, item(), qos, retain, bool_values)


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

    # def get_broker_info(self):
    #     if self.mod_mqtt:
    #         (self._broker, self.broker_monitoring) = self.mod_mqtt.get_broker_info()
    #
    #
    # def seconds_to_displaysting(self, sec):
    #     """
    #     Convert number of seconds to time display sting
    #     """
    #     min = sec // 60
    #     sec = sec - min * 60
    #     std = min // 60
    #     min = min - std * 60
    #     days = std // 24
    #     std = std - days * 24
    #
    #     result = ''
    #     if days == 1:
    #         result += str(days) + ' ' + self.translate('Tag') + ', '
    #     elif days > 0:
    #         result += str(days) + ' ' + self.translate('Tage') + ', '
    #     if std == 1:
    #         result += str(std) + ' ' + self.translate('Stunde') + ', '
    #     elif std > 0:
    #         result += str(std) + ' ' + self.translate('Stunden') + ', '
    #     if min == 1:
    #         result += str(min) + ' ' + self.translate('Minute') + ', '
    #     elif min > 0:
    #         result += str(min) + ' ' + self.translate('Minuten') + ', '
    #     if sec == 1:
    #         result += str(sec) + ' ' + self.translate('Sekunde')
    #     elif sec > 0:
    #         result += str(sec) + ' ' + self.translate('Sekunden')
    #     return result
    #
    #
    # def broker_uptime(self):
    #     """
    #     Return formatted uptime of broker
    #     """
    #     try:
    #         return self.seconds_to_displaysting(int(self._broker['uptime']))
    #     except:
    #         return '-'
    #
    #
    # def _start_subscriptions(self):
    #     """
    #     Start subscription to all topics
    #     """
    #     if self.mod_mqtt:
    #         for topic in self._subscribed_topics:
    #             # start subscription to all items for this topic
    #             for item_path in self._subscribed_topics[topic]:
    #                 current = str(self._subscribed_topics[topic][item_path]['current'])
    #                 qos = self._subscribed_topics[topic][item_path].get('qos', None)
    #                 payload_type = self._subscribed_topics[topic][item_path].get('payload_type', None)
    #                 # callback = self._subscribed_topics[topic][item_path].get('callback', None)
    #                 bool_values = self._subscribed_topics[topic][item_path].get('bool_values', None)
    #                 self.logger.info("run(): Subscribing to topic {} for item {}".format(topic, item_path))
    #                 self.mod_mqtt.subscribe_topic(self.get_shortname() + '-' + current, topic, qos=qos,
    #                                               payload_type=payload_type,
    #                                               callback=self.on_mqtt_message, bool_values=bool_values)
    #     return
    #
    # def _stop_subscriptions(self):
    #     """
    #     Stop subscription to all topics
    #     """
    #     if self.mod_mqtt:
    #         for topic in self._subscribed_topics:
    #             # stop subscription to all items for this topic
    #             for item_path in self._subscribed_topics[topic]:
    #                 current = str(self._subscribed_topics[topic][item_path]['current'])
    #                 self.logger.info("stop(): Unsubscribing from topic {} for item {}".format(topic, item_path))
    #                 self.mod_mqtt.unsubscribe_topic(self.get_shortname() + '-' + current, topic)
    #     return
    #
    # def _add_subscription(self, topic, payload_type, bool_values, item):
    #     """
    #
    #     :param topic:        topic to subscribe to
    #     :param payload_type: payload type of the topic (for this subscription to the topic)
    #     :param bool_values:  bool values (for this subscription to the topic)
    #     :param item:         item that should receive the payload as value
    #     :return:
    #     """
    #
    #     # test if topic is new
    #     if not self._subscribed_topics.get(topic, None):
    #         self._subscribed_topics[topic] = {}
    #     # add this item to topic
    #     self._subscribed_topics[topic][item.path()] = {}
    #     self._subscribe_current_number += 1
    #     self._subscribed_topics[topic][item.path()]['current'] = self._subscribe_current_number
    #     self._subscribed_topics[topic][item.path()]['item'] = item
    #     self._subscribed_topics[topic][item.path()]['qos'] = None
    #     self._subscribed_topics[topic][item.path()]['payload_type'] = payload_type
    #     # self._subscribed_topics[topic][item.path()]['callback'] = self.on_mqtt_message
    #     self._subscribed_topics[topic][item.path()]['bool_values'] = bool_values
    #
    #     return
    #
    #
    # def on_mqtt_message(self, topic, payload, qos=None, retain=None):
    #     """
    #     Callback function to handle received messages
    #
    #     :param topic:
    #     :param payload:
    #     :return:
    #     """
    #     self.logger.info(self.get_loginstance() + "MQTT2 on_mqtt_message: Received topic '{}', payload '{} (type {})', QoS '{}', retain '{}' ".format(topic, payload, type(payload), qos, retain))
    #
    #     # get item for topic
    #     if self._subscribed_topics.get(topic, None):
    #         # at least 1 item has subscribed to this topic
    #         for item_path in self._subscribed_topics[topic]:
    #             item = self._subscribed_topics[topic][item_path].get('item', None)
    #             if item != None:
    #                 self.logger.info(self.get_loginstance()+"Received topic '{}', payload '{}' (type {}), QoS '{}', retain '{}' for item '{}'".format( topic, payload, item.type(), qos, retain, item.id() ))
    #                 item(payload, 'mqtt2')
    #                 # Update dict for periodic updates of the web interface
    #                 self._update_item_values(item, payload)
    #     else:
    #         self.logger.error("on_mqtt_message: No definition found for subscribed topic '{}'".format(topic))
    #     return
    #
    #
    # def _publish_topic(self, item, topic, payload, qos, retain, bool_values):
    #     self.logger.info("_publish_topic: Item '{}' -> topic '{}', payload '{}', QoS '{}', retain '{}'".format(item.id(), topic, payload, qos, retain))
    #     self.mod_mqtt.publish_topic(self.get_shortname(), topic, payload, qos, retain, bool_values)
    #
    #     # Update dict for periodic updates of the web interface
    #     self._update_item_values(item, payload)
    #     return
    #
    #
    # def _update_item_values(self, item, payload):
    #     """
    #     Update dict for periodic updates of the web interface
    #
    #     :param item:
    #     :param payload:
    #     """
    #     if not self._item_values.get(item.id()):
    #         self._item_values[item.id()] = {}
    #     if isinstance(payload, bool):
    #         self._item_values[item.id()]['value'] = str(payload)
    #     else:
    #         self._item_values[item.id()]['value'] = payload
    #     self._item_values[item.id()]['last_update'] = item.last_update().strftime('%d.%m.%Y %H:%M:%S')
    #     self._item_values[item.id()]['last_change'] = item.last_change().strftime('%d.%m.%Y %H:%M:%S')
    #     self.logger.info("_update_item_values: self._item_values = {}".format(self._item_values))
    #     return


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


    _get_counter = 0

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

