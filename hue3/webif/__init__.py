#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This file implements the web interface for the hue2 plugin.
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

import datetime
import time
import os
import json

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
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
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()

    # ----------------------------------------------------------------------------------
    # Methods to handle v2bridge for webinterface
    #

    def get_itemsdata(self):

        result = {}
        if self.plugin.v2bridge is None:
            return result

        for item in self.plugin.get_item_list():
            item_config = self.plugin.get_item_config(item)
            value_dict = {}
            value_dict['path'] = item.property.path
            value_dict['type'] = item.type()
            value_dict['value'] = item()
            if value_dict['type'] == 'dict':
                value_dict['value'] = str(item())
            value_dict['resource'] = item_config['resource']
            value_dict['id'] = item_config['id']
            value_dict['function'] = item_config['function']

            value_dict['last_update'] = item.property.last_update.strftime('%d.%m.%y %H:%M:%S')
            value_dict['last_change'] = item.property.last_change.strftime('%d.%m.%y %H:%M:%S')

            result[value_dict['path']] = value_dict
        return result

    def get_lightsdata(self):

        result = {}
        if self.plugin.v2bridge is None or self.plugin.bridge_ip == '0.0.0.0':
            return result

        devicedata = self.get_devicesdata()

        #        self.logger.info(f"get_lightsdata() - Lights:")
        first = True
        for light in self.plugin.v2bridge.lights:
            value_dict = {}
            value_dict['_full'] = light

            device_id = light.owner.rid
            zigbee_status =  self.plugin.v2bridge.devices.get_zigbee_connectivity(device_id).status.value

            value_dict['id'] = light.id
            if light.id_v1 is None:
                value_dict['id_v1'] = ''
            else:
                value_dict['id_v1'] = light.id_v1

            value_dict['name'] = ''
            for d in devicedata:
                if value_dict['id_v1'] == devicedata[d]['id_v1']:
                    value_dict['name'] = devicedata[d]['name']

            value_dict['on'] = light.on.on

            value_dict['is_on'] = light.is_on
            value_dict['brightness'] = light.brightness
            # value_dict['color'] = light.color
            # value_dict['color_temperature'] = light.color_temperature
            value_dict['entertainment_active'] = light.entertainment_active
            # value_dict['powerup'] = light.powerup
            value_dict['supports_color'] = light.supports_color
            value_dict['supports_color_temperature'] = light.supports_color_temperature
            value_dict['supports_dimming'] = light.supports_dimming
            value_dict['zigbee_status'] = zigbee_status

            value_dict['xy'] = [light.color.xy.x, light.color.xy.y]
            try:
                value_dict['ct'] = light.color_temperature.mirek
                if light.color_temperature.mirek_valid == False:
                    value_dict['ct'] = '(' + str(light.color_temperature.mirek) + ')'
            except:
                value_dict['ct'] = ''
            value_dict['gamut_type'] = light.color.gamut_type.value
            value_dict['type'] = light.type.value

            result[light.id] = value_dict
            # self.logger.debug(f"-> {light.id}: {value_dict}")

        return result

    def get_scenesdata(self):

        result = {}
        if self.plugin.v2bridge is None or self.plugin.bridge_ip == '0.0.0.0':
            return result

        for scene in self.plugin.v2bridge.scenes:
            value_dict = {}
            value_dict['_full'] = scene
            value_dict['id'] = scene.id
            if scene.id_v1 is None:
                value_dict['id_v1'] = ''
            else:
                value_dict['id_v1'] = scene.id_v1
            value_dict['name'] = scene.metadata.name
            value_dict['type'] = scene.type.value

            result[scene.id] = value_dict

        return result

    def get_groupsdata(self):

        result = {}
        if self.plugin.v2bridge is None or self.plugin.bridge_ip == '0.0.0.0':
            return result

        for group in self.plugin.v2bridge.groups:
            #self.logger.notice(f"get_groupsdata: {group=}")
            if group.type.value == 'grouped_light':
                value_dict = {}
                value_dict['_full'] = group
                value_dict['id'] = group.id
                if group.id_v1 is None:
                    value_dict['id_v1'] = ''
                else:
                    value_dict['id_v1'] = group.id_v1
                try:
                    room = self.plugin.v2bridge.groups.grouped_light.get_zone(group.id)
                    value_dict['name'] = room.metadata.name
                    if value_dict['name'] == '':
                        value_dict['name'] = '(All lights)'
                except:
                    value_dict['name'] = ''
                value_dict['type'] = group.type.value

                result[group.id] = value_dict

        return result

    def get_sensorsdata(self):

        result = {}
        if self.plugin.v2bridge is None or self.plugin.bridge_ip == '0.0.0.0':
            return result

        devicedata = self.get_devicesdata()

        for sensor in self.plugin.v2bridge.sensors:
            value_dict = {}
            value_dict['_full'] = sensor
            value_dict['id'] = sensor.id
            if sensor.id_v1 is None:
                value_dict['id_v1'] = ''
            else:
                value_dict['id_v1'] = sensor.id_v1
            try:
                value_dict['name'] = sensor.name
            except:
                value_dict['name'] = ''
                self.logger.debug(f"get_sensorsdata: Exception 'no name'")
                self.logger.debug(f"- sensor={sensor}")
                self.logger.debug(f"- owner={sensor.owner}")

            try:
                value_dict['control_id'] = sensor.metadata.control_id
            except:
                value_dict['control_id'] = ''
            try:
                value_dict['event'] = sensor.button.last_event.value
            except:
                value_dict['event'] = ''
            try:
                value_dict['last_event'] = sensor.button.last_event.value
            except:
                value_dict['last_event'] = ''

            try:
                value_dict['battery_level'] = sensor.power_state.battery_level
                value_dict['battery_state'] = sensor.power_state.battery_state.value
            except:
                value_dict['battery_level'] = ''
                value_dict['battery_state'] = ''

            try:
                value_dict['device_id'] = sensor.owner.rid
                value_dict['device_name'] = ''
                for d in devicedata:
                    if value_dict['device_id'] == devicedata[d]['id']:
                        value_dict['device_name'] = devicedata[d]['name']
                        if value_dict['name'] == '':
                            value_dict['name'] = devicedata[d]['name']

            except Exception as ex:
                value_dict['device_id'] = ''
            try:
                value_dict['owner_type'] = sensor.owner.rtype.value
            except Exception as ex:
                value_dict['owner_type'] = ''
            try:
                value_dict['status'] = sensor.status.value
            except Exception as ex:
                value_dict['status'] = ''

            value_dict['type'] = sensor.type.value

            result[sensor.id] = value_dict

        return result

    def get_devicesdata(self):

        result = {}
        if self.plugin.v2bridge is None or self.plugin.bridge_ip == '0.0.0.0':
            return result

        for device in self.plugin.v2bridge.devices:
            value_dict = {}
            value_dict['_full'] = device
            value_dict['id'] = device.id
            if device.id_v1 is None:
                value_dict['id_v1'] = ''
            else:
                value_dict['id_v1'] = device.id_v1
            value_dict['name'] = device.metadata.name
            value_dict['model_id'] = device.product_data.model_id
            value_dict['manufacturer_name'] = device.product_data.manufacturer_name
            value_dict['product_name'] = device.product_data.product_name
            value_dict['software_version'] = device.product_data.software_version
            value_dict['hardware_platform_type'] = device.product_data.hardware_platform_type
            if device.lights == set():
                value_dict['lights'] = []
            else:
                value_dict['lights'] = list(device.lights)
            value_dict['services'] = []
            for s in device.services:
                if str(s.rtype.value) != 'unknown':
                    value_dict['services'].append(s.rtype.value)
                if str(s.rtype.value) == 'zigbee_connectivity':
                    # value_dict['zigbee_connectivity'] = s.rtype.status.value
                    sensor = self.plugin.v2bridge.devices.get_zigbee_connectivity(device.id)
                    try:
                        value_dict['zigbee_connectivity'] = str(sensor.status.value)
                    except:
                        value_dict['zigbee_connectivity'] = ''
            value_dict['product_archetype'] = device.product_data.product_archetype.value
            value_dict['certified'] = device.product_data.certified
            value_dict['archetype'] = device.metadata.archetype.value

            result[device.id] = value_dict
        return result

    def idv1_to_id(self, id_v1):

        if id_v1.startswith('/lights/'):
            return id_v1[8:]
        return ''

    # ----------------------------------------------------------------------------------

    def ja_nein(self, value) -> str:
        """
        Bool Wert in Ja/Nein String wandeln

        :param value:
        :return:
        """
        if isinstance(value, bool):
            if value:
                return self.translate('Ja')
            return self.translate('Nein')
        return value


    @cherrypy.expose
    def index(self, scan=None, connect=None, disconnect=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        if scan == 'on':
            self.plugin.discovered_bridges = self.plugin.discover_bridges()

        if connect is not None:
            self.logger.info("Connect: connect={}".format(connect))
            for db in self.plugin.discovered_bridges:
                if db['serialNumber'] == connect:
                    user = self.plugin.create_new_username(db['ip'])
                    if user != '':
                        self.plugin.bridge= db
                        self.plugin.bridge['username'] = user
                        self.plugin.bridge_user = user
                        self.plugin.update_plugin_config()

        if disconnect is not None:
            self.plugin.disconnect_bridge()
            self.plugin.discovered_bridges = self.plugin.discover_bridges()

        try:
            tmpl = self.tplenv.get_template('index.html')
        except:
            self.logger.error("Template file 'index.html' not found")
        else:
            # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
            #self.logger.notice(f"index: {self.plugin.get_parameter_value('webif_pagelength')}")
            return tmpl.render(p=self.plugin, w=self,
                               webif_pagelength=self.plugin.get_parameter_value('webif_pagelength'),
                               item_count=len(self.plugin.plugin_items),

                               bridge=self.plugin.bridge,

#                               bridge_devices=sorted(self.plugin.get_devicesdata().items(), key=lambda k: str.lower(k[1]['id_v1'])),
                               bridge_lights=self.get_lightsdata(),
                               bridge_groups=self.get_groupsdata(),
                               bridge_scenes=self.get_scenesdata(),
                               bridge_sensors=self.get_sensorsdata(),

                               bridge_config=self.plugin.get_bridge_config()
                               )


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
#        self.plugin.logger.info(f"get_data_html: dataSet={dataSet}")
        item_list = []
        light_list = []
        scene_list = []
        group_list = []
        sensor_list = []
        device_list = []
        if dataSet is None or dataSet == 'bridge_info':
            result_array = []

            # callect data for items
            items = self.get_itemsdata()
            for item in items:
                value_dict = {}
                for key in items[item]:
                    value_dict[key] = items[item][key]

                item_list.append(value_dict)


            # callect data for lights
            lights = self.get_lightsdata()
            for light in lights:
                value_dict = {}
                for key in lights[light]:
                    if key != '_full':
                        value_dict[key] = lights[light][key]
                        if key == 'id_v1' and len(value_dict[key].split('/')) > 2:
                            value_dict[key] = value_dict[key].split('/')[2]
                        elif key == 'on':
                            value_dict[key] =  self.ja_nein(value_dict[key])

                light_list.append(value_dict)

            # callect data for scenes
            scenes = self.get_scenesdata()
            for scene in scenes:
                value_dict = {}
                for key in scenes[scene]:
                    if key != '_full':
                        value_dict[key] = scenes[scene][key]
                        if key == 'id_v1' and len(value_dict[key].split('/')) > 2:
                            value_dict[key] = value_dict[key].split('/')[2]

                scene_list.append(value_dict)

            # callect data for groups
            groups = self.get_groupsdata()
            for group in groups:
                value_dict = {}
                for key in groups[group]:
                    if key != '_full':
                        value_dict[key] = groups[group][key]
                        if key == 'id_v1' and len(value_dict[key].split('/')) > 2:
                            value_dict[key] = value_dict[key].split('/')[2]

                group_list.append(value_dict)

            # callect data for sensors
            sensors = self.get_sensorsdata()
            for sensor in sensors:
                value_dict = {}
                for key in sensors[sensor]:
                    if key != '_full':
                        value_dict[key] = sensors[sensor][key]
                        #if key == 'id_v1' and len(value_dict[key].split('/')) > 2:
                        #    value_dict[key] = value_dict[key].split('/')[2]

                sensor_list.append(value_dict)

            # callect data for devices
            devices = self.get_devicesdata()
            for device in devices:
                value_dict = {}
                for key in devices[device]:
                    if key != '_full':
                        value_dict[key] = devices[device][key]
                        #if key == 'id_v1' and len(value_dict[key].split('/')) > 2:
                        #    value_dict[key] = value_dict[key].split('/')[2]

                device_list.append(value_dict)


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

        #result = {'items': item_list, 'devices': device_list, 'broker': broker_data}
        result = {'items': item_list, 'lights': light_list, 'scenes': scene_list, 'groups': group_list, 'sensors': sensor_list, 'devices': device_list}

        # send result to wen interface
        try:
            data = json.dumps(result)
            if data:
                return data
            else:
                return None
        except Exception as e:
            self.logger.error(f"get_data_html exception: {e}")
            self.logger.error(f"- {result}")

        return {}

