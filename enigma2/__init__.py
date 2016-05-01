#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2016 René Frieß                        rene.friess@gmail.com
#  Version 0.1
#########################################################################
#  Free for non-commercial use
#
#  Plugin for the software SmartHome.py (NG), which allows to control and read 
#  enigma2 compatible devices such as the VUSolo4k. For the API, the openwebif
#  needs to be installed.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
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
import socket
import time
import threading
from xml.dom import minidom
import requests
from requests.packages import urllib3
from requests.auth import HTTPDigestAuth

class Enigma2Device():
    """
    This class encapsulates information related to a specific Enigma2Device, such has host, port, ssl, username, password, or related items
    """
    def __init__(self, host, port, ssl, username, password, identifier):
        self.logger = logging.getLogger(__name__)
        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._identifier = identifier
        self._items = []

    def get_identifier(self):
        """
        Returns the internal identifier of the Enigma2Device

        :return: identifier of the device, as set in plugin.conf
        """
        return self._identifier

    def get_host(self):
        """
        Returns the hostname / IP of the Enigma2Device

        :return: hostname of the device, as set in plugin.conf
        """
        return self._host

    def get_port(self):
        """
        Returns the port of the Enigma2Device

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

    def get_user(self):
        """
        Returns the user for the Enigma2Device

        :return: user, as set in plugin.conf
        """
        return self._username

    def get_password(self):
        """
        Returns the password for the Enigma2Device

        :return: password, as set in plugin.conf
        """
        return self._password

class Enigma2():
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the Enigma2Device
    """

    _url_suffix_map = dict([('about','/web/about'),
                            ('deviceinfo', '/web/deviceinfo'),
                            ('powerstate', '/web/powerstate'),
                            ('subservices', '/web/subservices'),
                            ('remotecontrol','/web/remotecontrol'),
                            ('message', '/web/message'),
                            ('messageanswer','/web/messageanswer'),
                            ('getaudiotracks', '/web/getaudiotracks')])

    def __init__(self, smarthome, username='', password='', host='fritz.box', port='49443', ssl='True', verify='False', cycle=300, device_id='enigma2'):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param username:           Login name of user, cptional for devices which only support passwords
        :param password:           Password for the Enigma2Device
        :param host:               IP or host name of Enigma2Device
        :param port:               Port of the Enigma2Device (https: 49443, http: 49000)
        :param ssl:                True or False => https or http in URLs
        :param verify:             True or False => verification of SSL certificate
        :param cycle:              Update cycle in seconds
        :param device_id:          Internal identifier of the Enigma2Device
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Enigma2 Plugin with device_id %s' % device_id)

        self._session = requests.Session()
        self._timeout = 10

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

        self._enigma2_device = Enigma2Device(host, port, ssl, username, password, device_id)

        self._cycle = int(cycle)
        self._sh = smarthome

        # Response Cache: Dictionary for storing the result of requests which is used for several different items, refreshed each update cycle. Please use distinct keys!
        self._response_cache = dict()

    def run(self):
        """
        Run method for the plugin
        """
        self._sh.scheduler.add(__name__+"_"+self._enigma2_device.get_identifier(), self._update_loop, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False


    def _build_url(self, suffix, parameter=''):
        """
        Builds a request url

        :param suffix: url suffix, e.g. "/upnp/control/x_tam"
        :return: string of the url, dependent on settings of the Enigma2Device
        """
        if self._enigma2_device.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"
        url = "%s://%s:%s%s?%s" % (url_prefix, self._enigma2_device.get_host(), self._enigma2_device.get_port(), suffix, parameter)
        return url

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """
        self.logger.debug('Starting update loop for identifier %s' % self._enigma2_device.get_identifier())
        for item in self._enigma2_device.get_items():
            if not self.alive:
                return
            if item.conf['enigma2_page'] in ['about', 'powerstate', 'subservices']:
                self._update(item)

        #empty response cache
        self._response_cache = dict()

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to the Enigma2 device id and adds it to an internal array

        :param item: The item to process.
        """
        if 'device_id' in item.conf:
            value = item.conf['device_id']

            if value == self._enigma2_device.get_identifier():
                # normal items
                if 'enigma2_page' in item.conf:
                    if item.conf['enigma2_page'] in ['about', 'powerstate', 'subservices']:
                        self._enigma2_device._items.append(item)
                elif 'enigma2_remote_command_id' in item.conf:                                    # items for TV remote
                    #self._enigma2_device._remote_items.append(item)
                    return self.execute_item

    def execute_item(self, item, caller=None, source=None, dest=None):
        """
        | Write items values - in case they were changed from somewhere else than the Enigma2 plugin (=the Enigma2Device) to the Enigma2Device.

        :param item: item to be updated towards the Enigma2Device
        """
        if caller != 'Enigma2':
            # enigma2 remote control
            if 'enigma2_remote_command_id' in item.conf:
                
                url = self._build_url(self._url_suffix_map['remotecontrol'],'command=%s' % item.conf['enigma2_remote_command_id'])
                try:
                    response = self._session.get(url, timeout=self._timeout, auth=HTTPDigestAuth(self._enigma2_device.get_user(),
                                                                  self._enigma2_device.get_password()), verify=self._verify)
                except Exception as e:
                    self.logger.error("Exception when sending GET request: %s" % str(e))
                    return
                
                xml = minidom.parseString(response.content)
                e2result_xml = xml.getElementsByTagName('e2result')
                e2resulttext_xml = xml.getElementsByTagName('e2resulttext')
                if (len(e2resulttext_xml) > 0 and len(e2result_xml) >0):
                    if not e2resulttext_xml[0].firstChild is None and not e2result_xml[0].firstChild is None:
                        if e2result_xml[0].firstChild.data == 'True':
                            self.logger.debug(e2resulttext_xml[0].firstChild.data)
                            self.send_message("Test", 0)
                            time.sleep(10)
                            self.get_answer()

    def get_audio_tracks(self):
        """
        Retrieves an array of all available audio tracks
        """
        result = []
        url = self._build_url(self._url_suffix_map['getaudiotracks'])
        try:
            response = self._session.get(url, timeout=self._timeout, auth=HTTPDigestAuth(self._enigma2_device.get_user(),
                                                                                         self._enigma2_device.get_password()),
                                         verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:
            self.logger.error("Exception when sending GET request: %s" % str(e))
            return

        e2audiotrack_xml = xml.getElementsByTagName('e2audiotrack')
        if (len(e2audiotrack_xml)) > 0:
            for audiotrack_entry_xml in e2audiotrack_xml:
                result_entry = {}
                e2audiotrackdescription_xml = audiotrack_entry_xml.getElementsByTagName('e2audiotrackdescription')

                if (len(e2audiotrackdescription_xml)) > 0:
                    result_entry['e2audiotrackdescription'] = e2audiotrackdescription_xml[0].firstChild.data

                e2audiotrackid_xml = audiotrack_entry_xml.getElementsByTagName('e2audiotrackid')
                if (len(e2audiotrackid_xml)) > 0:
                    result_entry['e2audiotrackid'] = int(e2audiotrackid_xml[0].firstChild.data)

                e2audiotrackpid_xml = audiotrack_entry_xml.getElementsByTagName('e2audiotrackpid')
                if (len(e2audiotrackpid_xml)) > 0:
                    result_entry['e2audiotrackpid'] = int(e2audiotrackpid_xml[0].firstChild.data)

                e2audiotrackactive_xml = audiotrack_entry_xml.getElementsByTagName('e2audiotrackactive')
                if (len(e2audiotrackactive_xml)) > 0:
                    if e2audiotrackactive_xml[0].firstChild.data in 'True':
                        result_entry['e2audiotrackactive'] = True
                    else:
                        result_entry['e2audiotrackactive'] = False

                result.append(result_entry)

        return result

    def send_message(self, messagetext, messagetype=1, timeout=10):
        """
        Sends a message to the Enigma2 Device
        
        messagetext=Text of Message
        messagetype=Number from 0 to 3, 0= Yes/No, 1= Info, 2=Message, 3=Attention
        timeout=Can be empty or the Number of seconds the Message should disappear after.
        """
        url = self._build_url(self._url_suffix_map['message'],'text=%s&type=%s&timeout=%s' % (messagetext, messagetype, timeout))
        try:
            response = self._session.get(url, timeout=self._timeout, auth=HTTPDigestAuth(self._enigma2_device.get_user(),
                                                          self._enigma2_device.get_password()), verify=self._verify)
        except Exception as e:
            self.logger.error("Exception when sending GET request: %s" % str(e))
            return
        
        xml = minidom.parseString(response.content)
        e2result_xml = xml.getElementsByTagName('e2result')
        e2resulttext_xml = xml.getElementsByTagName('e2resulttext')
        if (len(e2resulttext_xml) > 0 and len(e2result_xml) >0):
            if not e2resulttext_xml[0].firstChild is None and not e2result_xml[0].firstChild is None:
                if e2result_xml[0].firstChild.data == 'True':
                    self.logger.debug(e2resulttext_xml[0].firstChild.data)
                    
    def get_answer(self):
        """
        Retrieves the answer to a currently sent message, take care to take the timeout into account in which the answer can be given and start a thread which is polling the answer for that period.
        """
        url = self._build_url(self._url_suffix_map['message'],'getanswer=now')
        try:
            response = self._session.get(url, timeout=self._timeout, auth=HTTPDigestAuth(self._enigma2_device.get_user(),
                                                          self._enigma2_device.get_password()), verify=self._verify)
            xml = minidom.parseString(response.content)
        except Exception as e:
            self.logger.error("Exception when sending GET request: %s" % str(e))
            return

        e2result_xml = xml.getElementsByTagName('e2state')
        e2resulttext_xml = xml.getElementsByTagName('e2statetext')
        if (len(e2resulttext_xml) > 0 and len(e2result_xml) >0):
            if not e2resulttext_xml[0].firstChild is None and not e2result_xml[0].firstChild is None:
                self.logger.debug(e2resulttext_xml[0].firstChild.data)
                if e2result_xml[0].firstChild.data == 'True':                    
                    return e2resulttext_xml[0].firstChild.data               
                     
    def _update(self, item):
        """
        Updates information found on about page of openwebif

        :param item: item to be updated
        """
        url = self._build_url(self._url_suffix_map[item.conf['enigma2_page']])

        if not 'enigma2_data_type' in item.conf:
            self.logger.error("No enigma2_data_type set in item!")
            return

        if not item.conf['enigma2_page'] in self._response_cache:
            try:
                response = self._session.get(url, timeout=self._timeout, auth=HTTPDigestAuth(self._enigma2_device.get_user(),
                                                                  self._enigma2_device.get_password()), verify=self._verify)
            except Exception as e:
                self.logger.error("Exception when sending POST request: %s" % str(e))
                return
            self._response_cache[item.conf['enigma2_page']] = response.content
        else:
            self.logger.debug("Accessing reponse cache for %s!" % self._url_suffix_map[item.conf['enigma2_page']])

        try:
            xml = minidom.parseString(self._response_cache[item.conf['enigma2_page']])
        except Exception as e:
            self.logger.error("Exception when parsing response: %s" % str(e))
            return

        element_xml = xml.getElementsByTagName(item.conf['enigma2_data_type'])
        if (len(element_xml) > 0):
            #self.logger.debug(element_xml[0].firstChild.data)
            if item.type() == 'bool':
                if element_xml[0].firstChild.data == 'true':
                    item(1)
                else:
                    item(0)
            elif item.type() == 'num':
                if (self._represents_int(element_xml[0].firstChild.data)):
                    item(int(element_xml[0].firstChild.data))
                elif (self._represents_float(element_xml[0].firstChild.data)):
                    item(float(element_xml[0].firstChild.data))
            else:
                item(element_xml[0].firstChild.data)
        else:
            self.logger.error("Attribute %s not available on the Enigma2Device" % item.conf['enigma2_data_type'])

    def _represents_int(self, string):
        try:
            int(string)
            return True
        except ValueError:
            return False

    def _represents_float(self, string):
        try:
            float(string)
            return True
        except ValueError:
            return False