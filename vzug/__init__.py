#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024       Matthias Manhart             smarthome@beathis.ch
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
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

# -----------------------------------------------------------------------
#
# History
# =======
#
# V0.1.0 240303 - erster Release
#
# -----------------------------------------------------------------------
#
# Getestete Geraete:           hh/API   ai/API
# - V4000 - Waschmaschine      1.7.0    1.8.0
# - V6000 - Geschirrspuehler   1.8.0    1.8.0
#
# -----------------------------------------------------------------------
#
# Notizen
# *******
#
# - Quelle: https://github.com/mico-micic/vzug-api  (Ausgangslage)
# - Version 1.1.0 ist die alte APIVersion
#   Version 1.7.0 ist die neue APIVersion mit Abfrage mit hh?command=getProgram
#
# -----------------------------------------------------------------------

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

import urllib.request
import datetime
from zoneinfo import ZoneInfo

import asyncio
import aiohttp
import aiohttp.web
from aiohttp import client_exceptions, hdrs
import json
from yarl import URL
import hashlib
import time
import os
import re
from typing import Optional, Any, Dict
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type, before_log

# -----------------------------------------------------------------------

VERSION = '0.1.0'

# vzug_cycle = 60
vzug_cycle = 120

make_anonymous = False
# make_anonymous = True

ENDPOINT_AI = 'ai'
ENDPOINT_HH = 'hh'
QUERY_PARAM_COMMAND = 'command'
QUERY_PARAM_VALUE = 'value'
COMMAND_GET_STATUS = 'getDeviceStatus'                         # ai
COMMAND_GET_MODEL_DESC = 'getModelDescription'                 # ai
COMMAND_GET_MACHINE_TYPE = 'getMachineType'                    # hh
COMMAND_GET_PROGRAM = 'getProgram'                             # hh
COMMAND_GET_COMMAND = 'getCommand'                             # hh
COMMAND_GET_APIVERSION = 'getAPIVersion'                       # ai
COMMAND_GET_FIRMWAREVERSION = 'getFWVersion'                   # ai
COMMAND_GET_FIRMWAREAVAILABLE = 'isAIFirmwareAvailable'        # ai
COMMAND_GET_LASTPUSHNOTIFICATONS = 'getLastPUSHNotifications'  # ai
COMMAND_GET_GETECOINFO = 'getEcoInfo'                          # hh

COMMAND_VALUE_ECOM_STAT_TOTAL = 'ecomXstatXtotal'              # hh COMMAND_GET_COMMAND
COMMAND_VALUE_ECOM_STAT_AVG = 'ecomXstatXavarage'              # hh COMMAND_GET_COMMAND

CMD_VALUE_CONSUMP_DRYER_TOTAL = 'TotalXconsumptionXdrumDry'    # hh COMMAND_GET_COMMAND
CMD_VALUE_CONSUMP_DRYER_AVG = 'AverageXperXcycleXdrumDry'      # hh COMMAND_GET_COMMAND

DEVICE_TYPE_UNKNOWN = 'UNKNOWN'
DEVICE_TYPE_WASHING_MACHINE = 'WASHING_MACHINE'
DEVICE_TYPE_DRYER = 'DRYER'
DEVICE_TYPE_DISHWASHER = 'DISHWASHER'
DEVICE_TYPE_OVEN = 'OVEN'
DEVICE_TYPE_STEAMER = 'STEAMER'
DEVICE_TYPE_MICRO_STEAM = 'MICRO_STEAM'
DEVICE_TYPE_MICROWAVE = 'MICROWAVE'
DEVICE_TYPE_COFFEE_CENTER = 'COFFEE_CENTER'
DEVICE_TYPE_RANGE_HOOD = 'RANGE_HOOD'
DEVICE_TYPE_FRIDGE = 'FRIDGE'
DEVICE_TYPE_WINE_COOLER = 'WINE_COOLER'
DEVICE_TYPE_REFRESH_BUTLER = 'REFRESH_BUTLER'
DEVICE_TYPE_GLASS_CERAMIC = 'GLASS_CERAMIC'
DEVICE_TYPE_CARD_SYSTEM = 'CARD_SYSTEM '
DEVICE_TYPE_COIN_SYSTEM = 'COIN_SYSTEM'

DEVICE_TYPE_SHORT_WASHING_MACHINE = 'WA'
DEVICE_TYPE_SHORT_DRYER = 'WT'
DEVICE_TYPE_SHORT_DISHWASHER = 'GS'
DEVICE_TYPE_SHORT_OVEN = 'BO'
DEVICE_TYPE_SHORT_STEAMER = 'ST'
DEVICE_TYPE_SHORT_MICRO_STEAM = 'MS'
DEVICE_TYPE_SHORT_MICROWAVE = 'UW'
DEVICE_TYPE_SHORT_COFFEE_CENTER = 'CC'
DEVICE_TYPE_SHORT_RANGE_HOOD = 'DA'
DEVICE_TYPE_SHORT_FRIDGE = 'KS'
DEVICE_TYPE_SHORT_WINE_COOLER = 'WC'
DEVICE_TYPE_SHORT_REFRESH_BUTLER = 'RB'
DEVICE_TYPE_SHORT_GLASS_CERAMIC = 'GK'
DEVICE_TYPE_SHORT_CARD_SYSTEM = 'CS '
DEVICE_TYPE_SHORT_COIN_SYSTEM = 'CO'

PROGRAM_NAME = 'name'
PROGRAM_DURATION = 'duration'
PROGRAM_ENERGY_SAVING = 'energySaving'
PROGRAM_OPTI_START = 'optiStart'
PROGRAM_PARTIALLOAD = 'partialload'
PROGRAM_RINSE_PLUS = 'rinsePlus'
PROGRAM_DRY_PLUS = 'dryPlus'
PROGRAM_DURATION_ACT = 'act'
PROGRAM_DURATION_SET = 'set'
PROGRAM_STATUS = 'status'
PROGRAM_STATUS_IDLE = 'idle'
PROGRAM_STATUS_TIMED = 'timed'
PROGRAM_INFORMATION_SET = 'set'
PROGRAM_STARTTIME = 'starttime'
PROGRAM_STARTTIME_SET = 'set'
PROGRAM_STARTTIME_ACT = 'act'
PROGRAM_ENDTIME = 'endtime'
PROGRAM_ENDTIME_SET = 'set'
PROGRAM_ENDTIME_ACT = 'act'
PROGRAM_OPTIDOS = 'optiDos'
PROGRAM_OPTIDOS_SET = 'set'
PROGRAM_OPTIDOS_DETERGENT_A_B = 'detergentAandB'
PROGRAM_OPTIDOS_FILL_LEVEL_A = 'fillLevelA'
PROGRAM_OPTIDOS_FILL_LEVEL_B = 'fillLevelB'
PROGRAM_OPTIDOS_FILL_LEVEL_ACT = 'act'

