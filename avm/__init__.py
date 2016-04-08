#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2016 René Frieß                        rene.friess@gmail.com
#  Version 0.911
#########################################################################
#  Free for non-commercial use
#  
#  Plugin for the software SmartHome.py (NG), which allows to control and read 
#  devices such as the FritzBox. 
#  For all functionality, the TR-064 interface is used.
#
#  Service implementation is mainly based on the information found on:
#  - http://avm.de/service/schnittstellen/
#  - http://www.fhemwiki.de/wiki/FRITZBOX
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py (NG). If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import datetime
import logging
import hashlib
import socket
import time
import threading
from xml.dom import minidom
import urllib.parse
import requests
from requests.packages import urllib3
from requests.auth import HTTPDigestAuth

__AVM__ = 'avm'
logger = logging.getLogger(__AVM__)

class MonitoringService():
    """
    Class which connects to the FritzBox service of the Callmonitor: http://www.wehavemorefun.de/fritzbox/Callmonitor
    Can currently handle three items: 
    - is_call_incoming:    avm_data_type = is_call_incoming, type = bool
    - last_caller:         avm_data_type = last_caller, type = str
    - last_call_date:      avm_data_type = last_call_date, type = str
    """
    def __init__(self, host, port, avm_identifier, callback):
        self._host = host
        self._port = port
        self._avm_identifier = avm_identifier
        self._callback = callback
        self._items = []
        self._items_incoming = []
        self._items_outgoing = []
        self._call_active = dict()
        self._call_active['incoming'] = False
        self._call_active['outgoing'] = False
        self._duration_item = dict()
        self._call_incoming_cid = dict()
        self._call_outgoing_cid = dict()
        self._old_event = dict()
        self._event = dict()
        self.conn = None
    
    def connect(self):
        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((self._host, self._port))
            self._listen_thread = threading.Thread(target=self._listen, name="MonitoringService_%s" % self._avm_identifier).start()
        except Exception as e:
            self.conn = None
            logger.error("MonitoringService: Cannot connect to "+self._host+" on port: "+str(self._port)+", CallMonitor activated by #96*5*? - Error: "+str(e))
            return

    def disconnect(self):
        self._listen_active = False
        try:
            self._listen_thread.join(1)
        except:
            pass
        self.conn.shutdown(2)
    
    def register_item(self, item):
        if item.conf['avm_data_type'] in ['is_call_incoming', 'last_caller_incoming', 'last_call_date_incoming', 'call_event_incoming']:
            self._items_incoming.append(item)
        elif item.conf['avm_data_type'] in ['is_call_outgoing', 'last_caller_outgoing', 'last_call_date_outgoing', 'call_event_outgoing']:
            self._items_outgoing.append(item)
        else:
            self._items.append(item)

    def set_duration_item(self, item):
        self._duration_item[item.conf['avm_data_type']] = item

    def _listen(self, recv_buffer=4096):
        """
        Function which listens to the established connection.
        """
        self._listen_active = True
        buffer = ""
        data = True
        while (self._listen_active == True):
            data = self.conn.recv(recv_buffer)
            buffer += data.decode("utf-8")
            while buffer.find("\n") != -1:
                line, buffer = buffer.split("\n", 1)
                self._parse_line(line)
            
            time.sleep(1)
        return

    def _parse_line(self, line):
        """
        Parses a data set in the form of a line.
        Data Format:
        Ausgehende Anrufe: datum;CALL;ConnectionID;Nebenstelle;GenutzteNummer;AngerufeneNummer;SIP+Nummer
        Eingehende Anrufe: datum;RING;ConnectionID;Anrufer-Nr;Angerufene-Nummer;SIP+Nummer
        Zustandegekommene Verbindung: datum;CONNECT;ConnectionID;Nebenstelle;Nummer;
        Ende der Verbindung: datum;DISCONNECT;ConnectionID;dauerInSekunden;
        """
        line = line.split(";")
        if not line[2] in self._old_event:
            self._old_event[line[2]] = ""
        if not line[2] in self._event:
            self._event[line[2]] = line[1]
        self._old_event[line[2]] = self._event[line[2]] # save event depending on connection id
        self._event[line[2]] = line[1]

        if (self._event[line[2]] == "RING"):
            call_from = line[3]
            call_to = line[4]
            self._trigger(call_from, call_to, line[0], line[2], '')
        elif (self._event[line[2]] == "CALL"):
            call_from = line[4]
            call_to = line[5]
            self._trigger(call_from, call_to, line[0], line[2], line[3])
        elif (self._event[line[2]] == "CONNECT"):
            self._trigger('', '', line[0], line[2], line[3])
        elif (self._event[line[2]] == "DISCONNECT"):
            self._trigger('', '', '', line[2], '')

    def _start_counter(self, timestamp, direction):
        if direction == 'incoming':
            self._call_connect_timestamp = time.mktime(
                datetime.datetime.strptime((timestamp), "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_incoming = threading.Thread(target=self._count_duration_incoming, name="MonitoringService_Duration_Incoming_%s" % self._avm_identifier).start()
        elif direction == 'outgoing':
            self._call_connect_timestamp = time.mktime(
                datetime.datetime.strptime((timestamp), "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_outgoing = threading.Thread(target=self._count_duration_outgoing, name="MonitoringService_Duration_Outgoing_%s" % self._avm_identifier).start()
    
    def _stop_counter(self, direction):
        self._call_active[direction] = False
        try:
            if direction == 'incoming':
                self._duration_counter_thread_incoming.join(1)
            else:
                self._duration_counter_thread_outgoing.join(1)
        except:
            pass

    def _count_duration_incoming(self):
        self._call_active['incoming'] = True
        while (self._call_active['incoming'] == True):
            if self._duration_item['call_duration_incoming'] != None:
                duration = time.time() - self._call_connect_timestamp
                self._duration_item['call_duration_incoming'](int(duration))
            time.sleep(1)

    def _count_duration_outgoing(self):
        self._call_active['outgoing'] = True
        while (self._call_active['outgoing'] == True):
            if self._duration_item['call_duration_outgoing'] != None:
                duration = time.time() - self._call_connect_timestamp
                self._duration_item['call_duration_outgoing'](int(duration))
            time.sleep(1)

    def _trigger(self, call_from, call_to, time, callid, branch):
        """
        Triggers the event: sets item values and looks up numbers in the phone book.
        """
        event = self._event[callid]

        if event == 'RING':
            self._call_incoming_cid = callid # set call id for incoming call
            self._duration_item['call_duration_incoming'](0) # reset duration for incoming calls
            for item in self._items_incoming:  # update items for incoming calls
                if item.conf['avm_data_type'] in ['is_call_incoming']:
                    item(1)
                if item.conf['avm_data_type'] in ['is_call_outgoing']:
                    item(0)
                elif item.conf['avm_data_type'] in ['last_caller_incoming']:
                    item(self._callback(call_from))
                elif item.conf['avm_data_type'] in ['last_call_date_incoming']:
                    item(time)
                elif item.conf['avm_data_type'] in ['call_event_incoming']:
                    item(event.lower())
            for item in self._items: # update generic items
                if item.conf['avm_data_type'] in ['call_event']:
                    item(event.lower())
                elif item.conf['avm_data_type'] in ['call_direction']:
                    item("incoming")
        elif event == 'CALL':
            self._call_outgoing_cid = callid # set call id for outgoing call
            self._duration_item['call_duration_outgoing'](0) # reset duration for outgoing calls
            for item in self._items_outgoing:  # update items for outgoing calls
                if item.conf['avm_data_type'] in ['is_call_incoming']:
                    item(0)
                elif item.conf['avm_data_type'] in ['is_call_outgoing']:
                    item(1)
                elif item.conf['avm_data_type'] in ['last_caller_outgoing']:
                    item(self._callback(call_to))
                elif item.conf['avm_data_type'] in ['last_call_date_outgoing']:
                    item(time)
                elif item.conf['avm_data_type'] in ['call_event_outgoing']:
                    item(event.lower())
            for item in self._items:  # update generic items
                if item.conf['avm_data_type'] in ['call_event']:
                    item(event.lower())
                elif item.conf['avm_data_type'] in ['call_direction']:
                    item("outgoing")
        else: #connect und disconnect
            if event == 'CONNECT':
                # start counter thread
                if self._old_event[callid] == "CALL":  # start counter thread only if duration item set and call is outgoing
                    if self._duration_item['call_duration_outgoing'] != None:
                        self._start_counter(time, 'outgoing', callid)
                elif self._old_event[callid] == "RING":  # start counter thread only if duration item set and call is incoming
                    if self._duration_item['call_duration_incoming'] != None:
                        self._start_counter(time, 'incoming', callid)
                # set item attributes
                if self._old_event[callid] == "CALL":
                    for item in self._items_outgoing:
                        if item.conf['avm_data_type'] in ['call_event_outgoing']:
                            item(event.lower())
                elif self._old_event[callid] == "RING":
                    for item in self._items_incoming:
                        if item.conf['avm_data_type'] in ['call_event_incoming']:
                            item(event.lower())
            elif event == 'DISCONNECT':
                # stop counter threads
                if callid == self._call_incoming_cid:
                    for item in self._items_incoming:
                        if item.conf['avm_data_type'] in ['call_event_incoming']:
                            item(event.lower())
                        elif item.conf['avm_data_type'] in['is_call_incoming']:
                            item(0)
                    if self._duration_item['call_duration_incoming'] != None:
                        self._stop_counter('incoming')
                        self._call_incoming_cid = None
                elif callid == self._call_outgoing_cid:
                    for item in self._items_outgoing:
                        if item.conf['avm_data_type'] in ['call_event_outgoing']:
                            item(event.lower())
                        elif item.conf['avm_data_type'] in ['is_call_outgoing']:
                            item(0)
                    if self._duration_item['call_duration_outgoing'] != None:
                        self._stop_counter('outgoing')
                        self._call_outgoing_cid = None

                # set item attributes
                if self._old_event[callid] == "CALL":
                    for item in self._items_outgoing:
                        if item.conf['avm_data_type'] in ['call_event_outgoing']:
                            item(event.lower())
                elif self._old_event[callid] == "RING":
                    for item in self._items_incoming:
                        if item.conf['avm_data_type'] in ['call_event_incoming']:
                            item(event.lower())
            for item in self._items:
                if item.conf['avm_data_type'] in ['call_event']:
                    item(event.lower())

class FritzDevice():
    """
    This class encapsulates information related to a specific FritzDevice, such has host, port, ssl, username, password, or related items
    """
    def __init__(self, host, port, ssl, username, password, identifier):
        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._identifier = identifier
        self._items = []

    def get_identifier(self):
        """
        Returns the internal identifier of the FritzDevice
        """
        return self._identifier

    def get_host(self):
        """
        Returns the hostname / IP of the FritzDevice
        """
        return self._host

    def get_port(self):
        """
        Returns the port of the FritzDevice
        """
        return self._port

    def get_items(self):
        """
        Returns added items
        """
        return self._items
#
    def get_item_count(self):
        """
        Returns number of added items
        """
        return len(self._items)

    def is_ssl(self):
        """
        Returns information if SSL is enabled
        """
        return self._ssl

    def get_user(self):
        """
        Returns the user for the FritzDevice
        """
        return self._username

    def get_password(self):
        """
        Returns the password for the FritzDevice
        """
        return self._password

class AVM():
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the different TR-064 services on the FritzDevice
    """

    _header = {'SOAPACTION': '','CONTENT-TYPE': 'text/xml; charset="utf-8"'}
    _envelope = """
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">%s
        </s:Envelope>
        """
    _body = """
        <s:Body>
        <u:%(action)s xmlns:u="%(service)s">%(arguments)s
        </u:%(action)s>
        </s:Body>
        """
    _argument = """
        <s:%(name)s>%(value)s</s:%(name)s>"""

    _urn_map = dict([('WLANConfiguration','urn:dslforum-org:service:WLANConfiguration:%s'), #index needs to be adjusted from 1 to 3
                     ('WANCommonInterfaceConfig','urn:dslforum-org:service:WANCommonInterfaceConfig:1'),
                     ('WANIPConnection', 'urn:schemas-upnp-org:service:WANIPConnection:1'),
                     ('TAM', 'urn:dslforum-org:service:X_AVM-DE_TAM:1'),
                     ('OnTel', 'urn:dslforum-org:service:X_AVM-DE_OnTel:1'),
                     ('Homeauto','urn:dslforum-org:service:X_AVM-DE_Homeauto:1'),
                     ('Hosts','urn:dslforum-org:service:Hosts:1'),
                     ('X_VoIP','urn:dslforum-org:service:X_VoIP:1'),
                     ('DeviceConfig', 'urn:dslforum-org:service:DeviceConfig:1'),
                     ('DeviceInfo','urn:dslforum-org:service:DeviceInfo:1'),
                     ('WANDSLInterfaceConfig','urn:dslforum-org:service:WANDSLInterfaceConfig:1'),
                     ('MyFritz', 'urn:dslforum-org:service:X_AVM-DE_MyFritz:1')])

    def __init__(self, smarthome, username='', password='', host='fritz.box', port='49443', ssl='True', verify='False', cycle=300, avm_identifier='fritzbox', call_monitor='False'):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.        
        @param username:           Login name of user, cptional for devices which only support passwords
        @param password:           Password for the FritzDevice
        @param host:               IP or host name of FritzDevice 
        @param port:               Port of the FritzDevice (https: 49443, http: 49000)
        @param ssl:                True or False => https or http in URLs
        @param verify:             True or False => verification of SSL certificate
        @param cycle:              Update cycle in seconds
        @param avm_identifier:     Internal identifier of the FritzDevice
        """
        logger.info('Init AVM Plugin with identifier %s' % avm_identifier)


        if verify == 'False':
            self._verify = False
        else:
            self._verify = True

        if ssl == 'True':
            ssl = True
            if not self._verify:
                urllib3.disable_warnings()
        else:
            ssl = False

        self._fritz_device = FritzDevice(host, port, ssl, username, password, avm_identifier)
        
        if call_monitor == 'True':
            self._monitoring_service = MonitoringService(self._fritz_device.get_host(), 1012, avm_identifier, self.get_contact_name_by_phone_number)
            self._monitoring_service.connect()

        self._cycle = int(cycle)
        self._sh = smarthome
        # Response Cache: Dictionary for storing the result of requests which is used for several different items, refreshed each update cycle. Please use distinct keys!
        self._response_cache = dict()

    def run(self):
        self._sh.scheduler.add(__AVM__+"_"+self._fritz_device.get_identifier(), self._update_loop, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        self._monitoring_service.disconnect()
        self.alive = False

    def _assemble_soap_data(self, action, service, argument=''):
        """
        Builds the soap data set (from body and envelope templates for a given request.
        @param action: string of the action
        @param service: string of the service
        @param argument: dictionary (name : value) of arguments
        @return: string of the soap data
        """
        argument_string = ''
        if argument:
            arguments = [
                self._argument % {'name': name, 'value': value}
                for name, value in argument.items()
            ]
            argument_string = argument_string.join(arguments)
        body = self._body.strip() % {'action': action, 'service': service, 'arguments': argument_string}
        soap_data = self._envelope.strip() % body
        return soap_data

    def _build_url(self, suffix):
        """
        Builds a request url
        @param suffix: url suffix, e.g. "/upnp/control/x_tam"
        @return: string of the url, dependent on settings of the FritzDevice
        """
        if self._fritz_device.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"
        url = "%s://%s:%s%s" % (url_prefix, self._fritz_device.get_host(), self._fritz_device.get_port(), suffix)
        return url

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        logger.debug('Starting update loop for identifier %s' % self._fritz_device.get_identifier())
        for item in self._fritz_device.get_items():
            if not self.alive:
                return
            if item.conf['avm_data_type'] in ['wan_connection_status', 'wan_connection_error', 'wan_is_connected', 'wan_uptime', 'wan_ip']:
                self._update_wan_ip_connection(item)
            elif item.conf['avm_data_type'] in ['tam', 'tam_name', 'tam_new_message_number', 'tam_total_message_number']:
                self._update_tam(item)
            elif item.conf['avm_data_type'] == 'aha_device':
                self._update_home_automation(item)
            elif item.conf['avm_data_type'] in ['wlanconfig', 'wlan_guest_time_remaining']:
                self._update_wlan_config(item)
            elif item.conf['avm_data_type'] in ['wan_total_packets_sent', 'wan_total_packets_received', 'wan_total_bytes_sent', 'wan_total_bytes_received', 'wan_link']:
                self._update_wan_common_interface_configuration(item)
            elif item.conf['avm_data_type'] in ['network_device']:
                self._update_host(item)
            elif item.conf['avm_data_type'] in ['uptime', 'software_version', 'hardware_version', 'serial_number']:
                self._update_fritz_device_info(item)
            elif item.conf['avm_data_type'] in ['wan_upstream', 'wan_downstream']:
                self._update_wan_dsl_interface_config(item)
            elif item.conf['avm_data_type'] == 'myfritz_status':
                self._update_myfritz(item)
        #empty response cache
        self._response_cache = dict()

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to the AVM identifier and adds it to an internal array
        """
        if 'avm_identifier' in item.conf:
            value = item.conf['avm_identifier']
            if value == self._fritz_device.get_identifier():
                if item.conf['avm_data_type']  in ['is_call_incoming','is_call_outgoing',
                                                   'last_caller_incoming', 'last_call_date_incoming', 'call_event_incoming',
                                                   'last_caller_outgoing', 'last_call_date_outgoing', 'call_event_outgoing',
                                                   'call_event', 'call_direction']:
                    # items specific to call monitor
                    self._monitoring_service.register_item(item)
                elif item.conf['avm_data_type'] in ['call_duration_incoming', 'call_duration_outgoing']:
                    # items specific to call monitor duration calculation
                    self._monitoring_service.set_duration_item(item)
                else:
                    # normal items
                    self._fritz_device._items.append(item)                
                if item.conf['avm_data_type']  in ['wlanconfig','tam','aha_device']:
                    # special items which can be changed outside the plugin context and need to be submitted to the FritzDevice
                    return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values - in case they were changed from somewhere else than the AVM plugin (=the FritzDevice) to the FritzDevice.
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_homeauto.pdf
        @param item: item to be updated towards the FritzDevice (Supported item avm_data_types: wlanconfig, tam, aha_device)
        """
        if caller != 'AVM':
            if item.conf['avm_data_type']  in ['wlanconfig','tam']:
                action = 'SetEnable'
            elif item.conf['avm_data_type'] == 'aha_device':
                action = 'SetSwitch'
            else:
                logger.error("%s is not defined to be updated." % item.conf['avm_data_type'])
                return
            
            headers = self._header.copy()
            if item.conf['avm_data_type']  == 'wlanconfig':
                if int(item.conf['avm_wlan_index']) > 0:
                    headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WLANConfiguration'] % str(item.conf['avm_wlan_index']), action)
                    soap_data = self._assemble_soap_data(action, self._urn_map['WLANConfiguration'] % str(item.conf['avm_wlan_index']),{'NewEnable':int(item())})
                else:
                    logger.error('No wlan_index attribute provided')
            elif item.conf['avm_data_type'] == 'tam':
                headers['SOAPACTION'] = "%s#%s" % (self._urn_map['TAM'], action)
                soap_data = self._assemble_soap_data(action, self._urn_map['TAM'],{'NewIndex':0,'NewEnable':int(item())})
            elif item.conf['avm_data_type'] == 'aha_device':
                headers['SOAPACTION'] = "%s#%s" % (self._urn_map['Homeauto'], action)
                # SwitchState: OFF, ON, TOGGLE, UNDEFINED
                if int(item()) == 1:
                    switch_state = "ON"
                else:
                    switch_state = "OFF"
                soap_data = self._assemble_soap_data(action, self._urn_map['Homeauto'],{'NewAIN':item.conf['ain'].strip(),'NewSwitchState':switch_state})
            
            if item.conf['avm_data_type'] == 'wlanconfig':
                param = "%s%s%s" % ("/upnp/control/", item.conf['avm_data_type'], item.conf['avm_wlan_index'])
                url = self._build_url(param)
            elif item.conf['avm_data_type'] == 'tam':
                url = self._build_url("/upnp/control/x_tam")
            elif item.conf['avm_data_type'] == 'aha_device':
                url = self._build_url("/upnp/control/x_homeauto")

            try:
                requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request for updating item towards the FritzDevice: %s" % str(e))
                return

    def get_contact_name_by_phone_number(self, phone_number=''):
        """
        Searches the phone book for a contact by a given (complete) phone number
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf        
        Used information from https://www.symcon.de/forum/threads/25745-FritzBox-mit-SOAP-auslesen-und-steuern
        @param phone_number: full phone number of contact
        @return: string of the contact's real name
        """
        url = self._build_url("/upnp/control/x_contact")
        headers = self._header.copy()
        action = "GetPhonebook"
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['OnTel'],action)
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'],{'NewPhonebookID':0})

        try:
            response = requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:            
            logger.error("Exception when sending POST request or parsing response: %s" % str(e))
            return

        pb_url_xml = xml.getElementsByTagName('NewPhonebookURL')
        if (len(pb_url_xml) > 0):
            pb_url = pb_url_xml[0].firstChild.data
            try:
                pb_result = requests.get(pb_url, verify=self._verify)
                pb_xml = minidom.parseString(pb_result.content)
            except Exception as e:            
                logger.error("Exception when sending GET request or parsing response: %s" % str(e))
                return
            contacts = pb_xml.getElementsByTagName('contact')
            if (len(contacts) > 0):
                for contact in contacts:
                    phone_numbers = contact.getElementsByTagName('number')
                    if (phone_numbers.length > 0):
                        i = phone_numbers.length
                        while (i >= 0):
                            i -= 1
                            if phone_number in phone_numbers[i].firstChild.data:
                                return contact.getElementsByTagName('realName')[0].firstChild.data.strip()
                # no contact with phone number found, return number only
                return phone_number
        else: 
            logger.error("Phonebook not available on the FritzDevice")

        return

    def get_calllist(self):
        """
        Returns an array of all calllist entries
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf        
        
        @return: Array of calllist entries with the attributes 'Id','Type','Caller','Called','CalledNumber','Name','Numbertype','Device','Port','Date','Duration' (some optional)
        """
        url = self._build_url("/upnp/control/x_contact")
        headers = self._header.copy()
        action = "GetCallList"
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['OnTel'],action)
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'],{'NewPhonebookID':0})
        try:
            response = requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:            
            logger.error("Exception when sending POST request or parsing response: %s" % str(e))
            return

        calllist_url_xml = xml.getElementsByTagName('NewCallListURL')
        if (len(calllist_url_xml) > 0):
            calllist_url = calllist_url_xml[0].firstChild.data

            try:
                calllist_result = requests.get(calllist_url, verify=self._verify)
                calllist_xml = minidom.parseString(calllist_result.content)
            except Exception as e:            
                logger.error("Exception when sending GET request or parsing response: %s" % str(e))
                return

            calllist_entries = calllist_xml.getElementsByTagName('Call')
            result_entries = []
            if (len(calllist_entries) > 0):              
                for calllist_entry in calllist_entries:
                    result_entry = {}
                    attributes = ['Id','Type','Caller','Called','CalledNumber','Name','Numbertype','Device','Port','Date','Duration']
                    
                    for attribute in attributes:
                        attribute_value = calllist_entry.getElementsByTagName(attribute)
                        if len(attribute_value) > 0:
                            if attribute_value[0].hasChildNodes():
                                if attribute != 'Date':
                                    result_entry[attribute] = attribute_value[0].firstChild.data
                                else:
                                    result_entry[attribute] = datetime.datetime.strptime(attribute_value[0].firstChild.data, '%d.%m.%y %H:%M')

                    result_entries.append(result_entry)
                return result_entries
            else: 
                logger.debug("No calllist entries on the FritzDevice")
        else: 
            logger.error("Calllist not available on the FritzDevice")

        return

    def reboot(self):
        """
        Reboots the FritzDevice
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceconfigSCPD.pdf
        """
        url = self._build_url("/upnp/control/deviceconfig")
        action = 'Reboot'
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['DeviceConfig'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceConfig'])
        try:
            requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

    def reconnect(self):
        """
        Reconnects the FritzDevice to the WAN 
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf
        """
        url = self._build_url("/igdupnp/control/WANIPConn1")
        action = 'ForceTermination'
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WANIPConnection'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['WANIPConnection'])
        try:
            requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

    def set_call_origin(self, phone_name):
        """
        Sets the call origin, e.g. before running "start_call" 
        Uses: 
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        
        @param phone_name: full phone identifier, could be e.g. "**610" for an internal device
        """
        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialNumber'
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['X_VoIP'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'],{'NewX_AVM-DE_PhoneName':phone_name.strip()})
        try:
            requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

    def start_call(self, phone_number):
        """
        Triggers a call for a given phone number
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        
        @param phone_number: full phone number to call
        """
        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialNumber'
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['X_VoIP'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'],{'NewX_AVM-DE_PhoneNumber':phone_number.strip()})
        try:
            requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

    def cancel_call(self):
        """
        Cancels an active call
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        """
        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialHangup'
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['X_VoIP'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'])
        try:
            requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

    def is_host_active(self, mac_address):
        """
        Checks if a MAC address is active on the FritzDevice, e.g. the status can be used for simple presence detection
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf
        Also reference: https://blog.pregos.info/2015/11/07/anwesenheitserkennung-fuer-smarthome-mit-der-fritzbox-via-tr-064/        
        @param mac_address: mac address of the host
        @return: True or False, depending if the host is active on the FritzDevice
        """
        url = self._build_url("/upnp/control/hosts")
        headers = self._header.copy()
        action = 'GetSpecificHostEntry'
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['Hosts'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'],{'NewMACAddress':mac_address})
        response = requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
        
        xml = minidom.parseString(response.content)
        tag_content = xml.getElementsByTagName('NewActive')
        if (len(tag_content) > 0):
            is_active = tag_content[0].firstChild.data
        else:
            is_active = False
            logger.debug("MAC Address not available on the FritzDevice - ID: %s" % self._fritz_device.get_identifier())
        return bool(is_active)

    def _update_myfritz(self, item):
        """
        Retrieves information related to myfritz status of the FritzDevice
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_myfritzSCPD.pdf        
        @param item: item to be updated (Supported item avm_data_types: myfritz_status)
        """        
        url = self._build_url("/upnp/control/x_myfritz")
        headers = self._header.copy()

        if item.conf['avm_data_type'] == 'myfritz_status':
            action = 'GetInfo'
            headers['SOAPACTION'] = "%s#%s" % (self._urn_map['MyFritz'], action)
            soap_data = self._assemble_soap_data(action, self._urn_map['MyFritz'])
        else:
            logger.error("Attribute %s not supported by plugin method" % item.conf['avm_data_type'])
            return

        try:
            response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:
            logger.error("Exception when sending POST request or parsing response: %s" % str(e))
            return
        
        tag_content = xml.getElementsByTagName('NewEnabled')
        if (len(tag_content) > 0):
            item(tag_content[0].firstChild.data)

    def _update_host(self, item):
        """
        Retrieves information related to a network_device represented by its MAC address, e.g. the status of the network_device can be used for simple presence detection
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf
        Also reference: https://blog.pregos.info/2015/11/07/anwesenheitserkennung-fuer-smarthome-mit-der-fritzbox-via-tr-064/
        @param item: item to be updated (Supported item avm_data_types: network_device, child item avm_data_types: device_ip, device_connection_type, device_hostname)
        """
        url = self._build_url("/upnp/control/hosts")
        headers = self._header.copy()
        
        if item.conf['avm_data_type'] == 'network_device':
            action = 'GetSpecificHostEntry'
            headers['SOAPACTION'] = "%s#%s" % (self._urn_map['Hosts'], action)
            soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'],{'NewMACAddress':item.conf['mac']})
        else:
            logger.error("Attribute %s not supported by plugin method" % item.conf['avm_data_type'])
            return

        try:
            response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:            
            logger.error("Exception when sending POST request: %s" % str(e))
            return

        tag_content = xml.getElementsByTagName('NewActive')
        if (len(tag_content) > 0):
            item(tag_content[0].firstChild.data)
            for child in item.return_children():
                    if child.conf['avm_data_type'] == 'device_ip':
                        device_ip = xml.getElementsByTagName('NewIPAddress')
                        if (len(device_ip) > 0):
                            child(device_ip[0].firstChild.data)
                        else:
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
                    elif child.conf['avm_data_type'] == 'device_connection_type':
                        device_connection_type = xml.getElementsByTagName('NewInterfaceType')
                        if (len(device_connection_type) > 0):
                            child(device_connection_type[0].firstChild.data)
                        else:
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
                    elif child.conf['avm_data_type'] == 'device_hostname':
                        device_hostname = xml.getElementsByTagName('NewHostName')
                        if (len(device_hostname) > 0):
                            child(device_hostname[0].firstChild.data)
                        else:
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        else:
            item(0)
            logger.debug("MAC Address not available on the FritzDevice - ID: %s" % self._fritz_device.get_identifier())

    def _update_home_automation(self, item):
        """
        Updates AVM home automation device related information
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_homeauto.pdf
        @param item: item to be updated (Supported item avm_data_types: aha_device)
        """
        url = self._build_url("/upnp/control/x_homeauto")
        headers = self._header.copy()
        
        if item.conf['avm_data_type'] == 'aha_device':
            action = 'GetSpecificDeviceInfos'
            headers['SOAPACTION'] = "%s#%s" % (self._urn_map['Homeauto'], action)
            soap_data = self._assemble_soap_data(action, self._urn_map['Homeauto'],{'NewAIN':item.conf['ain'].strip()})
        else:
            logger.error("Attribute %s not supported by plugin method" % item.conf['avm_data_type'])
            return

        try:
            response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:            
            logger.error("Exception when sending POST request or parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'aha_device':
            element_xml = xml.getElementsByTagName('NewSwitchState')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
                for child in item.return_children():
                    if child.conf['avm_data_type'] == 'temperature':
                        temp = xml.getElementsByTagName('NewTemperatureCelsius')
                        if (len(temp) > 0):
                            child(int(temp[0].firstChild.data))
                        else: 
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
                    elif child.conf['avm_data_type'] == 'power':
                        power = xml.getElementsByTagName('NewMultimeterPower')
                        if (len(power) > 0):
                            child(int(power[0].firstChild.data))
                        else: 
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
                    elif child.conf['avm_data_type'] == 'energy':
                        energy = xml.getElementsByTagName('NewMultimeterEnergy')
                        if (len(energy) > 0):
                            child(int(energy[0].firstChild.data))
                        else: 
                            logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])

    def _update_fritz_device_info(self, item):
        """
        Updates FritzDevice specific information    
        Uses: 
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceinfoSCPD.pdf        
        @param item: Item to be updated (Supported item avm_data_types: uptime, software_version, hardware_version,serial_number, description)
        """
        url = self._build_url("/upnp/control/deviceinfo")
        headers = self._header.copy()

        if item.conf['avm_data_type'] in ['uptime', 'software_version', 'hardware_version', 'serial_number']:
            action = 'GetInfo'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return

        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['DeviceInfo'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceInfo'])

        if not "dev_info_"+action in self._response_cache:
            try:
                response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request: %s" % str(e))
                return
            self._response_cache["dev_info_"+action] = response.content
        else:
            logger.debug("Accessing DeviceInfo reponse cache for action %s!" % action)

        try:
            xml = minidom.parseString(self._response_cache["dev_info_"+action])
        except Exception as e:            
            logger.error("Exception when parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'uptime':
            element_xml = xml.getElementsByTagName('NewUpTime')
            if (len(element_xml) > 0):
                item(int(element_xml[0].firstChild.data))
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'software_version':
            element_xml = xml.getElementsByTagName('NewSoftwareVersion')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'hardware_version':
            element_xml = xml.getElementsByTagName('NewHardwareVersion')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'serial_number':
            element_xml = xml.getElementsByTagName('NewSerialNumber')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
    
    def _update_tam(self, item):
        """
        Updates telephone answering machine (TAM) related information    
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        @param item: item to be updated (Supported item avm_data_types: tam, child item avm_data_types: tam_name)
        """
        url = self._build_url("/upnp/control/x_tam")
        headers = self._header.copy()

        if item.conf['avm_data_type'] in ['tam', 'tam_name']:
            action = 'GetInfo'
        elif item.conf['avm_data_type'] in ['tam_new_message_number', 'tam_total_message_number']:
            action = 'GetMessageList'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return

        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['TAM'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['TAM'],{'NewIndex':0})

        if not "tam_"+action in self._response_cache:
            try:
                response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request: %s" % str(e))
                return
            self._response_cache["tam_"+action] = response.content
        else:
            logger.debug("Accessing TAM reponse cache for action %s!" % action)
        
        try:
            xml = minidom.parseString(self._response_cache["tam_"+action])
        except Exception as e:            
            logger.error("Exception when parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'tam':
            element_xml = xml.getElementsByTagName('NewEnable')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'tam_name':
            element_xml = xml.getElementsByTagName('NewName')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] in ['tam_new_message_number', 'tam_total_message_number']:
            message_url_xml = xml.getElementsByTagName('NewURL')
            if (len(message_url_xml) > 0):
                message_url = message_url_xml[0].firstChild.data

                if not "tam_messages" in self._response_cache:
                    try:
                        message_result = requests.get(message_url, verify=self._verify)
                    except Exception as e:            
                        logger.error("Exception when sending GET request: %s" % str(e))
                        return
                    self._response_cache["tam_messages"] = message_result.content
                else:
                    logger.debug("Accessing TAM reponse cache for action %s!" % action)
                
                try:
                    message_xml = minidom.parseString(self._response_cache["tam_messages"])
                except Exception as e:            
                    logger.error("Exception when parsing response: %s" % str(e))
                    return

                messages = message_xml.getElementsByTagName('Message')
                message_count = 0
                if (len(messages) > 0):
                    if item.conf['avm_data_type'] == 'tam_total_message_number':
                        message_count = len(messages)
                    elif item.conf['avm_data_type'] == 'tam_new_message_number':
                        for message in messages:
                            is_new = message.getElementsByTagName('New')
                            if int(is_new[0].firstChild.data) == 1:
                                message_count = message_count+1
                item(message_count)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])

    def _update_wlan_config(self, item):
        """
        Updates wlan related information, all items of this method need an numeric avm_wlan_index (typically 1-3)
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        @param item: item to be updated (Supported item avm_data_types: wlanconfig, wlan_guest_time_remaining
        """
        if int(item.conf['avm_wlan_index']) > 0:
            url = self._build_url("/upnp/control/wlanconfig%s" % item.conf['avm_wlan_index'])
        else:
            logger.error('No wlan_index attribute provided')

        headers = self._header.copy()

        if item.conf['avm_data_type']  == 'wlanconfig':
            action = 'GetInfo'
        elif item.conf['avm_data_type'] == 'wlan_guest_time_remaining':
            action = 'X_AVM-DE_GetWLANExtInfo'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return

        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WLANConfiguration'] % str(item.conf['avm_wlan_index']), action)
        soap_data = self._assemble_soap_data(action,self._urn_map['WLANConfiguration'] % str(item.conf['avm_wlan_index']))

        try:
            response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:            
            logger.error("Exception when sending POST request or parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'wlanconfig':
            element_xml = xml.getElementsByTagName('NewEnable')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wlan_guest_time_remaining':
            element_xml = xml.getElementsByTagName('NewX_AVM-DE_TimeRemain')
            if (len(element_xml) > 0):
                item(int(element_xml[0].firstChild.data))
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])

    def _update_wan_dsl_interface_config(self, item):
        """
        Updates wide area network (WAN) speed related information
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wandslifconfigSCPD.pdf
        @param item: item to be updated (Supported item avm_data_types: wan_upstream, wan_downstream)
        """
        if item.conf['avm_data_type'] in ['wan_upstream', 'wan_downstream']:
            action = 'GetInfo'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return
        
        url = self._build_url("/upnp/control/wandslifconfig1")
        
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WANDSLInterfaceConfig'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['WANDSLInterfaceConfig'])

        # if action has not been called in a cycle so far, request it and cache response
        if not "wan_dsl_interface_config_"+action in self._response_cache:
            try:
                response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request: %s" % str(e))
                return
            self._response_cache["wan_dsl_interface_config_"+action] = response.content
        else:
            logger.debug("Accessing TAM reponse cache for action %s!" % action)

        try:
            xml = minidom.parseString(self._response_cache["wan_dsl_interface_config_"+action])
        except Exception as e:            
            logger.error("Exception when parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'wan_upstream':
            element_xml = xml.getElementsByTagName('NewUpstreamCurrRate')
            if (len(element_xml) > 0):
                item(int(element_xml[0].firstChild.data))
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_downstream':
            element_xml = xml.getElementsByTagName('NewDownstreamCurrRate')
            if (len(element_xml) > 0):
                item(int(element_xml[0].firstChild.data))
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        
    def _update_wan_common_interface_configuration(self, item):
        """
        Updates wide area network (WAN) related information    
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wancommonifconfigSCPD.pdf
        @param item: item to be updated (Supported item avm_data_types: wan_total_packets_sent, wan_total_packets_received, wan_total_bytes_sent, wan_total_bytes_received)
        """
        url = self._build_url("/upnp/control/wancommonifconfig1")

        if item.conf['avm_data_type']  == 'wan_total_packets_sent':
            action = 'GetTotalPacketsSent'
        elif item.conf['avm_data_type'] == 'wan_total_packets_received':
            action = 'GetTotalPacketsReceived'
        elif item.conf['avm_data_type'] == 'wan_total_bytes_sent':
            action = 'GetTotalBytesSent'
        elif item.conf['avm_data_type'] == 'wan_total_bytes_received':
            action = 'GetTotalBytesReceived'
        elif item.conf['avm_data_type'] == 'wan_link':
            action = 'GetCommonLinkProperties'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return
        
        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WANCommonInterfaceConfig'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['WANCommonInterfaceConfig'])

        # if action has not been called in a cycle so far, request it and cache response
        if not "wan_common_interface_configuration_"+action in self._response_cache:
            try:
                response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request: %s" % str(e))
                return
            self._response_cache["wan_common_interface_configuration_"+action] = response.content
        else:
            logger.debug("Accessing TAM reponse cache for action %s!" % action)

        try:
            xml = minidom.parseString(self._response_cache["wan_common_interface_configuration_"+action])
        except Exception as e:            
            logger.error("Exception when parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] == 'wan_total_packets_sent':
            element_xml = xml.getElementsByTagName('NewTotalPacketsSent')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_total_packets_received':
            element_xml = xml.getElementsByTagName('NewTotalPacketsReceived')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_total_bytes_sent':
            element_xml = xml.getElementsByTagName('NewTotalBytesSent')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_total_bytes_received':
            element_xml = xml.getElementsByTagName('NewTotalBytesReceived')
            if (len(element_xml) > 0):                
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_link':
            element_xml = xml.getElementsByTagName('NewPhysicalLinkStatus')
            if (len(element_xml) > 0):                
                if element_xml[0].firstChild.data == 'Up':
                    item(True)
                else:
                    item(False)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])

    def _update_wan_ip_connection(self, item):
        """
        Updates wide area network (WAN) IP related information    
        Uses:
        http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf
        @param item: item to be updated (Supported item avm_data_types: wan_connection_status, wan_is_connected, wan_uptime, wan_ip)
        """
        url = self._build_url("/igdupnp/control/WANIPConn1")

        if item.conf['avm_data_type'] in ['wan_connection_status','wan_is_connected','wan_uptime','wan_connection_error']:
            action = 'GetStatusInfo'
        elif item.conf['avm_data_type'] == 'wan_ip':
            action = 'GetExternalIPAddress'
        else:
            logger.error("Attribute %s not supported by plugin" % item.conf['avm_data_type'])
            return

        headers = self._header.copy()
        headers['SOAPACTION'] = "%s#%s" % (self._urn_map['WANIPConnection'], action)
        soap_data = self._assemble_soap_data(action, self._urn_map['WANIPConnection'])

        # if action has not been called in a cycle so far, request it and cache response
        if not "wan_ip_connection_"+action in self._response_cache:
            try:
                response= requests.post(url, data=soap_data, headers=headers, auth=HTTPDigestAuth(self._fritz_device.get_user(), self._fritz_device.get_password()), verify=self._verify)
            except Exception as e:            
                logger.error("Exception when sending POST request: %s" % str(e))
            self._response_cache["wan_ip_connection_"+action] = response.content
        else:
            logger.debug("Accessing TAM reponse cache for action %s!" % action)

        try:
            xml = minidom.parseString(self._response_cache["wan_ip_connection_"+action])
        except Exception as e:            
            logger.error("Exception when parsing response: %s" % str(e))
            return

        if item.conf['avm_data_type'] in ['wan_connection_status','wan_is_connected']:
            element_xml = xml.getElementsByTagName('NewConnectionStatus')
            if (len(element_xml) > 0):                
                if item.conf['avm_data_type'] == 'wan_connection_status':
                    item(element_xml[0].firstChild.data)
                elif item.conf['avm_data_type'] == 'wan_is_connected':
                    if element_xml[0].firstChild.data == 'Connected':
                        item(True)
                    else:
                        item(False)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_uptime':
            element_xml = xml.getElementsByTagName('NewUptime')
            if (len(element_xml) > 0):
                item(int(element_xml[0].firstChild.data))
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
        elif item.conf['avm_data_type'] == 'wan_connection_error':
            element_xml = xml.getElementsByTagName('NewLastConnectionError')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])
                
        elif item.conf['avm_data_type'] == 'wan_ip':
            element_xml = xml.getElementsByTagName('NewExternalIPAddress')
            if (len(element_xml) > 0):
                item(element_xml[0].firstChild.data)
            else: 
                logger.error("Attribute %s not available on the FritzDevice" % item.conf['avm_data_type'])