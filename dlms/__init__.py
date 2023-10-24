#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 - 2021 Bernd Meiners              Bernd.Meiners@mail.de
#########################################################################
#
#  DLMS plugin for SmartHomeNG
#
#  This file is part of SmartHomeNG
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import sys
import logging
import datetime

from lib.module import Modules
from lib.model.smartplugin import *
from lib.utils import Utils
from lib.shtime import Shtime
shtime = Shtime.get_instance()

import time
import re
from threading import Semaphore

try:
    import serial
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False

from . import dlms
from . import conversion


class DLMS(SmartPlugin, conversion.Conversion):
    """
    This class provides a Plugin for SmarthomeNG to reads out a smartmeter.
    The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB
    It is possible to use dlms.py standalone to test the results 
    prior to use it in SmarthomeNG
    
    The tag 'dlms_obis_code' identifies the items which are to be updated from the plugin,
    the tag ``dlms_obis_readout`` will receive the last readout from smartmeter
    """

    PLUGIN_VERSION = "1.9.5"

    # tags this plugin handles
    DLMS_OBIS_CODE = 'dlms_obis_code'       # a single code in form of '1-1:1.8.1'
    DLMS_OBIS_READOUT = 'dlms_obis_readout' # complete readout from smartmeter, if you want to examine codes yourself in a logic
    
    ITEM_TAG = [DLMS_OBIS_CODE,DLMS_OBIS_READOUT]


    def __init__(self, sh, *args, **kwargs ):
        """
        Initializes the DLMS plugin
        The parameters are retrieved from get_parameter_value(parameter_name)
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug(f"init {__name__}")
        self._init_complete = False

        # Exit if the required package(s) could not be imported
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error(f"{self.get_fullname()}: Unable to import Python package 'pyserial'")
            return

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._instance = self.get_parameter_value('instance')               # the instance of the plugin for questioning multiple smartmeter
        self._update_cycle  = self.get_parameter_value('update_cycle')      # the frequency in seconds how often the device should be accessed
        if self._update_cycle == 0:
            self._update_cycle = None
        self._update_crontab  = self.get_parameter_value('update_crontab')  # the more complex way to specify the device query frequency
        if self._update_crontab == '':
            self._update_crontab = None
        if not (self._update_cycle or self._update_crontab):
            self.logger.error(f"{self.get_fullname()}: no update cycle or crontab set. The smartmeter will not be queried automatically")
        self._sema = Semaphore()            # implement a semaphore to avoid multiple calls of the query function
        self._min_cycle_time = 0            # we measure the time for the value query and add some security value of 10 seconds
                                            
        self.dlms_obis_code_items = []      # this is a list of items to be updated
        self.dlms_obis_codes = []           # this is a list of codes that are to be parsed
                                            
        self.dlms_obis_readout_items = []   # this is a list of items that receive the full readout
        self._last_readout = ""
        
        # dict especially for the interface
        # 'serialport', 'device', 'querycode', 'speed', 'baudrate_fix', 'timeout', 'onlylisten', 'use_checksum'
        self._config = {}
        self._config['serialport'] = self.get_parameter_value('serialport')
        if not self._config['serialport']:
            return

        # there is a possibility of using a named device
        # normally this will be empty since only one meter will be attached
        # to one serial interface but the standard allows for it and we honor that.
        self._config['device'] = self.get_parameter_value('device_address')
        self._config['querycode'] = self.get_parameter_value('querycode')
        self._config['timeout'] = self.get_parameter_value('timeout')
        self._config['baudrate'] = self.get_parameter_value('baudrate')
        self._config['baudrate_fix'] = self.get_parameter_value('baudrate_fix')
        self._config['use_checksum'] = self.get_parameter_value('use_checksum')
        self._config['onlylisten'] = self.get_parameter_value('only_listen')
        self._config['reset_baudrate'] = self.get_parameter_value('reset_baudrate')
        self._config['no_waiting'] = self.get_parameter_value('no_waiting')

        self.logger.debug(f"Instance {self._instance if self._instance else 0} of DLMS configured to use serialport '{self._config.get('serialport')}' with update cycle of {self._update_cycle} seconds")
        self.logger.debug(f"Config: {self._config}")
        self.init_webinterface()

        self.logger.debug("init done")
        self._init_complete = True

    def run(self):
        """
        This is called when the plugins thread is about to run
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        self.alive = True
        if self._update_cycle or self._update_crontab:
            self.scheduler_add(self.get_shortname(), self._update_values_callback, prio=5, cycle=self._update_cycle, cron=self._update_crontab, next=shtime.now())
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method finished")

    def stop(self):
        """
        This is called when the plugins thread is about to stop
        """
        self.alive = False
        self.scheduler_remove(self.get_shortname())
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        :param item: The item to process.
        """

        if self.has_iattr(item.conf, self.DLMS_OBIS_CODE):
            self.dlms_obis_code_items.append(item)
            self.logger.debug(f"Item '{item}' has Attribute '{self.DLMS_OBIS_CODE}' so it is added to the list of items "
                              "to receive OBIS Code Values")
            obis_code = self.get_iattr_value(item.conf, self.DLMS_OBIS_CODE)
            if isinstance(obis_code, list):
                obis_code = obis_code[0]
            self.dlms_obis_codes.append( obis_code )
            self.logger.debug(f"The OBIS Code '{obis_code}' is added to the list of codes to inspect")
        elif self.has_iattr(item.conf, self.DLMS_OBIS_READOUT):
            self.dlms_obis_readout_items.append(item)
            self.logger.debug(f"Item '{item}' has Attribute '{self.DLMS_OBIS_READOUT}' so it is added to the list of items "
                              "to receive full OBIS Code readout")

    def init_webinterface(self):
        """
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error(f"Plugin '{self.get_shortname()}': Not initializing the web interface")
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning(f"Plugin '{self.get_shortname()}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
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

    def _update_values_callback(self):
        """
        This function aquires a semphore, queries the serial interface and upon successful data readout
        it calls the update function
        If it is not possible it passes on, issuing a warning about increasing the query interval
        """
        if self._sema.acquire(blocking=False):
            try:
                result = dlms.query(self._config)
                if result is None:
                    self.logger.error( "no results from smartmeter query received" )
                elif len(result) <= 5:
                    self.logger.error( "results from smartmeter query received but is smaller than 5 characters" )
                else:
                    self._update_values( result )
            except Exception as e:
                    self.logger.debug(f"Exception '{e}' occurred, please inform plugin author!")
            finally:
                    self._sema.release()
        else:
            self.logger.warning("update is alrady running, maybe it really takes very long or you should use longer "
                                "query interval time")

    def _update_dlms_obis_readout_items(self, textblock):
        """
        Sets all items with attribute to the full readout text given in textblock
        :param textblock: the result of the latest query
        """
        self._last_readout = textblock
        for item in self.dlms_obis_readout_items:
            item(textblock, 'DLMS')


    def _is_obis_code_wanted( self, code):
        """
        this stub function detects whether code is in the list of user defined OBIS codes to scan for
        :param code:
        :return: returns true if code is in user defined OBIS codes to scan for
        """
        if code in self.dlms_obis_codes:
            #self.logger.debug(f"Wanted OBIS Code found: '{code}'")
            return True
        #self.logger.debug(f"OBIS Code '{code}' is not interesting...")
        return False


    def _update_items( self, Code, Values):
        """
        this function takes the OBIS Code as text and accepts a list of dictionaries with Values
        :param Code: OBIS Code
        :param Values: list of dictionaries with Value / Unit entries
        """
        for item in self.dlms_obis_code_items:
            if self.has_iattr(item.conf, self.DLMS_OBIS_CODE):
                attribute = self.get_iattr_value(item.conf, self.DLMS_OBIS_CODE)
                if not isinstance(attribute, list):
                    self.logger.warning(f"Attribute '{attribute}' is a single argument, not a list")
                    attribute = [attribute]
                obis_code = attribute[0]
                if obis_code == Code:
                    try:
                        Index = int(attribute[1]) if len(attribute)>1 else 0
                        if Index < 0:
                            self.logger.warning(f"Index '{attribute[1]}' is negative, please provide a positive index or zero")    
                            Index = 0
                    except:
                        self.logger.warning(f"Index '{attribute[1]}' is not a positive integer")
                        Index = 0
                    try:
                        Key = attribute[2] if len(attribute)>2 else 'Value'
                    except:
                        pass
                    if not Key in ['Value', 'Unit']: 
                        self.logger.warning(f"Key should be either 'Value' or 'Unit' but is '{Key}', change to 'Value'")
                        Key = 'Value'
                        
                    Converter = attribute[3] if len(attribute)>3 else ''
                    try:
                        itemValue = Values[Index][Key]
                        itemValue = self._convert_value(itemValue, Converter )
                        item(itemValue, self.get_shortname())
                        self.logger.debug(f"Set item {item} for Obis Code {Code} to Value {itemValue}")
                    except IndexError as e:
                        self.logger.warning(f"Index Error '{str(e)}' while setting item {item} for Obis Code {Code} to Value "
                                            "with Index '{Index}' in '{Values}'")
                    except KeyError as e:
                        self.logger.warning(f"Key error '{str(e)}' while setting item {item} for Obis Code {Code} to "
                                            "Key '{Key}' in '{Values[Index]}'")
                    except NameError as e:
                        self.logger.warning(f"Name error '{str(e)}' while setting item {item} for Obis Code {Code} to "
                                            "Key '{Key}' in '{Values[Index]}'")

    def _split_header( self, readout, break_at_eod = True):
        """if there is an empty line at second position within readout then seperate this"""
        header = ''
        obis = []
        endofdata_count = 0
        for linecount, line in enumerate(readout.splitlines()):
            if linecount == 0 and line.startswith("/"):
                has_header = True
                header = line
                continue

            # an empty line separates the header from the codes, it must be suppressed here
            if len(line) == 0 and linecount == 1 and has_header:
                continue

            # if there is an empty line other than directly after the header
            # it is very likely that there is a faulty obis readout.
            # It might be that checksum is disabled an thus no error could be catched
            if len(line) == 0:
                self.logger.error("An empty line was encountered unexpectedly!")
                break

            # '!' as single OBIS code line means 'end of data'
            if line.startswith("!"):
                self.logger.debug("No more data available to read")
                if endofdata_count:
                    self.logger.debug("Found {endofdata_count} end of data marker '!' in readout")
                    if break_at_eod:    # omit the rest of data here
                        break
                endofdata_count +=1
            else:
                obis.append(line)
        return header, obis




    def _update_values(self, readout):
        """
        Takes the readout from smart meter with one OBIS code per line, 
        splits up the line into OBIS code itself and all values behind that will start encapsulated in parentheses

        If the OBIS code was included in one of the items attributes then the values will be parsed and assigned
        to the corresponding item.
        
        :param readout: readout from smart meter with one OBIS code per line
        :return: nothing
        """

        # update all items marked for a full readout
        self._update_dlms_obis_readout_items(readout)
        self.logger.debug(f"readout size is {len(readout)}")

        header, obis = self._split_header(readout)

        try:
            for line in obis:
                # Now check if we can split between values and OBIS code
                arguments = line.split('(')
                if len(arguments)==1:
                    # no values found at all; that seems to be a wrong OBIS code line then
                    arguments = arguments[0]
                    values = ""
                    self.logger.warning("Any line with OBIS Code should have at least one data item")
                else:
                    # ok, found some values to the right, lets isolate them
                    values = arguments[1:]
                    obis_code = arguments[0]

                    if self._is_obis_code_wanted(obis_code):
                        TempValues = values
                        values = []
                        for s in TempValues:
                            s = s.replace(')','')
                            if len(s) > 0:
                                # we now should have a list with values that may contain a number
                                # separated from a unit by a '*' or a date
                                # so see, if there is an '*' within
                                vu = s.split('*')
                                if len(vu) > 2:
                                    self.logger.error(f"Too many entries found in '{s}' of '{line}'")
                                elif len(vu) == 2:
                                    # just a value and a unit
                                    v = vu[0]
                                    u = vu[1]
                                    values.append( { 'Value': v, 'Unit': u} )
                                else:
                                    # just a value, no unit
                                    v = vu[0]
                                    values.append( { 'Value': v } )
                        # uncomment the following line to check the generation of the values dictionary
                        self.logger.debug(f"{line:40} ---> {values}")
                        try:
                            self._update_items(obis_code, values)
                        except:
                            self.logger.error(f"tried to update items for Obis Code {obis_code} to Values {values} failed with {sys.exc_info()[0]}")
            self.logger.debug("All lines inspected, no more data")
        except Exception as e:
            self.logger.debug("Exception '{e}' occurred, please inform plugin author!")


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
        return tmpl.render(p=self.plugin, i=self.plugin._instance, c=self.plugin._config, r=self.plugin._last_readout, cycle=self.plugin._update_cycle, cron=self.plugin._update_crontab, readout_items=self.plugin.dlms_obis_readout_items, code_items=self.plugin.dlms_obis_code_items )