DEVICE_TYPE_MAPPING = {
    DEVICE_TYPE_SHORT_WASHING_MACHINE: DEVICE_TYPE_WASHING_MACHINE,
    DEVICE_TYPE_SHORT_DRYER: DEVICE_TYPE_DRYER,
    DEVICE_TYPE_SHORT_DISHWASHER: DEVICE_TYPE_DISHWASHER,
    DEVICE_TYPE_SHORT_OVEN: DEVICE_TYPE_OVEN,
    DEVICE_TYPE_SHORT_STEAMER: DEVICE_TYPE_STEAMER,
    DEVICE_TYPE_SHORT_MICRO_STEAM: DEVICE_TYPE_MICRO_STEAM,
    DEVICE_TYPE_SHORT_MICROWAVE: DEVICE_TYPE_MICROWAVE,
    DEVICE_TYPE_SHORT_COFFEE_CENTER: DEVICE_TYPE_COFFEE_CENTER,
    DEVICE_TYPE_SHORT_RANGE_HOOD: DEVICE_TYPE_RANGE_HOOD,
    DEVICE_TYPE_SHORT_FRIDGE: DEVICE_TYPE_FRIDGE,
    DEVICE_TYPE_SHORT_WINE_COOLER: DEVICE_TYPE_WINE_COOLER,
    DEVICE_TYPE_SHORT_REFRESH_BUTLER: DEVICE_TYPE_REFRESH_BUTLER,
    DEVICE_TYPE_SHORT_GLASS_CERAMIC: DEVICE_TYPE_GLASS_CERAMIC,
    DEVICE_TYPE_SHORT_CARD_SYSTEM: DEVICE_TYPE_CARD_SYSTEM,
    DEVICE_TYPE_SHORT_COIN_SYSTEM: DEVICE_TYPE_COIN_SYSTEM
}

REQUEST_HEADERS = {
    f"User-Agent": f"vzug-lib/{VERSION}",
    "Accept": f"application/json, text/plain, */*",
}

CONSUMPTION_DETAILS_VALUE = 'value'
REGEX_MATCH_KWH = r"(\d+(?:[\,\.]\d+)?).?kWh"
REGEX_MATCH_LITER = r"(\d+(?:[\,\.]\d+)?).?ℓ"
REGEX_MATCH_WATER = r"(\d+(?:[\,\.]\d+)?).?l"
REGEX_MATCH_TEMP = r"(\d+(?:[\,\.]\d+)?).?°C"

vzug_log_max_rows = 40                       # maximale Anzahl Eintraege (html/json)
vzug_log_directory = "vzug_logs"
vzug_log_extension = "log"
vzug_log_special = "vzug_special"
vzug_log_newline = "\n"
vzug_log_sep = "\t"

vzug_msg_datetime = 0
vzug_msg_datestr = 1
vzug_msg_msg = 2
vzug_msg_power = 3
vzug_msg_water = 4
vzug_msg_temp = 5

# -----------------------------------------------------------------------


class DeviceAuthError(Exception):
    """Exception thrown if there is an authentication problem."""


class DeviceError(Exception):
    def __init__(self, message, err_code: str, inner_exception: Exception = None):
        super().__init__(message)
        self._device_err_code = err_code
        self._message = message
        self._inner_exception = inner_exception

    @property
    def error_code(self) -> str:
        return self._device_err_code

    @property
    def message(self) -> str:
        return self._message

    @property
    def inner_exception(self):
        if self._inner_exception is None:
          return None
        else:
          return self._inner_exception

    @property
    def is_auth_problem(self) -> bool:
        return isinstance(self.inner_exception, DeviceAuthError)


# -----------------------------------------------------------------------
# Plugin-Code
# -----------------------------------------------------------------------

