#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2021-      Michael Wenzel              wenzel_michael@web.de
#  Copyright 2023-      Sebastian Helms             morg @ knx-Forum
#########################################################################
#  This file is part of SmartHomeNG.
#
#  This plugin connect Zigbee2MQTT to SmartHomeNG.
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

from datetime import datetime
import json

from lib.model.mqttplugin import MqttPlugin
# from .webif import WebInterface

Z2M_TOPIC = 'z2m_topic'
Z2M_ATTR = 'z2m_attr'
Z2M_RO = 'z2m_readonly'
Z2M_WO = 'z2m_writeonly'
Z2M_BVAL = 'z2m_bool_values'
MSEP = '#'


class Zigbee2Mqtt(MqttPlugin):
    """ Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items """

    PLUGIN_VERSION = '2.0.0'

    def __init__(self, sh, **kwargs):
        """ Initializes the plugin. """

        # Call init code of parent class (MqttPlugin)
        super().__init__()

        self.logger.info(f'Init {self.get_shortname()} plugin {self.PLUGIN_VERSION}')

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.z2m_base = self.get_parameter_value('base_topic').lower()
        self.cycle = self.get_parameter_value('poll_period')
        self.read_at_init = self.get_parameter_value('read_at_init')
        self.bool_values = self.get_parameter_value('bool_values')

        self._items_read = []
        self._items_write = []
        self._devices = {'bridge': {'handler_in': self._handle_bridge}}
        # {
        #   'dev1': {
        #       'lastseen': <timestamp>,
        #       'meta': {[...]},  # really needed anymore?
        #       'data': {[...]},
        #       'exposes': {[...]},
        #       'scenes': {'name1': id1, 'name2': id2, [...]},
        #       'handler_in:' <func>,
        #       'handler_out:' <func>,
        #       'attr1': {
        #           'item': item1,
        #           'read': bool,
        #           'write': bool,
        #           'bool_values': ['OFF', 'ON'],
        #           'value': ...
        #           'handler_in:' <func>,
        #           'handler_out:' <func>,
        #       },
        #       'attr2': ...
        #   },
        #   'dev2': ...
        # }

        # Add subscription to get bridge announces
        bridge_subs = [
            ['devices', 'list', None],
            ['state', 'bool', ['offline', 'online']],
            ['info', 'dict', None],
            ['log', 'dict', None],
            ['extensions', 'list', None],
            ['config', 'dict', None],
            ['groups', 'list', None],
            ['response', 'dict', None]
        ]
        for attr, dtype, blist in bridge_subs:
            self.add_z2m_subscription('bridge', attr, '', '', dtype, callback=self.on_mqtt_msg, bool_values=blist)

        # Add subscription to get device announces
        self.add_z2m_subscription('+', '', '', '', 'dict', callback=self.on_mqtt_msg)

    def run(self):
        """ Run method for the plugin """

        self.logger.debug("Run method called")

        self.alive = True

        # start subscription to all topics
        self.start_subscriptions()

        self.scheduler_add('z2m_cycle', self.poll_bridge, cycle=self.cycle)
        self.publish_z2m_topic('bridge', 'config', 'devices', 'get')

        if self.read_at_init:
            self.publish_z2m_topic('bridge', 'request', 'restart')

        try:
            self._read_all_data()
        except Exception:
            pass

    def stop(self):
        """ Stop method for the plugin """

        self.alive = False
        self.logger.debug("Stop method called")
        self.scheduler_remove('z2m_c')

        # stop subscription to all topics
        self.stop_subscriptions()

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

        # remove this block when its included in smartplugin.py,
        # replace with super().parse_item(item)
        # check for suspend item
        if item.property.path == self._suspend_item_path:
            self.logger.debug(f'suspend item {item.property.path} registered')
            self._suspend_item = item
            self.add_item(item, updating=True)
            return self.update_item
        # end block

        if self.has_iattr(item.conf, Z2M_ATTR):
            self.logger.debug(f"parsing item: {item}")

            device = self._get_z2m_topic_from_item(item)
            if not device:
                self.logger.warning(f"parsed item {item} has no {Z2M_TOPIC} set, ignoring")
                return

            attr = self.get_iattr_value(item.conf, Z2M_ATTR).lower()
            bval = self.get_iattr_value(item.conf, Z2M_BVAL)
            if bval == []:
                bval = None
            elif not (bval is None or type(bval) is list):
                bval = self.bool_values

            # invert read-only/write-only logic to allow read/write
            write = not self.get_iattr_value(item.conf, Z2M_RO, False)
            read = not self.get_iattr_value(item.conf, Z2M_WO, False) or not write

            if device not in self._devices:
                self._devices[device] = {}

            if attr not in self._devices[device]:
                self._devices[device][attr] = {}

            self._devices[device][attr].update({
                'value': None,
                'item': item,
                'read': read,
                'write': write,
                'bool_values': bval
            })

            if read and item not in self._items_read:
                self._items_read.append(item)
            if write and item not in self._items_write:
                self._items_write.append(item)

            # use new smartplugin method of registering items
            # <dev>#<attr> needed as mapping, as device or attr
            # by themselves are not unique
            self.add_item(item, {}, device + MSEP + attr, write)
            if write:
                return self.update_item

    def remove_item(self, item):
        if item not in self._plg_item_dict:
            return

        mapping = self.get_item_mapping(item)
        if mapping:
            device, attr = mapping.split(MSEP)

            # remove references in plugin-internal storage
            try:
                del self._devices[device][attr]
            except KeyError:
                pass
            if not self._devices[device]:
                del self._devices[device]

        try:
            self._items_read.remove(item)
        except ValueError:
            pass
        try:
            self._items_write.remove(item)
        except ValueError:
            pass

        super().remove_item(item)

    def update_item(self, item, caller='', source=None, dest=None):
        """
        Item has been updated

        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        :param source:  if given it represents the source
        :param dest:    if given it represents the dest
        """
        self.logger.debug(f"update_item: {item} called by {caller} and source {source}")

        if self.alive and not self.suspended and not caller.startswith(self.get_shortname()):

            if item in self._items_write:

                mapping = self.get_item_mapping(item)
                if not mapping:
                    self.logger.error(f"update_item called for item {item}, but no z2m associations are stored. This shouldn't happen...")
                    return

                self.logger.info(f"update_item: {item}, item has been changed outside of this plugin in {caller} with value {item()}")

                device, attr = mapping.split(MSEP)

                # make access easier and code more readable
                _device = self._devices[device]
                _attr = _device[attr]

                topic_3 = topic_4 = topic_5 = ''
                payload = None
                bool_values = self.bool_values
                try:
                    bool_values = _attr.get('bool_values', self.bool_values)
                except KeyError:
                    pass
                scenes = _device.get('scenes')

                # statically defined cmds for interaction with z2m-gateway
                # independent from connected devices
                bridge_cmds = {
                    'permit_join': {'setval': 'VAL', 't5': ''},
                    'health_check': {'setval': None, 't5': ''},
                    'restart': {'setval': None, 't5': ''},
                    'networkmap': {'setval': 'raw', 't5': 'remove'},
                    'device_remove': {'setval': 'STR', 't5': ''},
                    'device_configure': {'setval': 'STR', 't5': ''},
                    'device_options': {'setval': 'STR', 't5': ''},
                    'device_rename': {'setval': 'STR', 't5': ''}
                }

                if device == 'bridge' and attr in bridge_cmds:
                    topic_3 = 'request'
                    topic_4 = attr
                    topic_5 = bridge_cmds[attr]['t5']
                    payload = ''
                    if attr.startswith('device_'):
                        topic_4, topic_5 = attr.split('_')
                    if bridge_cmds[attr]['setval'] == 'VAL':
                        payload = item()
                    if bridge_cmds[attr]['setval'] == 'STR':
                        payload = str(item())
                    elif bridge_cmds[attr]['setval'] == 'PATH':
                        payload = item.property.path

                    # insert special cases here which don't correspond to
                    # base/device/set with payload "{attr: value}"

