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

from .rgbxy import Converter
# from .webif import WebInterface

Z2M_TOPIC = 'z2m_topic'
Z2M_ATTR = 'z2m_attr'
Z2M_RO = 'z2m_readonly'
Z2M_WO = 'z2m_writeonly'
Z2M_BVAL = 'z2m_bool_values'
MSEP = '#'

HANDLE_IN_PREFIX = '_handle_in_'
HANDLE_OUT_PREFIX = '_handle_out_'
HANDLE_DEV = 'dev_'
HANDLE_ATTR = 'attr_'


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
        self._devices = {'bridge': {}}
        # {
        #   'dev1': {
        #       'lastseen': <timestamp>,
        #       'meta': {[...]},  # really needed anymore?
        #       'data': {[...]},
        #       'exposes': {[...]},
        #       'scenes': {'name1': id1, 'name2': id2, [...]},
        #       'attr1': {
        #           'item': item1,
        #           'read': bool,
        #           'write': bool,
        #           'bool_values': ['OFF', 'ON'],
        #           'value': ...
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

            if item.type() == 'bool':
                bval = self.get_iattr_value(item.conf, Z2M_BVAL)
                if bval == []:
                    bval = None
                if bval is None or type(bval) is not list:
                    bval = self.bool_values

            # invert read-only/write-only logic to allow read/write
            write = not self.get_iattr_value(item.conf, Z2M_RO, False)
            read = not self.get_iattr_value(item.conf, Z2M_WO, False) or not write

            if device not in self._devices:
                self._devices[device] = {}

            if attr not in self._devices[device]:
                self._devices[device][attr] = {}

            data = {
                'value': None,
                'item': item,
                'read': read,
                'write': write,
            }
            if item.type() == 'bool':
                data['bval'] = bval

            self._devices[device][attr].update(data)

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

                # pre-set values
                topic_3 = 'set'
                topic_4 = topic_5 = ''
                payload = None
                bool_values = _attr.get('bool_values', self.bool_values)
                scenes = _device.get('scenes')
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

                # check device handler
                if hasattr(self, HANDLE_OUT_PREFIX + HANDLE_DEV + device):
                    value, topic_3, topic_4, topic_5, abort = getattr(self, HANDLE_OUT_PREFIX + HANDLE_DEV + device)(item, value, topic_3, topic_4, topic_5, device, attr)
                    if abort:
                        self.logger.debug(f'processing of item {item} stopped due to abort statement from handler {HANDLE_OUT_PREFIX + HANDLE_DEV + device}')
                        return

                # check attribute handler
                if hasattr(self, HANDLE_OUT_PREFIX + HANDLE_ATTR + attr):
                    value, topic_3, topic_4, topic_5, abort = getattr(self, HANDLE_OUT_PREFIX + HANDLE_ATTR + attr)(item, value, topic_3, topic_4, topic_5, device, attr)
                    if abort:
                        self.logger.debug(f'processing of item {item} stopped due to abort statement from handler {HANDLE_OUT_PREFIX + HANDLE_ATTR + attr}')
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
        if hasattr(self, HANDLE_IN_PREFIX + HANDLE_DEV + device):
            if getattr(self, HANDLE_IN_PREFIX + HANDLE_DEV + device)(device, topic_3, topic_4, topic_5, payload, qos, retain):
                return

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
                item = self._devices[device][attr].get('item')
                src = self.get_shortname() + ':' + device

                # check handlers
                if hasattr(self, HANDLE_IN_PREFIX + HANDLE_ATTR + attr):
                    if getattr(self, HANDLE_IN_PREFIX + HANDLE_ATTR + attr)(device, attr, payload, item):
                        return

                value = payload[attr]
                self._devices[device][attr]['value'] = value
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
                    # key "scenelist" only present if attr/device requested in item tree
                    if _device.get('scenelist'):
                        try:
                            scenelist = list(_device['scenes'].keys())
                            _device['scenelist']['item'](scenelist)
                        except (KeyError, ValueError, TypeError):
                            pass

                    # TODO: possibly remove after further parsing
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