class vzug(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = VERSION
    ALLOW_MULTIINSTANCE = True

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # cycle time in seconds
        self._cycle = vzug_cycle

        # Initialization
        self.init_ok = True
        if self.get_parameter_value('host') != '':
          self._host = self.get_parameter_value('host')
        else:
          self.log_info("no host/ip defined !")
          self.init_ok = False
          self._init_complete = False
          return

        if self.get_parameter_value('username') != '':
          self._username = self.get_parameter_value('username')
        else:
          self._username = ""

        if self.get_parameter_value('password') != '':
          self._password = self.get_parameter_value('password')
        else:
          self._password = ""

        if self.get_parameter_value('log_data') != '':
          self._log_data = self.get_parameter_value('log_data')
          if self._log_data is None:
            self._log_data = False
        else:
          self.log_debug("log_data not defined => log_data=false")
          self._log_data = False
        
        if self.get_parameter_value('log_age') != '':
          self._log_age = self.get_parameter_value('log_age')
          if self._log_age is None:
            self._log_age = 365
        else:
          self.log_debug("no log_age defined => use default '" + str(365) + "s'")
          self._log_age = 365
        if self._log_age < 0:
          self._log_age = 0
          
        if self.get_parameter_value('save_raw') != '':
          self._save_raw = self.get_parameter_value('save_raw')
          if self._save_raw is None:
            self._save_raw = False
        else:
          self.log_debug("save_raw not defined => save_raw=false")
          self._save_raw = False
        
        self._instance = self.get_instance_name()  # Ist leer, wenn keine Instanzen verwendet werden !

        self._apiver = ""
        self._serial = ""
        self._model_desc = ""
        self._device_name = ""
        self._status = ""
        self._status_json: Dict[Any, Any] = {}
        self._info = ""
        self._softwareversion = ""
        self._hardwareversion = ""
        self._connectiontype = ""
        self._firmwareavailable = False
        self._program = ""
        self._error_code = ""
        self._error_message = ""
        self._error_exception: Optional[DeviceError] = None
        self._uuid = ""
        self._active = False
        self._device_information_loaded = False
        self._device_type_short = ""
        self._device_type: Optional[str] = DEVICE_TYPE_UNKNOWN
        self._auth_previous: Dict[str, str] = {}

        self._optidos_a_status = ""
        self._optidos_b_status = ""
        self._power_consumption_kwh_total = 0.0
        self._power_consumption_kwh_avg = 0.0
        self._power_consumption_kwh_last = 0.0
        self._water_consumption_l_total = 0.0
        self._water_consumption_l_avg = 0.0
        self._water_consumption_l_last = 0.0
        
        self._html = ""
        
        self._lpm = []
        self._f_show_consumption_prog = False
        
        self.reset_active_program_information()

        self.log_debug("V-Zug instance       = " + self._instance)
        self.log_debug("V-Zug host/ip        = " + self._host)
        self.log_debug("V-Zug username       = " + self._username)
        self.log_debug("V-Zug password       = " + self._password)
        self.log_debug("V-Zug log data       = " + str(self._log_data))
        self.log_debug("V-Zug log age        = " + str(self._log_age) + " days")
        self.log_debug("V-Zug save raw       = " + str(self._save_raw))

        self.root_found = False
        self.connection = False
        self.last_connection = ""

        self.items = []

        # Log-Verzeichnis erstellen
        if (self._log_data == True) or (self._save_raw == True):
          self._log_dir = self.create_logdirectory(self.get_sh().get_basedir(),vzug_log_directory)
          self.log_debug("log_dir=" + self._log_dir)
          
        self.sh = sh
        
        self.init_webinterface(WebInterface)

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.log_debug("run")
        
        self.scheduler_add('poll_device',self.poll_device,cycle=self._cycle)
        
        if self.root_found == True:
          self.root.info.host(self._host)
          
        # Erstelle die Liste der Items mit der Kennung 'vzug_parse_item'.
        for item in self.root:
#          self.log_debug("++++ V-Zug parse item: {}".format(item))
          for itemx in item:
#            self.log_debug("     V-Zug item: {}".format(itemx) + " / {}".format(itemx.conf))
            if 'vzug_parse_item' in itemx.conf:
              if not itemx in self.items:
                self.items.append(itemx)
#              self.log_debug("     ==> FOUND !")

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
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
        
        if self.has_iattr(item.conf,'vzug_root'):
          self.root = item
          self.root_found = True
          self.log_debug("V-Zug root = " + "{0}".format(self.root))
          
#        self.log_debug("V-Zug item: {}".format(item) + " / {}".format(item.conf))
        
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
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
            pass

    def poll_device(self):
        
        if self.init_ok == False:
          return

        self.reset_active_program_information()
          
        # Allgemeine Daten zum Geraet bestimmen
        result = asyncio.run(self.load_device_information())
        if result == False:
          # Abfrage hat nicht geklappt (Fehler oder Geraet nicht erreichbar)
          self.connection = False
          self.save_data()
          return
          
        # Angaben zum laufenden Programm im Geraet holen
        result = asyncio.run(self.load_program_details())
        
        # Angaben zum Energie- und Wasserverbrauch holen
        result = asyncio.run(self.load_consumption_data())
          
        # Die letzten Nachrichten laden
        result = asyncio.run(self.lastpushmessages_load())
        self.lastpushmessages_html_json()
        self.lastpushmessages_debug()

        self.connection = True
        self.last_connection = self.now_str()
        self.save_data()
        
        pass

# -----------------------------------------------------------------------
# Kommunikation
# -----------------------------------------------------------------------

    def get_base_url(self) -> URL:
        return URL.build(scheme='http',host=self._host.replace("http://", ""))

    def get_command_url(self,endpoint:str,command:str) -> URL:
        return self.get_base_url().join(URL(endpoint)).update_query({QUERY_PARAM_COMMAND:command})

    async def make_vzug_device_call_raw(self,url:URL) -> str:
        """
        Make raw service call to any V-Zug device and return the response as text
        """
        connector = aiohttp.TCPConnector(force_close=True)
        async with aiohttp.ClientSession(connector=connector) as session:
          try:
            self.log_debug("Raw service call URL: " + str(url))
            self.logging_special("CALL","url:" + str(url),"")

            auth = DigestAuth(self.logger,self._username,self._password,session,self._auth_previous)
            resp = await auth.request('GET',url=url,headers=REQUEST_HEADERS)
            self._auth_previous = {
                                    'nonce_count': auth.nonce_count,
                                    'last_nonce': auth.last_nonce,
                                    'challenge': auth.challenge,
                                  }

            if aiohttp.web.HTTPUnauthorized.status_code == resp.status:
              err_msg = "Authentication problem occurred while calling device API"
              self.log_debug(err_msg)
              self.logging_special("ERROR",err_msg,"")
              raise DeviceError(err_msg,"n/a",DeviceAuthError())

            txt_resp = await resp.read()
            self.log_debug("Raw response from " + self._host + ": status " + str(resp.status) + ", text: " + txt_resp.decode("utf-8"))
            self.logging_special("status:" + str(resp.status),"resp:" + txt_resp.decode("utf-8"),"")
            return txt_resp.decode("utf-8")

          except IOError as e:
            err_msg = "IOError while calling device API"
            self.log_debug(err_msg + ": " + str(e))
            self.logging_special("ERROR",err_msg + ":" + str(e),"")
            raise DeviceError(err_msg,"n/a",e)

    @retry(stop=stop_after_attempt(3),
           wait=wait_fixed(2),
           retry=retry_if_exception_type(DeviceError),
           reraise=True)
           
    async def make_vzug_device_call_json(self, url: URL) -> Dict:
        """
        Make service call for any V-Zug device and check if there is an error code in json response.
        Sometimes the devices returns an internal error (like 503). In this case DeviceError exception
        is raised after 3 retries.
        """
        try:
          text_resp = str(await self.make_vzug_device_call_raw(url))

          json_resp = json.loads(text_resp)
          if "error" in json_resp:
            err_code = json_resp['error']['code']
            self.log_debug("Device returned error code: " + str(err_code))
            raise DeviceError("Device returned error code", err_code)
          return json_resp

        except ValueError as e:
          err_msg = "Got invalid response from device"
          self.log_debug(err_msg + ": " + str(e))
          raise DeviceError(err_msg,"n/a",e)

    async def do_consumption_details_request(self, command: str) -> str:
        # Get consumption details
        url = self.get_command_url(ENDPOINT_HH,COMMAND_GET_COMMAND).update_query({QUERY_PARAM_VALUE:command})
        eco_json = await self.make_vzug_device_call_json(url)

        if CONSUMPTION_DETAILS_VALUE in eco_json:
          return eco_json[CONSUMPTION_DETAILS_VALUE]
        else:
          self.log_debug('Error reading consumption data, no \'value\' entry found in response.')
          raise DeviceError('Got invalid response while reading consumption data.', 'n/a')

    async def load_device_information(self) -> bool:
        # Load device status information by calling the corresponding API endpoint
        try:
          self.log_debug("Loading device api information for " + self._host)
          self._status_json = await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_AI,COMMAND_GET_APIVERSION))
          self._apiver = self._status_json['value']

          self.log_debug("Loading device firmware information for " + self._host)
          self._status_json = await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_AI,COMMAND_GET_FIRMWAREVERSION))
            
          self._softwareversion = self._status_json['SW']
          self._hardwareversion = self._status_json['HW']
          self._connectiontype = self._status_json['phy']

          self.log_debug("Loading device firmware available information for " + self._host)
          self._firmwareavailable = await self.make_vzug_device_call_raw(self.get_command_url(ENDPOINT_AI,COMMAND_GET_FIRMWAREAVAILABLE))
            
          self.log_debug("SW=" + self._softwareversion + " HW=" + self._hardwareversion + " Phy=" + self._connectiontype +
                         " Api=" + self._apiver + " Available=" + str(self._firmwareavailable))

          self.log_debug("Loading device information for " + self._host)
          self._status_json = await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_AI,COMMAND_GET_STATUS))

          self._error_code = ""
          self._serial = self._status_json['Serial']
          if make_anonymous == True:
            self._serial = "XXXXX XXXXXX"
          self._device_name = self._status_json['DeviceName']
          self._status = self._status_json['Status']
          self._uuid = self._status_json['deviceUuid']
          if make_anonymous == True:
            self._uuid = "XXXXXXXXXX"
          self._program = self._status_json['Program']
          self._active = not self.strtobool(self._status_json['Inactive'])

          # Load model description in separate call
          self._model_desc = await self.make_vzug_device_call_raw(self.get_command_url(ENDPOINT_AI,COMMAND_GET_MODEL_DESC))

          # Load short device type in separate call
          self._device_type_short = await self.make_vzug_device_call_raw(self.get_command_url(ENDPOINT_HH,COMMAND_GET_MACHINE_TYPE))

          self._set_device_type()
          
          if self._device_type == DEVICE_TYPE_DISHWASHER:
            self._f_show_consumption_prog = True
          
          self._device_information_loaded = True

          self.log_debug("Got device information. Type: " + self._device_type + ", model: " + self._model_desc + ", serial: " + self._serial +
                        ", uuid: " + self._uuid + ", name: " + self._device_name + ", status: " + self._status)
          return True

        except DeviceError as e:
          self._error_code = e.error_code
          self._error_message = e.message
          self._error_exception = e
          return False

    async def load_program_details(self) -> bool:
        """Load program details information by calling the corresponding API endpoint"""

        self.log_debug("Loading program information for " + self._host)

        # Aktuelle Uhrzeit bestimmen
        t_n = self.sh.shtime.now()
        
        try:
          program_json = (await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_HH,COMMAND_GET_PROGRAM)))[0]

          if self._device_type == DEVICE_TYPE_WASHING_MACHINE:
            result = self.read_optidos_details(program_json)

          self._program_status = program_json[PROGRAM_STATUS]
            
          if PROGRAM_STATUS_IDLE in self._program_status:
            self.log_debug("No program information available because no program is active")
            return False

          self._program_name = program_json[PROGRAM_NAME]
            
          if PROGRAM_STATUS_TIMED in self._program_status:
            # Start ist programmiert worden
            self._timed = True
            if PROGRAM_DURATION in program_json:
              # V6000
              self._program_duration = program_json[PROGRAM_DURATION][PROGRAM_DURATION_SET]
              self._seconds_to_start = program_json[PROGRAM_STARTTIME][PROGRAM_STARTTIME_SET]
              self._seconds_to_end = self._seconds_to_start + self._program_duration
            else:
              # V4000
              self._seconds_to_start = program_json[PROGRAM_STARTTIME][PROGRAM_STARTTIME_ACT]
              self._seconds_to_end = program_json[PROGRAM_ENDTIME][PROGRAM_ENDTIME_ACT]
              self._program_duration = self._seconds_to_end - self._seconds_to_start
            ts = t_n + datetime.timedelta(seconds=self._seconds_to_start)
            self._date_time_start = ts.strftime("%d.%m.%Y %H:%M:%S")
            self._program_duration = self._program_duration / 60  # Sekunden => Minuten
          else:
            p = program_json[PROGRAM_DURATION]
            if PROGRAM_DURATION_ACT in p:
              self._seconds_to_end = p[PROGRAM_DURATION_ACT]
            else:
              self._seconds_to_end = 0
              self.log_debug("program " + PROGRAM_DURATION_ACT + " not found in " + PROGRAM_DURATION)
            self._program_duration = self._seconds_to_end / 60
          te = t_n + datetime.timedelta(seconds=self._seconds_to_end)
          self._date_time_end = te.strftime("%d.%m.%Y %H:%M:%S")

          if self._device_type == DEVICE_TYPE_DISHWASHER:
            self._is_energy_saving = program_json[PROGRAM_ENERGY_SAVING][PROGRAM_INFORMATION_SET]
            self._is_opti_start = program_json[PROGRAM_OPTI_START][PROGRAM_INFORMATION_SET]
            self._is_partialload = program_json[PROGRAM_PARTIALLOAD][PROGRAM_INFORMATION_SET]
            self._is_rinse_plus = program_json[PROGRAM_RINSE_PLUS][PROGRAM_INFORMATION_SET]
            self._is_dry_plus = program_json[PROGRAM_DRY_PLUS][PROGRAM_INFORMATION_SET]
              
          self.log_debug("Go program information. Active program: " + self._program_name + ", minutes to end: " + str(self._seconds_to_end / 60) + ", end time: " + self._date_time_end)

          return True

        except DeviceError as e:
          self._error_code = e.error_code
          self._error_message = e.message
          self._error_exception = e
          return False

    def read_optidos_details(self, program_json: Dict[Any, Any]) -> None:
        """Read optiDos information from given program response"""

        if PROGRAM_OPTIDOS_FILL_LEVEL_A in program_json:
          self._optidos_a_status = program_json[PROGRAM_OPTIDOS_FILL_LEVEL_A][PROGRAM_OPTIDOS_FILL_LEVEL_ACT]

        if PROGRAM_OPTIDOS_FILL_LEVEL_B in program_json:
          self._optidos_b_status = program_json[PROGRAM_OPTIDOS_FILL_LEVEL_B][PROGRAM_OPTIDOS_FILL_LEVEL_ACT]

        self._optidos_active = False
        if PROGRAM_OPTIDOS in program_json:
          self._optidos_config = program_json[PROGRAM_OPTIDOS][PROGRAM_OPTIDOS_SET]

          # TODO: Add support for other optiDos configurations
          if self._optidos_config == PROGRAM_OPTIDOS_DETERGENT_A_B:
            self._optidos_active = True
          else:
            self.log_debug("Unknown optiDos configuration / status")
        else:
          self.log_debug("optiDos is not active / available")

        self.log_debug("optiDos information: " + self._optidos_config + "  optiDos A status: " + self._optidos_a_status + ", optiDos B status: " + self._optidos_b_status)

    async def load_consumption_data(self) -> bool:
        """Load power and water consumption data by calling the corresponding API endpoint"""

        self.log_debug("Loading power and water consumption data for " + self._host)
        
        # Die Geraete verwenden fuer den Verbrauch verschiedene Befehle.
        if self._device_type == DEVICE_TYPE_WASHING_MACHINE:
          cmd1 = COMMAND_VALUE_ECOM_STAT_TOTAL
          cmd2 = COMMAND_VALUE_ECOM_STAT_AVG
        elif self._device_type == DEVICE_TYPE_DRYER:
          cmd1 = CMD_VALUE_CONSUMP_DRYER_TOTAL
          cmd2 = CMD_VALUE_CONSUMP_DRYER_AVG
          
        power_consumption_kwh_total = 0
        water_consumption_l_total = 0
        power_consumption_kwh_avg = 0
        water_consumption_l_avg = 0
        power_consumption_kwh_last = 0
        water_consumption_l_last = 0
        
        f_total = False
        f_avg = False
        if (self._device_type == DEVICE_TYPE_WASHING_MACHINE) or (self._device_type == DEVICE_TYPE_DRYER):
          try:
            consumption_total = await self.do_consumption_details_request(cmd1)
            power_consumption_kwh_total = self.read_kwh_from_string(consumption_total)
            water_consumption_l_total = self.read_liter_from_string(consumption_total)
            f_total = True
          except:
            power_consumption_kwh_total = 0
            water_consumption_l_total = 0
          
          try:
            consumption_avg = await self.do_consumption_details_request(cmd2)
            power_consumption_kwh_avg = self.read_kwh_from_string(consumption_avg)
            water_consumption_l_avg = self.read_liter_from_string(consumption_avg)
            f_avg = True
          except:
            power_consumption_kwh_avg = 0
            water_consumption_l_avg = 0

        # Der Befehl 'COMMAND_GET_GETECOINFO' existiert auf verschiedenen Geraeten, hat aber '0' nach dem Einschalten des Geraetes.
        try:
          program_json = await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_HH,COMMAND_GET_GETECOINFO))
          energy = program_json['energy']
          water = program_json['water']
          if f_total == False:
            power_consumption_kwh_total = energy['total']
            water_consumption_l_total = water['total']
          if f_avg == False:
            power_consumption_kwh_avg = energy['average']
            water_consumption_l_avg = water['average']
          try:
            power_consumption_kwh_last = energy['program']
          except:
            power_consumption_kwh_last = 0
          try:
            water_consumption_l_last = water['program']
          except:
            water_consumption_l_last = 0
            
        except:
          x = 0  # Dummy-Eintrag - hier ist nichts weiter zu tun
              
        # Speichere die Werte fuer die spaetere Verwendung
        self._power_consumption_kwh_total = power_consumption_kwh_total
        self._power_consumption_kwh_avg = power_consumption_kwh_avg
        self._power_consumption_kwh_last = power_consumption_kwh_last
        self._water_consumption_l_total = water_consumption_l_total
        self._water_consumption_l_avg = water_consumption_l_avg
        self._water_consumption_l_last = water_consumption_l_last

        self.log_debug("Power consumption [kWh] total: " + str(self._power_consumption_kwh_total) + ", avg: " + str(self._power_consumption_kwh_avg) + ", last=" + str(self._power_consumption_kwh_last))
        self.log_debug("Water consumption [l]   total: " + str(self._water_consumption_l_total) + ", avg: " + str(self._water_consumption_l_avg) + ", last=" + str(self._water_consumption_l_last))

        return True

    async def lastpushmessages_load(self) -> bool:
        # Lade die letzten Pushmessages aus dem Geraet.
        try:
          data = await self.make_vzug_device_call_json(self.get_command_url(ENDPOINT_AI,COMMAND_GET_LASTPUSHNOTIFICATONS))
            
          # Das Geraet sendet die 10 letzten Meldungen.
          pw_f = False
          for i in range(0,10):
            a = self.convert_utcstr2local(data[i]['date'])
            d = a.strftime("%d.%m.%y, %H:%M")
            m = data[i]['message']
            p = self.read_kwh_from_string(m)
            w = self.read_liter_from_string(m)
            t = self.read_temp_from_string(m)
            if (pw_f == False) and (p > 0) and (w > 0) and (t > 0) and ((self._device_type == DEVICE_TYPE_WASHING_MACHINE) or (self._device_type == DEVICE_TYPE_DRYER)):
              self._power_consumption_kwh_last = p
              self._water_consumption_l_last = w
              pw_f = True
            lx = []
            lx.append(a)  # 0
            lx.append(d)  # 1
            lx.append(m)  # 2
            lx.append(p)  # 3
            lx.append(w)  # 4
            lx.append(t)  # 5
                
            self.lastpushmessages_update(lx)
            
          if self._log_data == True:
            self.logging_update()
                
        except DeviceError as e:
          self._error_code = e.error_code
          self._error_message = e.message
          self._error_exception = e
          return False

        return True

    def lastpushmessages_update(self,lpmx):
        # Fuegt die Meldung 'lpmx' in die Liste ein. Die neuste Meldung steht zu Beginn (Index=0).
        
        if len(self._lpm) == 0:
          self._lpm.append(lpmx)
          return
          
        for i in range(len(self._lpm)):
          dd = self._lpm[i]
          if (dd[vzug_msg_datetime] == lpmx[vzug_msg_datetime]) and (dd[vzug_msg_power] == lpmx[vzug_msg_power]) and (dd[vzug_msg_water] == lpmx[vzug_msg_water]) and (dd[vzug_msg_temp] == lpmx[vzug_msg_temp]):
            # Eintrag ist schon vorhanden
            return
          elif dd[vzug_msg_datetime] < lpmx[vzug_msg_datetime]:
            # Index 'i' zeigt auf das Element vor dem wir das neue Element einfuegen => neue Meldung !
            self._lpm.insert(i,lpmx)
            if (lpmx[vzug_msg_power] > 0) and (lpmx[vzug_msg_water] > 0):
              # Wir speichern Energie und Wasser in der Datenbank.
              self.root.program.power(lpmx[vzug_msg_power])
              self.root.program.water(lpmx[vzug_msg_water])
            return
        # Das Element 'lpmx' ist aelter als alle bisherigen Elemente.
        self._lpm.append(lpmx)
        return
          
    def lastpushmessages_html_json(self):
        # Erzeugt die HTML Tabelle und die Json-Liste aus den letzten Meldungen.
        
        line_string = ""
        json_list = []
        for i in range(len(self._lpm)):
          dd = self._lpm[i]
          # HTML
          line_string = line_string + '<tr>'
          line_string = line_string + '<td valign=top>' + dd[vzug_msg_datestr] + '</td>'
          line_string = line_string + '<td valign=top>' + dd[vzug_msg_msg] + '</td>'
          line_string = line_string + '</tr>'
          # JSON
          jd = {"id":str(i),"title":dd[vzug_msg_msg],"content":"","level":"info","date":dd[vzug_msg_datestr]}
          json_list.append(jd)
          if i > vzug_log_max_rows:
            break

        html_string = '<table cellpadding="2" border="1" style="border-collapse:collapse">' + line_string + '</table>'
        self._html = html_string
        
        old = self.root.pushmessages.html()
        if html_string != old:
          self.root.pushmessages.html(html_string)
        old = self.root.pushmessages.jsonlist()
        if json_list != old:
          self.root.pushmessages.jsonlist(json_list)

        return

    def lastpushmessages_debug(self):
        if len(self._lpm) == 0:
          self.log_debug("no push messages")
        for i in range(len(self._lpm)):
          dd = self._lpm[i]
          self.log_debug(str(i) + ": " + dd[1] + " - " + dd[2] + " p=" + str(dd[3]) + " w=" + str(dd[4]) + " t=" + str(dd[5]))
        return

    def _set_device_type(self) -> None:
        if self._device_type_short in DEVICE_TYPE_MAPPING:
          self._device_type = DEVICE_TYPE_MAPPING.get(self._device_type_short)
        else:
          self._device_type = DEVICE_TYPE_UNKNOWN

    def strtobool(self,val):
        """Convert a string representation of truth to true (1) or false (0).
    
        True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
        are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
        'val' is anything else.
        """
        val = val.lower()
        if val in ('y', 'yes', 't', 'true', 'on', '1'):
          return 1
        elif val in ('n', 'no', 'f', 'false', 'off', '0'):
          return 0
        else:
          raise ValueError("invalid truth value %r" % (val,))

    def read_kwh_from_string(self,value_str: str) -> float:
        kwh = self.read_float_from_string(value_str, REGEX_MATCH_KWH)
        if kwh < 0:
          kwh = 0
        return kwh
    
    def read_float_from_string(self,value_str: str, regex: str) -> float:
        match = re.search(regex, value_str)
        if match:
            return float(match.group(1).replace(',', '.'))
        return -1

    def read_liter_from_string(self,consumption_value: str) -> float:
        liter = self.read_float_from_string(consumption_value, REGEX_MATCH_LITER)
        if liter < 0:
          liter = self.read_float_from_string(consumption_value, REGEX_MATCH_WATER)
          if liter < 0:
            liter = 0
        return liter

    def read_temp_from_string(self,value_str: str) -> float:
        temp = self.read_float_from_string(value_str, REGEX_MATCH_TEMP)
        if temp < 0:
          temp = 0
        return temp
    
    def reset_active_program_information(self) -> None:
        self._timed = False
        self._seconds_to_end = 0
        self._date_time_end = ""
        self._seconds_to_start = 0
        self._date_time_start = ""
        self._program_duration = 0
        self._program_name = ""
        self._program_status = ""
        self._is_energy_saving = False
        self._is_opti_start = False
        self._is_partialload = False
        self._is_rinse_plus = False
        self._is_dry_plus = False
        self._optidos_active = False
        self._optidos_config = ""
        self._optidos_a_status = ""
        self._optidos_b_status = ""
            
    def save_data(self):
        # Speichert die Daten in den Items.
        self.root.info.host(self._host)
        self.root.info.serial(self._serial)
        self.root.info.uuid(self._uuid)
        self.root.info.device_type(self._device_type)
        self.root.info.device_name(self._device_name)
        self.root.info.device_short(self._device_type_short)
        self.root.info.model(self._model_desc)
        self.root.info.connection_type(self._connectiontype)
        self.root.info.api_version(self._apiver)
        self.root.info.software_version(self._softwareversion)
        self.root.info.hardware_version(self._hardwareversion)
        self.root.info.is_firmware_update_available(self._firmwareavailable)

        self.root.state.connection(self.connection)
        self.root.state.last_connection(self.last_connection)
        self.root.state.active(self._active)
        self.root.state.status(self._status)
        
        self.root.program.name(self._program_name)
        self.root.program.status(self._program_status)
        self.root.program.duration(self._program_duration)
        self.root.program.date_time_start(self._date_time_start)
        self.root.program.seconds_to_start(self._seconds_to_start)
        self.root.program.date_time_end(self._date_time_end)
        self.root.program.seconds_to_end(self._seconds_to_end)

        self.root.power.consumption_total(self._power_consumption_kwh_total)
        self.root.power.consumption_avg(self._power_consumption_kwh_avg)
        self.root.power.consumption_lastprog(self._power_consumption_kwh_last)
        self.root.water.consumption_total(self._water_consumption_l_total)
        self.root.water.consumption_avg(self._water_consumption_l_avg)
        self.root.water.consumption_lastprog(self._water_consumption_l_last)

        self.root.washing_machine.optidos_active(self._optidos_active)
        self.root.washing_machine.optidos_a_status(self._optidos_a_status)
        self.root.washing_machine.optidos_b_status(self._optidos_b_status)

        self.root.dishwasher.is_energy_saving(self._is_energy_saving)
        self.root.dishwasher.is_opti_start(self._is_opti_start)
        self.root.dishwasher.is_partialload(self._is_partialload)
        self.root.dishwasher.is_rinse_plus(self._is_rinse_plus)
        self.root.dishwasher.is_dry_plus(self._is_dry_plus)
        
        # Bestimme den aktuellen Zustand des Geraetes als Text.
        if self.connection == True:
          if self._active == True:
            self._info = self._program_name + ", " + self._status
            if (self._program_duration > 0) and (self._timed == False):
              self._info = self._info + " (" + f'{self._program_duration:.0f}' + " Min)"
            elif self._timed == True:
              self._info = self._info + " " + self._date_time_start
          else:
            self._info = self.translate("Standby")
        else:
          self._info = self.translate("Aus")
        self.root.state.info(self._info)
        
        self.logging_special("","","")
        self.log_debug("save_data done")
            
