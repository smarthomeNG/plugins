#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
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

from lib.model.smartplugin import SmartPlugin
from lib.utils import Utils
from .webif import WebInterface

TR064_DEVICE_NAMESPACE = {'': 'urn:dslforum-org:device-1-0'}
TR064_SERVICE_NAMESPACE = {'': 'urn:dslforum-org:service-1-0'}

### Devices / Services
""" 
    InternetGatewayDevice
        DeviceInfo
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

        self._session = requests.Session()
        self._timeout = 10
        self._verify = self.get_parameter_value('verify')
        ssl = self.get_parameter_value('ssl')

        if ssl and not self._verify:
            urllib3.disable_warnings()

        self._fritz_device = FritzDevice(self.get_parameter_value('host'), self.get_parameter_value('port'), ssl,
                                         self.get_parameter_value('username'), self.get_parameter_value('password'),
                                         self.get_instance_name(), self)

        self._cycle = int(self.get_parameter_value('cycle'))
        self.alive = False

        self.init_webinterface(WebInterface)


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        # self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # self.logger.debug(f"manufacturer_name = {self._fritz_device.manufacturer_name}")
        # self.logger.debug(f"model_name = {self._fritz_device.model_name}")
        # self.logger.debug(f"safe_port = {self._fritz_device.safe_port}")
        # self.logger.debug(f"network_devices = {self._fritz_device.get_network_devices()}")

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


class FritzDevice:
    """
    This class encapsulates information related to a specific FritzDevice, such has host, port, ssl, username, password, or related items
    """

    def __init__(self, host, port, ssl, username, password, identifier='default', plugin_instance=None):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init FritzDevice")

        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._identifier = identifier
        self._available = True
        self._items = []
        self._smarthome_items = []
        self._smarthome_devices = {}
        self.InternetGatewayDevice = None
        self.LANDevice = None
        self.WANDevice = None
        self.WANConnectionDevice = None

        self.client = FritzDevice.Client(self._username, self._password, base_url=self._build_url(), plugin_instance=plugin_instance)

        self._network_devices = self.network_devices()


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

    def get_identifier(self):
        """
        Returns the internal identifier of the FritzDevice

        :return: identifier of the device, as set in plugin.conf
        """
        return self._identifier

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

    def get_smarthome_items(self):
        """
        Returns added items

        :return: array of smarthome items hold by the plugin
        """
        return self._smarthome_items

    def get_smarthome_devices(self):
        """
        Returns added items

        :return: dict of smarthome devices hold by the plugin
        """
        return self._smarthome_devices

    def get_network_devices(self):
        return self._network_devices

    @property
    def manufacturer_name(self):
        if not self.InternetGatewayDevice:
            self.InternetGatewayDevice = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self.InternetGatewayDevice.NewManufacturerName

    @property
    def manufacturer_oui(self):
        if not self.InternetGatewayDevice:
            self.InternetGatewayDevice = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self.InternetGatewayDevice.NewManufacturerOUI

    @property
    def model_name(self):
        if not self.InternetGatewayDevice:
            self.InternetGatewayDevice = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self.InternetGatewayDevice.NewModelName

    @property
    def desciption(self):
        if not self.InternetGatewayDevice:
            self.InternetGatewayDevice = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self.InternetGatewayDevice.NewDescription

    @property
    def safe_port(self):
        return self.client.InternetGatewayDevice.DeviceInfo.GetSecurityPort().NewSecurityPort

    def network_devices(self):
        devices = dict()
        number_of_entries = self.client.LANDevice.Hosts.GetHostNumberOfEntries()
        for index in range(int(number_of_entries.NewHostNumberOfEntries)):
            host = self.client.LANDevice.Hosts.GetGenericHostEntry(NewIndex=index)
            self._plugin_instance.logger.debug(f"host = {host}")
            devices[index] = {'ip': host.NewIPAddress, 'mac': host.NewMACAddress, 'name': host.NewHostName}
        return devices

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

        def __init__(self, username, password, base_url='https://192.168.178.1:49443', plugin_instance=None):

            # handle plugin instance
            self._plugin_instance = plugin_instance

            self.base_url = base_url
            self.auth = HTTPDigestAuth(username, password)

            self.devices = {}
            self._plugin_instance.logger.debug(f"Init Client")

        def __getattr__(self, name):
            if name not in self.devices:
                self._fetch_devices()

            if name in self.devices:
                return self.devices[name]

        def _fetch_devices(self, description_file='/tr64desc.xml'):

            """Fetch device description."""
            request = requests.get(f'{self.base_url}{description_file}')

            if request.status_code == 200:
                xml = etree.parse(BytesIO(request.content))

                for device in xml.findall('.//device', namespaces=TR064_DEVICE_NAMESPACE):
                    name = device.findtext('deviceType', namespaces=TR064_DEVICE_NAMESPACE).split(':')[-2]
                    if name not in self.devices:
                        self.devices[name] = FritzDevice.Device(device, self.auth, self.base_url)

    class Device:
        """TR-064 device.
        :param lxml.etree.Element xml:
            XML device element
        :param HTTPBasicAuthHandler auth:
            HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
        :param str base_url:
            URL to router.
        """

        def __init__(self, xml, auth, base_url):
            self.logger = logging.getLogger(__name__)
            self.services = {}

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

        def __init__(self, auth, base_url, service_type, service_id, scpdurl, control_url, event_sub_url):
            self.auth = auth
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
            request = requests.get(f'{self.base_url}{scpdurl}')
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
                        self.control_url
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

        def __init__(self, xml, auth, base_url, name, service_type, service_id, control_url):

            self.logger = logging.getLogger(__name__)

            self.auth = auth
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
            self.logger.debug('post request in Action')
            request = requests.post(f'{self.base_url}{self.control_url}',
                                    headers=self.headers,
                                    auth=self.auth,
                                    data=data)
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
