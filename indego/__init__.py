#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 Marco Düchting                   Marco.Duechting@gmx.de
#  Copyright 2018 Bernd Meiners                     Bernd.Meiners@mail.de
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

from lib.module import Modules
from lib.model.smartplugin import *

import base64
import os
import ast
import datetime
import json
import http.client
from dateutil import tz


# If a package is needed, which might be not installed in the Python environment,
# import it like this:
#
# try:
#     import <exotic package>
#     REQUIRED_PACKAGE_IMPORTED = True
# except:
#     REQUIRED_PACKAGE_IMPORTED = False


class Indego(SmartPlugin):
    """
    Main class of the Indego Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    PLUGIN_VERSION = '1.6.0'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')

        self.user = self.get_parameter_value('user')
        self.password = self.get_parameter_value('password')
        self.img_pfad = self.get_parameter_value('img_pfad')
        self.cycle = self.get_parameter_value('cycle')
        self.indego_url = self.get_parameter_value('indego_url')
        self.parent_item = self.get_parameter_value('parent_item')

        self.context_id = ''
        self.user_id = ''
        self.alm_sn = ''
        self.alert_reset = True
        self.auth()
        self.add_keys = {}

        # Check for initialization errors:
        if not self.indego_url:
           self._init_complete = False
           return

        if not self.parent_item:
           self._init_complete = False
           return

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # if plugin should start even without web interface
        self.init_webinterface()

        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.get_sh().scheduler.add('state', self.state, cycle = self.cycle)
        self.get_sh().scheduler.add('alert', self.alert, cycle=3600)
        #self.get_sh().scheduler.add('auth', self.auth, cycle=7190)
        self.get_sh().scheduler.add('device_date', self.device_data, cycle=6000)
        self.get_sh().scheduler.add('get_weather', self.get_weather, cycle=600)
        self.get_sh().scheduler.add('get_next_time', self.get_next_time, cycle=300)
        self.get_sh().scheduler.add('get_smart_frequency', self.get_smart_frequency, cycle=500)
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.get_sh().scheduler.remove('state')
        self.get_sh().scheduler.remove('device_date')
        #self.get_sh().scheduler.remove('alert')
        self.get_url(self.indego_url + 'authenticate',self.context_id,5,'DELETE')
        self.logger.debug("Stop method called")
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
        if self.has_iattr(item.conf, 'indego_command'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format( item, 'indego_command', self.get_iattr_value(item.conf, 'indego_command')))
            return self.send_command

        if self.has_iattr(item.conf, 'indego_smart'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_smart', self.get_iattr_value(item.conf, 'indego_smart')))
            return self.set_smart

        if self.has_iattr(item.conf, 'indego_frequency'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_frequency',self.get_iattr_value(item.conf, 'indego_frequency')))
            return self.set_smart_frequency

        if self.has_iattr(item.conf, 'indego_add_key'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_add_key', self.get_iattr_value(item.conf, 'indego_add_key')))
            self.add_keys[item.conf['indego_add_key']] = item

        return None

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    ### Todo: will we ever need this function with indego plugin?
    ###def update_item(self, item, caller=None, source=None, dest=None):
    ###    """
    ###    Item has been updated
    ###
    ###    This method is called, if the value of an item has been updated by SmartHomeNG.
    ###    It should write the changed value out to the device (hardware/interface) that
    ###    is managed by this plugin.
    ###
    ###    :param item: item to be updated towards the plugin
    ###    :param caller: if given it represents the callers name
    ###    :param source: if given it represents the source
    ###    :param dest: if given it represents the dest
    ###    """
    ###    if caller != self.get_shortname():
    ###        # code to execute, only if the item has not been changed by this this plugin:
    ###        self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))
    ###
    ###        if self.has_iattr(item.conf, 'foo_itemtag'):
    ###            self.logger.debug(
    ###                "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
    ###                                                                                                           caller,
    ###                                                                                                           source,
    ###                                                                                                           dest))
    ###        pass

    ### Todo: will we ever need this function with indego plugin?
    ###def poll_device(self):
    ###    """
    ###    todo: Do we need to obey naming conventions?
    ###    Polls for updates of the device
    ###
    ###    This method is only needed, if the device (hardware/interface) does not propagate
    ###    changes on it's own, but has to be polled to get the actual status.
    ###    It is called by the scheduler.
    ###    """
    ###    # # get the value from the device
    ###    # device_value = ...
    ###    #
    ###    # # find the item(s) to update:
    ###    # for item in self.sh.find_items('...'):
    ###    #
    ###    #     # update the item
    ###    #     item(device_value, self.get_shortname())
    ###    pass

    def fetch_url(self, url, username=None, password=None, timeout=2, body=None):
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        headers = {'Content-Type': 'application/json'}
        plain = True
        if url.startswith('https'):
            plain = False
        lurl = url.split('/')
        host = lurl[2]
        purl = '/' + '/'.join(lurl[3:])
        if plain:
            conn = http.client.HTTPConnection(host, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
        if username and password:
            headers['Authorization'] = ('Basic '.encode() + base64.b64encode((username + ':' + password).encode()))
            self.logger.debug("headers: " + str(headers))
        try:
            conn.request("POST", purl, body=body, headers=headers)
        except Exception as e:
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))
            conn.close()
            return False
        resp = conn.getresponse()
        if resp.status == 200 or resp.status == 201:
            content = resp.read()
        else:
            self.logger.warning("Problem fetching {0}: {1} {2}".format(url, resp.status, resp.reason))
            content = False
        conn.close()
        return content
    
    def set_childitem(self, itemname, value ):
        """
        a shortcut function to set an item with a given value if it exists
        :param itemname:
        :param value:
        :return:
        """
        item = self.get_sh().return_item(self.parent_item + '.' + itemname)  
        if item is not None: 
            item(value, 'indego_plugin')
        else:
            self.logger.warning("Could not set item '{}.{}' to '{}'".format(self.parent_item, itemname, value))

    def get_url(self, url, contextid=None, timeout=40, method='GET'):
        headers = {'Content-Type': 'application/json'}
        headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        headers['x-im-context-id'] = contextid
        plain = True
        if url.startswith('https'):
            plain = False
        lurl = url.split('/')
        host = lurl[2]
        purl = '/' + '/'.join(lurl[3:])
        if plain:
            conn = http.client.HTTPConnection(host, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
        try:
            conn.request(method, purl, headers=headers)
        except Exception as e:
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))
            conn.close()
            return False
        resp = conn.getresponse()
        if resp.status == 401:
            self.logger.warning("get_url returned 401, reconnecting and trying again")
            self.set_childitem('online', False)
            self.auth()
            try:
                conn.request(method, purl, headers=headers)
            except Exception as e:
                self.logger.warning("Problem fetching {0}: {1}".format(url, e))
                conn.close()
                return False
            resp = conn.getresponse()
        if resp.status == 200 or resp.status == 201:
            content = resp.read()
        else:
            self.logger.warning("Problem fetching {0}: {1} {2}".format(url, resp.status, resp.reason))
            content = False
        conn.close()
        return content

    def put_url(self, url, contextid=None, state=None, timeout=2):
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
        headers = {'Content-Type': 'application/json'}
        plain = True
        if url.startswith('https'):
            plain = False
        lurl = url.split('/')
        host = lurl[2]
        purl = '/' + '/'.join(lurl[3:])
        if plain:
            conn = http.client.HTTPConnection(host, timeout=timeout)
        else:
            conn = http.client.HTTPSConnection(host, timeout=timeout)
            headers['x-im-context-id'] = contextid
        body = state
        try:
            conn.request("PUT", purl, body=body, headers=headers)
        except Exception as e:
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))
            conn.close()
            return False
        # resp = conn.getresponse()
        # content = resp.read()
        conn.close()
        self.logger.debug(
            'put gesendet an URL: ' + str(url) + 'context id: ' + str(contextid) + 'command: ' + str(state))
        return True

    def send_command(self, item, command=None, caller=None, source=None, dest=None):
        if self.has_iattr(item.conf, 'indego_command'):
            command = self.get_iattr_value(item.conf,'indego_command')
            self.logger.debug("Function Command " + command + ' ' + str(item()))
            if item():
                message = self.put_url(self.indego_url + 'alms/' + self.alm_sn + '/state', self.context_id, command, 10)
                self.logger.debug("Command " + command + ' gesendet! ' + str(message))

    def set_smart(self, item, command=None, caller=None, source=None, dest=None):
        self.logger.debug("Smart Mode Command " + str(item()))
        if item():
            self.logger.debug("SMAAAAAAAAAAAAAAAAAAAAART aktivieren")
            command = '{"enabled": true}'
        else:
            self.logger.debug("SMAAAAAAAAAAAAAAAAAAAAART deaktivieren")
            command = '{"enabled": false}'
        self.logger.debug("Smart URL: " + self.indego_url + 'alms/' + self.alm_sn + '/predictive')
        message = self.put_url(self.indego_url + 'alms/' + self.alm_sn + '/predictive', self.context_id, command, 10)
        self.logger.debug("Smart Command " + command + ' gesendet! ' + str(message))

    def set_smart_frequency(self, item, frequency=0, caller=None, source=None, dest=None):
        frequency = str(item())
        command = '{"user_adjustment": ' + frequency + '}'
        self.logger.debug("frequency smart " + command + ' ' + str(item()))
        message = self.put_url(self.indego_url + 'alms/' + self.alm_sn + '/predictive/useradjustment', self.context_id,
                               command, 10)
        self.logger.debug("Command " + command + ' gesendet! ' + str(message))

    def auth(self):
        auth_response = self.fetch_url(self.indego_url + 'authenticate', self.user, self.password, 25,
                                       '{"device":"","os_type":"Android","os_version":"4.0","dvc_manuf":"unknown","dvc_type":"unknown"}')
        if auth_response == False:
            self.logger.error('AUTHENTICATION INDEGO FAILED! Plugin not working now.')
        else:
            auth_response = json.loads(auth_response.decode(encoding='UTF-8', errors='strict'))
            self.logger.debug("String Auth: " + str(auth_response))
            self.context_id = auth_response['contextId']
            self.logger.info("context ID received " + self.context_id)
            self.user_id = auth_response['userId']
            self.logger.info("User ID received " + self.user_id)
            self.alm_sn = auth_response['alm_sn']
            self.logger.info("Serial received " + self.alm_sn)

    def get_next_time(self):
        next_time = self.get_url(
            self.indego_url + 'alms/' + self.alm_sn + '/predictive/nextcutting?last=YYYY-MM-DDTHH:MM:SS%2BHH:MM',
            self.context_id, 10)
        if next_time == False:
            self.logger.error("Error getting next smartmow time")
        else:
            self.logger.debug("Next time raw" + str(next_time))
            next_time = next_time.decode(encoding='UTF-8', errors='ignore')
            next_time = json.loads(next_time)
            next_time = next_time['mow_next']

            self.logger.debug("Next time raw 2: " + str(next_time))
            # next_time = next_time[:-6]
            # next_time = datetime.datetime.strptime(next_time,'%Y-%m-%dT%H:%M:%S').replace(tzinfo=tz.gettz('UTC')).astimezone(self.get_sh().tzinfo())
            # #datetime.datetime.strptime(next_time,'%Y-%m-%dT%H:%M:%S+02:00').replace(tzinfo=self.get_sh().tzinfo())
            next_time = next_time.replace(":", "")
            next_time = datetime.datetime.strptime(next_time, '%Y-%m-%dT%H%M%S%z')
            self.logger.debug("Next time final " + str(next_time))
            self.set_childitem('next_time',next_time)

    def get_weather(self):
        weather = self.get_url(self.indego_url +'alms/'+ self.alm_sn +'/predictive/weather',self.context_id,10)
        weather = weather.decode(encoding='UTF-8',errors='ignore')
        weather = json.loads(weather)
        for i in weather['LocationWeather']['forecast']['intervals']:
            position = str(weather['LocationWeather']['forecast']['intervals'].index(i))
            self.logger.debug("POSITION "+str(position))
            for x in i:
                wertpunkt = x
                wert = str(i[x])
                self.logger.debug("ITEEEEEM "+'indego.weather.int_'+position+'.'+wertpunkt)
                if wertpunkt == 'dateTime':
                    #wert = wert.replace('+00:00','+0000')
                    self.logger.debug("DATE__TIME "+ wert)
                    wert= datetime.datetime.strptime(wert,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=self.get_sh().tzinfo())
                if wertpunkt == 'wwsymbol_mg2008':
                    self.logger.debug("WERTPUNKT "+ str(wertpunkt))
                    if wert == '110000' or wert ==  '111000' or wert == '211000' or wert ==  '210000':
                        self.logger.debug("WERTCHEN SPELLS "+ wert)
                        self.set_childitem('weather.int_'+position+'.'+'spells',True)
                        self.set_childitem('weather.int_'+position+'.'+'Sonne',False)
                        self.set_childitem('weather.int_'+position+'.'+'Wolken',False)
                        self.set_childitem('weather.int_'+position+'.'+'Regen',False)
                        self.set_childitem('weather.int_'+position+'.'+'Gewitter',False)
                    elif wert == '100000' or wert ==  '200000':
                        self.logger.debug("WERTCHEN SONNE "+ wert)
                        self.set_childitem('weather.int_'+position+'.'+'spells',False)
                        self.set_childitem('weather.int_'+position+'.'+'Sonne',True)
                        self.set_childitem('weather.int_'+position+'.'+'Wolken',False)
                        self.set_childitem('weather.int_'+position+'.'+'Regen',False)
                        self.set_childitem('weather.int_'+position+'.'+'Gewitter',False)
                    elif wert == '220000' or wert == '121000' or wert == '120000' or wert == '330000' or wert == '320000':
                        self.logger.debug("WERTCHEN WOLKEN "+ wert)
                        self.set_childitem('weather.int_'+position+'.'+'spells',False)
                        self.set_childitem('weather.int_'+position+'.'+'Sonne',False)
                        self.set_childitem('weather.int_'+position+'.'+'Wolken',True)
                        self.set_childitem('weather.int_'+position+'.'+'Regen',False)
                        self.set_childitem('weather.int_'+position+'.'+'Gewitter',False)
                    elif wert == '122000' or wert == '331000' or wert == '221000' or wert == '321000':
                        self.logger.debug("WERTCHEN REGEN "+ wert)
                        self.set_childitem('weather.int_'+position+'.'+'spells',False)
                        self.set_childitem('weather.int_'+position+'.'+'Sonne',False)
                        self.set_childitem('weather.int_'+position+'.'+'Wolken',False)
                        self.set_childitem('weather.int_'+position+'.'+'Regen',True)
                        self.set_childitem('weather.int_'+position+'.'+'Gewitter',False)
                    elif wert == '110001' or wert == '113001' or wert == '123001' or wert == '223001' or wert == '213001' or wert == '210001':
                        self.logger.debug("WERTCHEN GEWITTER "+ wert)
                        self.set_childitem('weather.int_'+position+'.'+'spells',False)
                        self.set_childitem('weather.int_'+position+'.'+'Sonne',False)
                        self.set_childitem('weather.int_'+position+'.'+'Wolken',False)
                        self.set_childitem('weather.int_'+position+'.'+'Regen',False)
                        self.set_childitem('weather.int_'+position+'.'+'Gewitter',True)
                self.set_childitem('weather.int_'+position+'.'+wertpunkt,wert)

        for i in weather['LocationWeather']['forecast']['days']:
            position_day = str(weather['LocationWeather']['forecast']['days'].index(i))
            self.logger.debug("POSITION_day "+str(position_day))
            for x in i:
                wertpunkt_day = x
                wert_day = str(i[x])
                self.logger.debug("ITEEEEEM DAY "+'indego.weather.day_'+position_day+'.'+wertpunkt_day)
                if wertpunkt_day == 'date':
                    wert_day = datetime.datetime.strptime(wert_day,'%Y-%m-%d').replace(tzinfo=self.get_sh().tzinfo())
                    days = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
                    dayNumber = wert_day.weekday()
                    wochentag = days[dayNumber]
                    self.logger.debug("WOCHENTAG GEWITTER "+ wochentag)
                    self.set_childitem('weather.day_'+position_day+'.'+'wochentag',wochentag)
                    self.set_childitem('weather.day_'+position_day+'.'+wertpunkt_day,wert_day)

    def alert(self):
        self.logger.debug("ÄLÄRMCHEN START")
        alert_response = self.get_url(self.indego_url + 'alerts', self.context_id, 10)
        if alert_response == False:
            self.logger.debug("No Alert or error")
            self.alert_reset = False
        else:
            self.logger.debug("ALARM ELSE")
            alert_response = alert_response.decode(encoding='UTF-8', errors='ignore')
            self.logger.debug("Alärmchen: " + str(alert_response))
            alert_response = json.loads(alert_response)
            self.logger.debug("Alärmchen 2: " + str(alert_response))
            if len(alert_response) == 0:
                self.logger.debug("No new Alert Messages")

            else:
                self.logger.warning("alert_response " + str(alert_response))
                alerts = len(alert_response)
                self.logger.debug("ALERTS " + str(alerts))
                if len(alert_response) == 1:
                    alert_latest = alert_response[0]
                    self.alert_reset = False
                else:
                    # alert_latest = ast.literal_eval(alert_response[0]+'}')
                    self.logger.debug("ALERTerS " + str(alert_response[len(alert_response) - 1]))
                    alert_latest = alert_response[len(alert_response) - 1]
                    self.alert_reset = True

                alert_id = alert_latest['alert_id']
                self.set_childitem('alert_id',alert_id)
                self.logger.debug("alert_id " + str(alert_id))

                alert_message = alert_latest['message'].replace(
                    ' Bitte folgen Sie den Anweisungen im Display des Mähers.', '')
                self.set_childitem('alert_message',alert_message)
                self.logger.debug("alert_message " + str(alert_message))

                alert_date = datetime.datetime.strptime(alert_latest['date'], '%Y-%m-%dT%H:%M:%S.%fZ').replace(
                    tzinfo=tz.gettz('UTC')).astimezone(
                    self.get_sh().tzinfo())  # alert_date = datetime.datetime.strptime(alert_latest['date'],'%Y-%m-%dT%H:%M:%S.%fZ')
                self.set_childitem('alert_date',alert_date)
                self.logger.debug("alert_date " + str(alert_date))

                alert_headline = alert_latest['headline']
                self.set_childitem('alert_headline',alert_headline)
                self.logger.debug("alert_headline  " + str(alert_headline))

                alert_flag = alert_latest['flag']
                self.set_childitem('alert_flag',alert_flag)
                self.logger.debug("alert_flag " + str(alert_flag))

                self.alert_delete(alert_id)

    def get_smart_frequency(self):
        self.logger.debug("getting smart frequency")
        smart_frequency_response = self.get_url(self.indego_url + 'alms/' + self.alm_sn + '/predictive/useradjustment',
                                                self.context_id)
        smart_frequency_response = smart_frequency_response.decode(encoding='UTF-8', errors='strict')
        smart_frequency_response = json.loads(smart_frequency_response)
        frequency = smart_frequency_response['user_adjustment']
        self.set_childitem('SMART.frequenz',frequency)
        self.logger.debug("smart_frequenz " + str(frequency))

    def alert_delete(self, alert_id):
        self.logger.debug("deleting alert_id " + str(alert_id))
        self.get_url(self.indego_url + 'alerts/' + alert_id, self.context_id, 50, 'DELETE')

    def device_data(self):
        self.logger.debug('device_date')
        device_data_response = self.get_url(self.indego_url + 'alms/' + self.alm_sn, self.context_id)
        if device_data_response == False:
            self.logger.error('Device Data disconnected')
        else:
            self.logger.debug('device data RAW: ' + str(device_data_response))
            device_data_response = device_data_response.decode(encoding='UTF-8', errors='ignore')
            self.logger.debug('device date stringtanga: ' + device_data_response)
            # device_data_response = str(device_data_response).replace('false','False').replace('true','True')
            device_data_response = json.loads(device_data_response)
            self.logger.debug('device date JASON: ' + str(device_data_response))

            alm_sn = device_data_response['alm_sn']
            self.set_childitem('alm_sn',alm_sn)
            self.logger.debug("alm_sn " + str(alm_sn))

            if 'alm_name' in device_data_response:
                alm_name = device_data_response['alm_name']
                self.set_childitem('alm_name',alm_name)
                self.logger.debug("alm_name " + str(alm_name))

            service_counter = device_data_response['service_counter']
            self.set_childitem('service_counter',service_counter)
            self.logger.debug("service_counter " + str(service_counter))

            needs_service = device_data_response['needs_service']
            self.set_childitem('needs_service',needs_service)
            self.logger.debug("needs_service " + str(needs_service))

            alm_mode = device_data_response['alm_mode']
            self.set_childitem('alm_mode',alm_mode)
            if alm_mode == 'smart':
                self.logger.debug("ALM_MODE smaAAAAArt")
                self.set_childitem('SMART', True)
            else:
                self.logger.debug("ALM_MODE MANUAAAAAAAAL")
                self.set_childitem('SMART', False)
            self.logger.debug("alm_mode " + str(alm_mode))

            bareToolnumber = device_data_response['bareToolnumber']
            self.set_childitem('bareToolnumber',bareToolnumber)
            self.logger.debug("bareToolnumber " + str(bareToolnumber))

            if 'alm_firmware_version' in device_data_response:
                alm_firmware_version = device_data_response['alm_firmware_version']
                if alm_firmware_version != self.get_sh().indego.alm_firmware_version():
                    self.set_childitem('alm_firmware_version.before',self.get_sh().indego.alm_firmware_version())
                    self.set_childitem('alm_firmware_version.changed',self.get_sh().now())
                    self.logger.info(
                        "indego updated firmware from " + self.get_sh().indego.alm_firmware_version() + ' to ' + str(
                            alm_firmware_version))

                    self.set_childitem('alm_firmware_version',alm_firmware_version)
                self.logger.debug("alm_firmware_version " + str(alm_firmware_version))

    def state(self):
        state__str = {0: ['Lese Status', 'unknown'], 257: ['lädt', 'dock'], 258: ['docked', 'dock'],
                      259: ['Docked-Softwareupdate', 'dock'], 260: ['Docked', 'dock'], 261: ['docked', 'dock'],
                      262: ['docked - lädt Karte', 'dock'], 263: ['docked-speichert Karte', 'dock'],
                      513: ['mäht', 'moving'], 514: ['bestimme Ort', 'moving'], 515: ['lade Karte', 'moving'],
                      516: ['lerne Garten', 'moving'], 517: ['Pause', 'pause'], 518: ['schneide Rand', 'moving'],
                      519: ['stecke fest', 'hilfe'], 769: ['fährt in Station', 'moving'],
                      770: ['fährt in Station', 'moving'], 771: ['fährt zum Laden in Station', 'moving'],
                      772: ['fährt in Station – Mähzeit beendet', 'moving'],
                      773: ['fährt in Station - überhitzt', 'help'], 774: ['fährt in Station', 'moving'],
                      775: ['fährt in Station - fertig gemäht', 'moving'],
                      776: ['fährt in Station - bestimmt Ort', 'moving'], 1025: ['Diagnosemodus', 'unknown'],
                      1026: ['Endoflive', 'hilfe'], 1281: ['Softwareupdate', 'dock']}
        state_response = self.get_url(self.indego_url + 'alms/' + self.alm_sn + '/state', self.context_id)

        # now reconnection in get_url directly
        # if state_response == False:
        #	self.logger.error('Indego disconnected')
        #	self.set_childitem('online',False)
        #	self.auth()

        if state_response != False:
            state_response = state_response.decode(encoding='UTF-8', errors='ignore')
            self.set_childitem('online', True)
            self.logger.debug("indego state received " + str(state_response))
            states = json.loads(state_response)

            if 'error' in states:
                error_code = states['error']
                self.set_childitem('stateError',error_code)
                self.logger.error("error_code " + str(error_code))
            else:
                error_code = 0
                self.set_childitem('stateError',error_code)

            state_code = states['state']
            self.set_childitem('stateCode',state_code)
            self.logger.debug("state code " + str(state_code))
            if state__str[state_code][1] == 'dock':
                self.logger.debug('indego docked')
                self.alert_reset = True
                self.set_childitem('docked', True)
                self.set_childitem('moving', False)
                self.set_childitem('pause', False)
                self.set_childitem('help', False)
            if state__str[state_code][1] == 'moving':
                self.logger.debug('indego moving')
                self.alert_reset = True
                self.set_childitem('mowedDate', self.get_sh().now())
                self.set_childitem('docked', False)
                self.set_childitem('moving', True)
                self.set_childitem('pause', False)
                self.set_childitem('help', False)
            if state__str[state_code][1] == 'pause':
                self.logger.debug('indego pause')
                self.alert_reset = True
                self.set_childitem('docked', False)
                self.set_childitem('moving', False)
                self.set_childitem('pause', True)
                self.set_childitem('help', False)
            if state__str[state_code][1] == 'hilfe':
                self.logger.debug('indego hilfe')
                self.set_childitem('docked', False)
                self.set_childitem('moving', False)
                self.set_childitem('pause', False)
                self.set_childitem('help', True)
                if self.alert_reset == True:
                    self.logger.debug("Alert aufgefrufen, self_alert_reset = True")
                    self.alert()
                else:
                    self.logger.debug("Alert nicht aufgefrufen, self_alert_reset = False")

            state_str = state__str[state_code][0]
            self.set_childitem('state_str', state_str )
            self.logger.debug("state str " + state_str)

            mowed = states['mowed']
            self.set_childitem('mowedPercent', mowed)
            self.logger.debug("mowed " + str(mowed))

            mowmode = states['mowmode']
            self.set_childitem('mowmode',mowmode)
            self.logger.debug("mowmode  " + str(mowmode))

            total_operate = states['runtime']['total']['operate']
            self.set_childitem('runtimeTotalOperationMins',total_operate)
            self.logger.debug("total_operate " + str(total_operate))

            total_charge = states['runtime']['total']['charge']
            self.set_childitem('runtimeTotalChargeMins',total_charge)
            self.logger.debug("total_charge " + str(total_charge))

            session_operate = states['runtime']['session']['operate']
            self.set_childitem('runtimeSessionOperationMins',session_operate)
            self.logger.debug("session_operate " + str(session_operate))

            session_charge = states['runtime']['session']['charge']
            self.set_childitem('runtimeSessionChargeMins',session_charge)
            self.logger.debug("session_charge " + str(session_charge))

            if 'xPos' in states:
                xPos = states['xPos']
                self.set_childitem('xPos',xPos)
                self.logger.debug("xPos " + str(xPos))

                yPos = states['yPos']
                self.set_childitem('yPos',yPos)
                self.logger.debug("yPos " + str(yPos))

                svg_xPos = states['svg_xPos']
                self.set_childitem('svg_xPos',svg_xPos)
                self.logger.debug("svg_xPos " + str(svg_xPos))

                svg_yPos = states['svg_yPos']
                self.set_childitem('svg_yPos',svg_yPos)
                self.logger.debug("svg_yPos " + str(svg_yPos))

            if 'config_change' in states and 'config_change' in self.add_keys:
                config_change = states['config_change']
                self.get_sh().return_item(str(self.add_keys['config_change']),config_change)
                self.logger.debug("config_change " + str(config_change))

            if 'mow_trig' in states and 'mow_trig' in self.add_keys:
                mow_trig = states['mow_trig']
                self.get_sh().return_item(str(self.add_keys['mow_trig']),mow_trig)
                self.logger.debug("mow_trig " + str(mow_trig))

            # if 'map_update_available' in states and 'mow_trig' in self.add_keys:
            #	mow_trig = states['map_update_available']
            #	self.get_sh().return_item(str(self.add_keys['mow_trig']),mow_trig)
            #	self.logger.debug("mow_trig "+str(mow_trig))

            map_update = states['map_update_available']
            self.logger.debug("map_update " + str(map_update))
            self.set_childitem('mapUpdateAvailable',map_update)
            if map_update:
                self.logger.debug('lade neue Karte')
                garden = self.get_url(self.indego_url + 'alms/' + self.alm_sn + '/map', self.context_id, 120)
                if garden == False:
                    self.logger.warning('Map returned false')
                else:
                    with open(self.img_pfad, 'wb') as outfile:
                        outfile.write(garden)
                        self.logger.debug('You have a new MAP')
                        self.set_childitem('mapSvgCacheDate',self.get_sh().now())

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
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

import cherrypy
from jinja2 import Environment, FileSystemLoader


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
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