# -----------------------------------------------------------------------
# Hilfsroutinen
# -----------------------------------------------------------------------

    def convert_utcstr2local(self,utct):
        utc = ZoneInfo('UTC')
        localtz = ZoneInfo('localtime')
        a = datetime.datetime.strptime(utct,'%Y-%m-%dT%H:%M:%SZ')
        aa = a.replace(tzinfo=utc)
        b = aa.astimezone(localtz)
        return b
          
    def now_str(self):
        return self.now().strftime("%d.%m.%Y, %H:%M:%S")
        
    def log_debug(self,s1):
        self.logger.debug(s1)
#        self.logger.warning(s1)

    def log_info(self,s1):
        self.logger.warning(s1)
        
# -----------------------------------------------------------------------
# Routinen fuer das Logging der Daten
# -----------------------------------------------------------------------

    def create_logdirectory(self,base,log_directory):
        # Erstellt das Verzeichnis 'log_directory' im Log-Verzeichnis von smarthomeNG.
        if log_directory[0] != "/":
          if base[-1] != "/":
            base += "/"
          log_directory = base + "var/log/" + log_directory
        if not os.path.exists(log_directory):
          os.makedirs(log_directory)
        return log_directory
        
    def logging_update(self):
        # Aktualisiert die aktuelle Logdatei.
        # Fuer jeden Tag wird eine neue Log-Datei erstellt.
        
        # Dateiname erstellen und zugehoerige Log-Liste holen
        tn = self.now()
        fn = f"{tn.year-2000:2d}" + f"{tn.month:02d}" + f"{tn.day:02d}" + "_VZUG_" + self._instance
        ld = self._lpm
        fn = self._log_dir + "/" + fn + "." + vzug_log_extension
        self.log_debug("logging_update fn=" + fn)
        
        # Wir suchen den aeltesten Eintrag in der Liste 'ld' vom heutigen Tag
        mii = -1
        for mi in range(len(ld) - 1,-1,-1):  # len(ld)-1 .. 0
          dd = ld[mi]
          t1 = datetime.datetime.strptime(dd[vzug_msg_datestr],"%d.%m.%y, %H:%M")
          if (t1.year == tn.year) and (t1.month == tn.month) and (t1.day == tn.day):
            mii = mi
            break
        if mii == -1:
          # In der aktuellen Liste gibt es noch keinen Eintrag vom heutigen Datum - wir warten !
          return
        
        if not os.path.exists(fn):
          # Datei existiert noch nicht - erstellen mit Headerzeile
          self.log_debug("logging_update file not exist yet => create (" + fn + ")")
          f = open(fn,"wt",encoding='utf-8')
          s1 = "Date/Time (local)" + vzug_log_sep + "Message" + vzug_log_sep + "Power [kWh]" + vzug_log_sep + "Water [l]" + vzug_log_sep + "Temperature [°C]" + vzug_log_newline
          sx = []
          sx.append(s1)
          f.writelines(sx)
          f.close()
          self.logging_del_old_files()

        # Datei oeffnen und alle Zeilen einlesen
        fl = []
        with open(fn,"rt",encoding='utf-8') as f:
          fl = f.readlines()
        f.close()
        
        # Wir suchen diesen aeltesten Eintrag 'mii' in der Liste 'ld' in der Logdatei.
        wl = []
        wl.append(fl[0])  # Titelzeile direkt uebernehmen
        s1 = self.logging_create_str(ld[mii])
        if len(fl) > 1:
          for fi in range(1,len(fl)):   # 1..len(fl)-1 - ohne Titelzeile
            # Durchlaufe alle Zeilen, beginnend mit der aeltesten Zeile (oben in der Datei)
            if fl[fi] == s1:
              # Wir haben den Eintrag im Log gefunden - hier brechen wir ab
              break
            else:
              wl.append(fl[fi])
            
        # Nun fuegen wir alle Eintraege aus 'ld' an die Datei hinzu
        nn = 0
        for mi in range(mii,-1,-1):  # mii .. 0
          # Durchlaufe die Eintrage im Speicher, beginnend mit der aeltesten Zeile (am Ende der Liste)
          s1 = self.logging_create_str(ld[mi])
          wl.append(s1)
          nn = nn + 1
          
        if len(fl) - 1 == nn:
          # Anzahl Zeilen in der aktuellen Log unveraendert.
          self.log_debug("logging_update rows not changed ! " + str(len(fl) - 1) + "/" + str(nn))
          return
            
        # Schreibe die Log-Datei mit den neuen Daten
        f = open(fn,"wt",encoding='utf-8')
        f.writelines(wl)
        f.close()
        
    def logging_create_str(self,dd):
        s1 = dd[vzug_msg_datestr] + vzug_log_sep + dd[vzug_msg_msg] + vzug_log_sep + f"{dd[vzug_msg_power]:.1f}" + vzug_log_sep + f"{dd[vzug_msg_water]:.1f}" + vzug_log_sep + f"{dd[vzug_msg_temp]:.1f}" + vzug_log_newline
        return s1
        
    def logging_del_old_files(self):
        # Alte Log-Dateien loeschen.
        if self._log_age == 0:
          return
        tn = self.now()
        files = os.listdir(self._log_dir)
        ts = tn.replace(hour=0,minute=1,second=0)
        tx = ts - timedelta(days=self.log_age)
        tx = tx.replace(tzinfo=None)
