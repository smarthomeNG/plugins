#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Jens Höppner                      mail@jens-hoeppner.de
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

from typing import Pattern, Dict, Union
import re
from jinja2 import Environment, FileSystemLoader
import cherrypy
from lib.module import Modules
from lib.model.smartplugin import *
from lib.network import Network
from plugins.unifi.ubiquiti.unifi import API as UniFiAPI
from plugins.unifi.ubiquiti.unifi import DataException as UniFiDataException
import ruamel.yaml as yaml
from requests.exceptions import ConnectionError
import json
import traceback


class UniFiConst(object):
    PARAMETER_URL = 'unifi_controller_url'
    PARAMETER_USER = 'unifi_user'
    PARAMETER_PWD = 'unifi_password'
    PARAMETER_SITE_ID = 'unifi_site_id'
    PARAMETER_CYCLE_TIME = 'poll_cycle_time'

    ATTR_TYPE = 'unifi_type'
    TYPE_CL_PRESENT = 'client_present'
    TYPE_CL_IP = 'client_ip'
    TYPE_CL_HOSTNAME = 'client_hostname'
    TYPE_CL_AT_AP = 'client_present_at_ap'
    TYPE_SW_PORT_ENABLED = 'switch_port_enabled'
    TYPE_SW_PORT_PROFILE = 'switch_port_profile'
    TYPE_AP_ENABLED = 'ap_enabled'
    TYPE_DV_IP = 'device_ip'
    TYPE_DV_NAME = 'device_name'

    ATTR_MAC = 'mac'
    ATTR_SW_MAC = 'unifi_switch_mac'
    ATTR_DV_MAC = 'unifi_device_mac'
    ATTR_AP_MAC = 'unifi_ap_mac'
    ATTR_SW_PORT_NO = 'unifi_switch_port_no'
    ATTR_SW_PORT_PROF_ON = 'unifi_switch_port_profile_on'
    ATTR_SW_PORT_PROF_OFF = 'unifi_switch_port_profile_off'


class UniFiItemIssue(object):
    def __init__(self, itemPath: str):
        self.issues = []
        self.item = itemPath
        self.worst_level = 0

    def append_issue(self, issue, level):
        if self.issues.__contains__(issue):
            return
        self.issues.append(issue)
        if self.worst_level < level:
            self.worst_level = level

    def get_issues(self):
        return self.issues

    def get_worst_level(self):
        return self.worst_level