#
# special handlers for devices / attributes
#
# handlers_in:  activated if values come in from mqtt
#
# def handle_in_dev_<device>(self, device: str, topic_3: str = "", topic_4: str = "", topic_5: str = "", payload={}, qos=None, retain=None)
# def handle_in_attr_<attr>(self, device: str, attr: str, payload={}, item=None)
#
# return True: stop further processing
# return False/None: continue processing (possibly with changed payload)
#

    def _handle_in_dev_bridge(self, device: str, topic_3: str = "", topic_4: str = "", topic_5: str = "", payload={}, qos=None, retain=None):
        """ handle device topics for "bridge" """

        # catch AssertionError
        try:
            # easier to read
            _bridge = self._devices[device]

            if topic_3 == 'state':
                self.logger.debug(f"state: detail: {topic_3} datetime: {datetime.now()} payload: {payload}")
                _bridge['online'] = bool(payload)

            elif topic_3 in ('config', 'info'):
                assert isinstance(payload, dict), 'dict'
                _bridge[topic_3] = payload
                _bridge['online'] = True

            elif topic_3 == 'response' and topic_4 in ('health_check', 'permit_join', 'networkmap'):
                assert isinstance(payload, dict), 'dict'
                _bridge[topic_4] = payload
                _bridge['online'] = True

                if topic_4 == 'health_check':
                    _bridge['online'] = bool(payload['data']['healthy'])

            elif topic_3 == 'devices' or topic_3 == 'groups':
                assert isinstance(payload, list), 'list'
                self._get_device_data(payload, topic_4 == 'groups')

                for entry in payload:
                    friendly_name = entry.get('friendly_name')
                    if friendly_name in self._devices:
                        try:
                            self._devices[friendly_name]['exposes'] = entry['definition']['exposes']
                        except (KeyError, TypeError):
                            pass

            elif topic_3 == 'log':
                assert isinstance(payload, dict), 'dict'
                if 'message' in payload and payload.get('type') == 'devices':
                    self._get_device_data(payload['message'])

            else:
                self.logger.debug(f"Function type message bridge/{topic_3}/{topic_4} not implemented yet.")
        except AssertionError as e:
            self.logger.debug(f'Response format not of type {e}, ignoring data')

    def _handle_in_attr_color(self, device: str, attr: str, payload={}, item=None):
        """ automatically sync rgb items """
        if item is not None:
            col = payload['color']
            if 'x' in col and 'y' in col and 'brightness' in payload:
                r, g, b = self._color_xy_to_rgb(color=col, brightness=payload['brightness'] / 254)
                try:
                    items_default = True
                    item_r = item.r
                    item_g = item.g
                    item_b = item.b
                except AttributeError:
                    items_default = False

                try:
                    items_custom = True
                    # try to get user-specified items to override default
                    item_r = self._devices[device]['color_r']['item']
                    item_g = self._devices[device]['color_g']['item']
                    item_b = self._devices[device]['color_b']['item']
                except (AttributeError, KeyError):
                    items_custom = False

                if not items_default and not items_custom:
                    return

                try:
                    item_r(r, self.get_shortname())
                    item_g(g, self.get_shortname())
                    item_b(b, self.get_shortname())
                except Exception as e:
                    self.logger.warning(f'Trying to set rgb color values for color item {item}, but appropriate subitems ({item_r}, {item_g}, {item_b}) missing: {e}')

                try:
                    target = self._devices[device]['color_rgb']['item']
                except (AttributeError, KeyError):
                    return
                target(f'{r:x}{g:x}{b:x}', self.get_shortname())

    def _handle_in_attr_brightness(self, device: str, attr: str, payload={}, item=None):
        """ automatically set brightness percent """
        if item is not None:
            target = None
            try:
                target = item.percent
            except AttributeError:
                pass

            try:
                target = self._devices[device]['brightness_percent']['item']
            except (AttributeError, KeyError):
                pass

            if target is not None:
                target(payload['brightness'] / 2.54, self.get_shortname())

    def _handle_in_attr_color_temp(self, device: str, attr: str, payload={}, item=None):
        """ automatically set color temp in kelvin """
        if item is not None:
            target = None
            try:
                target = item.kelvin
            except AttributeError:
                pass

            try:
                target = self._devices[device]['color_temp_kelvin']['item']
            except (AttributeError, KeyError):
                pass

            if target is not None:
                target(int(1000000 / payload['color_temp']), self.get_shortname())