#        self.log_debug("ts=" + ts.strftime("%d.%m.%Y %H:%M:%S") + " tx=" + tx.strftime("%d.%m.%Y %H:%M:%S"))
        for i in range(0,len(files)):
          yy = int(files[i][0:2])
          mm = int(files[i][2:4])
          da = int(files[i][4:6])
          dt = datetime(2000 + yy,mm,da,0,1,0,0)  # Datum dieser Datei als 'datetime'
          dx = tx - dt
#          self.log_debug("i:" + str(i) + " -> " + files[i] + " / " + " y=" + str(yy) + " m=" + str(mm) + " d=" + str(da) + " - " + dt.strftime("%d.%m.%Y %H:%M:%S") + " dx=" + str(dx.total_seconds()) + " dx=" + str(dx.days))
          if dx.days > 0:
            # Positiv = Datei zu alt, wird geloescht !
            os.remove(self._log_dir + "/" + files[i])
            self.log_info("Log file " + files[i] + " too old -> deleted")

    def logging_special(self,s1,s2,s3):
        # Schreibt die Texte 's1,s2,s3' in die Spezial-Log-Datei.
        if self._save_raw == False:
          return
          
        fn = self._log_dir + "/" + vzug_log_special + "_" + self._instance + "." + vzug_log_extension
        if not os.path.exists(fn):
          f = open(fn,"wt",encoding='utf-8')
          sx = []
          sx.append("V-Zug Plugin - raw data " + self._instance + vzug_log_newline)
          sx.append(vzug_log_newline)
          sx.append("Date/Time" + vzug_log_sep + "Status" + vzug_log_sep + "Response" + vzug_log_sep + " " + vzug_log_newline)
          f.writelines(sx)
          f.close()
          
        file_stats = os.stat(fn)
        if file_stats.st_size > 5000000:
          return
          
        # Neuer Eintrag - an die Datei anfuegen.
        s = []
        tn = self.now()
        s.append(tn.strftime("%d.%m.%Y %H:%M:%S") + vzug_log_sep + s1 + vzug_log_sep + s2 + vzug_log_sep + s3 + vzug_log_newline)
        f = open(fn,"at",encoding='utf-8')
        f.writelines(s)
        f.close()
        return


