"""TR-064 client"""
from io import BytesIO
import lxml.etree as ET
import requests
import logging
from requests.auth import HTTPDigestAuth

from .config import TR064_DEVICE_NAMESPACE
from .exceptions import TR064UnknownDeviceException
from .device import Device


# pylint: disable=too-few-public-methods
class Client:
    """TR-064 client.

    :param str username: Username with access to router.
    :param str password: Passwort to access router.
    :param str base_url: URL to router.
    """

    def __init__(self, username, password, base_url='https://192.168.178.1:49443', description_file='tr64desc.xml', verify: bool = False, logger=None):
        self.base_url = base_url
        self.auth = HTTPDigestAuth(username, password)

        self.description_file = description_file
        self.verify = verify
        self.devices = {}

        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger("TR064 Client")

        self.logger.warning(f"Init TR064 Client")

    def __getattr__(self, name):
        if name not in self.devices:
            self._fetch_devices(self.description_file)

        if name in self.devices:
            return self.devices[name]

        raise TR064UnknownDeviceException

    def _fetch_devices(self, description_file='tr64desc.xml'):
        """Fetch device description."""
        request = requests.get('{0}/{1}'.format(self.base_url, description_file), verify=self.verify)
        # request = requests.get(f'{self.base_url}/{description_file}', verify=self.verify)

        if request.status_code == 200:
            xml = ET.parse(BytesIO(request.content))

            for device in xml.findall('.//device', namespaces=TR064_DEVICE_NAMESPACE):
                name = device.findtext('deviceType', namespaces=TR064_DEVICE_NAMESPACE).split(':')[-2]

                if name not in self.devices:
                    self.devices[name] = Device(device, self.auth, self.base_url, self.verify)
