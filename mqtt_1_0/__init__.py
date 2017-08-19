#!/usr/bin/env python

# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017 Martin Sinn                                m.sinn@gmx.de
# Copyright 2012 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG.   https://github.com/smarthomeNG/
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
#  along with SmartHomeNG.  If not, see <http://www.gnu.org/licenses/>.
#  Skender Haxhimolla
#########################################################################

import logging
import paho.mqtt.client as paho
import paho.mqtt.publish as pahopub
import os
from lib.utils import Utils
import json

logger = logging.getLogger()


class Mqtt():

    def __init__(self, smarthome, host='127.0.0.1', port='1883'):
        self._sh = smarthome
        self.clients = []
        self.items = {}
        self.logics = {}
        if Utils.is_ip(host):
            self.broker_ip = host
        else:
            self.broker_ip = ''
            logger.error('MQTT: Invalid ip address for broker specified, plugin not starting')
            return
        if Utils.is_int(port):
            self.broker_port = int(port)
        else:
            self.broker_port = 1883
            logger.error('MQTT: Invalid port number for broker specified, plugin trying standard port 1883')
        self.publisher = self.create_client('main')

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False
        for client in self.clients:
            logger.debug('Stopping mqtt client {0}'.format(client._client_id))
            client.loop_stop()

    def parse_item(self, item):
        if 'mqtt_topic' in item.conf:
            item.conf['mqtt_topic_in'] = item.conf['mqtt_topic']
            item.conf['mqtt_topic_out'] = item.conf['mqtt_topic']
            logger.debug("parse item: {0}".format(item))

        if 'mqtt_topic_in' in item.conf:
            if self.broker_ip != '':
                client = self.create_client(item.id())
#                client.on_message = lambda client, obj, msg: self.items[msg.topic](msg.payload, 'MQTT')
                client.on_message = lambda client, obj, msg: self.items[msg.topic](self.cast_mqtt(self.items[msg.topic], msg.payload), 'MQTT')
                client.on_connect = lambda client, obj, rc: client.subscribe(item.conf['mqtt_topic_in'], 2)
                client.loop_start()
                self.items[item.conf['mqtt_topic_in']] = item
                logger.debug('Item [{0}] is listening for messages on topic [{1}]'.format(item, item.conf['mqtt_topic_in']))

        if 'mqtt_topic_out' in item.conf:
            return self.update_item

    def parse_logic(self, logic):
        if 'mqtt_topic' in logic.conf:
            if self.broker_ip != '':
                client = self.create_client(logic.name)
                client.on_message = lambda client, obj, msg: self.logics[msg.topic].trigger('MQTT', msg.topic, msg.payload)
                client.subscribe(logic.conf['mqtt_topic'], 2)
                client.loop_start()
                self.logics[logic.conf['mqtt_topic']] = logic
                logger.debug('Logic [{0}] is listening for messages on topic [{1}]'.format(logic.name, logic.conf['mqtt_topic']))


    def update_item(self, item, caller=None, source=None, dest=None):
        if self.broker_ip != '':
            pahopub.single(topic=item.conf['mqtt_topic_out'], payload=str(item()), qos=2, hostname=self.broker_ip)
            logger.info("update item: {0}".format(item.id()))
            logger.debug("Mqtt caller item: {0} \t Source: {1} \t Destination:{2}".format(caller, source, dest))
            logger.info("update topic: {0}\t{1}".format(item.conf['mqtt_topic_out'], str(item())))


    def cast_mqtt(self, item, raw_data):
        """
        Cast input data to SmartHomeNG datatypes

        :param item: item to whichs type the data should be casted
        :param raw_data: data as received from the mqtt broker
        :return: data casted to the datatype of the item it should be written to
        """
        str_data = raw_data.decode('utf-8')
        if item.type() == 'str':
            data = str_data
        elif item.type() == 'num':
            data = str_data
        elif item.type() == 'bool':
            data = Utils.to_bool(str_data, default=False)
        elif item.type() == 'list':
            if (len(str_data) > 0) and (str_data[0] == '['):
                data = json.loads(str_data)
            else:
                data = json.loads('['+str_data+']')
        elif item.type() == 'dict':
            data = json.loads(str_data)
        elif item.type() == 'scene':
            data = '0'
            if Utils.is_int(str_data):
                if (int(str_data) >= 0) and (int(str_data) < 0):
                    data = str_data        
        elif item.type() == 'foo':
            data = raw_data
        else:
            logger.warning("mqtt: item '{}' - Casting to '{}' is not implemented".format(str(item._path), str(item.type())))
            data = raw_data
        return data


    def create_client(self, name):
        client = paho.Client('{0}.{1}'.format(os.uname()[1], name))
        client.connect(self.broker_ip, self.broker_port, 60)
        self.clients.append(client)
        return client
