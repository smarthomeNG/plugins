"""TR-064 action."""
from io import BytesIO
import lxml.etree as ET
import requests

from .config import TR064_SERVICE_NAMESPACE
from .config import TR064_CONTROL_NAMESPACE
from .config import IGD_SERVICE_NAMESPACE
from .config import IGD_CONTROL_NAMESPACE
from .exceptions import TR064MissingArgumentException, TR064UnknownArgumentException
from .attribute_dict import AttributeDict


# pylint: disable=too-many-instance-attributes, too-few-public-methods
class Action:
    """TR-064 action.

    :param lxml.etree.Element xml:          XML action element
    :param HTTPBasicAuthHandler auth:       HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
    :param str base_url:                    URL to router.
    :param str name:                        Action name
    :param str service_type:                Service type
    :param str service_id:                  Service ID
    :param str control_url:                 Control URL
    """

    # pylint: disable=too-many-arguments
    def __init__(self, xml, auth, base_url, name, service_type, service_id, control_url, verify: bool = False, description_file='tr64desc.xml'):
        self.auth = auth
        self.base_url = base_url
        self.name = name
        self.service_type = service_type
        self.service_id = service_id
        self.control_url = control_url
        self.verify = verify
        self.description_file = description_file
        self.namespaces = IGD_SERVICE_NAMESPACE if 'igd' in description_file else TR064_SERVICE_NAMESPACE
        self.control_namespace = IGD_CONTROL_NAMESPACE if 'igd' in description_file else TR064_CONTROL_NAMESPACE

        ET.register_namespace('s', 'http://schemas.xmlsoap.org/soap/envelope/')
        ET.register_namespace('h', 'http://soap-authentication.org/digest/2001/10/')

        self.headers = {'content-type': 'text/xml; charset="utf-8"'}
        self.envelope = ET.Element(
            '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
            attrib={
                '{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle':
                'http://schemas.xmlsoap.org/soap/encoding/'})
        self.body = ET.SubElement(self.envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

        self.in_arguments = {}
        self.out_arguments = {}

        for argument in xml.findall('./argumentList/argument', namespaces=self.namespaces):
            name = argument.findtext('name', namespaces=self.namespaces)
            direction = argument.findtext('direction', namespaces=self.namespaces)

            if direction == 'in':
                self.in_arguments[name.replace('-', '_')] = name

            if direction == 'out':
                self.out_arguments[name] = name.replace('-', '_')

    def __call__(self, **kwargs):
        missing_arguments = self.in_arguments.keys() - kwargs.keys()
        if missing_arguments:
            raise TR064MissingArgumentException(
                'Missing argument(s) \'' + "', '".join(missing_arguments) + '\'')

        unknown_arguments = kwargs.keys() - self.in_arguments.keys()
        if unknown_arguments:
            raise TR064UnknownArgumentException(
                'Unknown argument(s) \'' + "', '".join(unknown_arguments) + '\'')

        # Add SOAP action to header
        self.headers['soapaction'] = '"{}#{}"'.format(self.service_type, self.name)
        ET.register_namespace('u', self.service_type)

        # Prepare body for request
        self.body.clear()
        action = ET.SubElement(self.body, '{{{}}}{}'.format(self.service_type, self.name))
        for key in kwargs:
            arg = ET.SubElement(action, self.in_arguments[key])
            arg.text = str(kwargs[key])

        # soap._InitChallenge(header)
        data = ET.tostring(self.envelope, encoding='utf-8', xml_declaration=True).decode()
        request = requests.post('{0}{1}'.format(self.base_url, self.control_url),
                                headers=self.headers,
                                auth=self.auth,
                                data=data,
                                verify=self.verify)
        if request.status_code != 200:
            try:
                xml = ET.parse(BytesIO(request.content))
            except Exception:
                return request.status_code
            try:
                error_code = int(xml.find(f".//{{{self.control_namespace['']}}}errorCode").text)
            except Exception:
                error_code = None
                pass
            # self.logger.debug(f"status_code={request.status_code}, error_code={error_code.text}")
            return error_code if error_code is not None else request.status_code

        # Translate response and prepare dict
        xml = ET.parse(BytesIO(request.content))
        response = AttributeDict()
        for arg in list(xml.find('.//{{{}}}{}Response'.format(self.service_type, self.name))):
            name = self.out_arguments[arg.tag]
            response[name] = arg.text
        return response