class UniFiControllerClientModel():

    def __init__(self, api: UniFiAPI):
        self._items = []
        self._items_with_issues = {}
        self._api = api

    def append_item(self, item):
        self._items.append(item)

    def append_item_issue(self, item, issue, level):
        ipath = item.path()
        if not self._items_with_issues.__contains__(ipath):
            self._items_with_issues[ipath] = UniFiItemIssue(ipath)

        self._items_with_issues[ipath].append_issue(issue, level)

    def get_items_with_issues_count(self):
        return len(self._items_with_issues)

    def get_items_with_issues(self):
        for x in self._items_with_issues:
            yield self._items_with_issues[x]

    def get_item_issues(self, item_path):
        if not self._items_with_issues.__contains__(item_path):
            return UniFiItemIssue(item_path)
        return self._items_with_issues[item_path]

    def get_item_count(self):
        """
        Returns number of added items
        """
        return len(self._items)

    def get_items(self, filter=None):
        """
        Returns added items

        :return: array of items held by the device
        """
        to_ret = []
        if filter is None:
            return self._items

        for i in self._items:
            if filter(i):
                to_ret.append(i)
        return to_ret

    def _generate_item_key(self, source:str):
        step1 = source.lower().replace(' ', '_')
        step2 = re.sub('[^0-9a-z_]+', '_', step1)
        return step2.replace("___", "_").replace("__", "_")

    def _get_device_node_item(self, node_data, parent_type=""):
        n = node_data['node']
        node_key = self._generate_item_key(n['key'])
        node_body = {}

        if n['type'] == "wired_client":
            node_body[UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_PRESENT
            node_body['mac'] = n['mac']
            node_body['type'] = 'bool'
            node_body['hostname'] = {}
            node_body['hostname'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_HOSTNAME
            node_body['hostname']['type'] = 'str'
            node_body['ip'] = {}
            node_body['ip'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_IP
            node_body['ip']['type'] = 'str'
        elif n['type'] == 'uap':
            node_body[UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_AP_ENABLED
            node_body[UniFiConst.ATTR_AP_MAC] = n['mac']
            node_body['type'] = 'bool'
            node_body['ap_name'] = {}
            node_body['ap_name']['unifi_type'] = UniFiConst.TYPE_DV_NAME
            node_body['ap_name']['type'] = 'str'
            node_body['ip'] = {}
            node_body['ip'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_DV_IP
            node_body['ip']['type'] = 'str'
        elif n['type'] == 'ugw':
            node_body[UniFiConst.ATTR_DV_MAC] = n['mac']
            node_body['type'] = 'foo'
            node_body['ip'] = {}
            node_body['ip'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_DV_IP
            node_body['ip']['type'] = 'str'
        elif n['type'] == 'usw':
            node_body[UniFiConst.ATTR_SW_MAC] = n['mac']
            node_body['type'] = 'foo'
            node_body['switch_name'] = {}
            node_body['switch_name'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_DV_NAME
            node_body['switch_name']['type'] = 'str'
            node_body['ip'] = {}
            node_body['ip'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_DV_IP
            node_body['ip']['type'] = 'str'

        if parent_type == 'usw':
            node_body[UniFiConst.ATTR_SW_PORT_NO] = n['uplink_remote_port']

        if n['type'] == 'usw':
            portmap = {}

            for child in node_data['children']:
                child_data = self._get_device_node_item(child, n['type'])
                port_no = child_data[1][UniFiConst.ATTR_SW_PORT_NO]
                if not portmap.__contains__(port_no):
                    portmap[port_no] = []
                portmap[port_no].append(child_data)

            for port_no in portmap:
                if len(portmap[port_no]) == 1:
                    single_dev_key = portmap[port_no][0][0]
                    node_body[single_dev_key] = portmap[port_no][0][1]
                    node_body[single_dev_key]['port_enabled'] = {}
                    node_body[single_dev_key]['port_enabled']['type'] = 'bool'
                    node_body[single_dev_key]['port_enabled'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_SW_PORT_ENABLED
                    # Removed Port-Prof-Off as the default will be considered during run-time.
                    # node_body[single_dev_key]['port_enabled'][UniFiConst.ATTR_SW_PORT_PROF_OFF] = 'Disabled'
                    try:
                        node_body[single_dev_key]['port_enabled'][UniFiConst.ATTR_SW_PORT_PROF_ON] = self._api.get_port_profile_for(
                            n['mac'], port_no)
                    except:
                        pass
                else:
                    attached_clnts = {}
                    for ch in portmap[port_no]:
                        ch[1].__delitem__(UniFiConst.ATTR_SW_PORT_NO)
                        attached_clnts[ch[0]] = ch[1]

                    attached_clnts[UniFiConst.ATTR_SW_PORT_NO] = port_no
                    attached_clnts['port_enabled'] = {}
                    attached_clnts['port_enabled']['type'] = 'bool'
                    attached_clnts['port_enabled'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_SW_PORT_ENABLED
                    # Removed Port-Prof-Off as the default will be considered during run-time.
                    #attached_clnts['port_enabled'][UniFiConst.ATTR_SW_PORT_PROF_OFF] = 'Disabled'
                    try:
                        attached_clnts['port_enabled'][UniFiConst.ATTR_SW_PORT_PROF_ON] = self._api.get_port_profile_for(
                            n['mac'], port_no)
                    except:
                        pass
                    node_body["non_unifi_switch_at_port_{}".format(port_no)] = attached_clnts
        else:
            for child in node_data['children']:
                child_data = self._get_device_node_item(child, n['type'])
                node_body[child_data[0]] = child_data[1]

        return (node_key, node_body)

    def get_item_hierarchy(self):
        hr = "Fehler"
        try:
            hr = self._api.get_device_hierarchy()
        except Exception as e:
            return traceback.format_exc()

        try:
            model = {}
            model['unifi_network'] = {}
            model['unifi_network']['wifi_clients'] = {}
            for wlc_data in hr['wireless_clients']:
                wlc_key = "client_" + self._generate_item_key(wlc_data['name'])
                wlc_body = {}
                wlc_body['hostname'] = {}
                wlc_body['hostname']['type'] = 'str'
                wlc_body['hostname'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_HOSTNAME
                wlc_body['ip'] = {}
                wlc_body['ip']['type'] = 'str'
                wlc_body['ip'][UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_IP
                wlc_body[UniFiConst.ATTR_TYPE] = UniFiConst.TYPE_CL_PRESENT
                wlc_body[UniFiConst.ATTR_MAC] = wlc_data['mac']
                wlc_body['type'] = 'bool'
                model['unifi_network']['wifi_clients'][wlc_key] = wlc_body

            model['unifi_network']['devices'] = {}
            for dev in hr['devices']:
                child_data = self._get_device_node_item(dev)
                model['unifi_network']['devices'][child_data[0]] = child_data[1]

            return yaml.dump(model, Dumper=yaml.SafeDumper, indent=4, width=768, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            return "{}\n\nRaw data:\n{}".format(traceback.format_exc(), json.dumps(hr, indent=4))

    def get_total_number_of_requests_to_controller(self):
        try:
            return self._api.get_request_count()
        except Exception:
            return -1

    def get_controller_url(self):
        return self._api.get_connection_data()['url']

    def get_controller_user(self):
        return self._api.get_connection_data()['user']

    def get_controller_site(self):
        return self._api.get_connection_data()['site']


class UniFiControllerClient(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.6.1'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.yaml.
        """

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._unifi_controller_url = self.get_parameter_value(UniFiConst.PARAMETER_URL)
        self._unifi_user = self.get_parameter_value(UniFiConst.PARAMETER_USER)
        self._unifi_password = self.get_parameter_value(UniFiConst.PARAMETER_PWD)
        self._unifi_site_id = self.get_parameter_value(UniFiConst.PARAMETER_SITE_ID)

        self._model = UniFiControllerClientModel(UniFiAPI(username=self._unifi_user,
                                                          password=self._unifi_password,
                                                          site=self._unifi_site_id,
                                                          baseurl=self._unifi_controller_url,
                                                          verify_ssl=False))

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = self.get_parameter_value(UniFiConst.PARAMETER_CYCLE_TIME)
        self._logging = True

        self.init_webinterface()

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well
        self.scheduler_add('poll_unifi', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

        try:
            self._model._api.login()
        except Exception as e:
            self.logger.error(repr(e))
        try:
            self.poll_device()
        except Exception as e:
            self.logger.error(repr(e))

        self._logging = False

    def stop(self):
        """
        Stop method for the plugin
        """
        try:
            self._model._api.logout()
            self.logger.debug("Logout done")
        except:
            self.logger.warning("Exception during logout")
        self.alive = False

    def _log_item_info(self, item, msg: str, enable_logging=True, defaulting=False):
        if defaulting:
            self._model.append_item_issue(item, "2: " + msg, 2)
        else:
            self._model.append_item_issue(item, "1: "+msg, 1)

        if enable_logging:
            self.logger.info(msg + " in item " + item.path())

    def _log_item_warning(self, item, msg: str, enable_logging=True):
        self._model.append_item_issue(item, "3: "+msg, 3)
        if enable_logging:
            self.logger.warning(msg + " in item " + item.path())

    def _log_item_error(self, item, msg: str, enable_logging=True):
        self._model.append_item_issue(item, "4: " + msg, 4)
        if enable_logging:
            self.logger.error(msg + " in item " + item.path())

    def _mac_check(self, item, item_type: str, leaf_item=None):
        if not Network.is_mac(self.get_iattr_value(item.conf, item_type)):
            self._log_item_error(item, "invalid {} attribute provided from {}".format(item_type, item.path()))
            return False
        return True

    def _get_attribute_recursive(self, item, item_type: str, check=None, enable_logging=True, leaf_item=None):
        if item is None:
            self._log_item_warning(leaf_item, "No {} attribute provided".format(item_type), enable_logging)
            return None
        if leaf_item is None:
            leaf_item = item

        try:
            if item_type in item.conf:
                if not check is None:
                    if not check(item, item_type, leaf_item):
                        return None
                if not (item.path() == leaf_item.path()):
                    self._log_item_info(leaf_item, "{} attribute provided from {}".format(
                        item_type, item.path()), enable_logging)
                return self.get_iattr_value(item.conf, item_type)
        except AttributeError:
            self._log_item_warning(leaf_item, "No {} attribute provided".format(item_type), enable_logging)
            return None
        return self._get_attribute_recursive(item.return_parent(), item_type, check, enable_logging, leaf_item)

    def _get_one_of_attr_recursive(self, item, item_types: list, check=None, enable_logging=True, leaf_item=None):
        if item is None:
            self._log_item_warning(leaf_item, "No {} attribute provided".format(json.dump(item_types)), enable_logging)
            return None
        if leaf_item is None:
            leaf_item = item

        for item_type in item_types:
            try:
                if item_type in item.conf:
                    if not check is None:
                        if not check(item, item_type, leaf_item):
                            return None
                    if not (item.path() == leaf_item.path()):
                        self._log_item_info(leaf_item, "{} attribute provided from {} ".format(
                            item_type, item.path()), enable_logging)

                    return self.get_iattr_value(item.conf, item_type)
            except AttributeError:
                self._log_item_warning(leaf_item, "No {} attribute provided".format(item_type), enable_logging)
                return None
        return self._get_one_of_attr_recursive(item.return_parent(), item_types, check, enable_logging, leaf_item)

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
        if not self.has_iattr(item.conf, UniFiConst.ATTR_TYPE):
            return

        i_attr = self.get_iattr_value(item.conf, UniFiConst.ATTR_TYPE)
        if i_attr in [UniFiConst.TYPE_CL_PRESENT, UniFiConst.TYPE_CL_IP, UniFiConst.TYPE_CL_AT_AP, UniFiConst.TYPE_CL_HOSTNAME]:
            cl_mac = self._get_attribute_recursive(item, UniFiConst.ATTR_MAC, check=self._mac_check)
            if cl_mac is None:
                return
            self._model.append_item(item)

        elif i_attr in [UniFiConst.TYPE_AP_ENABLED]:
            ap_mac = self._get_attribute_recursive(item, UniFiConst.ATTR_AP_MAC, check=self._mac_check)
            if ap_mac is None:
                return
            self._model.append_item(item)
            return self.update_item

        elif i_attr in [UniFiConst.TYPE_DV_IP, UniFiConst.TYPE_DV_NAME]:
            dv_mac = self._get_one_of_attr_recursive(
                item, [UniFiConst.ATTR_AP_MAC, UniFiConst.ATTR_SW_MAC, UniFiConst.ATTR_DV_MAC], check=self._mac_check)
            if dv_mac is None:
                return
            self._model.append_item(item)
            return

        elif i_attr in [UniFiConst.TYPE_SW_PORT_PROFILE]:
            sw_mac = self._get_attribute_recursive(item, UniFiConst.ATTR_SW_MAC, check=self._mac_check)
            if sw_mac is None:
                return
            self._model.append_item(item)
            return self.update_item

        elif i_attr in [UniFiConst.TYPE_SW_PORT_ENABLED]:
            sw_mac = self._get_attribute_recursive(item, UniFiConst.ATTR_SW_MAC, check=self._mac_check)
            if sw_mac is None:
                return
            prof_on = self._get_attribute_recursive(item, UniFiConst.ATTR_SW_PORT_PROF_ON)
            if prof_on is None:
                self._log_item_info(
                    item, "Will use 'All' as port profile for on (https://help.ubnt.com/hc/en-us/articles/219654087-UniFi-Using-VLANs-with-UniFi-Wireless-Routing-Switching-Hardware#USW)", defaulting=True)
            prof_off = self._get_attribute_recursive(item, UniFiConst.ATTR_SW_PORT_PROF_OFF)
            if prof_off is None:
                self._log_item_info(
                    item, "Will use 'Disabled' as port profile for off (https://help.ubnt.com/hc/en-us/articles/219654087-UniFi-Using-VLANs-with-UniFi-Wireless-Routing-Switching-Hardware#USW)", defaulting=True)
            self._model.append_item(item)
            return self.update_item

        else:
            self._log_item_error(item, "{} {} unknown".format(UniFiConst.ATTR_TYPE, i_attr))
            self._model.append_item(item)

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        # if 'xxx' in logic.conf:
        # self.function(logic['name'])
        pass

    def _update_unifi_with_item(self, item, item_type, func):
        if self._item_filter(item, UniFiConst.ATTR_TYPE, item_type):
            try:
                func(item)
            except Exception as e:
                self._log_item_error(item, repr(e), self._logging)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != self.get_shortname():

            self._update_unifi_with_item(item, UniFiConst.TYPE_AP_ENABLED, lambda i: self._model._api.set_device_disabled(
                device_mac=self._get_attribute_recursive(
                    i, UniFiConst.ATTR_AP_MAC, check=self._mac_check, enable_logging=self._logging),
                disabled=not i())
            )

            self._update_unifi_with_item(item, UniFiConst.TYPE_SW_PORT_ENABLED, lambda i: self._model._api.set_port_profile_for(
                switch_mac=self._get_attribute_recursive(
                    i, UniFiConst.ATTR_SW_MAC, check=self._mac_check, enable_logging=self._logging),
                port_number=int(self._get_attribute_recursive(
                    i, UniFiConst.ATTR_SW_PORT_NO, enable_logging=self._logging)),
                profile_name=self._get_attribute_recursive(
                    i, UniFiConst.ATTR_SW_PORT_PROF_ON, enable_logging=self._logging) or "All" if i() else self._get_attribute_recursive(i, UniFiConst.ATTR_SW_PORT_PROF_OFF, enable_logging=self._logging) or "Disabled")
            )

            self.logger.debug(
                "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))

    def _item_filter(self, item, attr_type, attr_val):
        if not self.has_iattr(item.conf, attr_type):
            return False
        if attr_val == self.get_iattr_value(item.conf, attr_type):
            return True
        return False

    def _check_client_at_ap(self, i):
        ap_mac = self._get_attribute_recursive(
            i, UniFiConst.ATTR_AP_MAC, check=self._mac_check, enable_logging=self._logging)
        if ap_mac is None:
            return False
        client_mac = self._get_attribute_recursive(
            i, UniFiConst.ATTR_MAC, check=self._mac_check, enable_logging=self._logging)
        client_present = self._model._api.get_client_presence(client_mac)
        if not client_present:
            return False

        ap_of_client_mac = self._model._api.get_client_info(client_mac, 'ap_mac')
        if ap_of_client_mac is None:
            self._log_item_warning(i,  "Unable to get MAC of access-point for client %s" %
                                   (client_mac), enable_logging=self._logging)

        return ap_of_client_mac == ap_mac

    def _check_ap_enabled(self, item):
        ap_mac = self._get_attribute_recursive(
            item, UniFiConst.ATTR_AP_MAC, check=self._mac_check, enable_logging=self._logging)
        if ap_mac is None:
            return False
        rsl = self._model._api.get_device_info(ap_mac, 'disabled', if_no_prop=False)
        if rsl is None:
            self._log_item_warning(item, "No device %s found" % (ap_mac), enable_logging=self._logging)
            return False
        return not rsl

    def _get_device_info(self, item, info_type):
        mac = self._get_one_of_attr_recursive(
            item, [UniFiConst.ATTR_DV_MAC, UniFiConst.ATTR_AP_MAC, UniFiConst.ATTR_SW_MAC], check=self._mac_check, enable_logging=self._logging)
        if mac is None:
            return False
        rsl = self._model._api.get_device_info(mac, info_type)
        if rsl is None:
            self._log_item_warning(item, "No device %s found" % mac, enable_logging=self._logging)

        return rsl

    def _get_sw_port_profile(self, i):
        sw_mac = self._get_attribute_recursive(
            i, UniFiConst.ATTR_SW_MAC, check=self._mac_check, enable_logging=self._logging)
        try:
            sw_port = int(self._get_attribute_recursive(i, UniFiConst.ATTR_SW_PORT_NO,
                                                        enable_logging=self._logging))
            return self._model._api.get_port_profile_for(sw_mac, sw_port)
        except TypeError:
            return None
        except UniFiDataException as e:
            self._log_item_warning(
                i, "Unable to determine current switch-profile for switch {}, error: {}".format(sw_mac, e),  enable_logging=self._logging)
            return None

    def _check_sw_port_enabled(self, item):
        rslt = self._get_sw_port_profile(item)

        pp_on = self._get_attribute_recursive(
            item, UniFiConst.ATTR_SW_PORT_PROF_ON, enable_logging=self._logging)
        pp_off = self._get_attribute_recursive(
            item, UniFiConst.ATTR_SW_PORT_PROF_OFF, enable_logging=self._logging)

        if rslt == pp_off:
            return False
        elif rslt == pp_on:
            return True
        elif rslt is None:
            return None
        else:
            self._log_item_warning(item, "Current port profile \"{}\" doesn't match \"{}\" (on) or \"{}\" (off) (https://help.ubnt.com/hc/en-us/articles/219654087-UniFi-Using-VLANs-with-UniFi-Wireless-Routing-Switching-Hardware#USW)".format(
                rslt, pp_on, pp_off), enable_logging=self._logging)
            return None

    def _get_client_info(self, item, info_type):
        client_mac = self._get_attribute_recursive(
            item, UniFiConst.ATTR_MAC, check=self._mac_check, enable_logging=self._logging)
        return self._model._api.get_client_info(client_mac, info_type)

    def _get_client_presence(self, item):
        client_mac = self._get_attribute_recursive(
            item, UniFiConst.ATTR_MAC, check=self._mac_check, enable_logging=self._logging)
        return self._model._api.get_client_presence(client_mac)

    def _poll_with_unifi_type(self, unifi_type, func):
        # find all items that have the unifi_type attribute set to the given value:
        # apply func to item and set the value accordingly
        for item in self._model.get_items(lambda i: self._item_filter(i, UniFiConst.ATTR_TYPE, unifi_type)):
            try:
                item(func(item), self.get_shortname())
            except ConnectionError:
                # kills further processing in this round.
                raise
            except Exception as e:
                # log the error for this specific poll type and proceed with next item
                self._log_item_error(item, repr(e), self._logging)

    def poll_device(self):
        """
        Polls for updates of the devices connected to the controller
        """
        try:
            self._poll_with_unifi_type(UniFiConst.TYPE_SW_PORT_ENABLED, lambda i: self._check_sw_port_enabled(i))
            self._poll_with_unifi_type(UniFiConst.TYPE_SW_PORT_PROFILE, lambda i: self._get_sw_port_profile(i))
            self._poll_with_unifi_type(UniFiConst.TYPE_CL_PRESENT, lambda i: self._get_client_presence(i))
            self._poll_with_unifi_type(UniFiConst.TYPE_CL_IP, lambda i: self._get_client_info(i, 'ip'))
            self._poll_with_unifi_type(UniFiConst.TYPE_CL_HOSTNAME, lambda i: self._get_client_info(i, 'hostname'))
            self._poll_with_unifi_type(UniFiConst.TYPE_CL_AT_AP, lambda i: self._check_client_at_ap(i))
            self._poll_with_unifi_type(UniFiConst.TYPE_AP_ENABLED, lambda i: self._check_ap_enabled(i))
            self._poll_with_unifi_type(UniFiConst.TYPE_DV_IP, lambda i: self._get_device_info(i, 'ip'))
            self._poll_with_unifi_type(UniFiConst.TYPE_DV_NAME, lambda i: self._get_device_info(i, 'name'))
        except ConnectionError as ex:
            self.logger.error("Poll failed: " + repr(ex))

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            # try/except to handle running in a core version that does not support modules
            self.mod_http = Modules.get_instance().get_module('http')
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


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------


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

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        tabcount = 2

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           tabcount=tabcount,
                           p=self.plugin)