# -----------------------------------------------------------------------
# class DigestAuth
# -----------------------------------------------------------------------

class DigestAuth:
    """HTTP digest authentication helper.
    The work here is based off of https://github.com/requests/requests/blob/v2.18.4/requests/auth.py.
    """

    def __init__(self,logger,username,password,session,previous=None):
        if previous is None:
            previous = {}

        self.username = username
        self.password = password
        self.last_nonce = previous.get('last_nonce', '')
        self.nonce_count = previous.get('nonce_count', 0)
        self.challenge = previous.get('challenge')
        self.args = {}
        self.digest_auth_tried = False
        self.session = session
        self.logger = logger

    async def request(self,method,url,*,headers=None,**kwargs):
        if headers is None:
            headers = {}

        # Save the args so we can re-run the request
        self.args = {
            'method': method,
            'url': url,
            'headers': headers,
            'kwargs': kwargs
        }

        self.log_debug("==== DigestAuth")
        self.log_debug("  method  =" + method)
        self.log_debug("  url     =")
        self.log_debug(url)
        self.log_debug("  headers =")
        self.log_debug(headers)
        self.log_debug("  kwargs  =")
        self.log_debug(kwargs)
        self.log_debug("")

        if self.challenge:
            headers[hdrs.AUTHORIZATION] = self._build_digest_header(method.upper(),url)

        self.log_debug("  headers =")
        self.log_debug(headers)

        response = await self.session.request(method,url,headers=headers,**kwargs)

        self.log_debug("  response =")
        self.log_debug(response)

        # Only try performing digest authentication if the response status is # from 400 to 500.
        if 400 <= response.status < 500 and self.digest_auth_tried is False:
            self.digest_auth_tried = True
            return await self._handle_401(response)

        return response

    def _build_digest_header(self,method,url):
        """
        :rtype: str
        """

        realm = self.challenge['realm']
        nonce = self.challenge['nonce']
        qop = self.challenge.get('qop')
        algorithm = self.challenge.get('algorithm', 'MD5').upper()
        opaque = self.challenge.get('opaque')

        if qop and not (qop == 'auth' or 'auth' in qop.split(',')):
            raise client_exceptions.ClientError(
                'Unsupported qop value: %s' % qop
            )

        # lambdas assume digest modules are imported at the top level
        if algorithm == 'MD5' or algorithm == 'MD5-SESS':
            hash_fn = hashlib.md5
        elif algorithm == 'SHA':
            hash_fn = hashlib.sha1
        else:
            return ''

        def H(x):
            return hash_fn(x.encode()).hexdigest()

        def KD(s, d):
            return H('%s:%s' % (s, d))

        path = URL(url).path_qs
        A1 = '%s:%s:%s' % (self.username, realm, self.password)
        A2 = '%s:%s' % (method, path)

        HA1 = H(A1)
        HA2 = H(A2)

        if nonce == self.last_nonce:
            self.nonce_count += 1
        else:
            self.nonce_count = 1

        self.last_nonce = nonce

        ncvalue = '%08x' % self.nonce_count

        # cnonce is just a random string generated by the client.
        cnonce_data = ''.join([
            str(self.nonce_count),
            nonce,
            time.ctime(),
            os.urandom(8).decode(errors='ignore'),
        ]).encode()
        cnonce = hashlib.sha1(cnonce_data).hexdigest()[:16]

        if algorithm == 'MD5-SESS':
            HA1 = H('%s:%s:%s' % (HA1, nonce, cnonce))

        # This assumes qop was validated to be 'auth' above. If 'auth-int'
        # support is added this will need to change.
        if qop:
            noncebit = ':'.join([
                nonce, ncvalue, cnonce, 'auth', HA2
            ])
            response_digest = KD(HA1, noncebit)
        else:
            response_digest = KD(HA1, '%s:%s' % (nonce, HA2))

        base = ', '.join([
            'username="%s"' % self.username,
            'realm="%s"' % realm,
            'nonce="%s"' % nonce,
            'uri="%s"' % path,
            'response="%s"' % response_digest,
            'algorithm="%s"' % algorithm,
        ])
        if opaque:
            base += ', opaque="%s"' % opaque
        if qop:
            base += ', qop="auth", nc=%s, cnonce="%s"' % (ncvalue, cnonce)

        return 'Digest %s' % base

    async def _handle_401(self,response):
        """
        Takes the given response and tries digest-auth, if needed.
        :rtype: ClientResponse
        """
        auth_header = response.headers.get('WWW-Authenticate', '')

        parts = auth_header.split(' ', 1)
        if 'digest' == parts[0].lower() and len(parts) > 1:
            self.challenge = self.parse_key_value_list(parts[1])

            return await self.request(
                self.args['method'],
                self.args['url'],
                headers=self.args['headers'],
                **self.args['kwargs']
            )

        return response

    def parse_pair(self,pair):
        key, value = pair.split('=', 1)
    
        # If it has a trailing comma, remove it.
        if value[-1] == ',':
            value = value[:-1]
    
        # If it is quoted, then remove them.
        if value[0] == value[-1] == '"':
            value = value[1:-1]
    
        return str(key).strip(), str(value).strip()
    
    def parse_key_value_list(self,header):
        return {
            key: value for key, value in
            [self.parse_pair(header_pair) for header_pair in header.split(',')]
        }

    def log_debug(self,s1):
        x = 0
#        self.logger.debug(s1)

# -----------------------------------------------------------------------
