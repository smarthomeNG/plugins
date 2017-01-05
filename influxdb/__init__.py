

#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 Kai Meder <kai@meder.info>
#########################################################################
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
#########################################################################

import logging
import socket
import json
from lib.model.smartplugin import SmartPlugin


class InfluxDB(SmartPlugin):
    PLUGIN_VERSION = "1.0.0"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, smarthome, host='localhost', udp_port=8089, keyword='influxdb', tags={}, fields={}, value_field='value'):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init InfluxDB')

        self.host = host
        self.udp_port = udp_port
        self.keyword = keyword
        self.tags = tags
        self.fields = fields
        self.value_field = value_field
        self.item_config = {}

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.keyword in item.conf or 'influxdb_name' in item.conf or 'influxdb_tags' in item.conf or 'influxdb_fields' in item.conf:
            self.logger.debug("InfluxDB: enabling item {} ...".format(item.id()))

            if item.type() not in ['num', 'bool']:
                self.logger.error("InfluxDB: item {} has invalid type {}, only 'num' and 'bool' are supported".format(item.id(), item.type()))
                return

            # explicitly specified instead of fallback to item's ID
            name_is_specified = 'influxdb_name' in item.conf

            config = {
                'name_is_specified': name_is_specified,
                'name': item.conf['influxdb_name'] if name_is_specified else item.id(),
                'tags': {},
                'fields': {},
                'value_field': item.conf['influxdb_value_field'] if 'influxdb_value_field' in item.conf else self.value_field
            }

            if 'influxdb_tags' in item.conf:
                tags_json = item.conf['influxdb_tags']
                try:
                    config['tags'] = json.loads( tags_json.replace("'", "\"") )
                except Exception as e:
                    self.logger.error("InfluxDB: item {} has invalid tags {}, parsing JSON failed with: {}".format(item.id(), tags_json, e))
                    return

            if 'influxdb_fields' in item.conf:
                fields_json = item.conf['influxdb_fields']
                try:
                    config['fields'] = json.loads( fields_json.replace("'", "\"") )
                except Exception as e:
                    self.logger.error("InfluxDB: item {} has invalid fields {}, parsing JSON failed with: {}".format(item.id(), fields_json, e))
                    return

            self.logger.debug("InfluxDB: item {} config: {}".format(item.id(), config))

            self.item_config[ item.id() ] = config

            self.logger.info("InfluxDB: logging item {} as {}".format(item.id(), config['name']))
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        config = self.item_config[ item.id() ]
        name = config['name']

        tags = {
            'caller': caller,
            'source': source,
            'dest': dest
        }
        tags.update( self.tags ) # + plugin.conf tags
        tags.update( config['tags'] ) # + item's tags

        # if a name has been specified, additionally store item's ID
        # (if no name has been specified, the name is already the item's ID as a fallback)
        if config['name_is_specified']:
            tags['item'] = item.id()

        fields = {}
        fields.update( self.fields ) # + plugin.conf fields
        fields.update( config['fields'] ) # + item's fields
        fields[config['value_field']] = float( item() )

        line = self.create_line(name, tags, fields)
        self.send( line )
        return None

    def _update_values(self):
        return None

    def send(self, data):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data.encode(), (self.host, self.udp_port))
            sock.close()
        except Exception as e:
            self.logger.error("InfluxDB: failed sending UDP datagram [{}] to {}:{} with error: {}".format(data, self.host, self.udp_port, e))
        else:
            self.logger.debug("InfluxDB: sent UDP datagram [{}] to {}:{}".format(data, self.host, self.udp_port))

    def create_line(self, name, tags, fields):
        # https://docs.influxdata.com/influxdb/v1.0/guides/writing_data/

        # build name & tags
        kvs = [name]
        for tag_key in sorted(tags.keys()):
            kvs.append("{k}={v}".format(k=tag_key, v=tags[tag_key]))
        lineproto_name_tags = ','.join(kvs)

        # build fields (which include the actual value)
        kvs = []
        for field_key in sorted(fields.keys()):
            kvs.append("{k}={v}".format(k=field_key, v=fields[field_key]))
        lineproto_fields = ','.join(kvs)

        return lineproto_name_tags + ' ' + lineproto_fields