#
# handlers out: activated when values are sent out from shng
#
# def _handle_out_<device/attr>(self, item, value, topic_3, topic_4, topic_5, device, attr):
#     return value, topic_3, topic_4, topic_5, abort
#

    def _handle_out_dev_bridge(self, item, value, topic_3, topic_4, topic_5, device, attr):
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

        if attr in bridge_cmds:
            topic_3 = 'request'
            topic_4 = attr
            topic_5 = bridge_cmds[attr]['t5']
            payload = ''
            if attr.startswith('device_'):
                topic_4, topic_5 = attr.split('_')
            if bridge_cmds[attr]['setval'] == 'VAL':
                payload = value
            if bridge_cmds[attr]['setval'] == 'STR':
                payload = str(value)
            elif bridge_cmds[attr]['setval'] == 'PATH':
                payload = item.property.path

            value = payload

        return value, topic_3, topic_4, topic_5, False

    def _handle_out_attr_color_r(self, item, value, topic_3, topic_4, topic_5, device, attr):
        try:
            self._color_sync_from_rgb(self._devices[device]['state']['item'])
        except Exception as e:
            self.logger.debug(f'problem calling color sync: {e}')
        return value, topic_3, topic_4, topic_5, True

    def _handle_out_attr_color_g(self, item, value, topic_3, topic_4, topic_5, device, attr):
        try:
            self._color_sync_from_rgb(self._devices[device]['state']['item'])
        except Exception as e:
            self.logger.debug(f'problem calling color sync: {e}')
        return value, topic_3, topic_4, topic_5, True

    def _handle_out_attr_color_b(self, item, value, topic_3, topic_4, topic_5, device, attr):
        try:
            self._color_sync_from_rgb(self._devices[device]['state']['item'])
        except Exception as e:
            self.logger.debug(f'problem calling color sync: {e}')
        return value, topic_3, topic_4, topic_5, True

    def _handle_out_attr_brightness_percent(self, item, value, topic_3, topic_4, topic_5, device, attr):
        brightness = value * 2.54
        try:
            self._devices[device]['brightness']['item'](brightness)
        except (KeyError, AttributeError):
            pass
        return value, topic_3, topic_4, topic_5, True

    def _handle_out_attr_color_temp_kelvin(self, item, value, topic_3, topic_4, topic_5, device, attr):
        kelvin = int(1000000 / value)
        try:
            self._devices[device]['color_temp']['item'](kelvin)
        except (KeyError, AttributeError):
            pass
        return value, topic_3, topic_4, topic_5, True

    def _handle_out_attr_color_rgb(self, item, value, topic_3, topic_4, topic_5, device, attr):
        if item is not None:
            try:
                col = {}
                rgb = item()
                col['r'] = int(rgb[0:2], 16)
                col['g'] = int(rgb[2:4], 16)
                col['b'] = int(rgb[4:6], 16)

                for color in ('r', 'g', 'b'):
                    target = None
                    try:
                        target = getattr(item.return_parent(), color)
                    except AttributeError:
                        pass

                    try:
                        target = self._devices[device]['color_' + color]['item']
                    except (AttributeError, KeyError):
                        pass

                    if target is not None:
                        target(col[color], self.get_shortname())

                self._color_sync_from_rgb(self._devices[device]['state']['item'])

            except Exception as e:
                self.logger.debug(f'problem calling color sync: {e}')

        return value, topic_3, topic_4, topic_5, True

#
# Attention - color conversions xy/rgb:
# due to - probably - rounding differences, this ist not a true
# 1:1 conversion. Use at your own discretion...
#

    def _color_xy_to_rgb(self, color={}, x=None, y=None, brightness=1):
        if color:
            x = color.get('x')
            y = color.get('y')
        c = Converter()
        return c.xy_to_rgb(x, y, brightness)

    def _color_rgb_to_xy(self, r, g, b):
        c = Converter()
        return c.rgb_to_xyb(r, g, b)

    def _color_sync_to_rgb(self, item, source=''):
        """ sync xy color to rgb, needs struct items """
        self._item_color_xy_to_rgb(item.color, item.brightness, item.color.r, item.color.g, item.color.b, source)

    def _color_sync_from_rgb(self, item, source='', rgb=''):
        """ sync rgb color to xy, needs struct items """
        self._item_color_rgb_to_xy(item.color.r, item.color.g, item.color.b, item.color, item.brightness, source)

    def _item_color_xy_to_rgb(self, item_xy, item_brightness, item_r, item_g, item_b, source=''):
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
            bright /= 254
        except (ValueError, TypeError):
            self.logger.warning(f"Item {item_brightness} doesn't contain a valid brightness value: {item_brightness()}")
            return

        r, g, b = self._color_xy_to_rgb(x=x, y=y, brightness=bright)

        try:
            item_r(r, source)
            item_g(g, source)
            item_b(b, source)
        except (ValueError, TypeError):
            self.logger.warning(f"Error on assigning rgb values {r},{g},{b} to items {item_r}, {item_g}, {item_b}")

    def _item_color_rgb_to_xy(self, item_r, item_g, item_b, item_xy, item_brightness, source=''):
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
            item_xy({'x': x, 'y': y}, source)
            item_brightness(bright * 254, source)
        except (ValueError, TypeError):
            self.logger.warning(f"Error on assigning values {x},{y}, {bright} to items {item_xy} and {item_brightness}")
            return
