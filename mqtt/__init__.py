#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Martin Sinn                               m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  The mqtt-plugin implements a MQTT client. 
#
#  MQTT is a machine-to-machine (M2M)/"Internet of Things" connectivity 
#  protocol. It was designed as an extremely lightweight publish/subscribe 
#  messaging transport.
#  
#  For detail read http://mqtt.org
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

import logging
from lib.model.smartplugin import SmartPlugin

from lib.utils import Utils
import json
import os

import paho.mqtt.client as mqtt


class Mqtt(SmartPlugin):
    """
    Main class of the Mqtt-Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    
    # todo
    # change ALLOW_MULTIINSTANCE to true if your plugin will support multiple instances (seldom)
    ALLOW_MULTIINSTANCE = True
    
    PLUGIN_VERSION = "1.3.1"


    def __init__(self, sh, 
            host='127.0.0.1', port='1883', qos='1',
            last_will_topic='', last_will_payload='',
            birth_topic='', birth_payload='',
            publish_items='False', items_topic_prefix='devices/shng',
            user='', password='',
            tls=None, ca_certs='/etc/', acl='none'
        ):
        """
        Initalizes the plugin. The parameters described for this method are pulled from the entry in plugin.yaml.

        :param sh:  The instance of the smarthome object, save it for later references
        :param host:  .
        :param port:  .
        :param qos:  Default Quality-of-Service, can be overwritten in item definition
        :param acl:  Default Access-Control, can be overwritten in item definition
        :param publish_items:  .
        :param items_topic_prefix:  .
        :param user:  username to loginto broker
        :param password:  password to loginto broker
        :param tls:  .
        :param ca_certs:  .
        """
        # attention:
        # if your plugin runs standalone, sh will likely be None so do not rely on it later or check it within your code
        
        self._sh = sh

        # needed because self.set_attr_value() can only set but not add attributes
        self.at_instance_name = self.get_instance_name()
        if self.at_instance_name != '':
            self.at_instance_name = '@'+self.at_instance_name

        self.logIdentifier = ('MQTT '+self.at_instance_name).strip()

        self._connected = False
        
        # check parameters specified in plugin.yaml
        if Utils.is_ip(host):
            self.broker_ip = host
        else:
            self.broker_ip = ''
            self.logger.error(self.logIdentifier+': Invalid ip address for broker specified, plugin not starting')
            return

        if Utils.is_int(port):
            self.broker_port = int(port)
        else:
            self.broker_port = 1883
            self.logger.error(self.logIdentifier+": Invalid port number for broker specified, plugin trying standard port '{}'".format(str(self.broker_port)))
            
        self.qos = -1
        if Utils.is_int(qos):
            self.qos = int(qos)
        if not (self.qos in [0, 1, 2]):
            self.qos = 1
            self.logger.error(self.logIdentifier+": Invalid value specified for default quality-of-service, using standard '{}'".format(str(self.qos)))

        self.acl = acl.lower()
        if not (self.acl in ['none','pub','sub','pubsub']):
            self.acl ='none'
            self.logger.error(self.logIdentifier+": Invalid value specified for default acess-control, using standard '{}'".format(self.acl))

        if last_will_topic [-1] == '/':
            last_will_topic = last_will_topic[:-1]
        self.last_will_topic = last_will_topic
        self.last_will_payload = last_will_payload
        if birth_topic == '':
            self.birth_topic = self.last_will_topic
        else:
            if birth_topic [-1] == '/':
                birth_topic = birth_topic[:-1]
            self.birth_topic = birth_topic
        self.birth_payload = birth_payload
        
        self.publish_items = Utils.to_bool(publish_items, default=False)
        if items_topic_prefix [-1] == '/':
            items_topic_prefix = items_topic_prefix[:-1]
        self.items_topic_prefix = items_topic_prefix + '/'
        
        self.username = user
        if password == '':
           self.password = None
        else:
            self.password = password
        
        # tls ...
        # ca_certs ...
        
        self.ConnectToBroker()
        self.topics = {}                # subscribed topics
        self.logictopics = {}           # subscribed topics for triggering logics
        self.logicpayloadtypes = {}     # payload types for subscribed topics for triggering logics
        self.inittopics = {}            # topics for items publishing initial value ('mqtt_topic_init')
        

    def run(self):
        """
        Run method for the plugin
        """        
        self.alive = True
        if (self.birth_topic != '') and (self.birth_payload != ''):
            self._client.publish(self.birth_topic, self.birth_payload, self.qos, retain=True)
        self._client.loop_start()
        for topic in self.inittopics:
            item = self.inittopics[topic]
            self.update_item(item)


    def stop(self):
        """
        Stop method for the plugin
        """
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
            self.logger.info(self.logIdentifier+": parsing item: {0}".format(item.id()))
        
            # checking attribute 'mqtt_qos'
            if self.has_iattr(item.conf, 'mqtt_qos'):
                self.logger.debug(self.logIdentifier+": Setting QoS '{}' for item '{}'".format( str(self.get_iattr_value(item.conf, 'mqtt_qos')), str(item) ))
                qos = -1
                if Utils.is_int(self.get_iattr_value(item.conf, 'mqtt_qos')):
                    qos = int(self.get_iattr_value(item.conf, 'mqtt_qos'))
                if not (qos in [0, 1, 2]):
                    self.logger.warning(self.logIdentifier+": Item '{}' invalid value specified for mqtt_qos, using plugin's default".format(item.id()))
                    qos = self.qos
                self.set_attr_value(item.conf, 'mqtt_qos', str(qos))
            	
            # checking attribute 'mqtt_retain'
            if Utils.to_bool(self.get_iattr_value(item.conf, 'mqtt_retain'), default=False):
                self.set_attr_value(item.conf, 'mqtt_retain', 'True')
            else:
                self.set_attr_value(item.conf, 'mqtt_retain', 'False')
            
            self.logger.debug(self.logIdentifier+" (parsing result): item.conf '{}'".format( str(item.conf) ))
                   
            self._client.on_message = self.on_mqtt_message

        # subscribe to configured topics
        if self.has_iattr(item.conf, 'mqtt_topic_in'):
            if self._connected:
                topic = self.get_iattr_value(item.conf, 'mqtt_topic_in')
                self.topics[topic] = item
                self._client.subscribe(topic, qos=self.get_qos_forTopic(item) )
                self.logger.info(self.logIdentifier+": Listening on topic '{}' for item '{}'".format( topic, item.id() ))
        
        if self.has_iattr(item.conf, 'mqtt_topic_out'):
            # initialize topics if configured
            topic = self.get_iattr_value(item.conf, 'mqtt_topic_out')
            if self.has_iattr(item.conf, 'mqtt_topic_init'):
                self.inittopics[self.get_iattr_value(item.conf, 'mqtt_topic_init')] = item
                self.logger.info(self.logIdentifier+": Publishing and initialising topic '{}' for item '{}'".format( topic, item.id() ))
            else:
                self.logger.info(self.logIdentifier+": Publishing topic '{}' for item '{}'".format( topic, item.id() ))

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
                        self.logger.warning(self.logIdentifier+": Invalid payload-datatype specified for logic '{}', ignored".format( str(logic) ))            
                self._client.subscribe(topic, qos=self.qos)
                self.logger.warning(self.logIdentifier+": Listening on topic '{}' for logic '{}'".format( topic, str(logic) ))


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values

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
                self.logger.info("Item '{}': Publishing topic '{}', payload '{}', QoS '{}', retain '{}'".format( item.id(), topic, str(item()), str(self.get_qos_forTopic(item)), retain ))
                self._client.publish(topic=topic, payload=str(item()), qos=self.get_qos_forTopic(item), retain=(retain=='True'))


    def cast_mqtt(self, datatype, raw_data):
        """
        Cast input data to SmartHomeNG datatypes

        :param item:      item to whichs type the data should be casted
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
            self.logger.warning(self.logIdentifier+": item '{}' - Casting to '{}' is not implemented".format(str(item._path), str(datatype)))
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
        

    def ConnectToBroker(self):
        """
        Establish connection to MQTT broker
        """
        clientname = os.uname()[1]
        if self.get_instance_name() != '':
            clientname = clientname + '.' + self.get_instance_name()
        self.logger.info(self.logIdentifier+": Connecting to broker. Starting mqtt client '{0}'".format(clientname))
        self._client = mqtt.Client(clientname)

        # set testament, if configured
        if (self.last_will_topic != '') and (self.last_will_payload != ''):
            retain = False
            if (self.birth_topic != '') and (self.birth_payload != ''):
                retain = True
            self._client.will_set(self.last_will_topic, self.last_will_payload, self.qos, retain=retain)
            
        if self.username != '':
            self._client.username_pw_set(self.username, self.password)
        try:
            self._client.connect(self.broker_ip, self.broker_port, 60)
            self._connected = True
        except Exception as e:
            print('Connection error:', e)


    def DisconnectFromBroker(self):
        """
        Stop all communication with MQTT broker
        """
        for topic in self.topics:
            item = self.topics[topic]
            self.logger.debug(self.logIdentifier+": Unsubscribing topic '{}' for item '{}'".format( str(topic), str(item.id()) ))
            self._client.unsubscribe(topic)

        for topic in self.logictopics:
            logic = self.logictopics[topic]
            self.logger.debug(self.logIdentifier+": Unsubscribing topic '{}' for logic '{}'".format( str(topic), str(logic.id()) ))
            self._client.unsubscribe(topic)

        if (self.last_will_topic != '') and (self.last_will_payload != ''):
            if (self.birth_topic != '') and (self.birth_payload != ''):
                self._client.publish(self.last_will_topic, self.last_will_payload+' (shutdown)', self.qos, retain=True)
                
        self.logger.info(self.logIdentifier+": Stopping mqtt client '{}'. Disconnecting from broker.".format(self._client._client_id))
        self._client.loop_stop()
        self._connected = False
        self._client.disconnect()


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
            self.logger.info(self.logIdentifier+": Received topic '{}', payload '{}' (type {}), QoS '{}', retain '{}' for item '{}'".format( message.topic, str(payload), item.type(), str(message.qos), str(message.retain), str(item.id()) ))
            item(payload, 'MQTT')
        logic = self.logictopics.get(message.topic, None)
        if logic != None:
            datatype = self.logicpayloadtypes.get(message.topic, 'foo')
            payload = self.cast_mqtt(datatype, message.payload)
            self.logger.info(self.logIdentifier+": Received topic '{}', payload '{} (type {})', QoS '{}', retain '{}' for logic '{}'".format( message.topic, str(payload), datatype, str(message.qos), str(message.retain), str(logic) ))
            logic.trigger('MQTT'+self.at_instance_name, message.topic, payload )
        if (item == None) and (logic == None):
            self.logger.error(self.logIdentifier+": Received topic '{}', payload '{}', QoS '{}, retain '{}'' WITHOUT matching item/logic".format( message.topic, message.payload, str(message.qos), str(message.retain) ))

