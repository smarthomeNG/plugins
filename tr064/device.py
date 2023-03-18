"""TR-064 device"""

from .config import TR064_DEVICE_NAMESPACE
from .exceptions import TR064UnknownServiceException
from .service import Service
from .service_list import ServiceList


# pylint: disable=too-few-public-methods
class Device():
    """TR-064 device.

    :param lxml.etree.Element xml:
        XML device element
    :param HTTPBasicAuthHandler auth:
        HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
    :param str base_url:
        URL to router.
    """

    def __init__(self, xml, auth, base_url, verify: bool = False):
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
                self.services[name] = ServiceList()

            self.services[name].append(
                Service(
                    auth,
                    base_url,
                    service_type,
                    service_id,
                    scpdurl,
                    control_url,
                    event_sub_url,
                    self.verify
                )
            )

    def __getattr__(self, name):
        if name in self.services:
            return self.services[name]

        raise TR064UnknownServiceException
