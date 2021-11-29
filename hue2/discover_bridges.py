
import socket
import requests
import xmltodict

from datetime import datetime
import time


def get_bridge_desciptrion(ip, port):
    """
    Get description of bridge

    :param ip:
    :param port:
    :return:
    """
    br_info = {}

    protocol = 'http'
    if str(port) == '443':
        protocol = 'https'

    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(protocol + '://' + ip + ':' + str(port) + '/description.xml', verify=False)
    if r.status_code == 200:
        xmldict = xmltodict.parse(r.text)
        br_info['ip'] = ip
        br_info['port'] = str(port)
        br_info['friendlyName'] = str(xmldict['root']['device']['friendlyName'])
        br_info['manufacturer'] = str(xmldict['root']['device']['manufacturer'])
        br_info['manufacturerURL'] = str(xmldict['root']['device']['manufacturerURL'])
        br_info['modelDescription'] = str(xmldict['root']['device']['modelDescription'])
        br_info['modelName'] = str(xmldict['root']['device']['modelName'])
        br_info['modelURL'] = str(xmldict['root']['device']['modelURL'])
        br_info['modelNumber'] = str(xmldict['root']['device']['modelNumber'])
        br_info['serialNumber'] = str(xmldict['root']['device']['serialNumber'])
        br_info['UDN'] = str(xmldict['root']['device']['UDN'])
        br_info['gatewayName'] = str(xmldict['root']['device'].get('gatewayName', ''))

        br_info['URLBase'] = str(xmldict['root']['URLBase'])
        if br_info['modelName'] == 'Philips hue bridge 2012':
            br_info['version'] = 'v1'
        elif br_info['modelName'] == 'Philips hue bridge 2015':
            br_info['version'] = 'v2'
        else:
            br_info['version'] = 'unknown'

    return br_info


discovered_bridges = {}    # key: bridge_id, value: {, bridge_id, url_base}

def add_discovered_bridge(ip, port):

    if port == 443:
        protocol = 'https'
    else:
        protocol = 'http'
    url_base = protocol + '://' + ip + ':' + str(port)

    bridge_id = '?'
    requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(url_base + '/description.xml', verify=False)
    if r.status_code == 200:
        xmldict = xmltodict.parse(r.text)
        bridge_id = xmldict['root']['device']['serialNumber']

    if not bridge_id in discovered_bridges.keys():
        discovered_bridges[bridge_id] = url_base

    return


# ======================================================================================
#    Discover via mDNS
#

from zeroconf import ServiceBrowser, Zeroconf

class MyListener:

    services = {}

    def remove_service(self, zeroconf, type, name):
        pass

    def update_service(self, zeroconf, type, name, info):
        pass

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        self.services[name] = info


def discover_via_mdns():

    zeroconf = Zeroconf()
    listener = MyListener()
    t1 = datetime.now()
    browser = ServiceBrowser(zeroconf, "_hue._tcp.local.", listener)

    time.sleep(2)

    zeroconf.close()
    t2 = datetime.now()

    for sv in listener.services:
        service = listener.services[sv]

        ip = socket.gethostbyname(service.server)
        if service.port == 443:
            protocol = 'https'
        else:
            protocol = 'http'
        bridge_id = service.properties[b'bridgeid'].decode()

        add_discovered_bridge(ip, service.port)


# ======================================================================================
#    Discover via UPnP - second implementation
#

from .ssdp import discover as ssdp_discover

def discover_via_upnp():

    t1 = datetime.now()
    ssdp_list = ssdp_discover("ssdp:all", timeout=10)
    t2 = datetime.now()

    devices = [u for u in ssdp_list if 'IpBridge' in u.server]
    for d in devices:
        ip_port = d.location.split('/')[2]
        ip = ip_port.split(':')[0]
        port = ip_port.split(':')[1]

        add_discovered_bridge(ip, port)


# ======================================================================================
#    Discover Hue bridges
#

def discover_bridges(mdns=True, upnp=True, httponly=True):

    global discovered_bridges
    discovered_bridges = {}

    if mdns:
        discover_via_mdns()
    if upnp:
        discover_via_upnp()

    if httponly:
        for br_id in discovered_bridges:
            discovered_bridges[br_id] = discovered_bridges[br_id].replace(':443', ':80')

    return discovered_bridges

