#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 Marco Düchting                   Marco.Duechting@gmx.de
#  Copyright 2018 Bernd Meiners                     Bernd.Meiners@mail.de
#  Copyright 2019 Andre Kohler              andre.kohler01@googlemail.com
#  Copyright 2021 Andre Kohler              andre.kohler01@googlemail.com
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.6 and
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


import time
import base64
import os
import ast
import json
from dateutil import tz
import sys
import requests

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items
from lib.shtime import Shtime
from datetime import datetime
from datetime import date

import base64
import urllib.parse



#sys.path.append('/home/smarthome/.p2/pool/plugins/org.python.pydev.core_6.5.0.201809011628/pysrc')
sys.path.append('/devtools/eclipse/plugins/org.python.pydev.core_8.0.0.202009061309/pysrc/')
import pydevd


# If a package is needed, which might be not installed in the Python environment,
# import it like this:
#
# try:
#     import <exotic package>
#     REQUIRED_PACKAGE_IMPORTED = True
# except:
#     REQUIRED_PACKAGE_IMPORTED = False


class Indego4shNG(SmartPlugin):
    """
    Main class of the Indego Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    PLUGIN_VERSION = '4.0.1'

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

        self.user = ''
        self.password = ''
        self.credentials = self.get_parameter_value('indego_credentials').encode('utf-8')
        if (self.credentials != b'None'):
            self.credentials = base64.decodebytes(self.credentials).decode('utf-8')
        
        self.img_pfad = self.get_parameter_value('img_pfad')
        self.cycle = self.get_parameter_value('cycle')
        self.indego_url = self.get_parameter_value('indego_url')
        self.parent_item = self.get_parameter_value('parent_item')
        self.path_2_weather_pics = self.get_parameter_value('path_2_weather_pics') 
        
        self.items = Items.get_instance()
        self.shtime = Shtime.get_instance()
        self.sh = self.get_sh()

        self.expiration_timestamp = 0.0
        self.last_login_timestamp = 0.0
        self.logged_in = False
        self.login_pending = False
        
        self.context_id = ''
        self.user_id = ''
        self.alm_sn = ''
        self.alert_reset = True
        
        self.add_keys = {}
        self.cal_update_count = 0
        self.cal_update_running = False
        
        self.cal_upate_count_pred = 0
        self.cal_pred_update_running = False
        
        self.calendar_count_mow = []
        self.calendar_count_pred = []
        
        self.position_detection = False
        self.position_count = 0

        # Check for initialization errors:
        if not self.indego_url:
           self._init_complete = False
           return

        if not self.parent_item:
           self._init_complete = False
           return
        self.states = {}
        self.providers = {}
        self.mowertype = {}
        
        self._refresh_token = ''
        self._bearer        = ''
        self.token_expires  = ''
        
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
        if (self.credentials != b'None'):
            self.user = self.credentials.split(":")[0]
            self.password = self.credentials.split(":")[1]
        # taken from Init of the plugin
        if (self.user != '' and self.password != ''):
            self.login_pending = True
            self.logged_in, self._bearer, self._refresh_token, self.token_expires,self.alm_sn = self._login_single_key_id(self.user, self.password)
            self.login_pending = False
            self.context_id = self._bearer[:10]+ '.......'

        # start the refresh timers
        self.scheduler_add('operating_data',self._get_operating_data,cycle = 300)
        self.scheduler_add('get_state', self._get_state, cycle = self.cycle)
        self.scheduler_add('alert', self.alert, cycle=300)
        self.scheduler_add('get_all_calendars', self._get_all_calendars, cycle=300)
        self.scheduler_add('refresh_token', self._getrefreshToken, cycle=self.token_expires-100)
        self.scheduler_add('device_data', self._device_data, cycle=120)
        self.scheduler_add('get_weather', self._get_weather, cycle=600)
        self.scheduler_add('get_next_time', self._get_next_time, cycle=300)
        
        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)
        

    def stop(self):
        """
        Stop method for the plugin
        """
        self.scheduler_remove('operating_data')
        self.scheduler_remove('get_state')
        self.scheduler_remove('alert')
        self.scheduler_remove('get_all_calendars')
        #self.scheduler_remove('check_login_state')
        self.scheduler_remove('refresh_token')
        self.scheduler_remove('device_date')
        self.scheduler_remove('get_weather')
        self.scheduler_remove('get_next_time')
        
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
            return self.update_item

        if self.has_iattr(item.conf, 'indego_config'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_plugin_handled', self.get_iattr_value(item.conf, 'indego_config')))
            return self.update_item
        
        if self.has_iattr(item.conf, 'indego_plugin_handled'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_plugin_handled', self.get_iattr_value(item.conf, 'indego_plugin_handled')))
            return self.update_item
        
        if self.has_iattr(item.conf, 'indego_function_4_all'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_function_4_all', self.get_iattr_value(item.conf, 'indego_function_4_all')))
            return self.update_item
        
        if self.has_iattr(item.conf, 'indego_function_4_visu'):
            self.logger.debug("Item '{}' has attribute '{}' found with {}".format(item, 'indego_function_4_visu', self.get_iattr_value(item.conf, 'indego_function_4_visu')))
            return self.update_item
        
        if self.has_iattr(item.conf, 'indego_parse_2_attr'):
            #pydevd.settrace("192.168.178.37", port=5678)
            _attr_name = item.conf['indego_attr_name']
            newStruct = {}
            myStruct= json.loads(item())
            for entry in myStruct:
                if item.conf['indego_attr_type']=='int':
                    newStruct[int(entry)]=myStruct[entry]
                if item.conf['indego_attr_type']=='str':
                    newStruct[entry]=myStruct[entry]
            setattr(self, _attr_name, newStruct)


        return None

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
        #pydevd.settrace("192.168.178.37", port=5678)
        # Function when item is triggered by VISU
        if caller != self.get_shortname() and caller != 'Autotimer' and caller != 'Logic':
            
            # code to execute, only if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))
            
            # Update-Hander for Items changed by Visu
    
            if self.has_iattr(item.conf, 'indego_config'):
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,caller,source,dest))
                ''' Example
                PUT /api/v1/alms/603702021/config
                {"bump_sensitivity": 0 } = normal
                '''
                try:
                    myUrl = self.indego_url + item.conf['indego_config_url'].format(self.alm_sn)
                    myBody = json.loads(item.conf['indego_config'].replace('#',str(item.property.value)))
                    myResult = self._send_config(myUrl, myBody)
                except:
                    self.logger.warning("Error building config for item '{}' from caller '{}', source '{}' and dest '{}'".format(item,caller,source,dest))

            if self.has_iattr(item.conf, 'indego_function_4_visu'):
                self.logger.debug("Item '{}' has attribute '{}' found with {}".format( item, 'indego_function_4_visu', self.get_iattr_value(item.conf, 'indego_function_4_visu')))
                myFunction_Name = self.get_iattr_value(item.conf, 'indego_function_4_visu')
                myFunction = getattr(self,myFunction_Name)
                myFunction(item)    
           
                
            if item._name == self.parent_item+'.active_mode.uzsu':
                if item() == 10:
                    self._set_childitem('MOW', True)
                if item() == 20:
                    self._set_childitem('RETURN', True)
                if item() == 30:              
                    self._set_childitem('PAUSE', True)
            
            if ("show_uzsu_popup" in item.property.name and item() == True):
                self._set_childitem('visu.fire_uszu_popup','fire_uszu_popup|True' )
            
        
        # Function when item is triggered by anybody, also by plugin
            
        if self.has_iattr(item.conf, 'indego_command'):
            self.logger.debug("Item '{}' has attribute '{}' triggered {}".format( item, 'indego_command', self.get_iattr_value(item.conf, 'indego_command')))
            try:    
                command = self.get_iattr_value(item.conf,'indego_command')
                if item():
                    self.send_command(command,item.property.name)
            except:
                    self.logger.warning("Error sending command for item '{}' from caller '{}', source '{}' and dest '{}'".format(item,caller,source,dest))

        if self.has_iattr(item.conf, 'indego_function_4_all'):
            #pydevd.settrace("192.168.178.37", port=5678)
            try:
                self.logger.debug("Item '{}' has attribute '{}' found with {}".format( item, 'indego_plugin_function', self.get_iattr_value(item.conf, 'indego_function_4_all')))
                myFunction_Name = self.get_iattr_value(item.conf, 'indego_function_4_all')
                myFunction = getattr(self,myFunction_Name)
                myFunction(item)
            except:
                self.logger.warning("failed : Item '{}' has attribute '{}' found with {}".format( item, 'indego_function_4_all', self.get_iattr_value(item.conf, 'indego_function_4_all')))
                            
               
        if "active_mode" in item.property.name:
            self._set_childitem('visu.cal_2_show','cal2show|'+str(self._get_childitem('active_mode')))
        
        
        
        



                                                   
        
    ##############################################        
    # Public functions
    ##############################################
    
    def send_command(self, command, item_name):
        command = json.loads(command)
        self.logger.debug("Function Command " + json.dumps(command) + ' ' + item_name)
        message, response = self._put_url(self.indego_url + 'alms/' + self.alm_sn + '/state', self.context_id, command, 10)
        self.logger.debug("Command " + json.dumps(command) + ' gesendet! ' + str(message))

                    
    ##############################################
    # Functions for Update-Items 
    ##############################################
    def _handle_alerts(self, item):
        if item.property.name == self.parent_item+'.visu.alerts_set_read':
            self._set_read_messages()
        
        if item.property.name == self.parent_item+'.visu.alerts_set_clear':
            self._set_clear_message()
                
    def _handle_mow_track(self, item):
        if ("visu.mow_track" in item.property.name and self._get_childitem('visu.show_mow_track') == True) or ("visu.show_mow_track" in item.property.name and item() == True):
                self._create_mow_track()
        elif "visu.show_mow_track" in item.property.name and item() == False:
            self._set_childitem('visu.svg_mow_track','svg_mow_track|'+str(''))
            
    def _handle_wartung(self, item):
        
        if "wartung.wintermodus" in item.property.name:
            self._set_childitem('visu.wintermodus','wintermodus|'+str(self._get_childitem('wartung.wintermodus')))
                    
        if item.property.name == self.parent_item+".wartung.update_auto":
            self._set_automatic_updates()
            
        if item.property.name == self.parent_item+".wartung.messer_zaehler":
            #pydevd.settrace("192.168.178.37", port=5678)
            if (item.property.value == True):
                if (self._reset_bladeCounter() == True):
                    item(False)
                
        
        if item.property.name == self.parent_item+".wartung.update_start":
            if  item() == True:
                self._start_manual_update()
                item(False)
        
    def _handle_store_cals(self, item):
        if item.property.name == self.parent_item+'.visu.store_sms_profile' and item() == True:
                self._smart_mow_settings("write")
                self._set_childitem('visu.store_sms_profile', False)
                    
                    
        if item.property.name == self.parent_item+'.calendar_save' and item() == True:
            self._set_childitem('calendar_result', "speichern gestartet")
            # Now Save the Calendar on Bosch-API
            self.cal_update_count = 0
            self._auto_mow_cal_update()


        if item.property.name == self.parent_item+'.calendar_predictive_save' and item() == True:
            self._set_childitem('calendar_predictive_result', "speichern gestartet")
            # Now Save the Calendar on Bosch-API
            self.upate_count_pred = 0
            self._auto_pred_cal_update()

        
        
    def _handle_parse_map(self, item):
        self._parse_map()
    
    def _handle_calendar_list(self, item):
        if item.property.name == self.parent_item+'.calendar_list':
            #pydevd.settrace("192.168.178.37", port=5678)
            myList = item()
            myCal = self._get_childitem('calendar')
            myNewCal = self._parse_list_2_cal(myList, myCal,'MOW')
            self._set_childitem('calendar', myNewCal)


        if item.property.name == self.parent_item+'.calendar_predictive_list':
            myList = item()
            myCal = self._get_childitem('calendar_predictive')
            myNewCal = self._parse_list_2_cal(myList, myCal,'PRED')
            self._set_childitem('calendar_predictive', myNewCal)
            
        
    def _handle_alm_mode(self, item):
        if   (item() == 'smart'):
            self._set_childitem('active_mode', 2)      
            self._set_childitem('active_mode.aus', False)
            self._set_childitem('active_mode.kalender', False)          
            self._set_childitem('active_mode.smart', True)
            self.items.return_item('indego.active_mode.uzsu.schaltuhr').activate(False)
        elif (item() == 'calendar'):
            self._set_childitem('active_mode', 1)
            self._set_childitem('active_mode.aus', False)
            self._set_childitem('active_mode.kalender', True)          
            self._set_childitem('active_mode.smart', False)
            self.items.return_item('indego.active_mode.uzsu.schaltuhr').activate(False)
        elif (item() == 'manual'):
            self._set_childitem('active_mode', 3)
            self._set_childitem('active_mode.aus', True)
            self._set_childitem('active_mode.kalender', False)          
            self._set_childitem('active_mode.smart', False)
            
    def _handle_refresh(self, item):
        if item()== True:
            self._set_childitem('update_active_mode', True)
            self._get_all_calendars()
            self._get_state()
            self.alert()
            self._device_data()
            self._get_next_time()
            self._get_weather()
            self._load_map()
            self._set_childitem('update_active_mode', False)
            item(False)
        
    def _handle_active_mode(self, item):
        if item.property.name == self.parent_item+'.active_mode.kalender' and item() == True:
            self._set_childitem('update_active_mode', True)
            self._set_childitem('active_mode', 1)
            self.items.return_item('indego.active_mode.uzsu.schaltuhr').activate(False)
            self._set_childitem('active_mode.smart', False)
            self._set_childitem('active_mode.aus', False)
            self._set_smart(False)
            self._set_childitem('calendar_sel_cal', 2)
            self._set_childitem('calendar_save', True)
            self._set_childitem('alm_mode.str','Übersicht Kalender mähen:')
            self._set_childitem('alm_mode','calendar')
            self._set_childitem('update_active_mode', False)
            self._set_childitem('active_mode.uzsu.schaltuhr.active', False)
            
        if item.property.name == self.parent_item+'.active_mode.aus' and item() == True:
            self._set_childitem('update_active_mode', True)
            self._set_childitem('active_mode', 3)
            self._set_childitem('active_mode.kalender', False)
            self._set_childitem('alm_mode.str','')
            self._set_childitem('active_mode.smart', False)
            self._set_smart(False)
            self._set_childitem('calendar_sel_cal', 0)
            self._set_childitem('calendar_save', True)
            self._set_childitem('alm_mode','manual')
            self._set_childitem('update_active_mode', False)
        
        if item.property.name == self.parent_item+'.active_mode.smart' and item() == True:
            self._set_childitem('update_active_mode', True)
            self._set_childitem('active_mode', 2)
            self.items.return_item('indego.active_mode.uzsu.schaltuhr').activate(False)
            self._set_childitem('alm_mode.str','Übersicht SmartMow mähen:')
            self._set_childitem('active_mode.aus', False)
            self._set_childitem('active_mode.kalender', False)
            self._set_childitem('calendar_sel_cal', 3)
            self._set_childitem('calendar_save', True)
            self._set_smart(True)
            self._set_childitem('alm_mode','smart')
            self._set_childitem('update_active_mode', False)
            self._set_childitem('active_mode.uzsu.schaltuhr.active', False)
        
        if item.property.name == self.parent_item+".active_mode.uzsu.schaltuhr":
            myResult = self.items.return_item('indego.active_mode.uzsu.schaltuhr').activate()
            if myResult == True:
                self._set_childitem('active_mode.uzsu.schaltuhr.active', True)
                self._set_childitem('active_mode.uzsu.calendar_list',self._parse_uzsu_2_list(item()))
                self._set_childitem('alm_mode.str','Übersicht mähen nach UZSU:')
            else:                  
                self._set_childitem('active_mode.uzsu.schaltuhr.active', False)
        

    ##############################################
    # End - Update-Items
    
    ##############################################
    # Private functions
    ##############################################
    def _get_childitem(self, itemname):
        """
        a shortcut function to get value of an item if it exists
        :param itemname:
        :return:
        """
        item = self.items.return_item(self.parent_item + '.' + itemname)  
        if (item != None):
            return item()
        else:
            self.logger.warning("Could not get item '{}'".format(self.parent_item+'.'+itemname))    
    
    
    def _set_childitem(self, itemname, value ):
        """
        a shortcut function to set an item with a given value if it exists
        :param itemname:
        :param value:
        :return:
        """
        item = self.items.return_item(self.parent_item + '.' + itemname)  
        if (item != None): 
            item(value, self.get_shortname())
        else:
            self.logger.warning("Could not set item '{}' to '{}'".format(self.parent_item+'.'+itemname, value))


    def _set_location(self,body=None):
        url = "{}alms/{}/predictive/location".format( self.indego_url, self.alm_sn)
        try:
            myResult, response = self._put_url( url, self.context_id, body)
        except err as Exception:
            self.logger.warning("Error during putting Location {}".format(err))
            return False
        return True
                               
    def _send_config(self,url,body=None):
        try:
            myResult, response = self._put_url( url, self.context_id, body)
        except err as Exception:
            self.logger.warning("Error during putting Config {}".format(err))
            return False
        return True


                    
    def _create_mow_track(self):
        if self._get_childitem('visu.model_type') == 2:
            mystroke     ='#C3FECE'
            mystrokewidth ='17'
        else:
            mystroke      ='#999999'
            mystrokewidth ='5'
        myMowTrack = {'Points':self._get_childitem('visu.mow_track'),
                      'style':'fill:none; stroke:'+mystroke+ '; stroke-width: '+mystrokewidth+'; stroke-linecap:round; stroke-linejoin: round;'}
        self._set_childitem('visu.svg_mow_track','svg_mow_track|'+json.dumps(myMowTrack))
        
    def _daystring(self, zeitwert, ausgang):
        if ausgang == 'min':
            zeitwert = zeitwert / 60 / 24
        if ausgang == 'std':
            zeitwert = zeitwert / 24
        tage, std = divmod(zeitwert, 1)
        tage = int(tage)
        std = std * 24
        std, min = divmod(std,1)
        std = int(std)
        min = round(min * 60)
        dayout = str(tage)+' Tage '+str(std)+' Std '+str(min)+' Min'
        return dayout
    
    def _del_message_in_dict(self, myDict, myKey):
        del myDict[myKey]
        
    def _set_read_messages(self):
        msg2setread = self._get_childitem('visu.alerts_set_read')
        myReadMsg = self._get_childitem('visu.alerts')
        
        for message in msg2setread:
            myResult, response = self._put_url(self.indego_url +'alerts/{}'.format(message), self.context_id, None, 10)
            myReadMsg[message]['read_status'] = 'read'
            
        self._set_childitem('visu.alerts', myReadMsg)
        
        
    def _set_clear_message(self):
        msg2clear = self._get_childitem('visu.alerts_set_clear')
        myClearMsg = self._get_childitem('visu.alerts')
        
        for message in msg2clear:
            myResult = self._delete_url(self.indego_url +'alerts/{}'.format(message), self.context_id, 10,None)
            self._del_message_in_dict(myClearMsg, message)
            
        self._set_childitem('visu.alerts', myClearMsg)
        if (len(myClearMsg)) == 0:
            {
                self._set_childitem('visu.alert_new', False)
            } 
    
    def _check_login_state(self):
        if self.logged_in == False:
            self._set_childitem('online', False)
            self.context_id = ''
            return
        actTimeStamp = time.time()
        if self.expiration_timestamp < actTimeStamp+575:
            self.logged_in = False
            self.login_pending = True
            self.context_id = ''
            self.login_pending = False
            self._set_childitem('online', self.logged_in)
            actDate = datetime.now()
            self.logger.info("refreshed Session-ID at : {}".format(actDate.strftime('Date: %a, %d %b %H:%M:%S %Z %Y')))
        else:
            self.logger.info("Session-ID {} is still valid".format(self.context_id))
            
    def _auto_pred_cal_update(self):
        self.cal_upate_count_pred += 1
        self.cal_pred_update_running = True
        
        
        # set actual Calendar in Calendar-structure
        myCal = self._get_childitem('calendar_predictive')
        actCalendar = self._get_childitem('calendar_predictive_sel_cal')
        
        myCal['sel_cal'] = actCalendar
        self._set_childitem('calendar_predictive',myCal)
        
        #myResult = self._store_calendar(self.predictive_calendar(),'predictive/calendar')
        myResult = self._store_calendar(myCal,'predictive/calendar')
        
        if self.cal_upate_count_pred <=3:
            if myResult != 200:
                if self.cal_upate_count_pred == 1:
                    self.scheduler_add('auto_pred_cal_update', self._auto_pred_cal_update, cycle=60)
                myMsg = """Mäher konnte nicht erreicht werden 
                           nächster Versuch in 60 Sekunden 
                           Anzahl Versuche : """ + str(self.cal_upate_count_pred)
            else:
                self.cal_pred_update_running = False
                self.cal_upate_count_pred = 0
                self._set_childitem('calendar_predictive_save', False)
                try:
                    self.scheduler_remove('auto_pred_cal_update')
                except:
                    pass
                myMsg = "Ausschlusskalender wurde gespeichert"

        else: # Bereits drei Versuche getätigt
            try:
                self.scheduler_remove('auto_pred_cal_update')
            except:
                pass
            myMsg = """Ausschlusskalender konnte nach drei Versuchen nicht 
                       nicht gespeichert werden. "
                       Speichern abgebrochen"""
            self.cal_pred_update_running = False
            self.cal_upate_count_pred = 0
            self._set_childitem('calendar_predictive_save', False)
        
        self._set_childitem('calendar_predictive_result',myMsg)

            

    def _auto_mow_cal_update(self):
        self.cal_update_count += 1
        self.cal_update_running = True
        #pydevd.settrace("192.168.178.37", port=5678)
        # set actual Calendar in Calendar-structure
        myCal = self._get_childitem('calendar')
        actCalendar = self._get_childitem('calendar_sel_cal')
        myCal['sel_cal'] = actCalendar
        
        self._set_childitem('calendar',myCal)
        #myResult = self._store_calendar(self.calendar(),'calendar')
        myResult = self._store_calendar(myCal,'calendar')
        if self.cal_update_count <=3:
            if myResult != 200:
                if self.cal_update_count == 1:
                    self.scheduler_add('auto_mow_cal_update', self._auto_mow_cal_update, cycle=60)
                myMsg = """Mäher konnte nicht erreicht werden 
                           nächster Versuch in 60 Sekunden 
                           Anzahl Versuche : """ + str(self.cal_update_count)

            else:
                self.cal_update_running = False
                self.cal_update_count = 0
                self._set_childitem('calendar_save', False)
                try:
                    self.scheduler_remove('auto_cal_update')
                except:
                    pass
                myMsg = "Mähkalender wurde gespeichert"
                # Deactivate the UZSU, when saving the calendar, calendar-mode is activated
                # and set the correctmode
                self._set_childitem('active_mode.kalender',True)
                

        else: # Bereits drei Versuche getätigt
            try:
                self.scheduler_remove('auto_mow_cal_update')
            except:
                pass
            myMsg = """Mähkalender konnte nach drei Versuchen nicht 
                       nicht gespeichert werden. "
                       Speichern abgebrochen"""
            self.cal_update_running = False
            self.cal_update_count = 0
            self._set_childitem('calendar_save', False)
        
        self._set_childitem('calendar_result',myMsg)
    
    
    def _get_all_calendars(self):    
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return
        if (self._get_childitem("alm_mode") == 'smart') and ((self._get_childitem('stateCode') == 513) or (self._get_childitem('stateCode') == 518)):
            return     
        self._smart_mow_settings("read")
        try:
            if not self.cal_update_running:
                # get the mowing calendar
                myMowCal = self._get_calendar()
                self._set_childitem('calendar', myMowCal)
                
                myMowCalList = self._parse_cal_2_list(myMowCal,'MOW')
                self._set_childitem('calendar_list', myMowCalList)
                
                myActiveMowCal = self._get_active_calendar(myMowCal)
                self._set_childitem('calendar_sel_cal', myActiveMowCal)
                '''
                self.calendar = self.items.return_item(self.parent_item + '.' + 'calendar')
                self.calendar(self._get_calendar(), 'indego')
                calendar_list = self.items.return_item(self.parent_item + '.' + 'calendar_list')
                calendar_list(self._parse_cal_2_list(self.calendar._value,'MOW'),'indego')
                self.act_Calender = self.items.return_item(self.parent_item + '.' + 'calendar_sel_cal')
                self.act_Calender(self._get_active_calendar(self.calendar()),'indego')
                '''
            if not self.cal_pred_update_running:
                # get the predictve calendar for smartmowing
                self.predictive_calendar = self.items.return_item(self.parent_item + '.' + 'calendar_predictive')
                self.predictive_calendar(self._get_predictive_calendar(), 'indego')
                predictive_calendar_list = self.items.return_item(self.parent_item + '.' + 'calendar_predictive_list')
                predictive_calendar_list(self._parse_cal_2_list(self.predictive_calendar._value,'PRED'),'indego')
                self.act_pred_Calender = self.items.return_item(self.parent_item + '.' + 'calendar_predictive_sel_cal')
                self.act_pred_Calender(self._get_active_calendar(self.predictive_calendar()),'indego')
        except Exception as e:
            self.logger.warning("Problem fetching Calendars: {0}".format(e))
        
        # Get the scheduled smart-mow-calendar
        if self._get_childitem("alm_mode") == 'smart':
            try:
                schedule = self._get_url(self.indego_url + 'alms/' + self.alm_sn +'/predictive/schedule', self.context_id)

                if schedule == False:
                    return
            except Exception as e:
                self.logger.warning("Problem fetching Calendars: {0}".format(e))
            my_pred_cal = {
                            "cals" : [{
                                        "cal" : 9,
                                        'days' : schedule['exclusion_days']
                                     }]
                          } 
            my_smMow_cal = {
                            "cals" : [{
                                        "cal" : 9,
                                        'days' : schedule['schedule_days']
                                     }]
                          }
            #pydevd.settrace("192.168.178.37", port=5678)
            my_pred_list = self._parse_cal_2_list(my_pred_cal, None)
            my_smMow_list = self._parse_cal_2_list(my_smMow_cal, None)
            
            self._set_childitem('visu.smartmow_days',[ my_pred_list,my_smMow_list])
        
    def _log_communication(self, type, url, result):
        myLog = self._get_childitem('webif.communication_protocoll')
        if (myLog == None):
            return
        try:
            if len (myLog) >= 500:
                myLog = myLog[0:499]
        except:
            return
        now = self.shtime.now()
        myLog.insert(0,str(now)[0:19]+' Type: ' + str(type) + ' Result : '+str(result) + ' Url : ' + url)
        self._set_childitem('webif.communication_protocoll', myLog)

    def _fetch_url(self, url, username=None, password=None, timeout=10, body=None):
        #pydevd.settrace("192.168.178.37", port=5678)
        try:
            myResult, response = self._post_url(url, self.context_id, body, timeout,auth=(username,password),nowait = True)
        except Exception as e:
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))
            return False,''
        if myResult == False:
            return False,''
        
        if response.status_code == 200 or response.status_code == 201:
            content = response.json()
            try:
                expiration_timestamp = int(str(response.cookies._cookies['api.indego.iot.bosch-si.com']['/']).split(',')[11].split('=')[1])
            except:
                pass
        else:
            self.logger.warning("Problem fetching {}: HTTP : {}".format(url,  response.status_code))
            content = False
        
        return content,expiration_timestamp
    
    
    def _delete_url(self, url, contextid=None, timeout=40, auth=None,nowait = True):
        # Wait while login is pending
        myCouner = 1
        while self.login_pending == True and nowait == False and myCounter <=2:
            myCouner += 1
            time.sleep(2)
            
        headers = {'accept' : '*/*',
                   'authorization' : 'Bearer '+ self._bearer,
                   'connection' : 'Keep-Alive',
                   'host'  : 'api.indego-cloud.iot.bosch-si.com',
                   'user-agent' : 'Indego-Connect_4.0.0.12253',
                   'content-type' : 'application/json'
                    }
        response = False
        try:
            response = requests.delete(url, headers=headers)
            self._log_communication('delete', url, response.status_code)
        except Exception as e:
            self.logger.warning("Problem deleting {}: {}".format(url, e))
            return False

        if response.status_code == 200 or response.status_code == 201:
            try:
                content = response
            except:
                content = False
                pass
        else:
            self.logger.warning("Problem deleting {}: HTTP : {}".format(url, response.status_code))
            content = False
        
        return content

        
    def _get_url(self, url, contextid=None, timeout=40, auth=None):
        # Wait while login is pending
        myCouner = 1
        while self.login_pending == True and myCounter <=2:
            myCouner += 1
            time.sleep(2)
            
        headers = {'accept-encoding' : 'gzip',
                    'authorization' : 'Bearer '+ self._bearer,
                    'connection' : 'Keep-Alive',
                    'host'  : 'api.indego-cloud.iot.bosch-si.com',
                    'user-agent' : 'Indego-Connect_4.0.0.12253'
                    }
        response = False
        try:
            if auth == None:
                response = requests.get(url, headers=headers)
            else:
                response = requests.get(url, headers=headers, auth=auth)
            self._log_communication('GET   ', url, response.status_code)
        except Exception as e:
            self.logger.warning("Problem fetching {}: {}".format(url, e))
            return False
        
        if response.status_code == 204:                  # No content
                self.logger.info("Got no Content : {}".format(url))
                return False

        elif response.status_code == 200 or response.status_code == 201:
            try:
                if str(response.headers).find("json") > -1:
                    content = response.json()
                elif str(response.headers).find("svg") > -1:
                    content = response.content
                    
            except:
                content = False
                pass
        else:
            self.logger.warning("Problem getting {}: HTTP : {}".format(url, response.status_code))
            content = False
        
        return content
        
    def _post_url(self, url, contextid=None, body=None, timeout=2, auth = "", nowait = True):
        # Wait while login is pending
        myCounter = 1
        while self.login_pending == True and nowait == False and myCounter <=2:
            myCouner += 1
            time.sleep(2)
            
        headers = {'accept-encoding' : 'gzip',
                    'authorization' : 'Bearer '+ self._bearer,
                    'connection' : 'Keep-Alive',
                    'host'  : 'api.indego-cloud.iot.bosch-si.com',
                    'user-agent' : 'Indego-Connect_4.0.0.12253'
                    }
        
        response = False
        try:
            if body == None:
                response = requests.post(url, headers=headers, auth=auth)
            else:
                response = requests.post(url, headers=headers ,json=body, auth=auth)
            self._log_communication('post  ', url, response.status_code)
        except Exception as e:
            self.logger.warning("Problem posting {}: {}".format(url, e))
            return False
        self.logger.debug('post gesendet an URL: {} context-ID: {} json : {}'.format(url,self.context_id,json.dumps(body)))
        
        if response.status_code == 200:
            self.logger.info("Set correct post for {}".format(url))
            return True,response
        else:
            self.logger.info("Error during post for {} HTTP-Status :{}".format(url, response.status_code))
            return False,response
            
    
    
    def _put_url(self, url, contextid=None, body=None, timeout=2):
        # Wait while login is pending
        myCouner = 1
        while self.login_pending == True and myCounter <=2:
            myCouner += 1
            time.sleep(2)
            
        headers = {'accept-encoding' : 'gzip',
                    'authorization' : 'Bearer '+ self._bearer,
                    'connection' : 'Keep-Alive',
                    'host'  : 'api.indego-cloud.iot.bosch-si.com',
                    'user-agent' : 'Indego-Connect_4.0.0.12253'
                    }
        
        response = False
        try:
            response = requests.put(url, headers=headers, json=body)
            self._log_communication('put   ', url, response.status_code)
        except Exception as e:
            self.logger.warning("Problem putting {}: {}".format(url, e))
            self._log_communication('put   ', url, response.status_code)
            return False, response
        self.logger.debug('put gesendet an URL: {} context-ID: {} json : {}'.format(url,self.context_id,json.dumps(body)))
        
        if response.status_code == 200:
            self.logger.info("Set correct put for {}".format(url))
            return True, response
        else:
            self.logger.info("Error during put for {} HTTP-Status :{}".format(url, response.status_code))
            return False, response

    def _set_smart(self, enable=None):

        if enable:
            self.logger.debug("SMART-Mow-Modus aktivieren")
            command = {"enabled": True}
        else:
            self.logger.debug("SMART-Mow-Modus deaktivieren")
            command = {"enabled": False}
        result, response = self._put_url(self.indego_url + 'alms/' + self.alm_sn + '/predictive', self.context_id, command, 10)
        self.logger.debug("Smart Command " + json.dumps(command) + ' gesendet! Result :' + str(result))


    def _check_state_4_protocoll(self):
        myActState = self._get_childitem("stateCode")
        if myActState == 772 or myActState == 775 or myActState == 769 or myActState == 770 or myActState == 771 or myActState == 773 or myActState == 774 or myActState == 257 or myActState == 260 or myActState == 261 or myActState == 262 or myActState == 263:                           # 769 = fährt zur Station / 772 = Mähzeit beendet / 775 = fertig gemäht
            self.scheduler_change('get_state', cycle={self.cycle:None})
            self._set_childitem("laststateCode", myActState)
            self.position_detection = False
        
        

    def _store_calendar(self, myCal = None, myName = ""):
        '''
        PUT https://api.indego.iot.bosch-si.com/api/v1/alms/{serial}/calendar
        x-im-context-id: {contextId}
        '''
        url = "{}alms/{}/{}".format( self.indego_url, self.alm_sn, myName)
        
        try:
            myResult, response = self._put_url( url, self.context_id, myCal)
        except err as Exception:
            self.logger.warning("Error during saving Calendar-Infos Error {}".format(err))
            return None
            
        if response.status_code == 200:
            self.logger.info("Set correct Calendar settings for {}".format(myName))
        else:
            self.logger.info("Error during saving Calendar settings for {} HTTP-Status :{}".format(myName, response.status_code))

        return response.status_code            


    
    def _getrefreshToken(self):
        myUrl = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/b2c_1a_signup_signin/oauth2/v2.0/token'
        mySession = requests.session()
        mySession.headers['accept'] = 'application/json'
        mySession.headers['accept-encoding'] = 'gzip'
        mySession.headers['connection'] = 'Keep-Alive'
        mySession.headers['content-type'] = 'application/x-www-form-urlencoded'
        mySession.headers['host'] = 'prodindego.b2clogin.com'
        mySession.headers['user-agent'] = 'Dalvik/2.1.0 (Linux; U; Android 11; sdk_gphone_x86_arm Build/RSR1.201013.001)'
        params = {
          "grant_type":"refresh_token",
          "refresh_token": self._refresh_token
        }
    
        response = requests.post(myUrl, data=params)
        self._log_communication('POST  ', myUrl, response.status_code)
        
        myJson = json.loads (response.content.decode())
        self._refresh_token = myJson['refresh_token']
        self._bearer        = myJson['access_token']
        self.context_id     = self._bearer[:10]+ '.......'
        self.token_expires  = myJson['expires_in']
        self.last_login_timestamp = datetime.timestamp(datetime.now())
        self.expiration_timestamp = self.last_login_timestamp + self.token_expires


    def _login_single_key_id(self,user, pwd):
        try:
            # Standardvalues
            code_challenge  = 'iGz3HXMCebCh65NomBE5BbfSTBWE40xLew2JeSrDrF4'
            code_verifier   = '9aOBN3dvc634eBaj7F8iUnppHeqgUTwG7_3sxYMfpcjlIt7Uuv2n2tQlMLhsd0geWMNZPoryk_bGPmeZKjzbwA'
            nonce           = 'LtRKgCy_l1abdbKPuf5vhA'
            myClientID      = '65bb8c9d-1070-4fb4-aa95-853618acc876'         # das ist die echte Client-ID
            step            = 0
    
            myPerfPayload ={
              "navigation": {
                "type": 0,
                "redirectCount": 0
              },
              "timing": {
                "connectStart": 1678187315976,
                "navigationStart": 1678187315876,
                "loadEventEnd": 1678187317001,
                "domLoading": 1678187316710,
                "secureConnectionStart": 1678187315994,
                "fetchStart": 1678187315958,
                "domContentLoadedEventStart": 1678187316973,
                "responseStart": 1678187316262,
                "responseEnd": 1678187316322,
                "domInteractive": 1678187316973,
                "domainLookupEnd": 1678187315958,
                "redirectStart": 0,
                "requestStart": 1678187316010,
                "unloadEventEnd": 0,
                "unloadEventStart": 0,
                "domComplete": 1678187317001,
                "domainLookupStart": 1678187315958,
                "loadEventStart": 1678187317001,
                "domContentLoadedEventEnd": 1678187316977,
                "redirectEnd": 0,
                "connectEnd": 1678187316002
              },
              "entries": [
                {
                  "name": "https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/b2c_1a_signup_signin/oauth2/v2.0/authorize?redirect_uri=com.bosch.indegoconnect%3A%2F%2Flogin&client_id=65bb8c9d-1070-4fb4-aa95-853618acc876&response_type=code&state=j1A8L2zQMbolEja6yqbj4w&nonce={}&scope=openid%20profile%20email%20offline_access%20https%3A%2F%2Fprodindego.onmicrosoft.com%2Findego-mobile-api%2FIndego.Mower.User&code_challenge={}&code_challenge_method=S256".format(nonce,code_challenge),
                  "entryType": "navigation",
                  "startTime": 0,
                  "duration": 1125.3999999999849,
                  "initiatorType": "navigation",
                  "nextHopProtocol": "http/1.1",
                  "workerStart": 0,
                  "redirectStart": 0,
                  "redirectEnd": 0,
                  "fetchStart": 82.29999999997517,
                  "domainLookupStart": 82.29999999997517,
                  "domainLookupEnd": 82.29999999997517,
                  "connectStart": 99.99999999999432,
                  "connectEnd": 126.29999999998631,
                  "secureConnectionStart": 117.4999999999784,
                  "requestStart": 133.7999999999795,
                  "responseStart": 385.5999999999824,
                  "responseEnd": 445.699999999988,
                  "transferSize": 66955,
                  "encodedBodySize": 64581,
                  "decodedBodySize": 155950,
                  "serverTiming": [],
                  "workerTiming": [],
                  "unloadEventStart": 0,
                  "unloadEventEnd": 0,
                  "domInteractive": 1097.29999999999,
                  "domContentLoadedEventStart": 1097.29999999999,
                  "domContentLoadedEventEnd": 1100.999999999999,
                  "domComplete": 1125.2999999999815,
                  "loadEventStart": 1125.3999999999849,
                  "loadEventEnd": 1125.3999999999849,
                  "type": "navigate",
                  "redirectCount": 0
                },
                {
                  "name": "https://swsasharedprodb2c.blob.core.windows.net/b2c-templates/bosch/unified.html",
                  "entryType": "resource",
                  "startTime": 1038.0999999999858,
                  "duration": 21.600000000006503,
                  "initiatorType": "xmlhttprequest",
                  "nextHopProtocol": "",
                  "workerStart": 0,
                  "redirectStart": 0,
                  "redirectEnd": 0,
                  "fetchStart": 1038.0999999999858,
                  "domainLookupStart": 0,
                  "domainLookupEnd": 0,
                  "connectStart": 0,
                  "connectEnd": 0,
                  "secureConnectionStart": 0,
                  "requestStart": 0,
                  "responseStart": 0,
                  "responseEnd": 1059.6999999999923,
                  "transferSize": 0,
                  "encodedBodySize": 0,
                  "decodedBodySize": 0,
                  "serverTiming": [],
                  "workerTiming": []
                },
                {
                  "name": "https://swsasharedprodb2c.blob.core.windows.net/b2c-templates/bosch/bosch-header.png",
                  "entryType": "resource",
                  "startTime": 1312.7999999999815,
                  "duration": 7.900000000006457,
                  "initiatorType": "css",
                  "nextHopProtocol": "",
                  "workerStart": 0,
                  "redirectStart": 0,
                  "redirectEnd": 0,
                  "fetchStart": 1312.7999999999815,
                  "domainLookupStart": 0,
                  "domainLookupEnd": 0,
                  "connectStart": 0,
                  "connectEnd": 0,
                  "secureConnectionStart": 0,
                  "requestStart": 0,
                  "responseStart": 0,
                  "responseEnd": 1320.699999999988,
                  "transferSize": 0,
                  "encodedBodySize": 0,
                  "decodedBodySize": 0,
                  "serverTiming": [],
                  "workerTiming": []
                }
              ],
              "connection": {
                "onchange": None,
                "effectiveType": "4g",
                "rtt": 150,
                "downlink": 1.6,
                "saveData": False,
                "downlinkMax": None,
                "type": "unknown",
                "ontypechange": None
              }
            }
    
            myReqPayload = {
               "pageViewId":'',
               "pageId":"CombinedSigninAndSignup",
               "trace":[
                  {
                     "ac":"T005",
                     "acST":1678187316,
                     "acD":7
                  },
                  {
                     "ac":"T021 - URL:https://swsasharedprodb2c.blob.core.windows.net/b2c-templates/bosch/unified.html",
                     "acST":1678187316,
                     "acD":119
                  },
                  {
                     "ac":"T019",
                     "acST":1678187317,
                     "acD":44
                  },
                  {
                     "ac":"T004",
                     "acST":1678187317,
                     "acD":19
                  },
                  {
                     "ac":"T003",
                     "acST":1678187317,
                     "acD":5
                  },
                  {
                     "ac":"T035",
                     "acST":1678187317,
                     "acD":0
                  },
                  {
                     "ac":"T030Online",
                     "acST":1678187317,
                     "acD":0
                  },
                  {
                     "ac":"T002",
                     "acST":1678187328,
                     "acD":0
                  }
               ]
            }
            # Create a session
            mySession = requests.session()
    
            # Collect some Cookies
    
            url = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/b2c_1a_signup_signin/oauth2/v2.0/authorize?redirect_uri=com.bosch.indegoconnect%3A%2F%2Flogin&client_id={}&response_type=code&state=j1A8L2zQMbolEja6yqbj4w&nonce={}&scope=openid%20profile%20email%20offline_access%20https%3A%2F%2Fprodindego.onmicrosoft.com%2Findego-mobile-api%2FIndego.Mower.User&code_challenge={}&code_challenge_method=S256'.format(myClientID,nonce,code_challenge)
            loginReferer = url
    
            myHeader = {'accept'          : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                       'accept-encoding' : 'gzip, deflate, br',
                       'accept-language' : 'en-US',
                       'connection'      : 'keep-alive',
                       'host'            : 'prodindego.b2clogin.com',
                       'user-agent'      : 'Mozilla/5.0 (Linux; Android 11; sdk_gphone_x86_arm) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36'
                       }
            mySession.headers = myHeader
    
            response = mySession.get(url, allow_redirects=True )
            self._log_communication('GET   ', url, response.status_code)
            myText= response.content.decode()
            myText1 = myText[myText.find('"csrf"')+8:myText.find('"csrf"')+300]
            myCsrf =  (myText1[:myText1.find(',')-1])
    
            myText1 = myText[myText.find('nonce'):myText.find('nonce')+40]
            myNonce = myText1.split('"')[1]
    
            myText1      = myText[myText.find('pageViewId'):myText.find('pageViewId')+60]
            myPageViewID = myText1.split('"')[2]
    
            myReqPayload['pageViewId']=myPageViewID
    
            mySession.headers['x-csrf-token'] = myCsrf
            mySession.headers['referer'] = url
            mySession.headers['origin'] = 'https://prodindego.b2clogin.com'
            mySession.headers['host'] = 'prodindego.b2clogin.com'
            mySession.headers['x-requested-with'] = 'XMLHttpRequest'
            mySession.headers['content-length'] = str(len(json.dumps(myPerfPayload)))
            mySession.headers['content-type'] = 'application/json; charset=UTF-8'
            mySession.headers['accept-language'] = 'en-US,en;q=0.9'
    
    
            myState = mySession.cookies['x-ms-cpim-trans']
            myCookie = json.loads(base64.b64decode(myState).decode())
            myNewState = '{"TID":"'+myCookie['C_ID']+'"}'
            myNewState = base64.b64encode(myNewState.encode()).decode()[:-2]
            #'{"TID":"8912c0e6-defb-4d58-858b-27d1cfbbe8f5"}'
            #eyJUSUQiOiI4OTEyYzBlNi1kZWZiLTRkNTgtODU4Yi0yN2QxY2ZiYmU4ZjUifQ
    
    
            myUrl = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/B2C_1A_signup_signin/client/perftrace?tx=StateProperties={}&p=B2C_1A_signup_signin'.format(myNewState)
            CollectingCookie = {}
            for c in mySession.cookies:
                CollectingCookie[c.name] = c.value
    
    
            response=mySession.post(myUrl,data=json.dumps(myPerfPayload),cookies=CollectingCookie)
            self._log_communication('POST  ', myUrl, response.status_code)
    
            myUrl = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/B2C_1A_signup_signin/api/CombinedSigninAndSignup/unified'
            mySession.headers['accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
            mySession.headers['accept-encoding'] = 'gzip, deflate, br'
            mySession.headers['upgrade-insecure-requests'] = '1'
            mySession.headers['sec-fetch-mode'] = 'navigate'
            mySession.headers['sec-fetch-dest'] = 'document'
            mySession.headers['sec-fetch-user'] = '?1'
            mySession.headers['sec-fetch-site'] = 'same-origin'
    
    
            del mySession.headers['content-length']
            del mySession.headers['content-type']
            del mySession.headers['x-requested-with']
            del mySession.headers['x-csrf-token']
            del mySession.headers['origin']
    
            myParams = {
                'claimsexchange': 'BoschIDExchange',
                'csrf_token': myCsrf,
                'tx': 'StateProperties=' + myNewState,
                'p': 'B2C_1A_signup_signin',
                'diags': myReqPayload
                }
            # Get the redirect-URI
    
            response = mySession.get(myUrl,allow_redirects=False,params=myParams)
            self._log_communication('GET   ', myUrl, response.status_code)
            try:
                if (response.status_code == 302):
                    myText = response.content.decode()
                    myText1 = myText[myText.find('href') + 6:]
                    myNewUrl = myText1.split('"')[0].replace('&amp;','&')
                else:
                    pass
            except:
                pass
    
            mySession.headers['sec-fetch-site'] = 'cross-site'
            mySession.headers['host'] = 'identity.bosch.com'
    
            # Get the CIAMIDS
            response = mySession.get(myNewUrl,allow_redirects=True)
            self._log_communication('GET   ', myNewUrl, response.status_code)
            try:
                if (response.history[0].status_code != 302):
                    pass
                else:
                    myNewUrl = response.history[0].headers['location']
            except:
                pass
    
            # Signin to Session
            response = mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # Authorize -IDS
            myNewUrl = response.headers['location']
            mySession.headers['host'] = 'identity-myprofile.bosch.com'
            mySession.headers['upgrade-insecure-requests']='1'
    
            response = mySession.get(myNewUrl,allow_redirects=False)
            myNewUrl=response.headers['location']
    
            postConfirmUrl = myNewUrl[myNewUrl.find('postConfirmReturnUrl'):myNewUrl.find('postConfirmReturnUrl')+300].split('"')
            # Get the login page with redirect URI
            #returnUrl = myNewUrl
            #myNewUrl='https://identity-myprofile.bosch.com/ids/login?ReturnUrl='+returnUrl
    
            step2_AuthorizeUrl = myNewUrl
            response=mySession.get(myNewUrl,allow_redirects=True)
            self._log_communication('GET   ', myNewUrl, response.status_code)
            myText = response.content.decode()
            # find all the needed values
            RequestVerificationToken = myText[myText.find('__RequestVerificationToken'):myText.find('__RequestVerificationToken')+300].split('"')[4]
            contentReturnUrl = myText[myText.find('ReturnUrl'):myText.find('ReturnUrl')+1600].split('"')[4]
            ReturnUrl =myText[myText.find('ReturnUrl'):myText.find('ReturnUrl')+300].split('"')[4]
    
            postConfirmUrl = myText[myText.find('postConfirmReturnUrl'):myText.find('postConfirmReturnUrl')+700].split('"')
    
            myNewUrl='https://identity-myprofile.bosch.com/ids/api/v1/clients/'+myText[myText.find('ciamids_'):myText.find('ciamids_')+300].split('%2')[0]
            response=mySession.get(myNewUrl,allow_redirects=True)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            myNewUrl = step2_AuthorizeUrl+'&skid=true'
            mySession.headers['sec-fetch-site']='same-origin'
            mySession.headers['accept']='text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
            del (mySession.headers['referer'])
            # https://identity-myprofile.bosch.com
            # /ids/login?ReturnUrl=%2Fids%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3Dcentralids_65EC204B-85B2-4EC3-8BB7-F4B0F69D77D7%26redirect_uri%3Dhttps%253A%252F%252Fidentity.bosch.com%26response_type%3Dcode%26scope%3Dopenid%2520profile%2520email%26state%3DOpenIdConnect.AuthenticationProperties%253DZIkEldcO9j64ZsZ8lxkOF43KmLm9E-R7KiQ6vyWOHRY5coi-sQOCNbtzVfTmM30G2dQ8taj9dupmlMsdfl_aeQfBTLbXNPCoPMduVcoXcUVDx-G2Wo1BhyJmZZryQWMKBGVS5akW3441ocWSmzZ3sseK4ysrm14GxCYIjaXQLw-5-jqSp5xQ3fTbCIIuiEI0zql0bnoAQW2ElbUfFxCZGg2BPRJeIBGddPQOJ_TVR0fZ_Rb2Ex5CJorqDK-GzAq_eKEcqhLwSw3jLLJeyXqHiP8lVwo%26nonce%3D638175139721725147.NTYxMTVjOTEtZGQ2MC00NWFlLWFlMzgtZGRiNWVjZGNjZTNjMTk1ODMwMGQtNTY4OS00MDY5LThiYWItZDRjMTNkZmEzZTEy%26code_challenge%3DVZhREJ7Xv0gvQw6ehTBc55P9Lh3qWX7CiW7wTYYxqY0%26code_challenge_method%3DS256%26postConfirmReturnUrl%3Dhttps%253A%252F%252Fidentity.bosch.com%252Fconnect%252Fauthorize%253Fclient_id%253Dciamids_12E7F9D5-613D-444A-ACD3-838E4D974396%2526redirect_uri%253Dhttps%25253A%25252F%25252Fprodindego.b2clogin.com%25252Fprodindego.onmicrosoft.com%25252Foauth2%25252Fauthresp%2526response_type%253Dcode%2526scope%253Dopenid%252520profile%252520email%2526response_mode%253Dform_post%2526nonce%253DTRg%25252FDjkgw7qNuS2Rh3OslA%25253D%25253D%2526state%253DStateProperties%25253DeyJTSUQiOiJ4LW1zLWNwaW0tcmM6MjU2YzJjOWYtMzlkNC00Y2E2LWFlYTctMTYwZmE4ZTY1ZWRhIiwiVElEIjoiZTgxZjU1MWUtMmM4MC00YmNjLWI4ODgtYjU2NGJlMmEwYzllIiwiVE9JRCI6ImI4MTEzNjgxLWFlZjQtNDc0Yi05YmEyLTI1Mjk0Y2FhNDhmYyJ9%26x-client-SKU%3DID_NET461%26x-client-ver%3D6.7.1.0&skid=true
    
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
            myNewUrl = response.headers['location']
    
            # Now go for the single-key-id
            # Get Single-Key-Site
            # 1. Step
            #
            # auth/connect/authorize?client_id=7ca4e64b-faf6-ce9e-937d-6639339b4dac&redirect_uri=https%3A%2F%2Fidentity-myprofile.bosch.com%2Fids%2Fsignin-oidc&response_type=code&scope=openid%20profile%20email&code_challenge=5U4qTGs6v14xAZWvC3lENuVSzuvWLJ0IodizL75YWzk&code_challenge_method=S256&nonce=638175138999064799.OTMzYTExZGMtOGVhZS00MTQ5LTk2MmYtMTA0Mzg4YmJmYmVhOWYyZjEwZDYtZDE3Ny00OTczLTk1MDEtN2FmMjVmOTZiZmJm&state=CfDJ8BbTLtgL3GFMvpWDXN913TRMZYhIvGAQNZTmV8MG88I2iNRhqMCEorJUpmP8ShwrAEBHAAVfh7FgjR4gVnk3eQVuq_P-BvSRzmMKejfb_qxh7fq_Nhp8ULWZ9lU1LZzNEj140CnHaTaLY7LwsP5rXBy-JrdnDiYpPJOYMVswdn6BDZI_EvLnHqd4JJZ0P5Itay4pC0wyfKv2plk3_EyoOMteqnUFvGvfKUeevbbUScXXLwfdNgWjej3nP3BkCW5HDu3PDAz2g4jsC8l5eDZIIcYxpm3jXOcNJC_8B_2JwY9QTjeHDyfV3JNhPUruDTOCHDI4MWuh79pV5Eo-mHrkumSHfQRuycpQS7H6H5UT59io4D9B2xJfPrl-7tBU_5toC1nah0nUkfyyxirPzI6vBTXuJPiHdXC1mjj3wDX2UbFJEFhuvHuOsAzdICLtxS1rySeRcKcFD8nFGnSvIuVodgJSR9PRpXvzmS3cgaS0zae5FYN5LsDO7tTtTPTLadfaqQd11LjNqT7EZTnvT1SpW0HGiBBwPxzr8vSZGQG-xelop7scHH8SYGL4SrUn-nxvHbBYGDIwPrAoMYsIYfzcjPLZ4_VSPFPxVZcAK-8_i_LqKbUhm1ECJlfgOn5hOZhQGTR5uqXZTBJTSIrbHcdc0XMSXZSIi56qBWXiEHwYLAOtiEbNUVjMckyUI-HnrBmfZMhpiLndgLXHhLDr7lNIsBjll_1QOhZxFukftPVwFXIrgKPXWvUz4zky9mwFk9mwQvD2Ip77WvZz5MhJrfCNaPlASLelSdJlVQVRY3-qBdg7CzxFyJs_HOZX37oXsqH02lwda5uAHU2GAtNLfkmj_WGE05qB04gLfn9Y6rf_cXix4oIltbQqf57VUt7xdBKplcQUqeGqoDOg5eHLiz_-9iHu7GHRmqt3SDVxBrZlvL9KxwHAAuUpDJ97oRD51KdZlFFYjTNDjrHHrajshD6yRqFx2a4mGsd_pI_wnS12d9oZs8ILn3Lhdz9ATpNADGoTjbf0dRG8L-hMEx1DBeVID1GztCT-WIbl57xK-2NfbGjQ3MGk5W4vNxwGcxt3L6eRgrAIgAIGlTLHVJc-nQ4RSabzOB-kfUx-mTCHJYMkawqGIrJKkfozj-8aNYoE-wXUVFB63D-xVS25r5V0ttUGehjc4eZjN9JQA6U-ZZXe4UNv5hW8XVCYd-IT83JV340pMqERBjRNYAOPUn3LrDwXwFSKyYecgXMoyZ2d7wEZ-zuqHNCnlAKkLpsR5fJuybDPYNDDdFFHz-du-G2Aq38EUSBPjoUZVRjIUHhQfOUOEicg29ReBOueI-I61pkJKdgfiI7Zezy7Uit71CiZ1kNDjLWC0JkvpiUbXAv_TUySqk62tNkDL2T8E7gj1aT250Pxg7gSmmpBxRWv_0ZltyXwRTR564egzv0BDe4mhIOX5sNGL1HjwBJidNrZ0Q2jL6qr1a2W6DFIyuQ68eZmFAiq4WDkdv928fWMedndQHjgw6t1gBnG6l-J_JINqYaw0vnDUsyWKSzErcf5LN-4_o9RjwcJ3A0iui6PpUyYpQlRlwhobOlCa7V4_4sNQXH5-dlD6lhvXEtHHdBjb9xB9MNIwAJCMkoNU3q3ln10yeFBh_W6Iy25bPthFOeIONFWhC_FslnJvAzlX_kLCieFrGpOmkgE5V9FN-I9fxDX18a3JgdG-qt3YZzgcjTwwiM7YtgRHU4Ikmo7TqaOMfdJjz-Y3FPoaSOKUv6_eVfoY22lNyOMvU-SGLec_7MfpOR0YD2Cvz9Ibo6uh0umjrRHQKEIjzeR0yBjdl68BkoLu7qE0A_tVbcUK918fK2eExs7LONzVshb0_Ruwk5u1sqeft5AWxfYBZSSfnOwzHhS1-PZuWZSF9YVZXd72aKVgvWcyAEDOnsCifsXXzaboJAzs7K00gq9Tq-o3Mlfd44jugQ5-_maYnV9oY646o7ILJ6FD1A93X1mYkR6V7Ma6hxADmoYmD3-teZo_EVmSH6w_ElnYF98-TRyhXqI7tUK10c92kqB_biWHlH25cE-KvH3MaqBkGt1PSBr7kbpX9bxAKS9vP9gYEwCqJG6Ho796cItahFicQDqL2XdxUARA6eyeQUwwz216rIKsPypst-hCyqFWVcv7IS_hzVtSzJfxPLCkmzMmD84u6OL_SMO_GVfnb0X5C33ndFqRu6_aa-6QnuHpyyOBsuWUV_JZ5GED7PajJ-K16Py_23vRp4gKXpfXCOH8E3wESB2aSCXWC5It7tgqQBpdxiavH6CcvsfN-JrBRbHgw&x-client-SKU=ID_NETSTANDARD2_0&x-client-ver=5.6.0.0'
            # https://singlekey-id.com
            step += 1
            del (mySession.headers['host'])
            mySession.headers['user-agent'] = 'Mozilla/5.0 (Linux; Android 11; sdk_gphone_x86_arm) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36'
            mySession.headers['sec-fetch-site']='cross-site'
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 2. Step
            # https://singlekey-id.com
            # auth/log-in?ReturnUrl=%2Fauth%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3D7ca4e64b-faf6-ce9e-937d-6639339b4dac%26redirect_uri%3Dhttps%253A%252F%252Fidentity-myprofile.bosch.com%252Fids%252Fsignin-oidc%26response_type%3Dcode%26scope%3Dopenid%2520profile%2520email%26code_challenge%3D_H7Bn1EBzLmdvYxRd-ZU9moDgCCOeLhuZlr2oWbTr8Y%26code_challenge_method%3DS256%26nonce%3D638175138466544692.Y2MwNjJlMDEtMjYzZS00MjZlLThhYTQtMTg0MmFjZGMwMzgzMmNmMTI0MGUtYWEyNC00OWExLWJlNTMtMTgzZDFmMDg3NTE5%26state%3DCfDJ8BbTLtgL3GFMvpWDXN913TTi4lyCR0HNQl1e_IHHsZzeJpmbm3hvFYhV6JhmVAlez_YwxFKyT18rCdVOrh8ncg6h6Wi3zCKgovjE7Jn7k9ZuZoWDC7XldFX_3Z2IzwG8WdD4V7ZVlwFChaohZ3fMDYvVPVhzbu7K-5VdMJdSGvyD0J5qaoSL0x-W76jQz15WAMP0npoq4Eyl1rjCVLTunSiQdt1mDJQE_3W1BFj41iW-1nfNeU5Xy8du_AnxyJ-UtWAAAeIr2lwaPKdyr1Mh_G3Q0QwJLxsJY-GhcJXxsBn95cUEDlHjBHRGbgn9T9ab87ppLvyMV3YI6PCu0RWs10IkIxdPFgAVZxb2PRggc8NOGQLnKIOr_2pHKmYw73JT2afa8cPc1CIobT-OS9Xt5_qfKgL6a2dl0RGc29tIPeHqlF-tolY3LSjyEEbOYJ1rLIO9MnR-HHRgq1JpmOPZe5DAl2wRmUDw16GdqQw71NRA0FmExtfLV6vKDrYJfs6IrJEaiC2dsU1mK8WVrTippBdINKhOmTgfvW0o8NiDnHmaKMg35niVI9SKgfEDlccj9EZYw9BOy9pdsPqkQzpAFpCP_BYHHhSmu-Pcj5KAqhY3wm2iRTuMuTLHWt0PP54c9l1kQ2JEoCYt9hHYLl4_D0szQVBUpJLYZgDrWtoLLRbEEPHLnO45pc6gtHyM8j15U0N4GWeiPXZJMnwA-d_dIU5meiWCc3HeA0o-F0IQ688U-GBNXg_QKyatAk6_pGdz7BAokNTiiA9IkJewfqINtjjPkujuNEMhSGNI65GSdk1PBgGAGVgY4o4G1JXUv8VMOQgR5ULtSMfepBf6z2ZIZu7lClg3YUdEGiEyfhU-Gz164D9JYbBtx0gCExg585eXsG2YZ1JNCWqu6eobXWjKBN0IejMmdw4N8uy4EvvWK9RBZ4TCZWXqPM-q0T-REUfm4HmvQvtL-WU8IO8FM1pZaHvePi6qcpivuZWnD1I7PWDbtNSai7uuEm4tMA7NpkBMlh2MNYG5XadLoFN0rrR4TJHHuq2r-AhiGXw8KlXsgff3yZdgCjn854gVjOnnvjwdTrzCaUSsSPiAZ5yFAVYUHKqIzGKXK6MQ7vBdJzfEPwFDNe4aIxEAHogn7hHLJn37b5WgrXZhUxha1zDQcEhdTtEr161soKFRJ1njLwWvXTSCbYUUfVN6BVCIAluWi0C2RLNYmSdUji3B4l_oJ5mq_gjmfdc37e3Xd1EWZtcgFRiO0yEldcscbwsltEzelF_lnK-VImZsr1Y1BD4VahyiykFZF15SAbrhVF6sAHf28mvO38dOqzdt7_B4K2VcOnmo9gM63BNw9rU_dMGLHXub4lJISoOMqeTFN_NmMUrkv41uKUc15e0e2fWS-faC4cZ6hRibrkkCdH5MyqHc8jtMDdIKp59LwXEKskaXrNUO9EL8XR_EfboHIER8dhEUG_ZuaY4FiO64ttgrRvPCC3uokeWhXsa7gx9HsONKqGjFAxCiMDba35uRpcWpunix601ex2le-6vuGpAQ-vqcMrUOvh45sAuHCIa8PLU08zx99lqrd9ERSodPfAGFBVyNh0Y0-y6d1vKYykOj4o7REphB3LnSotJruBVpCaLS1omcA88NtMkJoboKjDBPqzaIX3d9bZhnur3yoFcnjGKoismBmLgDtJY2PT3AAaOBbBjuM_KeqNC92gO_vUkXCa6MJ7JYmlnaRJVMtTFB3Ta4iSaGy7CGkz9KZZcaWPEpTEop-yb64cmkebDCWpcY9Tzouvsvg7CsX2ONM6ejOqDXo_ZpIQrEYVg7PMgZ7NxJhRlrjUDiyYQPofugwC_zaTA1p0oruIkPEmqUwgGSVaBZ8V9WBr2e_dregnUukkjKyft1secvXqaHdV1Ob684PRs_A3-zgKEHAjrkrglRljfsTzTDuDYC3uU3nxFtXFDG42SEcaDAHCPQWwr9j9KwZWgbbohX2dZly9ukvxO1WgPpfyvzKZOK7PpjsbghdIqTu9LX8gFbDNFuPoZ91X4jMG5SnL63YbdLgo68I8c_N_8bBRz1x233HRpJn0ltrxuQULalNjw7XQn9L0iNvZxDf6ZoFgOGNrtFe7PiZTRC6uksaWbFfhXAACmWrAIsi1_6KXLQfjXRhn7ZThfSVDdWWF0M9dv9AUHLoJDbt6eXYQqCTUkBJRkDXPDGzpkCpZT09FIOBFhRt5KKWkAkjldQ5l-6imVGir7LbIPoUVuMDN3C3y8oo2Vd3oWuT3-GhZXz6TkAwlTFeAGfe0g4XtW4wRrz8TYmHw%26x-client-SKU%3DID_NETSTANDARD2_0%26x-client-ver%3D5.6.0.0'
            step += 1
            myNewUrl = response.headers['location']
            mySession.headers['Host']='singlekey-id.com'
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 3. Step
            # https://singlekey-id.com
            # auth/log-in/?ReturnUrl=%2Fauth%2Fconnect%2Fauthorize%2Fcallback%3Fclient_id%3D7ca4e64b-faf6-ce9e-937d-6639339b4dac%26redirect_uri%3Dhttps%253A%252F%252Fidentity-myprofile.bosch.com%252Fids%252Fsignin-oidc%26response_type%3Dcode%26scope%3Dopenid%2520profile%2520email%26code_challenge%3DTZdCd3C1FX0t08NtCr-rCmJxOrAQiPaNYytL-1Wi9TY%26code_challenge_method%3DS256%26nonce%3D638175136336911121.MGJiYTY0ZGQtN2E4My00MTJmLTg4NjgtNDc1NzAwYTExZDE3NmJhMzExMTEtYWIxZC00MjQ4LWFlNzItODI0MWYyMjg1Y2Zj%26state%3DCfDJ8BbTLtgL3GFMvpWDXN913TQFZ0MRP7aNSvpY-IwH5nqb4gdz1W3Ohx6L_5jrLoqk-iG8_Fb6txKNub_FyGnywp_hEdKhmOrG1QvFtB9Zok6PoKNloLcq1IwoxS2eFAS6qsvHBRR84Yq9D24B1d7klbITisHcQPNTYf-bsMv5w_CcMSrgzRHUFnqFPIHREMkunq1cqUfDCmOw_gFOCzZIAyp0GDRVMvJEmc7mBGjk8nhpJLtdIy2iPn2WXcueAfN7cF8jKtf_uOmSR233K2YM38GoIRgVb_ICWHJ_tqDWs7GIbMffl9D9Q5A2Aa_fopg4vZtk53G8P4jWoX47caPYSmyKwjzAPcP327lUR8tTVFduPEgcGwFrB_U41vtytxSGIrrSQAJU-GyvULXF-BwEJ_ScceQ4udNb_yFbUa8x1YMeVNqsyMvOItv46wPCW5OAycPEfzGfmcntKg4d1XVOkjr4hzc-3oehALLrCI4RFc_-3NtuUMkdZoV93QPA1pndlGajn5CkWu5_QCCa1aUR3unKd5g3OhiQ3ngxjEFbxiHcOrOt4PwaC6Nf6qvVixTXDLWvkL7MOjsSAjLZmoPtYHh4nWK6rnWKvh5J-kn-uJxZm0yKBnm59BQVemH-5XHAIzNGuXuo7R6nxUcsFWZnMCfyxu-d4ta7tUqI2LL-Sz3Fc6qw-3sVrXb9hyxITKAn1-KYNqhWokE3rzhU1itdgQyJIQd4b4eMPES-np8YNHld0hOKCeai4WD8rph054rW049Hfph1g4VVilswqfjEt7jPvIqIlEpMjAs38i6w8GREeJr2_lbrqPN0KF6Bj9jeZV4zy5LCDKItLc-ZRiBxon4dWHYhXy1UjjvPDpDepWtUhPF6FXHyYjN4D222itkTwxOuwLQc-AlWCD09A0bTi4FWOYy2IlwDhprTT15TLfb8QJ3upE8LvPNkRUiadvM0f0M214-Y_K0s53W6oUOvMtXnjqXmYRCoBW18HL1AOfyMto2aJtEB_83sE6Qf18Y2pBMZPMb2bkMURckCBhWwAVFxC0w30HaIVPfrXcRypgFBeh3GS54jrQTC3ropVvqQVUcZXNeZNCApV7M_eLsvgkUlVVeKB0-Dgce7SNaH8AcNtf-17c6WiY3T3FypjsNTzpBgobj7Ay0HL8B8FBighQ0wJxyARRyFRLHTubgVN4Y-tV2hFlc4o2eWzLeJyEFtE48KTpvz8ydXuhYoXAj6gPWoyt-VEdxYwE8OUcswQxWX7De4VyeUi8eOxHwdE3-T3blmDWLzsCuvhUSeL-ykXd0V-T6zMmSDonVL8taIt2xO14yM40X48xCp8d4slOXtZOFuVodMeV5otdZXZmeMVWgVPSUdcuCkCDP2KljEqhtOfCpDy5vDVgJKK9axabMpI-AbzINbz9vFId5wN6crBDjW0bwrQ68gCUhRcHtTtBoLC7y65onvzTLPTslASYTAIGQojvdxxOe5j_nB0iHqcnhbxUtp_vLv2UsrLVfI06MhXfJHO8Sx3LGgxhkXDMMorPnfe2gPLHB39SwZDinwewE2hQU0G-LCqUL5B3AG-lsT-i2FimJTqca6OqPkOo-QuVr2b72iskzxyOFxK6gQhNuvpmlj_47SVcRqK8HbLGU_rAYlmucAP9BbRBKnT0pcVmYpVxCt7tWnQ5uKywZRvUvWX9RVTICz7TssZCm4JnCp8_wRKMxrcJ7hFNb4h2qdjCUm4QgU16h-3L6E1j0UlRzf3w2gPiONPWt3vOGgyn-SGM1jXpLDzWfr-dUxeVlr1Z6we1fjaDo3dDZEJrj1fEeQFb9NxH6LlZmPLDHBXYex3YzO1OxUzaigPqmsMXIuh5STg78lB8k1m2cN96b8I0ohwL0eWbDvoTaLlLudfeo9RkGQ9cMkjTvQvQ4rQEfKVU1YnBM1NijW98yr9Fq8WRuoQL01_s8jnSI7htLo4u8VVpnDC1dSvErrcoM6ob-GBVstIeHdPJV36NHevlylkabKgoZKhl5tqpbVzjrKuyrc2IKdFiavPiTsSxojpFmL8fpqGZiK6XDEe6TWmrZ8Xy8QL6vDTbVtHRvW4-2WIgMdOqP20IzTQTDfUDs9FWrvo0z4JtJ_iC0ZTP3eEk5q1DGHNmzSTkAp4qq1pjgAkiU7hOrTNTFgLkBcy7wAk0eD16DzACp7mY4Z04exIHhPbou7p_904xcptBXT4XtjrS2qneEP8P5j51W0y3kCdEqiR73L0nBpLxj26NVXPDUYxLym1trfQrVyKMiFYIS8u7KiVIlWodukE7fJ1E7gQ_dfpA%26x-client-SKU%3DID_NETSTANDARD2_0%26x-client-ver%3D5.6.0.0
            step += 1
            myNewUrl = response.headers['location']
            postConfirmUrl = myNewUrl[myNewUrl.find('ReturnUrl')+10:].split('"')[0]
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 4. Step - get XSRF-Token
            #https://singlekey-id.com/static/roboto-latin-400-normal-b009a76ad6afe4ebd301e36f847a29be.woff2
            step += 1
            myNewUrl='https://singlekey-id.com/favicon.ico'
            response=mySession.get(myNewUrl,allow_redirects=True)
            self._log_communication('GET   ', myNewUrl, response.status_code)
            myXRSF_Token = response.history[0].cookies.get('XSRF-TOKEN')
    
            # 5. Step
            step += 1
            mySession.headers['x-xsrf-token']=myXRSF_Token
    
            myNewUrl='https://singlekey-id.com/auth/api/v1/authentication/UserExists'
            myJson = { "username": user }
    
            mySession.headers['origin']= 'https://singlekey-id.com'
            mySession.headers['content-type']= 'application/json'
            response=mySession.post(myNewUrl,json=myJson,allow_redirects=False)
            self._log_communication('POST  ', myNewUrl, response.status_code)
    
    
            # 6. Step
            step += 1
            postConfirmUrl = urllib.parse.unquote(postConfirmUrl)
            myJson = {
                          "username": user,
                          "password": pwd,
                          "keepMeSignedIn": False,
                          "returnUrl": postConfirmUrl
                        }
            RequestVerificationToken = mySession.cookies.get('X-CSRF-FORM-TOKEN')
            mySession.cookies.set('XSRF-TOKEN',myXRSF_Token)
            mySession.cookies.set('X-CSRF-FORM-TOKEN',mySession.cookies.get('X-CSRF-FORM-TOKEN'))
            mySession.cookies.set('.AspNetCore.Antiforgery.085ONM3l57w',mySession.cookies.get('.AspNetCore.Antiforgery.085ONM3l57w'))
    
    
    
            mySession.headers['content-type']= 'application/json'
            mySession.headers['accept'] = 'application/json, text/plain, */*'
            mySession.headers['sec-fetch-site'] = 'same-origin'
            mySession.headers['host'] = 'singlekey-id.com'
            mySession.headers['origin'] = 'https://singlekey-id.com'
            mySession.headers['sec-fetch-dest'] = 'empty'
            mySession.headers['sec-fetch-mode'] = 'cors'
    
            del mySession.headers['upgrade-insecure-requests']
            del mySession.headers['sec-fetch-user']
    
            mySession.headers['requestverificationtoken'] = RequestVerificationToken
    
            myNewUrl='https://singlekey-id.com/auth/api/v1/authentication/login'
            response=mySession.post(myNewUrl,json=myJson,allow_redirects=True)
            self._log_communication('POST  ', myNewUrl, response.status_code)
    
    
            # 7. Step
            step += 1
            mySession.cookies.set('idsrv.session',mySession.cookies.get('idsrv.session'))
            mySession.cookies.set('.AspNetCore.Identity.Application',mySession.cookies.get('.AspNetCore.Identity.Application'))
            mySession.headers['accept']='text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9'
            mySession.headers['host']='singlekey-id.com'
            mySession.headers['sec-fetch-dest']='document'
            mySession.headers['sec-fetch-site']='same-origin'
            mySession.headers['sec-fetch-user']='?1'
            mySession.headers['upgrade-insecure-requests']='1'
            mySession.headers['sec-fetch-mode']='navigate'
            del(mySession.headers['origin'])
            del(mySession.headers['requestverificationtoken'])
    
            myNewUrl = 'https://singlekey-id.com'+postConfirmUrl
            response= mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ',myNewUrl, response.status_code)
    
    
            # 8. Step
            step += 1
            myNewUrl = response.headers['location']
            mySession.headers['host']='identity-myprofile.bosch.com'
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 9. Step
            step += 1
            myNewUrl = 'https://identity-myprofile.bosch.com'+response.headers['location']
            response=mySession.get(myNewUrl,allow_redirects=False)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 10. Step - Authorize
            step += 1
            CollectingCookie = {}
            CollectingCookie['idsrv.session'] = mySession.cookies.get_dict('identity-myprofile.bosch.com','/ids')['idsrv.session']
            CollectingCookie['.AspNetCore.Identity.Application'] = mySession.cookies.get_dict('identity-myprofile.bosch.com','/ids')['.AspNetCore.Identity.Application']
            myNewUrl = 'https://identity-myprofile.bosch.com'+response.headers['location']
            response=mySession.get(myNewUrl,allow_redirects=False,cookies=CollectingCookie)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 11. Step
            step += 1
            del mySession.headers['x-xsrf-token']
            del mySession.headers['content-type']
            mySession.headers['host']='identity.bosch.com'
            mySession.headers['sec-fetch-site']='same-origin'
            CollectingCookie = {}
            CollectingCookie['styleId'] = mySession.cookies.get_dict('identity.bosch.com','/')['styleId']
            myDict = mySession.cookies.get_dict('identity.bosch.com','/')
            for c in myDict:
                if ('SignInMessage' in c):
                    CollectingCookie[c] = myDict[c]
            myNewUrl = response.headers['location']
            response=mySession.get(myNewUrl,allow_redirects=False,cookies=CollectingCookie)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 12. Step
            step += 1
            CollectingCookie['idsrv.external'] = mySession.cookies.get_dict('identity.bosch.com','/')['idsrv.external']
            myNewUrl = 'https://identity.bosch.com'+ response.headers['location']
            response=mySession.get(myNewUrl,allow_redirects=False,cookies=CollectingCookie)
            self._log_communication('GET   ', myNewUrl, response.status_code)
    
            # 13. Step
            step += 1
            CollectingCookie={}
            CollectingCookie['idsrv'] = mySession.cookies.get_dict('identity.bosch.com','/')['idsrv']
            CollectingCookie['styleId'] = mySession.cookies.get_dict('identity.bosch.com','/')['styleId']
            CollectingCookie['idsvr.session'] = mySession.cookies.get_dict('identity.bosch.com','/')['idsvr.session']
    
            myNewUrl = response.headers['location']
            response=mySession.get(myNewUrl,allow_redirects=False,cookies=CollectingCookie)
            self._log_communication('GET   ', myNewUrl, response.status_code)
            myText= response.content.decode()
            myCode = myText[myText.find('"code"')+14:myText.find('"code"')+300].split('"')[0]
            mySessionState = myText[myText.find('"session_state"')+23:myText.find('"session_state"')+300].split('"')[0]
            myState = myText[myText.find('"state"')+15:myText.find('"state"')+300].split('"')[0]
    
            # 14. Step - /csp/report
            step += 1
            myReferer = myNewUrl # the last URL is the referer
            CollectingCookie['idsvr.clients'] = mySession.cookies.get_dict('identity.bosch.com','/')['idsvr.clients']
            myNewUrl='https://identity.bosch.com/csp/report'
    
            myHeaders = {
                        'accept' : '*/*',
                        'accept-encoding':'gzip, deflate, br',
                        'accept-language' : 'en-US,en;q=0.9',
                        'connection':'keep-alive',
                        'content-type' : 'application/csp-report',
                        'origin' : 'https://identity.bosch.com',
                        'referer' : myReferer,
                        'sec-fetch-dest' : 'report',
                        'sec-fetch-mode' : 'no-cors',
                        'sec-fetch-site' : 'same-origin',
                        'user-agent' : 'Mozilla/5.0 (Linux; Android 11; sdk_gphone_x86_arm) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36'
                        }
    
            myPayload = {"csp-report":{"document-uri": myReferer ,"referrer":"","violated-directive":"script-src","effective-directive":"script-src","original-policy":"default-src 'self'; script-src 'self' ; style-src 'self' 'unsafe-inline' ; img-src *;  report-uri https://identity.bosch.com/csp/report","disposition":"enforce","blocked-uri":"eval","line-number":174,"column-number":361,"source-file":"https://identity.bosch.com/assets/scripts.2.5.0.js","status-code":0,"script-sample":""}}
            response=mySession.post(myNewUrl,allow_redirects=False,cookies=CollectingCookie)
            self._log_communication('POST  ', myNewUrl, response.status_code)
    
            # 15. Step
            step += 1
            myHeaders = {
                        'accept' : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
                        'cache-control' : 'max-age=0',
                        'accept-encoding':'gzip, deflate, br',
                        'accept-language' : 'en-US,en;q=0.9',
                        'connection':'keep-alive',
                        'content-type' : 'application/x-www-form-urlencoded',
                        'host' : 'prodindego.b2clogin.com',
                        'origin' : 'https://identity.bosch.com',
                        'referer' : myReferer,
                        'sec-fetch-dest' : 'document',
                        'sec-fetch-mode' : 'navigate',
                        'sec-fetch-site' : 'cross-site',
                        'user-agent' : 'Mozilla/5.0 (Linux; Android 11; sdk_gphone_x86_arm) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Mobile Safari/537.36'
                        }
            request_body = {
                            'code' : myCode,
                            'state' : myState,
                            'session_state' : mySessionState
                           }
            myNewUrl = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/oauth2/authresp'
            response=mySession.post(myNewUrl,allow_redirects=False,data=request_body,headers=myHeaders)
            self._log_communication('POST  ', myNewUrl, response.status_code)
    
    
    
            # 16. Step
            # go end get the Token
            step += 1
    
            myText= response.content.decode()
            myFinalCode = myText[myText.find('code%3d')+7:myText.find('"code%3"')+1700].split('"')[0]
    
            request_body = {
                            'code' : myFinalCode,
                            'grant_type' : 'authorization_code',
                            'redirect_uri' : 'com.bosch.indegoconnect://login',
                            'code_verifier' : code_verifier,
                            'client_id' : myClientID
                            }
    
            url = 'https://prodindego.b2clogin.com/prodindego.onmicrosoft.com/b2c_1a_signup_signin/oauth2/v2.0/token'
            mySession = requests.session()
            mySession.headers['accept'] = 'application/json'
            mySession.headers['accept-encoding'] = 'gzip'
            mySession.headers['connection'] = 'Keep-Alive'
            mySession.headers['content-type'] = 'application/x-www-form-urlencoded'
            mySession.headers['host'] = 'prodindego.b2clogin.com'
            mySession.headers['user-agent'] = 'Dalvik/2.1.0 (Linux; U; Android 11; sdk_gphone_x86_arm Build/RSR1.201013.001)'
    
            response = mySession.post(url,data=request_body)
            self._log_communication('POST  ', url,response.status_code)
            myJson = json.loads (response.content.decode())
            _refresh_token = myJson['refresh_token']
            _access_token  = myJson['access_token']
            _token_expires  = myJson['expires_in']
            

            # 17. Step
            # Check-Login
            step += 1
            url='https://api.indego-cloud.iot.bosch-si.com/api/v1/alms'
            myHeader = {'accept-encoding' : 'gzip',
                        'authorization' : 'Bearer '+ _access_token,
                        'connection' : 'Keep-Alive',
                        'host'  : 'api.indego-cloud.iot.bosch-si.com',
                        'user-agent' : 'Indego-Connect_4.0.0.12253'
                        }
            response = requests.get(url, headers=myHeader,allow_redirects=True )
            self._log_communication('GET   ', url, response.status_code)
            if (response.status_code == 200):
                myJson = json.loads (response.content.decode())
                _alm_sn = myJson[0]['alm_sn']
                self.last_login_timestamp = datetime.timestamp(datetime.now())
                self.expiration_timestamp = self.last_login_timestamp + _token_expires
                self._log_communication('LOGIN ', 'Login to Sinlge-Key-ID successful done ', 666)
                return True,_access_token,_refresh_token,_token_expires,_alm_sn
            else:
                return False,'','',0,''
            
        except err as Exception:
            self._log_communication('LOGIN ', 'something went wrong during getting Sinlge-Key-ID Login on Step : {} - {}'.format(step,err), 999)
            self.logger.warning('something went wrong during getting Sinlge-Key-ID Login on Step : {} - {}'.format(step,err))
            return False,'','',0,''



    
    def _get_predictive_calendar(self):
        '''
        GET
        https://api.indego.iot.bosch-si.com/api/v1/alms/{serial}/predictive/calendar
        x-im-context-id: {contextId}
        '''
        if (self._get_childitem("alm_mode") == 'smart') and ((self._get_childitem('stateCode') == 513) or (self._get_childitem('stateCode') == 518)):
            return        
        url = "{}alms/{}/predictive/calendar".format( self.indego_url, self.alm_sn)
        
        headers = {
                   'x-im-context-id' : self.context_id
                  }

        try:
            response = self._get_url(url, self.context_id, 10)
        except err as Exception:
            self.logger.warning("Error during getting predictive Calendar-Infos")
            return None
            
        if response != False:
            self.logger.info("Got correct predictive Calendar settings for smartmowing")
            return response

    
    def _get_calendar(self):
        '''
        GET
        https://api.indego.iot.bosch-si.com/api/v1/alms/{serial}/calendar
        x-im-context-id: {contextId}
        '''
        url = "{}alms/{}/calendar".format( self.indego_url, self.alm_sn)
        headers = {
                   'x-im-context-id' : self.context_id
                  }

        try:
            response = self._get_url(url, self.context_id, 10)
        except err as Exception:
            self.logger.warning("Error during getting Calendar-Infos")
            return None
            
        if response != False:
            self.logger.info("Got correct Calendar settings for mowing")
            return response
    
    def _clear_calendar(self, myCal = None):
        for cal_item in myCal['cals']:
            myCalendarNo = cal_item['cal']
            for days in cal_item['days']:
                myDay = days['day']
                for slots in days['slots']:
                    slots['En'] = False
                    slots['StHr'] = "00"
                    slots['StMin'] = "00"
                    slots['EnHr'] = "00"
                    slots['EnMin'] = "00"

        return myCal
    
            
    def _build_new_calendar(self, myList = None,type = None):
        if (type =='MOW'):
            selected_calendar = self._get_childitem('calendar_sel_cal')
        else:
            selected_calendar = self._get_childitem('calendar_predictive_sel_cal')
        newCal = {}
        emptySlot = {
                    'StHr' : '00',
                    'StMin' : '00',
                    'EnHr' : '00',
                    'EnMin' : '00',
                    'En' : False
                    }
        newCal['sel_cal'] = selected_calendar
        newCal['cals'] = []
        newCal['cals'].append({'cal':selected_calendar})  #['cal'] = selected_calendar
        newCal['cals'][0]['days'] = []
    
        for myKey in myList:
            if (myKey == "Params"):
                continue
            NewEntry = {}
            Start = ""
            End = ""
            Days  = ""
            myCalNo = 0
            calEntry = myList[myKey].items()
    
            for myEntry in  calEntry:
                if (myEntry[0] =='Start'):
                    Start = myEntry[1]
                elif (myEntry[0] == 'End'):
                    End = myEntry[1]
                elif (myEntry[0] == 'Days'):
                    Days = myEntry[1]
                elif (myEntry[0] == 'Key'):
                    myCalNo = int(myEntry[1][0:1])
            if (myCalNo != 1 and type =='PRED') or (myCalNo != 2 and type =='MOW'):
                continue
            for day in Days.split((',')):
                newSlot = {
                            'StHr' : Start[0:2],
                            'StMin' : Start[3:5],
                            'EnHr' : End[0:2],
                            'EnMin' : End[3:5],
                            'En' : True
                           }
                newDay = {
                            'slots': [newSlot],
                            'day' : int(day)
                         }
                dayFound = False
                for x in newCal['cals'][0]['days']:
                    if x['day'] == int(day):
                        oldSlot = x['slots']
                        x['slots'].append(newSlot)
                        dayFound = True
                        break
                if not dayFound:
                    newCal['cals'][0]['days'].append(newDay)
        # Add the empty slots for mowing calendars
        final_Cal = newCal
        calCounter = 0
        for calEntry in newCal['cals']:
            if calEntry['cal'] != 2:
                calCounter += 1
                continue
            dayCounter = 0
            for days in calEntry['days']:
                if len(days['slots']) < 2:
                       # add a empty slot
                       final_Cal['cals'][calCounter]['days'][dayCounter]['slots'].append(emptySlot)
                dayCounter += 1

        return final_Cal
        
    
 
                
    def _parse_list_2_cal(self,myList = None, myCal = None,type = None):
        if (type == 'MOW' and len(self.calendar_count_mow) == 5):
            self._clear_calendar(myCal)

        if (type == 'PRED' and len(self.calendar_count_pred) == 5):
            self._clear_calendar(myCal)
                
        if (type == 'MOW' and len(self.calendar_count_mow) < 5):
            myCal = self._build_new_calendar(myList,type)
        
        elif (type == 'PRED' and len(self.calendar_count_pred) < 5):
            myCal = self._build_new_calendar(myList,type)
        
        else:
            self._clear_calendar(myCal)
            for myKey in myList:
                if (myKey == "Params"):
                    continue
                Start = ""
                End = ""
                Days  = ""
                myCalNo = 0
                calEntry = myList[myKey].items()
                for myEntry in  calEntry:
                    if (myEntry[0] =='Start'):
                        Start = myEntry[1]
                    elif (myEntry[0] == 'End'):
                        End = myEntry[1]
                    elif (myEntry[0] == 'Days'):
                        Days = myEntry[1]
                    elif (myEntry[0] == 'Key'):
                        myCalNo = int(myEntry[1][0:1])-1
                # Now Fill the Entry in the Calendar
                for day in Days.split((',')):
                    if (myCal['cals'][myCalNo]['days'][int(day)]['slots'][0]['En'] == True):
                        actSlot = 1
                    else:
                        actSlot = 0
                    myCal['cals'][myCalNo]['days'][int(day)]['slots'][actSlot]['StHr'] = Start[0:2]
                    myCal['cals'][myCalNo]['days'][int(day)]['slots'][actSlot]['StMin'] = Start[3:5]
                    myCal['cals'][myCalNo]['days'][int(day)]['slots'][actSlot]['EnHr'] = End[0:2]
                    myCal['cals'][myCalNo]['days'][int(day)]['slots'][actSlot]['EnMin'] = End[3:5]
                    myCal['cals'][myCalNo]['days'][int(day)]['slots'][actSlot]['En'] = True  

        self.logger.info("Calendar was updated Name :'{}'".format(type))
        return myCal
    
    def _get_active_calendar(self, myCal = None):    
        # First get active Calendar
        activeCal = myCal['sel_cal']
        return activeCal
    
    def _parse_uzsu_2_list(self, uzsu_dict=None):
        #pydevd.settrace("192.168.178.37", port=5678)
        weekDays = {'MO' : "0" ,'TU' : "1" ,'WE' : "2" ,'TH' : "3",'FR' : "4",'SA' : "5" ,'SU' : "6" }
        myCal = {}
        
        for myItem in uzsu_dict['list']:
            # First run get all the start times
            myDays = myItem['rrule'].split(';')[1].split("=")[1].split(",")
            if myItem['value'] == '10' and myItem['active'] == True:
                if "sun" in myItem['time']:
                    if not 'calculated' in myItem:
                        continue
                    else:
                        myItem['time']=myItem['calculated']
                myKey = "8-"+myItem['time']
                if not myKey in myCal:
                    myCal[myKey] = {'Days':'', 'Start':'','End':'','Key':'','Color' : '#0AFF0A'}
                    start_hour = float(myItem['time'].split(':')[0])
                    myCal[myKey]['Start']=str("%02d" % start_hour)+':'+myItem['time'].split(':')[1]
                    calDays =""
                else:
                    calDays = myCal[myKey]['Days']
    
                for day in myDays:
                    calDays += ","+ weekDays[day]
                if calDays[0:1] == ",":
                    calDays = calDays[1:]
                myCal[myKey]['Days'] = calDays
            # Second run get all the stop times
        for myItem in uzsu_dict['list']:
            myDays = myItem['rrule'].split(';')[1].split("=")[1].split(",")
            if myItem['value'] == '20' and myItem['active'] == True:
                if "sun" in myItem['time']:
                    if not 'calculated' in myItem:
                        continue
                    else:
                        myItem['time']=myItem['calculated']
                for myCalEntry in myCal:
                    for day in myDays:
                        if weekDays[day] in myCal[myCalEntry]['Days']:
                            myCal[myCalEntry]['End'] = myItem['time']
                            myCal[myCalEntry]['Key'] = myCalEntry+'-'+ myItem['time']
        # finally build the calendar
        final_Calender = {}
        for myCalEntry in myCal:
            if myCal[myCalEntry]['End'] == "":
                start_hour = myCal[myCalEntry]['Start'].split(':')[0]
                stop_hour = float(start_hour)+4
                if stop_hour > 23:
                    stop_hour = 23
                    
                myCal[myCalEntry]['Color']='#FFA985'    
                myCal[myCalEntry]['End']=str("%02d" % stop_hour)+':'+myCal[myCalEntry]['Start'].split(':')[1]
                myCal[myCalEntry]['Key']='8-'+myCal[myCalEntry]['Start']+'-'+myCal[myCalEntry]['End']
            final_Calender[myCal[myCalEntry]['Key']]=myCal[myCalEntry]
        if len(final_Calender) > 0:
            final_Calender['Params']={'CalCount': [8]}
        else:
            final_Calender['Params']={'CalCount': [8]}
        return final_Calender
    
    
    
    def _parse_cal_2_list(self, myCal = None, type=None):
        myList = {}
        myList['Params']={}
        myCalList = []
        for cal_item in myCal['cals']:
            myCalendarNo = cal_item['cal']
            if not(myCalendarNo in myCalList):
                myCalList.append(int(myCalendarNo))
            for days in cal_item['days']:
                myDay = days['day']
                for slots in days['slots']:
                    #for slot in slots:
                    myEnabled = slots['En']
                    if (myEnabled):
                        try:
                            myStartTime1 = str('%0.2d' %slots['StHr'])+':'+str('%0.2d' %slots['StMin'])
                        except Exception as err:
    
                            myStartTime1 = '00:00'
                        try:
                            myEndTime1 = str('%0.2d' %slots['EnHr'])+':'+str('%0.2d' %slots['EnMin'])
                        except:
                            myEndTime1 = '00:00'
                        myKey = str(myCalendarNo)+'-'+myStartTime1+'-'+myEndTime1
                        myDict = {
                                    'Key':myKey,
                                    'Start' : myStartTime1,
                                    'End'   : myEndTime1,
                                    'Days'  : str(myDay)
                                 }
                        #pydevd.settrace("192.168.178.37", port=5678)
                        if 'Attr' in slots:
                            if slots['Attr'] == "C":    # manual Exclusion Time
                                mycolour = '#DC143C'
                            elif slots['Attr'] == "p":  # Rain
                                mycolour = '#BEBEBE'
                            elif slots['Attr'] == "P":  # Heavy Rain
                                mycolour = '#BEBEBE'
                            elif slots['Attr'] == "D":
                                mycolour = '#BEBEBE'    # dont know ??
                            else:
                                mycolour = '#BEBEBE'    # Heat ??
                            myDict['Color']= mycolour
                            
                        if not myKey in str(myList):
                            myList[myKey] = myDict
    
                        else:
                            if (myStartTime1 != '00:00:' and myEndTime1 != '00:00'):
                                myList[myKey]['Days'] = myList[myKey]['Days']+','+str(myDay)

        myList['Params']['CalCount'] = myCalList
        if (type == 'MOW'):
            self.calendar_count_mow = myCalList
        elif (type == 'PRED'):
            self.calendar_count_pred = myCalList
        
        return myList

    def _store_dict_2_item(self, myDict, item_name):
        newStruct = json.dumps(myDict)
        self._set_childitem(item_name, newStruct)
    
    
    def _parse_dict_2_item(self,myDict, keyEntry):
        for m in myDict:
            if type(myDict[m]) != dict:
                self._set_childitem(keyEntry+m, myDict[m])
            else:
                self._parse_dict_2_item(myDict[m],keyEntry+m+'.')
                
                
    def _get_location(self):
        url = "{}alms/{}/predictive/location".format( self.indego_url, self.alm_sn)
        try:
            location = self._get_url( url, self.context_id, 20)    
        except Exception as e:
            self.logger.warning("Problem fetching {}: {}".format(url, e))
            return false
        if location != False:
            self._set_childitem('location', location)
            if "latitude" in location:
                self._set_childitem('location.latitude', location["latitude"])
            if "longitude" in location:
                self._set_childitem('location.longitude', location["longitude"])
            if "timezone" in location:
                self._set_childitem('location.timezone', location["timezone"])
            return True
        else:
            return False 
    
    def _smart_mow_settings(self, mode =""):
        # get SmartMowSetup
        url = "{}alms/{}/predictive/setup".format( self.indego_url, self.alm_sn)
        if (mode == 'read'):
            try:
                predictiveSetup = self._get_url( url, self.context_id, 10)    
            except Exception as e:
                self.logger.warning("Problem fetching {}: {}".format(url, e))
            if predictiveSetup != False:
                self._set_childitem('smartmowsetup', predictiveSetup)
            else:       # create empty dict
                self._set_childitem('smartmowsetup',{
                                                      "full_cuts": 2,
                                                      "no_mow_calendar_days": [],
                                                      "avoid_rain": False,
                                                      "use_grass_growth": False,
                                                      "avoid_temperature": False,
                                                    })
                
            predictiveSetup = self._get_childitem('smartmowsetup')
            try:
                self._set_childitem('visu.avoid_temperature',predictiveSetup['avoid_temperature'] )
            except:
                self._set_childitem('visu.avoid_temperature',False)
            try:
                self._set_childitem('visu.avoid_rain',predictiveSetup['avoid_rain'] )
            except:
                self._set_childitem('visu.avoid_rain',False)
            try:
                self._set_childitem('visu.use_grass_growth',predictiveSetup['use_grass_growth'])
            except:
                self._set_childitem('visu.use_grass_growth',False)
            try:
                self._set_childitem('visu.full_cuts',predictiveSetup['full_cuts'] )
            except:
                self._set_childitem('visu.full_cuts',2 )
            
        if (mode == "write"):
            predictiveSetup = {   "full_cuts": 2,
                                  "no_mow_calendar_days": [],
                                  "avoid_rain": False,
                                  "use_grass_growth": False,
                                  "avoid_temperature": False,
                               }
            predictiveSetup['avoid_temperature'] = self._get_childitem('visu.avoid_temperature')
            predictiveSetup['avoid_rain'] = self._get_childitem('visu.avoid_rain')
            predictiveSetup['use_grass_growth'] = self._get_childitem('visu.use_grass_growth')
            predictiveSetup['full_cuts'] = self._get_childitem('visu.full_cuts')
            if (self._get_childitem('visu.use_exclude_time_4_sms') == True):
                predictiveSetup['no_mow_calendar_days'] = self._get_childitem('calendar_predictive')['cals'][0]['days']
            else:
                predictiveSetup['no_mow_calendar_days']=[]
            
            try:
                myResult, response = self._put_url( url, self.context_id, predictiveSetup)    
            except Exception as e:
                self.logger.warning("Problem putting {}: {}".format(url, e))
    
    
    def _get_alm_config(self):
        '''
        @GET("alms/{alm_serial}/config")")
        '''
        activeModel = self._get_childitem('visu.model_type')
        if activeModel != 2:
            return
        
        url = "{}alms/{}/config".format( self.indego_url, self.alm_sn)
        try:
            alm_config = self._get_url( url, self.context_id, 20)    
        except Exception as e:
            self.logger.warning("Problem getting {}: {}".format(url, e))
        
        if alm_config != False:
            self._set_childitem('wartung.alm_config', alm_config)
    
    def _start_manual_update(self):
        '''
        @PUT("alms/{alm_serial}/updates")
        '''
        url = '{}alms/{}/updates'.format( self.indego_url, self.alm_sn)
        myResult, response = self._put_url(url, self.context_id, None, 10)
        
           
    def _get_automatic_updates(self):
        '''
        @GET("alms/{alm_serial}/automaticUpdate")
        '''
        url = '{}alms/{}/automaticUpdate'.format( self.indego_url, self.alm_sn)
        automatic_updates = self._get_url( url, self.context_id, 20)
        if automatic_updates != False:
            self._set_childitem('wartung.update_auto', automatic_updates['allow_automatic_update'])
    
    def _reset_bladeCounter(self):
        '''
        @PUT https://api.indego.iot.bosch-si.com/api/v1/alms/{serial}
        Request:
        {
            "needs_service": false
        }
        '''
        body ={ "needs_service": False } 
        url = '{}alms/{}'.format( self.indego_url, self.alm_sn)
        myResult, response = self._put_url(url, self.context_id, body, 10)
        return myResult
        
    def _set_automatic_updates(self):
        '''
        @PUT("alms/{alm_serial}/automaticUpdate")
        '''
        body = {"allow_automatic_update": self._get_childitem('wartung.update_auto')}
        url = '{}alms/{}/automaticUpdate'.format( self.indego_url, self.alm_sn)
        myResult, response = self._put_url(url, self.context_id, body, 10)
        
        
    def _check_update(self):
        '''
        @GET("alms/{alm_serial}/updates")
        '''
        url = "{}alms/{}/updates".format( self.indego_url, self.alm_sn)
        try:
            available_updates = self._get_url( url, self.context_id, 20)    
        except Exception as e:
            self.logger.warning("Problem getting {}: {}".format(url, e))
        if available_updates != False:
            if (available_updates['available']) == True:
                self._set_childitem('wartung.update','JA')
            else:
                self._set_childitem('wartung.update','NEIN')
                
                
    def _get_operating_data(self):
        '''
        @GET("alms/{alm_serial}/operatingData")
        '''
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return
            
        url = "{}alms/{}/operatingData".format( self.indego_url, self.alm_sn)
        try:
            operating_data = self._get_url( url, self.context_id, 20)    
        except Exception as e:
            self.logger.warning("Problem getting {}: {}".format(url, e))
        if operating_data != False:
            self._parse_dict_2_item(operating_data,'operatingInfo.')
        # Set Visu-Items
        activeModel = self._get_childitem('visu.model_type')
        if (activeModel == 1):      # the big ones
            try:
                myBatteryVoltage = self._get_childitem('operatingInfo.battery.voltage')
                if myBatteryVoltage > 35.0:
                    myBatteryVoltage = 35.0
                myVoltage = myBatteryVoltage - 30.0
                myLoad_percent = myVoltage/5.0 * 100.0
                self._set_childitem('visu.battery_load', myLoad_percent)
                myLoad_icon = myVoltage/5.0*255.0
                self._set_childitem('visu.battery_load_icon', myLoad_icon)
            except err as Exception:
                self.logger.warning("Problem to calculate Battery load")
        elif (activeModel == 2):    # the small ones
            try:
                myLoad_percent = self._get_childitem('operatingInfo.battery.percent')
                self._set_childitem('visu.battery_load', myLoad_percent)
                myLoad_icon = myLoad_percent/100.0*255.0
                self._set_childitem('visu.battery_load_icon', myLoad_icon)
            except err as Exception:
                self.logger.warning("Problem to calculate Battery load")
        else:
            pass
    

        
        # Get Network-Info - only for the 350/400er
        myType = self._get_childitem('visu.model_type')
        if (myType == 2):
            url = "{}alms/{}/network".format( self.indego_url, self.alm_sn)
            try:
                network_data = self._get_url( url, self.context_id, 20)    
            except Exception as e:
                self.logger.warning("Problem fetching {}: {}".format(url, e))
            if network_data != False:
                try:
                    self._parse_dict_2_item(network_data,'network.')
                except err as Exception:
                    self.logger.warning("Problem parsing Network-Info : {}".format(err))
            
            myMcc = self._get_childitem('network.mcc')
            myMnc = self._get_childitem('network.mnc')
            try:
                actProvider = self.providers[str(myMcc)+str('%0.2d' %myMnc)]
            except:
                actProvider = 'unknown('+str(myMcc)+str('%0.2d' %myMnc)+')'
                self.providers[str(myMcc)+str('%0.2d' %myMnc)] = str(myMcc)+str('%0.2d' %myMnc)+'unknown'
                self._store_dict_2_item(self.providers,'providers')
                
            self._set_childitem('visu.network.act_provider', actProvider)
            ProviderLst = self._get_childitem('network.networks')
            myLst = ""
            for entry in ProviderLst:
                try:
                    myLst += self.providers[str(entry)]+', '
                except:
                    myLst += entry + ' - unknown'+', '
            self._set_childitem('visu.network.available_provider', myLst[0:-2])
             
                           
    
    def _get_next_time(self):
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return        
        # get the next mowing time
        url = "{}alms/{}/predictive/nextcutting?last=YYYY-MM-DD-HH:MM:SS%2BHH:MM".format( self.indego_url, self.alm_sn)

        try:
            next_time = self._get_url( url, self.context_id, 10)
        except Exception as e:
            next_time = False
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))        
        if next_time == False:
            self._set_childitem('next_time','nicht geplant')
            self.logger.info("Got next-time - nothing scheduled")
        else:
            try:
                
                self.logger.debug("Next time raw : {}".format(json.dumps(next_time))) # net_time was here
                new_time = next_time['mow_next']
                new_time = new_time.replace(':', '')
                    
                time_text  = new_time[8:10] + '.'
                time_text += new_time[5:7] + '.'
                time_text += new_time[0:4] + ' - '
                time_text += new_time[11:13] + ':'
                time_text += new_time[13:15]
                next_time = str(time_text)

                self.logger.debug("Next time final : {}".format(next_time))
                self._set_childitem('next_time',next_time)
            except Exception as e:
                self._set_childitem('next_time','kein Mähen geplant')
                self.logger.warning("Problem to decode {0} in function get_next_time(): {1}".format(next_time, e))
                
        # get the last mowing time
        url = "{}alms/{}/predictive/lastcutting".format( self.indego_url, self.alm_sn)
        try:
            last_time = self._get_url( url, self.context_id, 10)
        except Exception as e:
            last_time = False
            self.logger.warning("Problem fetching {0}: {1}".format(url, e))        
        if last_time == False:
            self._set_childitem('last_time','kein letztes Mähen bekannt')
            self.logger.info("Got last-time - nothing stored")
        else:
            try:
                
                self.logger.debug("Last time raw : {}".format(json.dumps(last_time))) # net_time was here
                new_time = last_time['last_mowed']
                new_time = new_time.replace(':', '')
                    
                time_text  = new_time[8:10] + '.'
                time_text += new_time[5:7] + '.'
                time_text += new_time[0:4] + ' - '
                time_text += new_time[11:13] + ':'
                time_text += new_time[13:15]
                last_time = str(time_text)

                self.logger.debug("Next time final : {}".format(next_time))
                self._set_childitem('last_time',last_time)
            except Exception as e:
                self._set_childitem('last_time','kein letztes Mähen bekannt')
                self.logger.warning("Problem to decode {0} in function get_next_time(): {1}".format(next_time, e))

                
    def _get_weather(self):
        if self.logged_in == False:
            return
        try:
            weather = self._get_url(self.indego_url +'alms/'+ self.alm_sn +'/predictive/weather',self.context_id,10)
        except err as Exception:
            return 
        if weather == False:
            return
        myDummy = self._get_childitem("weather_pics")
        lastDay = -1
        tn = 100.0
        tx =-100.0
        
        myPictures = json.loads(myDummy)
        for i in weather['LocationWeather']['forecast']['intervals']:
            position = str(weather['LocationWeather']['forecast']['intervals'].index(i))
            self.logger.debug("POSITION :".format(position))
            for x in i:
                wertpunkt = x
                wert = str(i[x])
                self.logger.debug('ITEM indego.weather.int_{} - Wert {}:'.format(position,wertpunkt))
                if wertpunkt == 'dateTime':
                    self.logger.debug("DATE__TIME :{}".format(wert))
                    wert= datetime.strptime(wert,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=self.shtime.tzinfo())
                if wertpunkt == 'wwsymbol_mg2008':
                    try:
                        self._set_childitem('weather.int_'+position+'.'+'picture',self.path_2_weather_pics+myPictures[wert])
                    except:
                        # got known Weather-Symbol
                        self.logger.warning("Got unknown Value for Weather-Pic, Value: {}".format(str(wert)))
                        self._set_childitem('weather.int_'+position+'.'+'picture',self.path_2_weather_pics+'na.png')
                    self.logger.debug("WERTPUNKT : {}".format(wertpunkt))
                self._set_childitem('weather.int_'+position+'.'+wertpunkt,wert)
                ######### New Weather #############
                position_day = str(int(int(position)/4)) # four entries per day
                if (int(position_day) != lastDay):
                    lastDay = int(position_day)
                    tx=-100.0
                    tn= 100.0
                
                if (wertpunkt == 'tt'):                
                    if (float(wert) > tx):
                        myItemName = 'weather.day_'+position_day+'.tx' # highest Temp
                        self._set_childitem(myItemName, float(wert))
                        tx = float(wert)
                    if (float(wert) < tn):
                        myItemName = 'weather.day_'+position_day+'.tn' # lowest Temp
                        self._set_childitem(myItemName, float(wert))
                        tn = float(wert)
                
                if (wertpunkt == 'dateTime'):                
                    myItemName = 'weather.day_'+position_day+'.wochentag' # Weekday
                    wert = str(i[x])
                    wert_day = datetime.strptime(wert[:10],'%Y-%m-%d').replace(tzinfo=self.shtime.tzinfo())
                    days = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
                    dayNumber = wert_day.weekday()
                    wochentag = days[dayNumber]
                    self._set_childitem('weather.day_'+position_day+'.'+'wochentag',wochentag)
                    
                ######### New Weather #############

    
    def alert(self):
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return
        alert_response = self._get_url(self.indego_url + 'alerts', self.context_id, 10)
        if alert_response == False:
            self.logger.debug("No Alert or error")
            self.alert_reset = False
        else:
            if len(alert_response) == 0:
                self.logger.debug("No new Alert Messages")

            else:
                actAlerts = self._get_childitem('visu.alerts')
                #pydevd.settrace("192.168.178.37", port=5678)
                for myAlert in alert_response:
                    if not (myAlert['alert_id'] in actAlerts):
                        # add new alert to dict
                        self.logger.debug("Got new Alarm : {} - {} ".format(myAlert['alert_id'], myAlert['message']))
                        myAlert['message'].replace(' Bitte folgen Sie den Anweisungen im Display des Mähers.', '')
                        actAlerts[myAlert['alert_id']]=myAlert
                        self._set_childitem('visu.alert_new', True)
                        self._check_alarm_triggers(myAlert['message']+' '+myAlert['headline'])
                
                self._set_childitem('visu.alerts', actAlerts)


    def _device_data(self):
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return        
        
        # Get Location
        if self.logged_in == True:
            self._get_location()
        # CheckUpdates
        if self.logged_in == True:        
            self._check_update()
        # Get ALM-Config
        if self.logged_in == True:        
            self._get_alm_config()
        # Get Auto-Updates enabled
        if self.logged_in == True:        
            self._get_automatic_updates()
        
        if self.logged_in == False:
            return
        
        self.logger.debug('getting device_date')
        device_data_response = self._get_url(self.indego_url + 'alms/' + self.alm_sn, self.context_id)
        if device_data_response == False:
            self.logger.error('Device Data disconnected')
        else:
            self.logger.debug('device date JSON: {} '.format(json.dumps(device_data_response)))

            alm_sn = device_data_response['alm_sn']
            self._set_childitem('alm_sn',alm_sn)
            self.logger.debug("alm_sn :".format(alm_sn))

            if 'alm_name' in device_data_response:
                alm_name = device_data_response['alm_name']
                self._set_childitem('alm_name',alm_name)
                self.logger.debug("alm_name " + str(alm_name))

            service_counter = device_data_response['service_counter']
            self._set_childitem('service_counter',service_counter)
            self.logger.debug("service_counter :".format(service_counter))
            service_counter = self._daystring(service_counter, 'min')
            self._set_childitem('service_counter.dhm',service_counter)

            needs_service = device_data_response['needs_service']
            self._set_childitem('needs_service',needs_service)
            self.logger.debug("needs_service : {}".format(needs_service))

            alm_mode = device_data_response['alm_mode']
            self._set_childitem('alm_mode',alm_mode)
            if alm_mode == 'smart':
                self._set_childitem('SMART', True)
            else:
                self._set_childitem('SMART', False)
                
            if alm_mode == 'smart':
                self._set_childitem('alm_mode.str','Übersicht SmartMow mähen:')
            elif alm_mode == 'calendar':
                self._set_childitem('alm_mode.str','Übersicht Kalender mähen:')
            elif alm_mode == 'manual' and self._get_childitem('active_mode.uzsu.schaltuhr.active')== False:
                self._set_childitem('alm_mode.str','')
            elif alm_mode == 'manual' and self._get_childitem('active_mode.uzsu.schaltuhr.active')== True:
                self._set_childitem('alm_mode.str','Übersicht mähen nach UZSU:')
            else:
                self._set_childitem('alm_mode.str','unbekannt')
            self.logger.debug("alm_mode " + str(alm_mode))

            bareToolnumber = device_data_response['bareToolnumber']
            # Detect Modell
            myModells = self.mowertype
            try:
                myModell = myModells[bareToolnumber].split(',')[0]
                myModellType = int(myModells[bareToolnumber].split(',')[1])
            except:
                myModell = "unknown Modell ("+bareToolnumber+")"
                myModellType = 0
                self.mowertype[bareToolnumber]="unknown"
                self._store_dict_2_item(self.mowertype,'mowertype')
            self._set_childitem('visu.model', 'Indego '+myModell)
            self._set_childitem('visu.model_type', myModellType)
            
            self._set_childitem('bareToolnumber',bareToolnumber)
            self.logger.debug("bareToolnumber " + str(bareToolnumber))

            if 'alm_firmware_version' in device_data_response:
                alm_firmware_version = device_data_response['alm_firmware_version']
                if alm_firmware_version != self.get_sh().indego.alm_firmware_version():
                    self._set_childitem('alm_firmware_version.before',self.get_sh().indego.alm_firmware_version())
                    self._set_childitem('alm_firmware_version.changed', self.shtime.now() )
                    self.logger.info("indego updated firmware from {0} to {1}".format(self.get_sh().indego.alm_firmware_version(), str(alm_firmware_version)))

                    self._set_childitem('alm_firmware_version',alm_firmware_version)
                self.logger.debug("alm_firmware_version : {}".format(str(alm_firmware_version)))
    
    
    def _check_state_triggers(self, myStatecode):
        myStatecode = str('%0.5d' %int(myStatecode))
        counter = 1
        while counter <=4:
            myItemName="trigger.state_trigger_" + str(counter) + ".state"
            myTrigger = self._get_childitem(myItemName).split("-")[0]
            if myStatecode == myTrigger:
                myTriggerItem="trigger.state_trigger_"+ str(counter)
                self._set_childitem(myTriggerItem, True)
            counter += 1


    def _check_alarm_triggers(self, myAlarm):
            counter = 1
            #pydevd.settrace("192.168.178.37", port=5678)
            while counter <=4:
                myItemName="trigger.alarm_trigger_" + str(counter) + ".alarm"
                myAlarmTrigger = self._get_childitem(myItemName)
                if myAlarmTrigger.lower() !='' and myAlarmTrigger.lower() in myAlarm.lower() :
                    myTriggerItem="trigger.alarm_trigger_"+ str(counter)
                    self._set_childitem(myTriggerItem, True)
                counter += 1        
    
    def _get_state(self):
        if (self._get_childitem("wartung.wintermodus") == True or self.logged_in == False):
            return
        #pydevd.settrace("192.168.178.37", port=5678)

        if (self.position_detection):
            self.position_count += 1
        state_response = self._get_url(self.indego_url + 'alms/' + self.alm_sn + '/state', self.context_id)
        states = state_response
        if state_response != False:
            self._set_childitem('online', True)
            self.logger.debug("indego state received :{}".format(str(state_response)))


            if 'error' in states:
                error_code = states['error']
                self._set_childitem('stateError',error_code)
                self.logger.error("error_code : {]".format(str(error_code)))
            else:
                error_code = 0
                self._set_childitem('stateError',error_code)
            #pydevd.settrace("192.168.178.37", port=5678)
            state_code = states['state']
            try:
                if not str(state_code) in str(self.states) and len(self.states) > 0:
                    # got new unknown State-Code
                    self.states[state_code]=[str(state_code)+" unknown","unknown"]
                    # Store to Item 
                    self._store_dict_2_item(self.states,'states_str')
                   
                        
            except err as Exception:
                self.logger.warning("Error while adding new State-Code : {}".format(err))
                pass
            self._set_childitem('stateCode',state_code)
            myLastStateCode = self._get_childitem('webif.laststateCode')
            
            # Loggin the states in Timeline for the Web-Interface
            if state_code != myLastStateCode:
                self._set_childitem('webif.laststateCode', state_code)
                # Add to self rotating Array
                myLog = self._get_childitem('webif.state_protocoll')
                try:
                    if len (myLog) >= 500:
                        myLog = myLog[0:499]
                except:
                    pass
                now = self.shtime.now()
                logLine =str(now)[0:19]+'  State : '+str(state_code) + ' State-Message : ' + self.states[state_code][0]
                myLog.insert(0,logLine)
                self._set_childitem('webif.state_protocoll', myLog)
                self._check_state_triggers(state_code)
                
            self.logger.debug("state code :".format(str(state_code)))
            if self.states[state_code][1] == 'dock':
                self.logger.debug('indego docked')
                self.alert_reset = True
                self._set_childitem('docked', True)
                self._set_childitem('moving', False)
                self._set_childitem('pause', False)
                self._set_childitem('help', False)
            if self.states[state_code][1] == 'moving':
                self.logger.debug('indego moving')
                self.alert_reset = True
                self._set_childitem('mowedDate', self.shtime.now())
                self._set_childitem('docked', False)
                self._set_childitem('moving', True)
                self._set_childitem('pause', False)
                self._set_childitem('help', False)
            if self.states[state_code][1] == 'pause':
                self.logger.debug('indego pause')
                self.alert_reset = True
                self._set_childitem('docked', False)
                self._set_childitem('moving', False)
                self._set_childitem('pause', True)
                self._set_childitem('help', False)
            if self.states[state_code][1] == 'hilfe':
                self.logger.debug('indego hilfe')
                self._set_childitem('docked', False)
                self._set_childitem('moving', False)
                self._set_childitem('pause', False)
                self._set_childitem('help', True)
                if self.alert_reset == True:
                    self.logger.debug("Alert aufgefrufen, self_alert_reset = True")
                    self.alert()
                else:
                    self.logger.debug("Alert nicht aufgefrufen, self_alert_reset = False")

            state_str = self.states[state_code][0]
            self._set_childitem('state_str', state_str )
            self.logger.debug("state str : {}".format(state_str))

            mowed = states['mowed']
            self._set_childitem('mowedPercent', mowed)
            self.logger.debug("mowed " + str(mowed))
            
            myLast_percent_mowed = self._get_childitem('visu.mow_track.last_percent_mowed')
            if (mowed == 0.0 and myLast_percent_mowed > 0.0):
                # New mow-Cycle startet
                self._set_childitem("visu.mow_track", [])
                #################################
            if state_code == 518 or state_code == 513 or state_code ==515 or state_code == 514 :    # 518 = mähe / 513 = schneide Rand / 515 = lade Karte / 514 = mähen, bestimme Ort
                # First run of position detection
                if not self.position_detection:
                    # Now set Position-Detection ON
                    myResult = self._post_url(self.indego_url + 'alms/' + self.alm_sn + '/requestPosition?count=100&interval=7', self.context_id, None, 10)
                    if myResult != True:
                        pass
                    # Now set scheduler for state to 8 Sec.
                    self.scheduler_change('get_state', cycle={7:None}) # Zum Testen von 6 auf 10 Sekunden geändert
                    self.position_detection = True
                    self.position_count = 0
                # Following runs of position detection
                if  (self.position_detection and self.position_count >= 90):
                    self.position_count = 0
                    myResult = self._post_url(self.indego_url + 'alms/' + self.alm_sn + '/requestPosition?count=100&interval=7', self.context_id, None, 10)
                    if myResult != True:
                        pass

                #################################
            self._set_childitem('visu.mow_track.last_percent_mowed', mowed)

            mowmode = states['mowmode']
            self._set_childitem('mowmode',mowmode)
            self.logger.debug("mowmode  :{}".format(str(mowmode)))

            total_operate = states['runtime']['total']['operate']
            self._set_childitem('runtimeTotalOperationMins',total_operate)
            self.logger.debug("total_operate : {}".format(str(total_operate)))
            total_operate = self._daystring(total_operate, 'min')
            self._set_childitem('runtimeTotalOperationMins.dhm',total_operate)

            total_charge = states['runtime']['total']['charge']
            self._set_childitem('runtimeTotalChargeMins',total_charge)
            self.logger.debug("total_charge " + str(total_charge))
            total_charge = self._daystring(total_charge, 'min')
            self._set_childitem('runtimeTotalChargeMins.dhm',total_charge)

            session_operate = states['runtime']['session']['operate']
            self._set_childitem('runtimeSessionOperationMins',session_operate)
            self.logger.debug("session_operate : {}".format(str(session_operate)))

            session_charge = states['runtime']['session']['charge']
            self._set_childitem('runtimeSessionChargeMins',session_charge)
            self.logger.debug("session_charge " + str(session_charge))

            if 'xPos' in states:
                xPos = states['xPos']
                self._set_childitem('xPos',xPos)
                self.logger.debug("xPos :{}".format(str(xPos)))

                yPos = states['yPos']
                self._set_childitem('yPos',yPos)
                self.logger.debug("yPos : {}".format(str(yPos)))

                svg_xPos = states['svg_xPos']
                self._set_childitem('svg_xPos',svg_xPos)
                self.logger.debug("svg_xPos :{}".format(str(svg_xPos)))

                svg_yPos = states['svg_yPos']
                self._set_childitem('svg_yPos',svg_yPos)
                self.logger.debug("svg_yPos :{}".format(str(svg_yPos)))
                
                # SVG-Position
                mySvgPos = self._get_childitem("visu.mow_track")
                newPos = str(svg_xPos)+","+str(svg_yPos)
                self._set_childitem('visu.svg_pos', 'svg_pos|'+newPos)
                if (len(mySvgPos) == 0):
                    mySvgPos.append(newPos)
                    self._set_childitem("visu.mow_track", mySvgPos)
                else:
                    if (newPos != mySvgPos[len(mySvgPos)-1]):
                        mySvgPos.append(newPos)
                        self._set_childitem("visu.mow_track", mySvgPos)

            map_update = states['map_update_available']
            self.logger.debug("map_update " + str(map_update))
            self._set_childitem('mapUpdateAvailable',map_update)

            if map_update:
                self._load_map()
                        
            # Postion-Detection during mowing
            self._check_state_4_protocoll()

    def _load_map(self):
        self.logger.debug('lade neue Karte')
        garden = self._get_url(self.indego_url + 'alms/' + self.alm_sn + '/map?cached=0&showMower=1', self.context_id, 120)
        if garden == False:
            self.logger.warning('Map returned false')
        else:
            with open(self.img_pfad, 'wb') as outfile:
                outfile.write(garden)
            self.logger.debug('You have a new MAP')
            self._set_childitem('mapSvgCacheDate',self.shtime.now())
            self._set_childitem('webif.garden_map', garden.decode("utf-8"))
            #pydevd.settrace("192.168.178.37", port=5678)
            self._parse_map()
            
    def _parse_map(self):
        myMap = self._get_childitem('webif.garden_map')
        myCustomDrawing = self._get_childitem('visu.add_svg_images')
        mowerColour = self._get_childitem('visu.mower_colour')
        mowerColour = mowerColour.split(':')[1]

        mowerColour = mowerColour.replace('"','')
        #=======================================================================
        # # after here replace bs4
        #=======================================================================
        myMap = myMap.replace(">",">\n")
        mapArray = myMap.split('\n')
        #pydevd.settrace("192.168.178.37", port=5678)
        # till here new
        # Get the Mower-Position and extract it
        i= 0
        for line in mapArray:
            if '<circle' in line:
                mowerPos = line + '</circle>'
                myMowerPos = i
            if '<svg' in line:
                line = line.replace('<svg', '<svg id="svg_garden_map"')
                mapArray[i]=line
            i += 1
        # Delete the Mower-Position from the SVG
        del mapArray[myMowerPos+1]
        del mapArray[myMowerPos]
        # Change the Colour of the Mower and give an ID
        colorPos_one = mowerPos.find('fill="#')+7
        colorPos_two = mowerPos.find('"',colorPos_one)
        mowerPos = mowerPos.replace(mowerPos[colorPos_one:colorPos_two], mowerColour)
        mowerPos = mowerPos.replace('<circle', '<circle id="mower_pos"')

        # delete last Line ( closing the svg-vectors)
        mapLength = len(mapArray)-1
        del mapArray[mapLength]

        # Now add the custom paintings to the map

        if myCustomDrawing != None and myCustomDrawing != "":
            myCustomSoup = myCustomDrawing.replace(">",">\n")
            customArray = myCustomSoup.split('\n')
            for line in customArray:
                mapArray.append(line)

        # finally add the Mower-Position and close again the svg-vectors
        mapArray.append('<g id="mower_track_id"></g>')
        mapArray.append(mowerPos)
        mapArray.append('</svg>')
        value =''
        for line in mapArray:
            value += line
        value = value.replace('\n','')
        value = value.replace('\r','')
        
        self._set_childitem('visu.map_2_display', value)
            
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
from ephem import degree

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
        self.items = Items.get_instance()
        
        
    @cherrypy.expose
    def store_color_html(self, newColor = None):
        self.plugin._set_childitem('visu.mower_colour','mower_colour:"'+newColor[1:]+'"')
    
    
    @cherrypy.expose
    def store_state_trigger_html(self, Trigger_State_Item = None,newState=None):
        myItemSuffix=Trigger_State_Item
        myItem="trigger." + myItemSuffix + ".state"
        self.plugin._set_childitem(myItem,newState)    

    
    @cherrypy.expose
    def store_alarm_trigger_html(self, Trigger_Alarm_Item = None,newAlarm=None):
        #pydevd.settrace("192.168.178.37", port=5678)
        myItemSuffix=Trigger_Alarm_Item
        myItem="trigger." + myItemSuffix + ".alarm"
        self.plugin._set_childitem(myItem,newAlarm)    

    @cherrypy.expose
    def store_add_svg_html(self, add_svg_str = None):
        self.plugin._set_childitem('visu.add_svg_images',add_svg_str)


    @cherrypy.expose
    def store_credentials_html(self, encoded='', pwd = '', user= '', store_2_config=None):
        txt_Result = []
        result2send={}
        resultParams={}
        
        #pydevd.settrace("192.168.178.37", port=5678)
        myCredentials = user+':'+pwd
        byte_credentials = base64.b64encode(myCredentials.encode('utf-8'))
        encoded = byte_credentials.decode("utf-8")
        txt_Result.append("encoded:"+encoded) 
        txt_Result.append("Encoding done")
        conf_file=self.plugin.sh.get_basedir()+'/etc/plugin.yaml'
        
        if (store_2_config == 'true'):
            new_conf = ""
            with open (conf_file, 'r') as myFile:
                for line in myFile:
                    if line.find('indego_credentials') > 0:
                        line = '    indego_credentials: '+encoded+ "\r\n"
                    new_conf += line 
            myFile.close()         
            txt_Result.append("replaced credentials in temporary file")
            with open (conf_file, 'w') as myFile:
                for line in new_conf.splitlines():
                    myFile.write(line+'\r\n')
            myFile.close()
            #pydevd.settrace("192.168.178.37", port=5678)
            txt_Result.append("stored new config to filesystem")
            self.plugin.user = user
            self.plugin.password = pwd
            # Here the login-procedure
            self.plugin.login_pending = True
            self.plugin.logged_in, self.plugin._bearer, self.plugin._refresh_token, self.plugin.token_expires,self.plugin.alm_sn = self.plugin._login_single_key_id(self.plugin.user, self.plugin.password)
            self.plugin.login_pending = False
            
            if self.plugin.logged_in:
                txt_Result.append("logged in succesfully")
            else:
                txt_Result.append("login failed")
            myExperitation_Time = datetime.fromtimestamp(self.plugin.expiration_timestamp).strftime('%Y-%m-%d %H:%M:%S')
            myLastLogin = datetime.fromtimestamp(float(self.plugin.last_login_timestamp)).strftime('%Y-%m-%d %H:%M:%S')
            resultParams['logged_in']= self.plugin.logged_in
            resultParams['timeStamp']= myLastLogin + " / " + myExperitation_Time
            resultParams['SessionID']= self.plugin._bearer 
            self.plugin._set_childitem('visu.refresh',True)
            txt_Result.append("refresh of Items initiated")
        
        resultParams['encoded']= encoded    
        result2send['Proto']=txt_Result
        result2send['Params']=resultParams
        return json.dumps(result2send)
    
    
    @cherrypy.expose
    def get_proto_html(self, proto_Name= None):
        if proto_Name == 'Com_log_file':
            return json.dumps(self.plugin._get_childitem('webif.communication_protocoll'))
        if proto_Name == 'state_log_file':
            return json.dumps(self.plugin._get_childitem('webif.state_protocoll'))

    @cherrypy.expose
    def clear_proto_html(self, proto_Name= None):
        #pydevd.settrace("192.168.178.37", port=5678)
        self.plugin._set_childitem(proto_Name,[])
        return None
    
    @cherrypy.expose
    def set_location_html(self, longitude=None, latitude=None):
        pydevd.settrace("192.168.178.37", port=5678)
        self.plugin._set_childitem('webif.location_longitude',float(longitude))
        self.plugin._set_childitem('webif.location_latitude',float(latitude))
        myLocation = {"latitude":str(latitude),"longitude":str(longitude),"timezone":"Europe/Berlin"}
        result = self.plugin._set_location(myLocation)
        if (result == True):
            myResult = "Stored location successfully"
        else:
            myResult = "could not store location"
        return myResult
    
            
    
    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered 
        """
        tmpl = self.tplenv.get_template('index.html')
        
        item_count = 0
        plgitems = []
        for item in self.items.return_items():
            if ('indego' in item.property.name):
                plgitems.append(item)
                item_count += 1
                
        try:
            my_state_loglines = self.plugin._get_childitem('webif.state_protocoll')
            state_log_file = ''
            for line in my_state_loglines:
                state_log_file += str(line)+'\n'
        except:
            state_log_file = 'No Data available right now\n'
        
        try:
            my_com_loglines = self.plugin._get_childitem('webif.communication_protocoll')
            com_log_file = ''
            for line in my_com_loglines:
                com_log_file += str(line)+'\n'
        except:
            state_log_file = 'No Data available right now\n'
            
        # get the login-times
        myExperitation_Time = datetime.fromtimestamp(self.plugin.expiration_timestamp).strftime('%Y-%m-%d %H:%M:%S')
        myLastLogin = datetime.fromtimestamp(float(self.plugin.last_login_timestamp)).strftime('%Y-%m-%d %H:%M:%S')
        # get the mower-colour
        myColour = '#'+self.plugin._get_childitem('visu.mower_colour')[14:-1]
        # get all the available states
        selectStates = []
        try:
            myStates = self.plugin.states
            for state in myStates:
                newEntry={}
                newEntry['ID']=str('%0.5d' %int(state))
                newEntry['Caption']=myStates[state][0]
                selectStates.append(newEntry)
            # add empty Entry
            newEntry={}
            newEntry['ID']='99999'
            newEntry['Caption']="kein State-Trigger"
            selectStates.append(newEntry)
        except:
            pass
        
        try:
            # get the actual triggers
            Trigger_1_state=self.plugin._get_childitem('trigger.state_trigger_1.state')
            Trigger_2_state=self.plugin._get_childitem('trigger.state_trigger_2.state')
            Trigger_3_state=self.plugin._get_childitem('trigger.state_trigger_3.state')
            Trigger_4_state=self.plugin._get_childitem('trigger.state_trigger_4.state')
            
            Alarm_Trigger_1=self.plugin._get_childitem('trigger.alarm_trigger_1.alarm')
            Alarm_Trigger_2=self.plugin._get_childitem('trigger.alarm_trigger_2.alarm')
            Alarm_Trigger_3=self.plugin._get_childitem('trigger.alarm_trigger_3.alarm')
            Alarm_Trigger_4=self.plugin._get_childitem('trigger.alarm_trigger_4.alarm')
        except:
            pass
        myLongitude = ""
        myLatitude = ""
        myText = ""
        try:
            #pydevd.settrace("192.168.178.37", port=5678)
            myLongitude = self.plugin._get_childitem('webif.location_longitude')
            myLatitude = self.plugin._get_childitem('webif.location_latitude')
            myText = 'Location from Indego-Server'
            if (myLongitude == 0.0):
                myLongitude = self.plugin.sh.sun._obs.long / degree
                myLatitude =  self.plugin.sh.sun._obs.lat  / degree
                myText = 'Location from shNG-Settings'
        except:
            pass
        
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           item_count=item_count,
                           state_log_lines=state_log_file,
                           com_log_lines=com_log_file,
                           myExperitation_Time=myExperitation_Time,
                           myLastLogin=myLastLogin,
                           myColour=myColour,
                           myMap=self.plugin._get_childitem('webif.garden_map'),
                           txt_add_svg=self.plugin._get_childitem('visu.add_svg_images'),
                           selectStates=sorted(selectStates, key=lambda k: str.lower(k['ID'])),
                           Trigger_1_state=Trigger_1_state,
                           Trigger_2_state=Trigger_2_state,
                           Trigger_3_state=Trigger_3_state,
                           Trigger_4_state=Trigger_4_state,
                           Alarm_Trigger_1=Alarm_Trigger_1,
                           Alarm_Trigger_2=Alarm_Trigger_2,
                           Alarm_Trigger_3=Alarm_Trigger_3,
                           Alarm_Trigger_4=Alarm_Trigger_4,
                           myLongitude=myLongitude,
                           myLatitude=myLatitude,
                           myText=myText )


