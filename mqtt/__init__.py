#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017-2018  Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  The mqtt-plugin implements a MQTT client. 
#
#  MQTT is a machine-to-machine (M2M)/"Internet of Things" connectivity 
#  protocol. It was designed as an extremely lightweight publish/subscribe 
#  messaging transport.
#  
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

# todo
# - checken warum logging der stop Methode nur erfolgt, wenn nicht letztes Plugin
# - password als hash speichern / auswerten
# - Logiken testen
# - Broker disconnect erkennen

import logging

import json
import os
import socket    # for gethostbyname

import paho.mqtt.client as mqtt

from lib.model.smartplugin import *

from lib.utils import Utils
from lib.item import Items

import threading
connect_lock = threading.Lock()


class Mqtt(SmartPlugin):
    """
    Main class of the Mqtt-Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    ALLOW_MULTIINSTANCE = True
    
    PLUGIN_VERSION = "1.4.7"

    __plugif_CallbackTopics = {}         # for plugin interface
    __plugif_Sub = None
        
    _broker_version = '?'
    _broker = {}
    
    
    def __init__(self, sh, *args, **kwargs):

        """
        Initalizes the plugin. The parameters described for this method are pulled from the entry in plugin.yaml.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support older plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.

        :param sh:                 The instance of the smarthome object, save it for later references
        :param host:               ip address or hostname of the MQTT broker
        :param port:               port number of the MQTT broker (should not be specified under normal conditions
        :param qos:                Default Quality-of-Service, can be overwritten in item definition
        :param last_will_topic:    topic for MQTT last-will message to be sent by broker if shng terminates
        :param last_will_payload:  payload for MQTT last-will message to be sent by broker if shng terminates
        :param birth_topic:        topic for birth message to be sent when shng starts
        :param birth_payload:      payload for birth message to be sent when shng starts
        :param publish_items:      .
        :param items_topic_prefix: .
        :param user:               username to log into broker
        :param password:           password to log into broker
        :param broker_monitoring:  enable/disable monitoring broker data
        :param tls:                .
        :param ca_certs:           .
        :param acl:                Default Access-Control, can be overwritten in item definition
        """

        self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')

        # Initialization code goes here
        self.broker_hostname = self.get_parameter_value('host')
        self.broker_port = self.get_parameter_value('port')
        try:
            self.broker_ip = socket.gethostbyname( self.broker_hostname )
        except Exception as e:
            self.logger.error(self.get_loginstance()+"Error resolving '%s': %s" % (self.broker_hostname, e))
            self._init_complete = False
            return
        if self.broker_ip == self.broker_hostname:
            self.broker_hostname = ''

        self.broker_monitoring = self.get_parameter_value('broker_monitoring')
        self.qos = self.get_parameter_value('qos')
        self.acl = self.get_parameter_value('acl').lower()

        self.last_will_topic = self.get_parameter_value('last_will_topic')
        self.last_will_payload = self.get_parameter_value('last_will_payload')
        self.birth_topic = self.get_parameter_value('birth_topic')
        self.birth_payload = self.get_parameter_value('birth_payload')
        if (self.last_will_topic != '') and (self.last_will_topic [-1] == '/'):
            self.last_will_topic = self.last_will_topic[:-1]
        if self.birth_topic == '':
            self.birth_topic = self.last_will_topic
        else:
            if self.birth_topic [-1] == '/':
                self.birth_topic = self.birth_topic[:-1]

        self.publish_items = self.get_parameter_value('publish_items')
        self.items_topic_prefix = self.get_parameter_value('items_topic_prefix')
        if self.items_topic_prefix [-1] != '/':
            self.items_topic_prefix = self.items_topic_prefix + '/'

        self.username = self.get_parameter_value('user')
        self.password = self.get_parameter_value('password')
        if self.password == '':
            self.password = None

        # tls ...
        # ca_certs ...




        self.topics = {}                # subscribed topics
        self.logictopics = {}           # subscribed topics for triggering logics
        self.logicpayloadtypes = {}     # payload types for subscribed topics for triggering logics
        self.inittopics = {}            # topics for items publishing initial value ('mqtt_topic_init')

        # needed because self.set_attr_value() can only set but not add attributes
        self.at_instance_name = self.get_instance_name()
        if self.at_instance_name != '':
            self.at_instance_name = '@'+self.at_instance_name

        self._connected = False
        self._connect_result = ''
        
        # tls ...
        # ca_certs ...

        if not self.ConnectToBroker():
            self._init_complete = False
            return

        self.init_webinterface()
        

    def run(self):
        """
        Run method for the plugin
        """        
        self.alive = True
        if (self.birth_topic != '') and (self.birth_payload != ''):
            self._client.publish(self.birth_topic, self.birth_payload, self.qos, retain=True)
        self._client.loop_start()
        # set the name of the paho thread for this plugin instance
        try:
            self._client._thread.name = "paho_" + self.get_fullname()
        except:
            self.logger.warning(self.get_loginstance()+"Unable to set name for paho thread")


    def stop(self):
        """
        Stop method for the plugin
        """
        self._client.loop_stop()
        self.DisconnectFromBroker()
        self.alive = False


    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:  The item to process
        :return:      If the plugin needs to be informed of an items change you should return a call back function
                      like the function update_item down below. An example when this is needed is the knx plugin
                      where parse_item returns the update_item function when the attribute knx_send is found.
                      This means that when the items value is about to be updated, the call back function is called
                      with the item, caller, source and dest as arguments and in case of the knx plugin the value
                      can be sent to the knx with a knx write function within the knx plugin.

        """
        # first checking for mqtt-topic attributes 'mqtt_topic', 'mqtt_topic_in' and 'mqtt_topic_out'
        if self.has_iattr(item.conf, 'mqtt_topic'):
            item.conf['mqtt_topic_in'+self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic')
            item.conf['mqtt_topic_out'+self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic')

        if self.has_iattr(item.conf, 'mqtt_topic_init'):
            item.conf['mqtt_topic_out'+self.at_instance_name] = self.get_iattr_value(item.conf, 'mqtt_topic_init') 
        
        # check other mqtt attributes, if a topic attribute has been specified
        if self.has_iattr(item.conf, 'mqtt_topic_in') or self.has_iattr(item.conf, 'mqtt_topic_out'):
            self.logger.debug(self.get_loginstance()+"parsing item: {0}".format(item.id()))
        
            # checking attribute 'mqtt_qos'
            if self.has_iattr(item.conf, 'mqtt_qos'):
                self.logger.debug(self.get_loginstance()+"Setting QoS '{}' for item '{}'".format( str(self.get_iattr_value(item.conf, 'mqtt_qos')), str(item) ))
                qos = -1
                if Utils.is_int(self.get_iattr_value(item.conf, 'mqtt_qos')):
                    qos = int(self.get_iattr_value(item.conf, 'mqtt_qos'))
                if not (qos in [0, 1, 2]):
                    self.logger.warning(self.get_loginstance()+"Item '{}' invalid value specified for mqtt_qos, using plugin's default".format(item.id()))
                    qos = self.qos
                self.set_attr_value(item.conf, 'mqtt_qos', str(qos))
            	
            # checking attribute 'mqtt_retain'
            if Utils.to_bool(self.get_iattr_value(item.conf, 'mqtt_retain'), default=False):
                self.set_attr_value(item.conf, 'mqtt_retain', 'True')
            else:
                self.set_attr_value(item.conf, 'mqtt_retain', 'False')
            
            self.logger.debug(self.get_loginstance()+"(parsing result): item.conf '{}'".format( str(item.conf) ))
                   
        # subscribe to configured topics
        if self.has_iattr(item.conf, 'mqtt_topic_in'):
            if self._connected or True:
                topic = self.get_iattr_value(item.conf, 'mqtt_topic_in')
                self.topics[topic] = item
                # the real subscription is made by the callback function self.on_connect()

        if self.has_iattr(item.conf, 'mqtt_topic_out'):
            # initialize topics if configured
            topic = self.get_iattr_value(item.conf, 'mqtt_topic_out')
            if self.has_iattr(item.conf, 'mqtt_topic_init'):
                self.inittopics[self.get_iattr_value(item.conf, 'mqtt_topic_init')] = item
#                self.logger.info(self.get_loginstance()+"Publishing and initialising topic '{}' for item '{}'".format( topic, item.id() ))
            else:
                self.logger.info(self.get_loginstance()+"Publishing topic '{}' (when needed) for item '{}'".format( topic, item.id() ))

            return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method

        :param logic:  The logic to process
        """
        if 'mqtt_watch_topic'+self.at_instance_name in logic.conf:
            if self._connected:
                topic = logic.conf['mqtt_watch_topic'+self.at_instance_name]
                self.logictopics[topic] = logic
                if 'mqtt_payload_type'+self.at_instance_name in logic.conf:
                    if (logic.conf['mqtt_payload_type'+self.at_instance_name]).lower() in ['str', 'num', 'bool', 'list', 'dict', 'scene']:
                        self.logicpayloadtypes[topic] = (logic.conf['mqtt_payload_type'+self.at_instance_name]).lower()
                    else:
                        self.logger.warning(self.get_loginstance()+"Invalid payload-datatype specified for logic '{}', ignored".format( str(logic) ))
                    # the real subscription is made by the callback function self.on_connect()


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        
        This function is called by the core when a value changed, 
        so the plugin can update it's peripherals

        :param item:   item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest:   if given it represents the dest
        """
        if caller != 'Mqtt':
            if (self._connected) and (self.has_iattr(item.conf, 'mqtt_topic_out')):
                topic = self.get_iattr_value(item.conf, 'mqtt_topic_out')
                retain = self.get_iattr_value(item.conf, 'mqtt_retain')
                if retain == None:
                    retain = 'False'
                self.logger.info(self.get_loginstance()+"Item '{}': Publishing topic '{}', payload '{}', QoS '{}', retain '{}'".format( item.id(), topic, str(item()), str(self.get_qos_forTopic(item)), retain ))
                self._client.publish(topic=topic, payload=str(item()), qos=self.get_qos_forTopic(item), retain=(retain=='True'))


    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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


    def cast_mqtt(self, datatype, raw_data):
        """
        Cast input data to SmartHomeNG datatypes

        :param datatype:  datatype to which the data should be casted to
        :param raw_data:  data as received from the mqtt broker
        :return:          data casted to the datatype of the item it should be written to
        """
        str_data = raw_data.decode('utf-8')
        if datatype == 'str':
            data = str_data
        elif datatype == 'num':
            data = str_data
        elif datatype == 'bool':
            data = Utils.to_bool(str_data, default=False)
        elif datatype == 'list':
            if (len(str_data) > 0) and (str_data[0] == '['):
                data = json.loads(str_data)
            else:
                data = json.loads('['+str_data+']')
        elif datatype == 'dict':
            data = json.loads(str_data)
        elif datatype == 'scene':
            data = '0'
            if Utils.is_int(str_data):
                if (int(str_data) >= 0) and (int(str_data) < 0):
                    data = str_data        
        elif datatype == 'foo':
            data = raw_data
        else:
            self.logger.warning(self.get_loginstance()+"item '{}' - Casting to '{}' is not implemented".format(str(item._path), str(datatype)))
            data = raw_data
        return data


    def get_qos_forTopic(self, item):
        """
        Return the configured QoS for a topic/item as an integer

        :param item:      item to get the QoS for
        :return:          Quality of Service (0..2)
        """
        qos = self.get_iattr_value(item.conf, 'mqtt_qos')
        if qos == None:
            qos = self.qos
        return int(qos)


    def on_mqtt_log(self, client, userdata, level, buf):
        # self.logger.info("on_log: {}".format(buf))
        return


    def ConnectToBroker(self):
        """
        Establish connection to MQTT broker
        """
        clientname = os.uname()[1]
        if self.get_instance_name() != '':
            clientname = clientname + '.' + self.get_instance_name()
        self.logger.info(self.get_loginstance()+"Connecting to broker '{}:{}'. Starting mqtt client '{}'".format(self.broker_ip, self.broker_port, clientname))
        self._client = mqtt.Client(client_id=clientname)


        # set testament, if configured
        if (self.last_will_topic != '') and (self.last_will_payload != ''):
            retain = False
            if (self.birth_topic != '') and (self.birth_payload != ''):
                retain = True
            self._client.will_set(self.last_will_topic, self.last_will_payload, self.qos, retain=retain)
            
        if self.username != '':
            self._client.username_pw_set(self.username, self.password)
        self._client.on_connect = self.on_connect
        self._client.on_log = self.on_mqtt_log
        self._client.on_message = self.on_mqtt_message
        try:
            self._client.connect(self.broker_ip, self.broker_port, 60)
        except ERROR as e:
            self.logger.error(self.get_loginstance()+'Connection error:', e)
            return False
        return True




    def on_connect(self, client, userdata, flags, rc):
        """
        Callback function called on connect
        """

        self._connect_result = mqtt.connack_string(rc)

        if rc == 0:
            self.logger.info(self.get_loginstance()+"Connection returned result '{}' (userdata={}) ".format( mqtt.connack_string(rc), userdata ))
            self._connected = True

            self._client.subscribe('$SYS/broker/version', qos=0)
            self._client.subscribe('$SYS/broker/clients/active', qos=0)
            self._client.subscribe('$SYS/broker/subscriptions/count', qos=0)
            self._client.subscribe('$SYS/broker/messages/stored', qos=0)

            if self.broker_monitoring:
                self._client.subscribe('$SYS/broker/uptime', qos=0)
                self._client.subscribe('$SYS/broker/retained messages/count', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/received/1min', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/received/5min', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/received/15min', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/sent/1min', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/sent/5min', qos=0)
                self._client.subscribe('$SYS/broker/load/messages/sent/15min', qos=0)

            # subscribe to topics to listen for items
            for topic in self.topics:
                item = self.topics[topic]
                self._client.subscribe(topic, qos=self.get_qos_forTopic(item) )
                self.logger.info(self.get_loginstance()+"Listening on topic '{}' for item '{}'".format( topic, item.id() ))

            # subscribe to topics to listen for triggering logics
            for topic in self.logictopics:
                logic = self.logictopics[topic]
                self._client.subscribe(topic, qos=self.qos)
                self.logger.info(self.get_loginstance()+"Listening on topic '{}' for logic '{}'".format( topic, str(logic) ))

            for topic in self.inittopics:
                item = self.inittopics[topic]
                self.logger.info(self.get_loginstance()+"Publishing and initialising topic '{}' for item '{}'".format( topic, item.id() ))
                self.update_item(item)
            self.logger.info("self.topics = {}".format(self.topics))

            return

        self.logger.warning(self.get_loginstance()+"Connection returned result '{}': {} (client={}, userdata={}, self._client={})".format( str(rc), mqtt.connack_string(rc), client, userdata, self._client ))
        if rc == 5:
            self.DisconnectFromBroker()


    def on_disconnect(client, userdata, rc):
        """
        Callback function called on disconnect
        """
        self.logger.info(self.get_loginstance() + "Disconnection returned result '{}' ".format(rc))
        return


    def DisconnectFromBroker(self):
        """
        Stop all communication with MQTT broker
        """
        self._client.unsubscribe('$SYS/broker/version')
        self._client.unsubscribe('$SYS/broker/clients/active')
        self._client.unsubscribe('$SYS/broker/subscriptions/count')
        self._client.unsubscribe('$SYS/broker/messages/stored')

        if self.broker_monitoring:
            self._client.unsubscribe('$SYS/broker/uptime')
            self._client.unsubscribe('$SYS/broker/retained messages/count')
            self._client.unsubscribe('$SYS/broker/load/messages/received/1min')
            self._client.unsubscribe('$SYS/broker/load/messages/received/5min')
            self._client.unsubscribe('$SYS/broker/load/messages/received/15min')
            self._client.unsubscribe('$SYS/broker/load/messages/sent/1min')
            self._client.unsubscribe('$SYS/broker/load/messages/sent/5min')
            self._client.unsubscribe('$SYS/broker/load/messages/sent/15min')

        for topic in self.topics:
            item = self.topics[topic]
            self.logger.debug(self.get_loginstance()+"Unsubscribing topic '{}' for item '{}'".format( str(topic), str(item.id()) ))
            self._client.unsubscribe(topic)

        for topic in self.logictopics:
            logic = self.logictopics[topic]
            self.logger.debug(self.get_loginstance()+"Unsubscribing topic '{}' for logic '{}'".format( str(topic), str(logic.id()) ))
            self._client.unsubscribe(topic)

        if (self.last_will_topic != '') and (self.last_will_payload != ''):
            if (self.birth_topic != '') and (self.birth_payload != ''):
                self._client.publish(self.last_will_topic, self.last_will_payload+' (shutdown)', self.qos, retain=True)
                
        self.logger.info(self.get_loginstance()+"Stopping mqtt client '{}'. Disconnecting from broker.".format(self._client._client_id.decode('utf-8')))
        self._client.loop_stop()
        self._connected = False
        self._client.disconnect()


    def seconds_to_displaysting(self, sec):
        """
        Convert number of seconds to time display sting
        """
        min = sec // 60
        sec = sec - min * 60
        std = min // 60
        min = min - std * 60
        days = std // 24
        std = std - days * 24

        result = ''
        if days == 1:
            result += str(days) + ' ' + self.translate('Tag') + ', '
        elif days > 0:
            result += str(days) + ' ' + self.translate('Tage') + ', '
        if std == 1:
            result += str(std) + ' ' + self.translate('Stunde') + ', '
        elif std > 0:
            result += str(std) + ' ' + self.translate('Stunden') + ', '
        if min == 1:
            result += str(min) + ' ' + self.translate('Minute') + ', '
        elif min > 0:
            result += str(min) + ' ' + self.translate('Minuten') + ', '
        if sec == 1:
            result += str(sec) + ' ' + self.translate('Sekunde')
        elif sec > 0:
            result += str(sec) + ' ' + self.translate('Sekunden')
        return result


    def broker_uptime(self):
        """
        Return formatted uptime of broker
        """
        try:
            return self.seconds_to_displaysting(int(self._broker['uptime']))
        except:
            return '-'


    def on_mqtt_message(self, client, userdata, message):
        """
        Callback function to handle received messages for items and logics

        :param client:    the client instance for this callback
        :param userdata:  the private user data as set in Client() or userdata_set()
        :param message:   an instance of MQTTMessage. 
                          This is a class with members topic, payload, qos, retain.
        """
        item = self.topics.get(message.topic, None)
        if item != None:
            payload = self.cast_mqtt(item.type(), message.payload)
            self.logger.info(self.get_loginstance()+"Received topic '{}', payload '{}' (type {}), QoS '{}', retain '{}' for item '{}'".format( message.topic, str(payload), item.type(), str(message.qos), str(message.retain), str(item.id()) ))
            item(payload, 'MQTT')
        logic = self.logictopics.get(message.topic, None)
        if logic != None:
            datatype = self.logicpayloadtypes.get(message.topic, 'foo')
            payload = self.cast_mqtt(datatype, message.payload)
            self.logger.info(self.get_loginstance()+"Received topic '{}', payload '{} (type {})', QoS '{}', retain '{}' for logic '{}'".format( message.topic, str(payload), datatype, str(message.qos), str(message.retain), str(logic) ))
            logic.trigger('MQTT'+self.at_instance_name, message.topic, payload )

        if (item == None) and (logic == None):
            if message.topic == '$SYS/broker/clients/active':
                self._broker['active_clients'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/subscriptions/count':
                self._broker['subscriptions'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/messages/stored':
                self._broker['stored_messages'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/retained messages/count':
                self._broker['retained_messages'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/uptime':
                self._broker['uptime'] = message.payload.decode('utf-8').split(' ')[0]
            elif message.topic == '$SYS/broker/load/messages/received/1min':
                self._broker['msg_rcv_1min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/load/messages/received/5min':
                self._broker['msg_rcv_5min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/load/messages/received/15min':
                self._broker['msg_rcv_15min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/load/messages/sent/1min':
                self._broker['msg_snt_1min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/load/messages/sent/5min':
                self._broker['msg_snt_5min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/load/messages/sent/15min':
                self._broker['msg_snt_15min'] = message.payload.decode('utf-8')
            elif message.topic == '$SYS/broker/version':
                self.log_brokerinfo(message.payload)
                self._broker['version'] = message.payload.decode('utf-8')
                # self._client.unsubscribe('$SYS/broker/version')
            else:
                self.logger.error(self.get_loginstance()+"Received topic '{}', payload '{}', QoS '{}, retain '{}'' WITHOUT matching item/logic".format( message.topic, message.payload, str(message.qos), str(message.retain) ))


    def log_brokerinfo(self, payload):
        """
        Log info about broker connection
        """
        payload = self.cast_mqtt('str', payload)
        if self.broker_hostname == '':
            address = str(self.broker_ip)+':'+str(self.broker_port)
        else:
            address = self.broker_hostname + ' (' + str(self.broker_ip)+':'+str(self.broker_port) + ')'
        sn = self.get_shortname()
#        self.mqttlogger.warning("-{}: Connected to broker '{}' at address {}".format( sn, str(payload), address ))
        self.logger.info(self.get_loginstance()+"Connected to broker '{}' at address {}".format( str(payload), address ))


    # ---------------------------------------------------------------------------------
    # Following functions build the interface for other plugins which want to use MQTT
    #

    def publish_topic(self, plug, topic, payload, qos=None, retain=False):
        """
        function to publish a topic
        
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
        
        :param topic:      topic to publish to
        :param payload:    payload to publish
        :param qos:        quality of service (optional) otherwise the default of the mqtt plugin will be used
        :param retain:     retain flag (optional)
        """
        if not self._connected:
            return
        if qos == None:
            qos = self.qos
        self.logger.warning(self.get_loginstance()+"(interface: Plugin '{}' is publishing topic '{}'".format( str(plug), str(topic) ))
        self._client.publish(topic=topic, payload=payload, qos=qos, retain=retain)


    def subscription_callback(self, plug, sub, callback=None):
        """
        function set a callback function
        
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
        
        :param plug:       identifier of plgin/logic using the MQTT plugin
        :param sub:        topic(s) which should call the callback function
                           example: 'device/eno-gw1/#'
        :param callback:   quality of service (optional) otherwise the default of the mqtt plugin will be used
        """
        if self.__plugif_Sub == None:
            if sub[-2:] != '/#':
                if sub[-1] == '/':
                    sub = sub[:-1]
                self.__plugif_Sub = sub + '/#'
            else:
                self.__plugif_Sub = sub
        
            self.logger.warning(self.get_loginstance()+"(interface): Plugin '{}' is registering a callback function for subscription of topics '{}'".format( str(plug), str(self.__plugif_Sub) ))
            self._client.message_callback_add(self.__plugif_Sub, callback)
        else:
            if sub == '':
                self.logger.warning(self.get_loginstance()+"(interface): Plugin '{}' is clearing the callback function for subscription of topics '{}'".format( str(plug), str(self.__plugif_Sub) ))
                self._client.message_callback_remove(self.__plugif_Sub)
                self.__plugif_Sub = None
            else:
                self.logger.error(self.get_loginstance()+"(interface): Plugin '{}' is trying to register a second callback function (for subscription of topics '{}')".format( str(plug), str(self.__plugif_Sub) ))


    def subscribe_topic(self, plug, topic, qos=None):
        """
        function to subscribe to a topic
         
        this function is to be called from other plugins, which are utilizing
        the mqtt plugin
         
        :param topic:      topic to subscribe to
        :param qos:        quality of service (optional) otherwise the default of the mqtt plugin will be used
        """
        if qos == None:
            qos = self.qos
        self._client.subscribe(topic, qos=qos)
        self.logger.info(self.get_loginstance()+"(interface): Plugin '{}' is subscribing to topic '{}'".format( str(plug), str(topic) ))


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
        return tmpl.render(p=self.plugin, connection_result=self.plugin._connect_result,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path']))
                          )

