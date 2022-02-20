#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
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
from requests.packages import urllib3
from requests.auth import HTTPDigestAuth
from io import BytesIO
import lxml.etree as etree
import requests

import hashlib
import time
from xml.etree import ElementTree
from typing import Dict
from enum import IntFlag
from abc import ABC

from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils
from .webif import WebInterface

TR064_DEVICE_NAMESPACE = {'': 'urn:dslforum-org:device-1-0'}
TR064_SERVICE_NAMESPACE = {'': 'urn:dslforum-org:service-1-0'}


class AVM2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.logger.info('Init AVM-Discover Plugin')

        _host = self.get_parameter_value('host')
        _port = self.get_parameter_value('port')
        _verify = self.get_parameter_value('verify')
        _username = self.get_parameter_value('username')
        _passwort = self.get_parameter_value('password')

        ssl = self.get_parameter_value('ssl')
        if ssl and not _verify:
            urllib3.disable_warnings()
        self._cycle = int(self.get_parameter_value('cycle'))
        self.alive = False

        self._fritz_device = FritzDevice(_host, _port, ssl, _verify, _username, _passwort, self)
        self._fritz_home = FritzHome(_host, ssl, _verify, _username, _passwort, self)

        self.aha_devices = dict()

        # init WebIF
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_aha, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

        # self.poll_aha()
        # self.logger.debug(f"manufacturer_name = {self._fritz_device.manufacturer_name}")
        # self.logger.debug(f"model_name = {self._fritz_device.model_name}")
        # self.logger.debug(f"safe_port = {self._fritz_device.safe_port}")

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

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
        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug(f"parse item: {item}")

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
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
            pass

    def poll_aha(self):

        self.logger.debug(f'Starting AHA update loop for instance {self.get_instance_name()}.')

        # update devices
        self._fritz_home.update_devices()

        # get device dict
        _device_dict = self._fritz_home.get_devices_as_dict()

        for ain in _device_dict:
            if not self.aha_devices.get(ain):
                self.aha_devices[ain] = {}
                self.aha_devices[ain]['connected_to_item'] = False
                self.aha_devices[ain]['switch'] = {}
                self.aha_devices[ain]['temperature_sensor'] = {}
                self.aha_devices[ain]['thermostat'] = {}
                self.aha_devices[ain]['alarm'] = {}

            self.aha_devices[ain]['online'] = bool(_device_dict[ain].present)
            self.aha_devices[ain]['name'] = _device_dict[ain].name
            self.aha_devices[ain]['productname'] = _device_dict[ain].productname
            self.aha_devices[ain]['manufacturer'] = _device_dict[ain].manufacturer
            self.aha_devices[ain]['fw_version'] = _device_dict[ain].fw_version
            self.aha_devices[ain]['lock'] = bool(_device_dict[ain].lock)
            self.aha_devices[ain]['device_lock'] = bool(_device_dict[ain].device_lock)
            self.aha_devices[ain]['functions'] = []

            if _device_dict[ain].has_thermostat:
                self.aha_devices[ain]['functions'].append('thermostat')
                self.aha_devices[ain]['thermostat']['actual_temperature'] = _device_dict[ain].actual_temperature
                self.aha_devices[ain]['thermostat']['target_temperature'] = _device_dict[ain].target_temperature
                self.aha_devices[ain]['thermostat']['comfort_temperature'] = _device_dict[ain].comfort_temperature
                self.aha_devices[ain]['thermostat']['eco_temperature'] = _device_dict[ain].eco_temperature
                self.aha_devices[ain]['thermostat']['battery_low'] = bool(_device_dict[ain].battery_low)
                self.aha_devices[ain]['thermostat']['battery_level'] = _device_dict[ain].battery_level
                self.aha_devices[ain]['thermostat']['window_open'] = bool(_device_dict[ain].window_open)
                self.aha_devices[ain]['thermostat']['summer_active'] = bool(_device_dict[ain].summer_active)
                self.aha_devices[ain]['thermostat']['holiday_active'] = bool(_device_dict[ain].holiday_active)

            if _device_dict[ain].has_switch:
                self.aha_devices[ain]['functions'].append('switch')
                self.aha_devices[ain]['switch']['switch_state'] = bool(_device_dict[ain].switch_state)
                self.aha_devices[ain]['switch']['power'] = _device_dict[ain].power
                self.aha_devices[ain]['switch']['energy'] = _device_dict[ain].energy
                self.aha_devices[ain]['switch']['voltage'] = _device_dict[ain].voltage

            if _device_dict[ain].has_temperature_sensor:
                self.aha_devices[ain]['functions'].append('temperature_sensor')
                self.aha_devices[ain]['temperature_sensor']['temperature'] = _device_dict[ain].temperature
                self.aha_devices[ain]['temperature_sensor']['offset'] = _device_dict[ain].offset

            if _device_dict[ain].has_alarm:
                self.aha_devices[ain]['functions'].append('alarm')
                self.aha_devices[ain]['alarm']['alert_state'] = bool(_device_dict[ain].alert_state)


