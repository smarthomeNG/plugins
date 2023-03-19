"""TR-064 device"""
from .config import TR064_DEVICE_NAMESPACE
from .config import IGD_DEVICE_NAMESPACE
from .exceptions import TR064UnknownServiceException
from .service import Service
from .service_list import ServiceList


# pylint: disable=too-few-public-methods
class Device:
    """TR-064 device.

    :param lxml.etree.Element xml:
        XML device element
    :param HTTPBasicAuthHandler auth:
        HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
    :param str base_url:
        URL to router.
    """

    def __init__(self, xml, auth, base_url, verify: bool = False, description_file='tr64desc.xml'):
        self.services = {}
        self.verify = verify
        self.description_file = description_file
        self.namespaces = IGD_DEVICE_NAMESPACE if 'igd' in description_file else TR064_DEVICE_NAMESPACE

        for service in xml.findall('./serviceList/service', namespaces=self.namespaces):
            service_type = service.findtext('serviceType', namespaces=self.namespaces)
            service_id = service.findtext('serviceId', namespaces=self.namespaces)
            control_url = service.findtext('controlURL', namespaces=self.namespaces)
            event_sub_url = service.findtext('eventSubURL', namespaces=self.namespaces)
            scpdurl = service.findtext('SCPDURL', namespaces=self.namespaces)

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
                    self.verify,
                    self.description_file
                )
            )

    def __getattr__(self, name):
        if name in self.services:
            return self.services[name]

        raise TR064UnknownServiceException(f"Requested Service Name {name!r} not available.")