# TODO: shall we offer brightness scaled to 100%?
# TODO: shall we offer color_temp as Kelvin?

                else:
                    topic_3 = 'set'
                    value = item()

                    # apply bool_values if present and applicable
                    if bool_values and isinstance(value, bool):
                        value = bool_values[value]

                    # replace scene with index
                    if attr == 'scene_recall' and scenes:
                        try:
                            value = scenes[value]
                        except KeyError:
                            self.logger.warning(f'scene {value} not defined for {device}')
                            return

                    # create payload
                    payload = json.dumps({
                        attr: value
                    })

                if payload is not None:
                    self.publish_z2m_topic(device, topic_3, topic_4, topic_5, payload, item, bool_values=bool_values)
                else:
                    self.logger.warning(f"update_item: {item}, no payload defined (by {caller})")
            else:
                self.logger.warning(f"update_item: {item}, trying to change item in SmartHomeNG that is readonly (by {caller})")

    def poll_bridge(self):
        """ Polls for health state of the bridge """

        self.logger.info("poll_bridge: Checking health status of bridge")
        self.publish_z2m_topic('bridge', 'request', 'health_check')

    def add_z2m_subscription(self, device: str, topic_3: str, topic_4: str, topic_5: str, payload_type: str, bool_values=None, item=None, callback=None):
        """ build the topic in zigbee2mqtt style and add the subscription to mqtt """

        tpc = self._build_topic_str(device, topic_3, topic_4, topic_5)
        self.add_subscription(tpc, payload_type, bool_values=bool_values, callback=callback)

    def publish_z2m_topic(self, device: str, topic_3: str = '', topic_4: str = '', topic_5: str = '', payload='', item=None, qos: int = 0, retain: bool = False, bool_values=None):
        """ build the topic in zigbee2mqtt style and publish to mqtt """

        tpc = self._build_topic_str(device, topic_3, topic_4, topic_5)
        self.publish_topic(tpc, payload, item, qos, retain, bool_values)

    def on_mqtt_msg(self, topic: str, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:           mqtt topic
        :param payload:         mqtt message payload
        :param qos:             qos for this message (unused)
        :param retain:          retain flag for this message (unused)
        """

        z2m_base, device, topic_3, topic_4, topic_5, *_ = (topic + '////').split('/')
        self.logger.debug(f"received mqtt msg: z2m_base={z2m_base}, device={device}, topic_3={topic_3}, topic_4={topic_4}, topic_5={topic_5}, payload={payload}")

        if z2m_base != self.z2m_base:
            self.logger.error(f'received mqtt msg with wrong base topic {topic}. Please report')
            return

        # check handlers
        try:
            if 'handler_in' in self._devices[device]:
                # handler has to return True to continue processing
                if not self._devices[device]['handler_in'](device, topic_3, topic_4, topic_5, payload, qos, retain):
                    return
        except (KeyError, TypeError):
            pass

        if not isinstance(payload, dict):
            return

        # Wenn Geräte zur Laufzeit des Plugins hinzugefügt werden, werden diese im dict ergänzt
        if device not in self._devices:
            self._devices[device] = {}
            self.logger.info(f"New device discovered: {device}")

        # Korrekturen in der Payload

        # Umbenennen des Key 'friendlyName' in 'friendly_name', damit er identisch zu denen aus Log Topic und Config Topic ist
        if 'device' in payload:
            meta = payload['device']
            if 'friendlyName' in meta:
                meta['friendly_name'] = meta.pop('friendlyName')
            del payload['device']

            if 'meta' not in self._devices[device]:
                self._devices[device]['meta'] = {}
            self._devices[device]['meta'].update(meta)

        # Korrektur des Lastseen
        if 'last_seen' in payload:
            last_seen = payload['last_seen']
            if isinstance(last_seen, int):
                payload.update({'last_seen': datetime.fromtimestamp(last_seen / 1000)})
            elif isinstance(last_seen, str):
                try:
                    payload.update({'last_seen': datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%S.%fZ").replace(microsecond=0)})
                except Exception:
                    try:
                        payload.update({'last_seen': datetime.strptime(last_seen, "%Y-%m-%dT%H:%M:%SZ")})
                    except Exception as e:
                        self.logger.debug(f"Error {e} occurred during decoding of last_seen using format '%Y-%m-%dT%H:%M:%SZ'.")

        # # Korrektur der Brightness von 0-254 auf 0-100%
        # if 'brightness' in payload:
        #     try:
        #         payload.update({'brightness': int(round(payload['brightness'] * 100 / 254, 0))})
        #     except Exception as e:
        #         self.logger.debug(f"Error {e} occurred during decoding of brightness.")

        # # Korrektur der Farbtemperatur von "mired scale" (Reziproke Megakelvin) auf Kelvin
        # if 'color_temp' in payload:
        #     try:
        #         # keep mired and "true" kelvin
        #         payload.update({'color_temp_mired': payload['color_temp']})
        #         payload.update({'color_temp_k': int(round(1000000 / int(payload['color_temp']), 0))})
        #
        #         payload.update({'color_temp': int(round(10000 / int(payload['color_temp']), 0)) * 100})
        #     except Exception as e:
        #         self.logger.debug(f"Error {e} occurred during decoding of color_temp.")

        # # Verarbeitung von Farbdaten
        # if 'color_mode' in payload and 'color' in payload:
        #     color_mode = payload['color_mode']
        #     color = payload.pop('color')
        #
        #     if color_mode == 'hs':
        #         payload['hue'] = color['hue']
        #         payload['saturation'] = color['saturation']
        #
        #     if color_mode == 'xy':
        #         payload['color_x'] = color['x']
        #         payload['color_y'] = color['y']

        if 'data' not in self._devices[device]:
            self._devices[device]['data'] = {}
        self._devices[device]['data'].update(payload)

        # Setzen des Itemwertes
        for attr in payload:
            if attr in self._devices[device]:
                value = payload[attr]
                self._devices[device][attr]['value'] = value
                item = self._devices[device][attr].get('item')
                src = self.get_shortname() + ':' + device
                self.logger.debug(f"attribute: {attr}, value: {value}, item: {item}")

                if item is not None:
                    item(value, src)
                    self.logger.info(f"{device}: Item '{item}' set to value {value}")
                else:
                    self.logger.info(f"{device}: No item for attribute '{attr}' defined to set to {value}")

    def _build_topic_str(self, device: str, topic_3: str, topic_4: str, topic_5: str) -> str:
        """ Build the mqtt topic as string """
        return "/".join(filter(None, (self.z2m_base, device, topic_3, topic_4, topic_5)))

    def _get_device_data(self, device_data: list, is_group=False):
        """
        Extract the Zigbee Meta-Data for a certain device out of the device_data

        :param device_data:     Payload of the bridge config message
        :param is_group:        indicates wether device is a real device or a group
        """
        # device_data is list of dicts
        for element in device_data:
            if type(element) is dict:
                device = element.get('friendly_name')
                if device:
                    if 'lastSeen' in element:
                        element.update({'lastSeen': datetime.fromtimestamp(element['lastSeen'] / 1000)})

                    # create device entry if needed
                    if device not in self._devices:
                        self._devices[device] = {'isgroup': is_group}

                    # easier to read
                    _device = self._devices[device]

                    # scenes in devices
                    try:
                        for endpoint in element['endpoints']:
                            if element['endpoints'][endpoint].get('scenes'):
                                _device['scenes'] = {
                                    name: id for id, name in (x.values() for x in element['endpoints'][endpoint]['scenes'])
                                }
                    except KeyError:
                        pass

                    # scenes in groups
                    if element.get('scenes'):
                        _device['scenes'] = {
                            name: id for id, name in (scene.values() for scene in element['scenes'])
                        }

                    # put list of scene names in scenelist item
                    if _device.get('scenelist'):
                        try:
                            scenelist = list(_device['scenes'].keys())
                            _device['scenelist']['item'](scenelist)
                        except (KeyError, ValueError, TypeError):
                            pass

                    # TODO: whatfor? really needed anymore?
                    # just copy meta
                    if 'meta' not in _device:
                        _device['meta'] = {}
                    _device['meta'].update(element)

                    # TODO: parse meta and extract valid values for attrs

                    self.logger.info(f'Imported {"group" if is_group else "device"} {device}')
            else:
                self.logger.debug(f"(Received payload {device_data} is not of type dict")

    def _read_all_data(self):
        """ Try to get current status of all devices linked to items """

        for device in self._devices:
            for attr in self._devices[device]:
                a = self._devices[device][attr]
                if a.get('read', False) and a.get('item') is not None:
                    self.publish_z2m_topic(device, attr, 'get')

#
# special handlers
#

    def _handle_bridge(self, device: str, topic_3: str = "", topic_4: str = "", topic_5: str = "", payload=None, qos=None, retain=None):
        """ handle device topics for "bridge" """

        # catch AssertionError
        try:
            # easier to read
            _bridge = self._devices[device]

            if topic_3 == 'state':
                self.logger.debug(f"state: detail: {topic_3} datetime: {datetime.now()} payload: {payload}")
                # TODO: check - needs bool_values?
                _bridge['online'] = bool(payload)

            elif topic_3 == 'response' and topic_4 in ('health_check', 'permit_join', 'networkmap'):
                assert isinstance(payload, dict), 'dict'
                if topic_4 == 'health_check':
                    _bridge['online'] = bool(payload['data']['healthy'])
                else:
                    _bridge['online'] = True

                _bridge[topic_4] = payload

            elif topic_3 == 'config' and topic_4 == '':
                assert isinstance(payload, dict), 'dict'
                _bridge['config'] = payload

            elif topic_3 == 'devices' or topic_3 == 'groups':
                assert isinstance(payload, list), 'list'
                self._get_device_data(payload, topic_4 == 'groups')

                for entry in payload:
                    friendly_name = entry.get('friendly_name')
                    try:
                        exposes = entry['definition']['exposes']
                    except (KeyError, TypeError):
                        pass
                    else:
                        if friendly_name in self._devices:
                            self._devices[friendly_name]['exposes'] = exposes

            elif topic_3 == 'log':
                assert isinstance(payload, dict), 'dict'
                if 'message' in payload and 'type' in payload:
                    message = payload['message']
                    message_type = payload['type']
                    if message_type == 'devices' and isinstance(message, list):
                        self._get_device_data(message)

            elif topic_3 == 'info' and topic_4 == '':
                assert isinstance(payload, dict), 'dict'
                if isinstance(payload, dict):
                    _bridge['info'] = payload
                    _bridge['online'] = True

            else:
                self.logger.debug(f"Function type message bridge/{topic_3} not implemented yet.")
        except AssertionError as e:
            self.logger.debug(f'Response format not of type {e}, ignoring data')

    def _get_z2m_topic_from_item(self, item) -> str:
        """ Get z2m_topic for given item search from given item in parent direction """

        topic = ''
        lookup_item = item
        for _ in range(3):
            topic = self.get_iattr_value(lookup_item.conf, Z2M_TOPIC)
            if topic:
                break
            else:
                lookup_item = lookup_item.return_parent()

        return topic

    def _item_color_xy_to_rgb(self, item_xy, item_brightness, item_r, item_g, item_b):
        """ convert xy and brightness item data to rgb and assign """
        try:
            x = item_xy()['x']
            y = item_xy()['y']
        except (ValueError, TypeError, KeyError):
            self.logger.warning(f"Item {item_xy} doesn't contain a valid {{'x': x, 'y': y}} color definition: {item_xy()}")
            return

        try:
            bright = item_brightness()
            if bright < 0 or bright > 254:
                raise TypeError
        except (ValueError, TypeError):
            self.logger.warning(f"Item {item_brightness} doesn't contain a valid brightness value: {item_brightness()}")
            return

        r, g, b = self._color_xy_to_rgb(x, y, bright)

        try:
            item_r(r)
            item_g(g)
            item_b(b)
        except (ValueError, TypeError):
            self.logger.warning(f"Error on assigning rgb values {r},{g},{b} to items {item_r}, {item_g}, {item_b}")

    def _item_color_rgb_to_xy(self, item_r, item_g, item_b, item_xy, item_brightness):
        """ convert r, g, b items data to xy and brightness and assign """
        try:
            r = item_r()
            g = item_g()
            b = item_b()
        except (ValueError, TypeError):
            self.logger.warning(f"Error on getting rgb values from items {item_r}, {item_g}, {item_b}")
            return

        x, y, bright = self._color_rgb_to_xy(r, g, b)

        try:
            item_xy({'x': x, 'y': y})
            item_brightness(bright)
        except (ValueError, TypeError):
            self.logger.warning(f"Error on assigning values {x},{y}, {bright} to items {item_xy} and {item_brightness}")
            return

#
# TODO: check correctness of calculations
#

    def _color_xy_to_rgb(self, x: float, y: float, brightness: int):
        """
        convert xy color value to Wide RGB

        x, y are given as float 0.0...1.0
        brightness is given as 0..255

        returns a tuple (r, g, b) (0..255)
        """

        z = 1.0 - y - x

        # calculate XYZ
        Y = float(brightness) / 254.0
        X = (Y / y) * x
        Z = (Y / y) * z

        # calculate rgb
        rg = X * 1.612 - Y * 0.203 - Z * 0.302
        gg = -X * 0.509 + Y * 1.412 + Z * 0.066
        bg = X * 0.026 - Y * 0.072 + Z * 0.962

        # remove gamma correction
        if rg <= 0.0031308:
            r = 0.0031308
        else:
            r = 12.92 * rg
        if gg <= 0.0031308:
            g = 0.0031308
        else:
            g = 12.92 * gg
        if bg <= 0.0031308:
            b = 0.0031308
        else:
            b = 12.92 * bg

        # return (round(r * 255, 0), round(g * 255, 0), round(b * 255, 0))
        return (r, g, b)

    def _color_rgb_to_xy(self, r: int, g: int, b: int):
        """
        convert Wide RGB color value to xy

        r, g, b are given as byte value 0..255
        returns tuple (x, y, brightness)
        """

        # normalize
        r1 = float(r) / 255.0
        g1 = float(g) / 255.0
        b1 = float(b) / 255.0

        # apply gamma correction
        if r1 > 0.04045:
            rg = ((r1 + 0.055) / 1.055) ** 2.4
        else:
            rg = r1 / 12.92
        if g1 > 0.04045:
            gg = ((g1 + 0.055) / 1.055) ** 2.4
        else:
            gg = g1 / 12.92
        if b1 > 0.04045:
            bg = ((b1 + 0.055) / 1.055) ** 2.4
        else:
            bg = b1 / 12.92

        # calculate XYZ values
        X = rg * 0.649926 + gg * 0.103455 + bg * 0.197109
        Y = rg * 0.234327 + gg * 0.743075 + bg * 0.022598
        Z = rg * 0.0000000 + gg * 0.053077 + bg * 1.035763

        # convert to xy
        x = X / (X + Y + Z)
        y = Y / (X + Y + Z)

        return (x, y, round(Y * 254, 0))