class FritzDevice:
    """
    This class encapsulates information related to a specific FritzDevice

    # Devices / Services
         InternetGatewayDevice
            DeviceInfo
                GetInfo
                SetProvisioningCode
                GetDeviceLog
                GetSecurityPort
            DeviceConfig
            Layer3Forwarding
            LANConfigSecurity
            ManagementServer
            Time
            UserInterface
            X_AVM-DE_Storage
            X_AVM-DE_WebDAVClient
            X_AVM-DE_UPnP
            X_AVM-DE_Speedtest
            X_AVM-DE_RemoteAccess
            X_AVM-DE_MyFritz
            X_VoIP
            X_AVM-DE_OnTel
            X_AVM-DE_Dect
            X_AVM-DE_TAM
            X_AVM-DE_AppSetup
            X_AVM-DE_Homeauto
            X_AVM-DE_Homeplug
            X_AVM-DE_Filelinks
            X_AVM-DE_Auth
            X_AVM-DE_HostFilter
        LANDevice
            WLANConfiguration
            Hosts
            LANEthernetInterfaceConfig
            LANHostConfigManagement
        WANDevice
            WANCommonInterfaceConfig
            WANDSLInterfaceConfig
        WANConnectionDevice
            WANDSLLinkConfig
            WANEthernetLinkConfig
            WANPPPConnection
            WANIPConnection
    """

    def __init__(self, host, port, ssl, verify, username, password, plugin_instance=None):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init FritzDevice")

        self._host = host
        self._port = port
        self._ssl = ssl
        self._verify = verify
        self._username = username
        self._password = password
        self._available = True
        self._items = []
        self._smarthome_items = []
        self._smarthome_devices = {}
        self._DeviceInfo = {}
        self._Hosts = {}

        self.client = FritzDevice.Client(self._username, self._password, self._verify, base_url=self._build_url(), plugin_instance=plugin_instance)

    def _build_url(self):
        """
        Builds a request url

         :return: string of the url, dependent on settings of the FritzDevice
        """
        if self.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"
        url = f"{url_prefix}://{self._host}:{self._port}"

        return url

    def get_host(self):
        """
        Returns the hostname / IP of the FritzDevice

        :return: hostname of the device, as set in plugin.conf
        """
        return self._host

    def get_port(self):
        """
        Returns the port of the FritzDevice

        :return: port of the device, as set in plugin.conf
        """
        return self._port

    def get_verify(self):
        """
        Returns the wether to verify or not

        :return: verify
        """
        return self._verify

    def get_items(self):
        """
        Returns added items

        :return: array of items hold by the device
        """
        return self._items

    def get_item_count(self):
        """
        Returns number of added items

        :return: number of items hold by the device
        """
        return len(self._items)

    def is_ssl(self):
        """
        Returns information if SSL is enabled

        :return: is ssl enabled, as set in plugin.conf
        """
        return self._ssl

    def is_available(self):
        """
        Returns information if the device is currently available

        :return: boolean, if device is available
        """
        return self._available

    def set_available(self, is_available):
        """
        Sets the boolean, if the device is available

        :param is_available: boolean of the availability status
        """
        self._available = is_available

    def get_user(self):
        """
        Returns the user for the FritzDevice

        :return: user, as set in plugin.conf
        """
        return self._username

    def get_password(self):
        """
        Returns the password for the FritzDevice

        :return: password, as set in plugin.conf
        """
        return self._password

    @property
    def manufacturer_name(self):
        if 'GetInfo' not in self._DeviceInfo:
            self._DeviceInfo['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._DeviceInfo['GetInfo'].NewManufacturerName

    @property
    def manufacturer_oui(self):
        if 'GetInfo' not in self._DeviceInfo:
            self._DeviceInfo['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._DeviceInfo['GetInfo'].NewManufacturerOUI

    @property
    def model_name(self):
        if 'GetInfo' not in self._DeviceInfo:
            self._DeviceInfo['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._DeviceInfo['GetInfo'].NewModelName

    @property
    def desciption(self):
        if 'GetInfo' not in self._DeviceInfo:
            self._DeviceInfo['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._DeviceInfo['GetInfo'].NewDescription

    @property
    def safe_port(self):
        if 'GetSecurityPort' not in self._DeviceInfo:
            self._DeviceInfo['GetSecurityPort'] = self.client.InternetGatewayDevice.DeviceInfo.GetSecurityPort()
        return self._DeviceInfo['GetSecurityPort'].NewSecurityPort

    def GetGenericHostEntry(self, index):
        if 'GetGenericHostEntry' not in self._Hosts:
            self._Hosts['GetGenericHostEntry'] = {}
        if index not in self._Hosts['GetGenericHostEntry']:
            self._Hosts['GetGenericHostEntry'][index] = {}
        self._Hosts['GetGenericHostEntry'][index].update(self.client.LANDevice.Hosts.GetGenericHostEntry(NewIndex=index))
        return self._Hosts['GetGenericHostEntry'][index]

    def wlan_info(self):
        for index in range(3):
            info = self.client.LANDevice.WLANConfiguration[index].GetInfo()
            self._plugin_instance.logger.debug(f"WLAN info{index} = {info}")

    class Client:
        """TR-064 client.
        :param str username:
            Username with access to router.
        :param str password:
            Passwort to access router.
        :param str base_url:
            URL to router.
        """

        def __init__(self, username, password, verify, base_url='https://192.168.178.1:49443', plugin_instance=None):

            # handle plugin instance
            self._plugin_instance = plugin_instance

            self.base_url = base_url
            self.auth = HTTPDigestAuth(username, password)
            self.verify = verify

            self.devices = {}
            self._plugin_instance.logger.debug(f"Init Client")

        def __getattr__(self, name):
            if name not in self.devices:
                self._fetch_devices()

            if name in self.devices:
                return self.devices[name]

        def _fetch_devices(self, description_file='/tr64desc.xml'):

            """Fetch device description."""
            request = requests.get(f'{self.base_url}{description_file}', verify=self.verify)

            if request.status_code == 200:
                xml = etree.parse(BytesIO(request.content))

                for device in xml.findall('.//device', namespaces=TR064_DEVICE_NAMESPACE):
                    name = device.findtext('deviceType', namespaces=TR064_DEVICE_NAMESPACE).split(':')[-2]
                    if name not in self.devices:
                        self.devices[name] = FritzDevice.Device(device, self.auth, self.verify, self.base_url)

    class Device:
        """TR-064 device.
        :param lxml.etree.Element xml:
            XML device element
        :param HTTPBasicAuthHandler auth:
            HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
        :param str base_url:
            URL to router.
        """

        def __init__(self, xml, auth, verify, base_url):
            self.logger = logging.getLogger(__name__)
            self.services = {}
            self.verify = verify

            for service in xml.findall('./serviceList/service', namespaces=TR064_DEVICE_NAMESPACE):
                service_type = service.findtext('serviceType', namespaces=TR064_DEVICE_NAMESPACE)
                service_id = service.findtext('serviceId', namespaces=TR064_DEVICE_NAMESPACE)
                control_url = service.findtext('controlURL', namespaces=TR064_DEVICE_NAMESPACE)
                event_sub_url = service.findtext('eventSubURL', namespaces=TR064_DEVICE_NAMESPACE)
                scpdurl = service.findtext('SCPDURL', namespaces=TR064_DEVICE_NAMESPACE)

                name = service_type.split(':')[-2].replace('-', '_')
                if name not in self.services:
                    self.services[name] = FritzDevice.ServiceList()

                self.services[name].append(
                    FritzDevice.Service(
                        auth,
                        self.verify,
                        base_url,
                        service_type,
                        service_id,
                        scpdurl,
                        control_url,
                        event_sub_url
                    )
                )

        def __getattr__(self, name):
            if name in self.services:
                return self.services[name]

    class ServiceList(list):
        """Service list."""

        def __getattr__(self, name):
            """Direct access to first list entry if brackets omit."""
            return self[0].__getattr__(name)

        def __getitem__(self, index):
            """Overriden braket operator to return TR-064 exception."""
            if len(self) > index:
                return super().__getitem__(index)

    class Service:
        """TR-064 service."""

        def __init__(self, auth, verify, base_url, service_type, service_id, scpdurl, control_url, event_sub_url):
            self.auth = auth
            self.verify = verify
            self.base_url = base_url
            self.service_type = service_type
            self.service_id = service_id
            self.scpdurl = scpdurl
            self.control_url = control_url
            self.event_sub_url = event_sub_url
            self.actions = {}

        def __getattr__(self, name):
            if name not in self.actions:
                self._fetch_actions(self.scpdurl)

            if name in self.actions:
                return self.actions[name]

        def _fetch_actions(self, scpdurl):
            """Fetch action description."""
            request = requests.get(f'{self.base_url}{scpdurl}', verify=self.verify)
            if request.status_code == 200:
                xml = etree.parse(BytesIO(request.content))

                for action in xml.findall('./actionList/action', namespaces=TR064_SERVICE_NAMESPACE):
                    name = action.findtext('name', namespaces=TR064_SERVICE_NAMESPACE)
                    canonical_name = name.replace('-', '_')
                    self.actions[canonical_name] = FritzDevice.Action(
                        action,
                        self.auth,
                        self.base_url,
                        name,
                        self.service_type,
                        self.service_id,
                        self.control_url,
                        self.verify
                    )

    class Action:
        """TR-064 action.
        :param lxml.etree.Element xml:
            XML action element
        :param HTTPBasicAuthHandler auth:
            HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
        :param str base_url:
            URL to router.
        :param str name:
            Action name
        :param str service_type:
            Service type
        :param str service_id:
            Service ID
        :param str control_url:
            Control URL
        """

        def __init__(self, xml, auth, base_url, name, service_type, service_id, control_url, verify):

            self.logger = logging.getLogger(__name__)

            self.auth = auth
            self.verify = verify
            self.base_url = base_url
            self.name = name
            self.service_type = service_type
            self.service_id = service_id
            self.control_url = control_url

            etree.register_namespace('s', 'http://schemas.xmlsoap.org/soap/envelope/')
            etree.register_namespace('h', 'http://soap-authentication.org/digest/2001/10/')

            self.headers = {'content-type': 'text/xml; charset="utf-8"'}
            self.envelope = etree.Element(
                '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                attrib={
                    '{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle':
                    'http://schemas.xmlsoap.org/soap/encoding/'})
            self.body = etree.SubElement(self.envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

            self.in_arguments = {}
            self.out_arguments = {}

            for argument in xml.findall('./argumentList/argument', namespaces=TR064_SERVICE_NAMESPACE):
                name = argument.findtext('name', namespaces=TR064_SERVICE_NAMESPACE)
                direction = argument.findtext('direction', namespaces=TR064_SERVICE_NAMESPACE)

                if direction == 'in':
                    self.in_arguments[name.replace('-', '_')] = name

                if direction == 'out':
                    self.out_arguments[name] = name.replace('-', '_')

        def __call__(self, **kwargs):
            missing_arguments = self.in_arguments.keys() - kwargs.keys()
            if missing_arguments:
                self.logger.warning('Missing argument(s) \'' + "', '".join(missing_arguments) + '\'')

            unknown_arguments = kwargs.keys() - self.in_arguments.keys()
            if unknown_arguments:
                self.logger.warning('Unknown argument(s) \'' + "', '".join(unknown_arguments) + '\'')

            # Add SOAP action to header
            self.headers['soapaction'] = '"{}#{}"'.format(self.service_type, self.name)
            etree.register_namespace('u', self.service_type)

            # Prepare body for request
            self.body.clear()
            action = etree.SubElement(self.body, '{{{}}}{}'.format(self.service_type, self.name))
            for key in kwargs:
                arg = etree.SubElement(action, self.in_arguments[key])
                arg.text = str(kwargs[key])

            # soap._InitChallenge(header)
            data = etree.tostring(self.envelope, encoding='utf-8', xml_declaration=True).decode()
            request = requests.post(f'{self.base_url}{self.control_url}',
                                    headers=self.headers,
                                    auth=self.auth,
                                    data=data,
                                    verify=self.verify)
            if request.status_code != 200:
                return request.status_code

            # Translate response and prepare dict
            xml = etree.parse(BytesIO(request.content))
            response = FritzDevice.AttributeDict()
            for arg in list(xml.find('.//{{{}}}{}Response'.format(self.service_type, self.name))):
                name = self.out_arguments[arg.tag]
                response[name] = arg.text
            return response

    class AttributeDict(dict):
        """Direct access dict entries like attributes."""

        def __getattr__(self, name):
            return self[name]


class FritzHome:
    """Fritzhome object to communicate with the device."""

    def __init__(self, host, ssl, verify, user, password, plugin_instance):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init Fritzhome")

        self._host = host
        self._ssl = ssl
        self._verify = verify
        self._user = user
        self._password = password

        self._sid = None
        self._devices: Dict[str, FritzHome.FritzhomeDevice] = None
        self._templates: Dict[str, FritzHome.FritzhomeTemplate] = None
        self._logged_in = False

        self._session = requests.Session()

    def _request(self, url, params=None, timeout=10):
        """Send a request with parameters."""
        rsp = self._session.get(url, params=params, timeout=timeout, verify=self._verify)
        rsp.raise_for_status()
        return rsp.text.strip()

    def _login_request(self, username=None, secret=None):
        """Send a login request with paramerters."""
        url = self.get_prefixed_host() + "/login_sid.lua"
        params = {}
        if username:
            params["username"] = username
        if secret:
            params["response"] = secret
        plain = self._request(url, params)
        dom = ElementTree.fromstring(plain)
        sid = dom.findtext("SID")
        challenge = dom.findtext("Challenge")
        return sid, challenge

    def _logout_request(self):
        """Send a logout request."""
        url = self.get_prefixed_host() + "/login_sid.lua"
        params = {"security:command/logout": "1", "sid": self._sid}

        self._request(url, params)

    @staticmethod
    def _create_login_secret(challenge, password):
        """Create a login secret."""
        to_hash = (challenge + "-" + password).encode("UTF-16LE")
        hashed = hashlib.md5(to_hash).hexdigest()
        return "{0}-{1}".format(challenge, hashed)

    def _aha_request(self, cmd, ain=None, param=None, rf=str):
        """Send an AHA request."""

        self._plugin_instance.logger.debug(f"_aha_request called with cmd={cmd}, ain={ain}, param={param}, rf={rf} ")

        if not self._logged_in:
            self.login()

        url = self.get_prefixed_host() + "/webservices/homeautoswitch.lua"
        params = {"switchcmd": cmd, "sid": self._sid}
        if param:
            params.update(param)
        if ain:
            params["ain"] = ain

        plain = self._request(url, params)

        self.logout()

        if plain == "inval":
            self._plugin_instance.logger.error("InvalidError")
            return

        if rf == bool:
            return bool(int(plain))
        return rf(plain)

    def login(self):
        """Login and get a valid session ID."""
        self._plugin_instance.logger.debug("AHA login called")
        try:
            (sid, challenge) = self._login_request()
            if sid == "0000000000000000":
                secret = self._create_login_secret(challenge, self._password)
                (sid2, challenge) = self._login_request(username=self._user, secret=secret)
                if sid2 == "0000000000000000":
                    self._plugin_instance.logger.warning("login failed %s", sid2)
                    self._plugin_instance.logger.error(f"LoginError for {self._user}")
                    return
                self._sid = sid2
        except Exception as e:
            self._plugin_instance.logger.error(f"LoginError {e} occurred for {self._user}")
        else:
            self._logged_in = True

    def logout(self):
        """Logout."""
        self._plugin_instance.logger.debug("AHA logout called")
        self._logout_request()
        self._sid = None
        self._logged_in = False

    def get_prefixed_host(self):
        """Choose the correct protocol prefix for the host.
        Supports three input formats:
        - https://<host>(requests use strict certificate validation by default)
        - http://<host> (unecrypted)
        - <host> (unencrypted)
        """
        host = self._host
        if not host.startswith("https://") or not host.startswith("http://"):
            if self._ssl:
                host = "https://"+host
            else:
                host = "http://"+host
        return host

    def update_devices(self):
        self._plugin_instance.logger.info("Updating Devices ...")
        if self._devices is None:
            self._devices = {}

        for element in self.get_device_elements():
            if element.attrib["identifier"] in self._devices.keys():
                self._plugin_instance.logger.info("Updating already existing Device " + element.attrib["identifier"])
                self._devices[element.attrib["identifier"]]._update_from_node(element)
            else:
                self._plugin_instance.logger.info("Adding new Device " + element.attrib["identifier"])
                device = FritzHome.FritzhomeDevice(self, node=element)
                self._devices[device.ain] = device
        return True

    def _get_listinfo_elements(self, entity_type):
        """Get the DOM elements for the entity list."""
        plain = self._aha_request("get" + entity_type + "listinfos")
        dom = ElementTree.fromstring(plain)
        return dom.findall(entity_type)

    def get_device_elements(self):
        """Get the DOM elements for the device list."""
        return self._get_listinfo_elements("device")

    def get_device_element(self, ain):
        """Get the DOM element for the specified device."""
        elements = self.get_device_elements()
        for element in elements:
            if element.attrib["identifier"] == ain:
                return element
        return None

    def get_devices(self):
        """Get the list of all known devices."""
        return list(self.get_devices_as_dict().values())

    def get_devices_as_dict(self):
        """Get the list of all known devices."""
        if self._devices is None:
            self.update_devices()
        return self._devices

    def get_device_by_ain(self, ain):
        """Return a device specified by the AIN."""
        return self.get_devices_as_dict()[ain]

    def get_device_present(self, ain):
        """Get the device presence."""
        return self._aha_request("getswitchpresent", ain=ain, rf=bool)

    def get_device_name(self, ain):
        """Get the device name."""
        return self._aha_request("getswitchname", ain=ain)

    def get_switch_state(self, ain):
        """Get the switch state."""
        return self._aha_request("getswitchstate", ain=ain, rf=bool)

    def set_switch_state_on(self, ain):
        """Set the switch to on state."""
        return self._aha_request("setswitchon", ain=ain, rf=bool)

    def set_switch_state_off(self, ain):
        """Set the switch to off state."""
        return self._aha_request("setswitchoff", ain=ain, rf=bool)

    def set_switch_state_toggle(self, ain):
        """Toggle the switch state."""
        return self._aha_request("setswitchtoggle", ain=ain, rf=bool)

    def get_switch_power(self, ain):
        """Get the switch power consumption."""
        return self._aha_request("getswitchpower", ain=ain, rf=int)

    def get_switch_energy(self, ain):
        """Get the switch energy."""
        return self._aha_request("getswitchenergy", ain=ain, rf=int)

    def get_temperature(self, ain):
        """Get the device temperature sensor value."""
        return self._aha_request("gettemperature", ain=ain, rf=float) / 10.0

    def _get_temperature(self, ain, name):
        plain = self._aha_request(name, ain=ain, rf=float)
        return (plain - 16) / 2 + 8

    def get_target_temperature(self, ain):
        """Get the thermostate target temperature."""
        return self._get_temperature(ain, "gethkrtsoll")

    def set_target_temperature(self, ain, temperature):
        """Set the thermostate target temperature."""
        temp = int(16 + ((float(temperature) - 8) * 2))

        if temp < min(range(16, 56)):
            temp = 253
        elif temp > max(range(16, 56)):
            temp = 254

        self._aha_request("sethkrtsoll", ain=ain, param={'param': temp})

    def set_window_open(self, ain, seconds):
        """Set the thermostate target temperature."""
        endtimestamp = int(time.time() + seconds)

        self._aha_request("sethkrwindowopen", ain=ain, param={'endtimestamp': endtimestamp})

    def get_comfort_temperature(self, ain):
        """Get the thermostate comfort temperature."""
        return self._get_temperature(ain, "gethkrkomfort")

    def get_eco_temperature(self, ain):
        """Get the thermostate eco temperature."""
        return self._get_temperature(ain, "gethkrabsenk")

    def get_device_statistics(self, ain):
        """Get device statistics."""
        plain = self._aha_request("getbasicdevicestats", ain=ain)
        return plain

    # Lightbulb-related commands

    def set_state_off(self, ain):
        """Set the switch/actuator/lightbulb to on state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 0})

    def set_state_on(self, ain):
        """Set the switch/actuator/lightbulb to on state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 1})

    def set_state_toggle(self, ain):
        """Toggle the switch/actuator/lightbulb state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 2})

    def set_level(self, ain, level):
        """Set level/brightness/height in interval [0,255]."""
        if level < 0:
            level = 0  # 0%
        elif level > 255:
            level = 255  # 100 %

        self._aha_request("setlevel", ain=ain, param={'level': int(level)})

    def set_level_percentage(self, ain, level):
        """Set level/brightness/height in interval [0,100]."""
        # Scale percentage to [0,255] interval
        self.set_level(ain, int(level * 2.55))

    def _get_colordefaults(self, ain):
        plain = self._aha_request("getcolordefaults", ain=ain)
        return ElementTree.fromstring(plain)

    def get_colors(self, ain):
        """Get colors (HSV-space) supported by this lightbulb."""
        colordefaults = self._get_colordefaults(ain)
        colors = {}
        for hs in colordefaults.iter('hs'):
            name = hs.find("name").text.strip()
            values = []
            for st in hs.iter("color"):
                values.append(
                    (
                        st.get("hue"),
                        st.get("sat"),
                        st.get("val")
                    )
                )
            colors[name] = values
        return colors

    def set_color(self, ain, hsv, duration=0, mapped=True):
        """Set hue and saturation.
        hsv: HUE colorspace element obtained from get_colors()
        duration: Speed of change in seconds, 0 = instant
        """
        params = {
            'hue': int(hsv[0]),
            'saturation': int(hsv[1]),
            "duration": int(duration) * 10
        }
        if mapped:
            self._aha_request("setcolor", ain=ain, param=params)
        else:
            # undocumented API method for free color selection
            self._aha_request("setunmappedcolor", ain=ain, param=params)

    def get_color_temps(self, ain):
        """Get temperatures supported by this lightbulb."""
        colordefaults = self._get_colordefaults(ain)
        temperatures = []
        for temp in colordefaults.iter('temp'):
            temperatures.append(temp.get("value"))
        return temperatures

    def set_color_temp(self, ain, temperature, duration=0):
        """Set color temperature.
        temperature: temperature element obtained from get_temperatures()
        duration: Speed of change in seconds, 0 = instant
        """
        params = {
            'temperature': int(temperature),
            "duration": int(duration) * 10
        }
        self._aha_request("setcolortemperature", ain=ain, param=params)

    # Template-related commands

    def update_templates(self):
        self._plugin_instance.logger.info("Updating Templates ...")
        if self._templates is None:
            self._templates = {}

        for element in self.get_template_elements():
            if element.attrib["identifier"] in self._templates.keys():
                self._plugin_instance.logger.info(
                    "Updating already existing Template " + element.attrib["identifier"]
                )
                self._templates[element.attrib["identifier"]]._update_from_node(element)
            else:
                self._plugin_instance.logger.info("Adding new Template " + element.attrib["identifier"])
                template = FritzHome.FritzhomeTemplate(self, node=element)
                self._templates[template.ain] = template
        return True

    def get_template_elements(self):
        """Get the DOM elements for the template list."""
        return self._get_listinfo_elements("template")

    def get_templates(self):
        """Get the list of all known templates."""
        return list(self.get_templates_as_dict().values())

    def get_templates_as_dict(self):
        """Get the list of all known templates."""
        if self._templates is None:
            self.update_templates()
        return self._templates

    def get_template_by_ain(self, ain):
        """Return a template specified by the AIN."""
        return self.get_templates_as_dict()[ain]

    def apply_template(self, ain):
        """Applies a template."""
        self._aha_request("applytemplate", ain=ain)

    class FritzhomeDeviceFeatures(IntFlag):
        ALARM = 0x0010
        UNKNOWN = 0x0020
        BUTTON = 0x0020
        THERMOSTAT = 0x0040
        POWER_METER = 0x0080
        TEMPERATURE = 0x0100
        SWITCH = 0x0200
        DECT_REPEATER = 0x0400
        MICROPHONE = 0x0800
        HANFUN = 0x2000
        SWITCHABLE = 0x8000
        DIMMABLE = 0x10000
        LIGHTBULB = 0x20000

    class FritzhomeEntityBase(ABC):
        """The Fritzhome Entity class."""

        def __init__(self, fritz=None, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            self._fritz = None
            self.ain: str = None
            self._functionsbitmask = None

            if fritz is not None:
                self._fritz = fritz
            if node is not None:
                self._update_from_node(node)

        def __repr__(self):
            """Return a string."""
            return f"{self.ain} {self.name}"

        def _has_feature(self, feature) -> bool:
            return feature in FritzHome.FritzhomeDeviceFeatures(self._functionsbitmask)

        def _update_from_node(self, node):
            self.logger.debug(ElementTree.tostring(node))
            self.ain = node.attrib["identifier"]
            self._functionsbitmask = int(node.attrib["functionbitmask"])

            self.name = node.findtext("name").strip()

        # XML Helpers

        def get_node_value(self, elem, node):
            return elem.findtext(node)

        def get_node_value_as_int(self, elem, node) -> int:
            return int(self.get_node_value(elem, node))

        def get_node_value_as_int_as_bool(self, elem, node) -> bool:
            return bool(self.get_node_value_as_int(elem, node))

        def get_temp_from_node(self, elem, node):
            return float(self.get_node_value(elem, node)) / 2

    class FritzhomeTemplate(FritzhomeEntityBase):
        """The Fritzhome Template class."""

        devices = None
        features = None
        apply_hkr_summer = None
        apply_hkr_temperature = None
        apply_hkr_holidays = None
        apply_hkr_time_table = None
        apply_relay_manual = None
        apply_relay_automatic = None
        apply_level = None
        apply_color = None
        apply_dialhelper = None

        def _update_from_node(self, node):
            super()._update_from_node(node)

            self.features = FritzHome.FritzhomeDeviceFeatures(self._functionsbitmask)

            applymask = node.find("applymask")
            self.apply_hkr_summer = applymask.find("hkr_summer") is not None
            self.apply_hkr_temperature = applymask.find("hkr_temperature") is not None
            self.apply_hkr_holidays = applymask.find("hkr_holidays") is not None
            self.apply_hkr_time_table = applymask.find("hkr_time_table") is not None
            self.apply_relay_manual = applymask.find("relay_manual") is not None
            self.apply_relay_automatic = applymask.find("relay_automatic") is not None
            self.apply_level = applymask.find("level") is not None
            self.apply_color = applymask.find("color") is not None
            self.apply_dialhelper = applymask.find("dialhelper") is not None

            self.devices = []
            for device in node.find("devices").findall("device"):
                self.devices.append(device.attrib["identifier"])

    class FritzhomeDeviceBase(FritzhomeEntityBase):
        """The Fritzhome Device class."""

        identifier = None
        fw_version = None
        manufacturer = None
        productname = None
        present = None

        def __repr__(self):
            """Return a string."""
            return "{ain} {identifier} {manuf} {prod} {name}".format(
                ain=self.ain,
                identifier=self.identifier,
                manuf=self.manufacturer,
                prod=self.productname,
                name=self.name,
            )

        def update(self):
            """Update the device values."""
            self._fritz.update_devices()

        def _update_from_node(self, node):
            super()._update_from_node(node)
            self.ain = node.attrib["identifier"]
            self.identifier = node.attrib["id"]
            self.fw_version = node.attrib["fwversion"]
            self.manufacturer = node.attrib["manufacturer"]
            self.productname = node.attrib["productname"]

            self.present = bool(int(node.findtext("present")))

        # General
        def get_present(self):
            """Check if the device is present."""
            return self._fritz.get_device_present(self.ain)

    class FritzhomeDeviceAlarm(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        alert_state = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_alarm:
                self._update_alarm_from_node(node)

        # Alarm
        @property
        def has_alarm(self):
            """Check if the device has alarm function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.ALARM)

        def _update_alarm_from_node(self, node):
            val = node.find("alert")
            try:
                self.alert_state = self.get_node_value_as_int_as_bool(val, "state")
            except (Exception, ValueError):
                pass

    class FritzhomeDeviceButton(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_button:
                self._update_button_from_node(node)

        # Button
        @property
        def has_button(self):
            """Check if the device has button function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.BUTTON)

        def _update_button_from_node(self, node):
            self.buttons = {}

            for element in node.findall("button"):
                button = FritzHome.FritzhomeButton(element)
                self.buttons[button.ain] = button

            try:
                self.tx_busy = self.get_node_value_as_int_as_bool(node, "txbusy")
                self.battery_low = self.get_node_value_as_int_as_bool(node, "batterylow")
                self.battery_level = int(self.get_node_value_as_int(node, "battery"))
            except Exception:
                pass

        def get_button_by_ain(self, ain):
            return self.buttons[ain]

    class FritzhomeButton(object):
        """The Fritzhome Button Device class."""

        ain = None
        identifier = None
        name = None
        last_pressed = None

        def __init__(self, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            if node is not None:
                self._update_from_node(node)

        def _update_from_node(self, node):
            self.logger.debug(ElementTree.tostring(node))
            self.ain = node.attrib["identifier"]
            self.identifier = node.attrib["id"]
            self.name = node.findtext("name")
            try:
                self.last_pressed = self.get_node_value_as_int(node, "lastpressedtimestamp")
            except ValueError:
                pass

        def get_node_value(self, elem, node):
            return elem.findtext(node)

        def get_node_value_as_int(self, elem, node) -> int:
            return int(self.get_node_value(elem, node))

    class FritzhomeDeviceLightBulb(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        state = None
        level = None
        hue = None
        saturation = None
        unmapped_hue = None
        unmapped_saturation = None
        color_temp = None
        color_mode = None
        supported_color_mode = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_lightbulb:
                self._update_lightbulb_from_node(node)

        # Light Bulb
        @property
        def has_lightbulb(self):
            """Check if the device has LightBulb function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.LIGHTBULB)

        def _update_lightbulb_from_node(self, node):
            state_element = node.find("simpleonoff")
            try:
                self.state = self.get_node_value_as_int_as_bool(state_element, "state")

            except ValueError:
                pass

            level_element = node.find("levelcontrol")
            try:
                self.level = self.get_node_value_as_int(level_element, "level")

                self.level_percentage = int(self.level / 2.55)
            except ValueError:
                pass

            colorcontrol_element = node.find("colorcontrol")
            try:
                self.color_mode = colorcontrol_element.attrib.get("current_mode")

                self.supported_color_mode = colorcontrol_element.attrib.get(
                    "supported_modes")

            except ValueError:
                pass

            try:
                self.hue = self.get_node_value_as_int(colorcontrol_element, "hue")

                self.saturation = self.get_node_value_as_int(colorcontrol_element,
                                                             "saturation")

                self.unmapped_hue = self.get_node_value_as_int(colorcontrol_element, "unmapped_hue")

                self.unmapped_saturation = self.get_node_value_as_int(colorcontrol_element,
                                                                      "unmapped_saturation")
            except ValueError:
                # reset values after color mode changed
                self.hue = None
                self.saturation = None
                self.unmapped_hue = None
                self.unmapped_saturation = None

            try:
                self.color_temp = self.get_node_value_as_int(colorcontrol_element,
                                                             "temperature")

            except ValueError:
                # reset values after color mode changed
                self.color_temp = None

        def set_state_off(self):
            """Switch light bulb off."""
            self.state = True
            self._fritz.set_state_off(self.ain)

        def set_state_on(self):
            """Switch light bulb on."""
            self.state = True
            self._fritz.set_state_on(self.ain)

        def set_state_toggle(self):
            """Toogle light bulb state."""
            self.state = True
            self._fritz.set_state_toggle(self.ain)

        def set_level(self, level):
            """Set HSV color."""
            self._fritz.set_level(self.ain, level)

        def get_colors(self):
            """Get the supported colors."""
            return self._fritz.get_colors(self.ain)

        def set_color(self, hsv, duration=0):
            """Set HSV color."""
            self._fritz.set_color(self.ain, hsv, duration, True)

        def set_unmapped_color(self, hsv, duration=0):
            """Set unmapped HSV color (Free color selection)."""
            self._fritz.set_color(self.ain, hsv, duration, False)

        def get_color_temps(self):
            """Get the supported color temperatures energy."""
            return self._fritz.get_color_temps(self.ain)

        def set_color_temp(self, temperature, duration=0):
            """Set white color temperature."""
            self._fritz.set_color_temp(self.ain, temperature, duration)

    class FritzhomeDevicePowermeter(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        power = None
        energy = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_powermeter:
                self._update_powermeter_from_node(node)

        # Power Meter
        @property
        def has_powermeter(self):
            """Check if the device has powermeter function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.POWER_METER)

        def _update_powermeter_from_node(self, node):
            val = node.find("powermeter")
            self.power = int(val.findtext("power"))
            self.energy = int(val.findtext("energy"))
            try:
                self.voltage = float(int(val.findtext("voltage")) / 1000)
            except Exception:
                pass

        def get_switch_power(self):
            """The switch state."""
            return self._fritz.get_switch_power(self.ain)

        def get_switch_energy(self):
            """Get the switch energy."""
            return self._fritz.get_switch_energy(self.ain)

    class FritzhomeDeviceRepeater(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

        # Repeater
        @property
        def has_repeater(self):
            """Check if the device has repeater function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.DECT_REPEATER)

    class FritzhomeDeviceSwitch(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        switch_state = None
        switch_mode = None
        lock = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_switch:
                self._update_switch_from_node(node)

        # Switch
        @property
        def has_switch(self):
            """Check if the device has switch function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCH)

        def _update_switch_from_node(self, node):
            val = node.find("switch")
            self.switch_state = self.get_node_value_as_int_as_bool(val, "state")
            self.switch_mode = self.get_node_value(val, "mode")
            self.lock = bool(self.get_node_value(val, "lock"))
            # optional value
            try:
                self.device_lock = self.get_node_value_as_int_as_bool(val, "devicelock")
            except Exception:
                pass

        def get_switch_state(self):
            """Get the switch state."""
            return self._fritz.get_switch_state(self.ain)

        def set_switch_state_on(self):
            """Set the switch state to on."""
            return self._fritz.set_switch_state_on(self.ain)

        def set_switch_state_off(self):
            """Set the switch state to off."""
            return self._fritz.set_switch_state_off(self.ain)

        def set_switch_state_toggle(self):
            """Toggle the switch state."""
            return self._fritz.set_switch_state_toggle(self.ain)

    class FritzhomeDeviceTemperature(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        offset = None
        temperature = None
        rel_humidity = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_temperature_sensor:
                self._update_temperature_from_node(node)

        # Temperature
        @property
        def has_temperature_sensor(self):
            """Check if the device has temperature function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.TEMPERATURE)

        def _update_temperature_from_node(self, node):
            temperature_element = node.find("temperature")
            try:
                self.offset = (
                        self.get_node_value_as_int(temperature_element, "offset") / 10.0
                )
            except ValueError:
                pass

            try:
                self.temperature = (
                        self.get_node_value_as_int(temperature_element, "celsius") / 10.0
                )
            except ValueError:
                pass

            humidity_element = node.find("humidity")
            if humidity_element is not None:
                try:
                    self.rel_humidity = self.get_node_value_as_int(humidity_element,
                                                                   "rel_humidity")
                except ValueError:
                    pass

    class FritzhomeDeviceThermostat(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        actual_temperature = None
        target_temperature = None
        eco_temperature = None
        comfort_temperature = None
        device_lock = None
        lock = None
        error_code = None
        battery_low = None
        battery_level = None
        window_open = None
        summer_active = None
        holiday_active = None
        nextchange_endperiod = None
        nextchange_temperature = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_thermostat:
                self._update_hkr_from_node(node)

        # Thermostat
        @property
        def has_thermostat(self):
            """Check if the device has thermostat function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.THERMOSTAT)

        def _update_hkr_from_node(self, node):
            hkr_element = node.find("hkr")

            try:
                self.actual_temperature = self.get_temp_from_node(hkr_element, "tist")
            except ValueError:
                pass

            self.target_temperature = self.get_temp_from_node(hkr_element, "tsoll")
            self.eco_temperature = self.get_temp_from_node(hkr_element, "absenk")
            self.comfort_temperature = self.get_temp_from_node(hkr_element, "komfort")

            # optional value
            try:
                self.device_lock = self.get_node_value_as_int_as_bool(
                    hkr_element, "devicelock"
                )
                self.lock = self.get_node_value_as_int_as_bool(hkr_element, "lock")
                self.error_code = self.get_node_value_as_int(hkr_element, "errorcode")
                self.battery_low = self.get_node_value_as_int_as_bool(
                    hkr_element, "batterylow"
                )
                self.battery_level = int(self.get_node_value_as_int(hkr_element, "battery"))
                self.window_open = self.get_node_value_as_int_as_bool(
                    hkr_element, "windowopenactiv"
                )
                self.summer_active = self.get_node_value_as_int_as_bool(
                    hkr_element, "summeractive"
                )
                self.holiday_active = self.get_node_value_as_int_as_bool(
                    hkr_element, "holidayactive"
                )
                nextchange_element = hkr_element.find("nextchange")
                self.nextchange_endperiod = int(
                    self.get_node_value_as_int(nextchange_element, "endperiod")
                )
                self.nextchange_temperature = self.get_temp_from_node(
                    nextchange_element, "tchange"
                )
            except Exception:
                pass

        def get_temperature(self):
            """Get the device temperature value."""
            return self._fritz.get_temperature(self.ain)

        def get_target_temperature(self):
            """Get the thermostate target temperature."""
            return self._fritz.get_target_temperature(self.ain)

        def set_target_temperature(self, temperature):
            """Set the thermostate target temperature."""
            return self._fritz.set_target_temperature(self.ain, temperature)

        def set_window_open(self, seconds):
            """Set the thermostate to window open."""
            return self._fritz.set_window_open(self.ain, seconds)

        def get_comfort_temperature(self):
            """Get the thermostate comfort temperature."""
            return self._fritz.get_comfort_temperature(self.ain)

        def get_eco_temperature(self):
            """Get the thermostate eco temperature."""
            return self._fritz.get_eco_temperature(self.ain)

        def get_hkr_state(self):
            """Get the thermostate state."""
            try:
                return {
                    126.5: "off",
                    127.0: "on",
                    self.eco_temperature: "eco",
                    self.comfort_temperature: "comfort",
                }[self.target_temperature]
            except KeyError:
                return "manual"

        def set_hkr_state(self, state):
            """Set the state of the thermostat.
            Possible values for state are: 'on', 'off', 'comfort', 'eco'.
            """
            try:
                value = {
                    "off": 0,
                    "on": 100,
                    "eco": self.eco_temperature,
                    "comfort": self.comfort_temperature,
                }[state]
            except KeyError:
                return

            self.set_target_temperature(value)

    class FritzhomeDevice(
        FritzhomeDeviceAlarm,
        FritzhomeDeviceButton,
        FritzhomeDevicePowermeter,
        FritzhomeDeviceRepeater,
        FritzhomeDeviceSwitch,
        FritzhomeDeviceTemperature,
        FritzhomeDeviceThermostat,
        FritzhomeDeviceLightBulb,
    ):
        """The Fritzhome Device class."""

        def __init__(self, fritz=None, node=None):
            super().__init__(fritz, node)

        def _update_from_node(self, node):
            super()._update_from_node(node)
