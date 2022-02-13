#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Thomas Hengsberg <thomas@thomash.eu>
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

from lib.model.smartplugin import *
from lib.item import Items
import binascii
import sys
import requests
import json
import random
import string
from base64 import b64encode,b64decode
from Crypto.Hash import SHA, HMAC
from requests.auth import HTTPDigestAuth


class Philips_TV(SmartPlugin):
    PLUGIN_VERSION = '1.9.1'

    def __init__(self, sh, *args, **kwargs):

        self._sh = sh
        self._cycle = 60
        self._num_retries = 2
        # Key used for generated the HMAC signature
        self.secret_key="JCqdN5AcnAHgJYseUn7ER5k3qgtemfUvMRghQpTfTZq7Cvv8EPQPqfz6dDxPQPSu4gKFPWkJGw32zyASgJkHwCjU"
        self.session = requests.Session()
        self.ip = self.get_parameter_value('ip')
        self.deviceID = 'invalid'
        self.auth_Timestamp = None
        self.deviceKey = 'invalid'
        self._rx_items = []
        self.verbose = False
        self._errors = ''

        
        temp = self.get_parameter_value('deviceID')
        if not temp == '':
            self.deviceID = temp
            self.logger.debug(f"Loaded deviceID: {self.deviceID}")

        temp = self.get_parameter_value('deviceKey')
        if not temp == '':
            self.deviceKey = temp
            self.logger.debug(f"Loaded deviceKey: {self.deviceKey}")



        # Check plugin parameters:
        if (len(self.ip) < 1):
            self.logger.error("No valid ip specified. Aborting.")
            self._init_complete = False
            return
        else:
            self.logger.info(f"Philips TV configured on IP: {self.ip}")
        self.logger.debug("Init completed.")
        self.init_webinterface()
        self._items = {}
        return 

    # creates random device id
    def createDeviceId(self):
        return "".join(random.SystemRandom().choice(string.ascii_uppercase + string.digits + string.ascii_lowercase) for _ in range(16))

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, prio=5, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.scheduler_remove('poll_device')
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the neato_attribute and adds it to an internal array

        :param item: The item to process.
        """
        if self.get_iattr_value(item.conf, 'philips_tv_rx_key'):
            self._rx_items.append(item)
            #self.logger.debug(f"rx-items dict: {self._rx_items}")

        if self.has_iattr(item.conf, 'philips_tv_tx_key'):
            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        self.logger.debug(f"Update philips item: Caller: {caller}, pluginname: {self.get_shortname()}")
        if caller != self.get_shortname():
            if self.has_iattr(item.conf, 'philips_tv_tx_key'):
                tx_key = item.conf['philips_tv_tx_key'].upper()
                if tx_key == 'MUTE':
                    body = '{"key": "Mute"}'
                    #self.logger.debug("Sending mute command")
                    self.post("input/key", body, verbose=self.verbose, err_count=0)
                elif tx_key == 'POWEROFF':
                    if item() == True:
                        body = '{"key": "Standby"}'
                        #self.logger.debug("Sending poweroff command")
                        self.post("input/key", body=body, verbose=self.verbose, err_count=0)
                else:
                    self.logger.error(f"Unknown tx key: {tx_key}")
        pass

    def poll_device(self):
        #self.logger.debug("Polling philips device")

        error_msg    = None
        volume       = None
        muted        = None 
        powerstate   = None
        channel_name = None

        value = self.get("audio/volume", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response: {value}")
        
        value_json = json.loads(value)
        if value_json is not None:
            if 'error' in value_json:
                error_msg = value_json["error"]
                self._errors = error_msg
                powerstate = 'OFF'
                if error_msg == 'Can not reach the API': 
                    #self.logger.debug(f"Error: {error_msg}")
                    pass
                else:
                    self.logger.error(f"Error: {error_msg}")
            else:
                error_msg = ''
                self._errors = error_msg

            if 'muted' in value_json:
                muted = value_json["muted"]
                #self.logger.debug(f"Mute state is: {muted}")
            if 'current' in value_json:
                volume = value_json["current"]
                #self.logger.debug(f"Volume state is: {volume}")
         
        value = self.get("activities/current", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response: {value}")
        value_json = json.loads(value)
        if value_json is not None:
            if 'component' in value_json:
                component = value_json["component"]
                if 'packageName' in component:
                    packageName = component["packageName"]
                if 'className' in component:
                    className= component["className"]
                if className != 'NA' or packageName != 'NA':
                    self.logger.info(f"APP state is: {packageName}, {className}")

        #value = self.get("recordings/list", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response recordings: {value}")
        #value_json = json.loads(value)
        #if value_json is not None:
        #    if 'recordings' in value_json:
        #        recordingList = value_json["recordings"]
        #        self.logger.debug(f"{len(recordingList)} recordings available")

        #does not work:
        #value = self.get("activities", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response Activities: {value}")


        # does not work:
        #value = self.get("channeldb/tv/favoritelLists/all", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response Favorite: {value}")

        # does not work:
        #value = self.get("channeldb/tv/favoritelLists/all", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response Favorite list: {value}")


        # works: lists all tv channels:
        #value = self.get("channeldb/tv/channelLists/all", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response: {value}")

        # does not work:
        #value = self.get("applications/current", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response apps current: {value}".format())

        #does not work
        #value = self.get("sources/current", verbose=self.verbose, err_count=0, print_response=False)

        # works: lists all apps
        #value = self.get("applications", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response applications: {value}")
        #value_json = json.loads(value)
        #if value_json is not None:
        #    if 'applications' in value_json:
        #        applicationList = value_json["applications"]
        #        self.logger.debug("Applications:")
        #        for app in applicationList:
        #            if 'label' in app:
        #                self.logger.debug(f"\t{app['label']}")


        value = self.get("powerstate", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response: {value}")
        value_json = json.loads(value)
        if value_json is not None:
            if 'powerstate' in value_json:
                powerstate = value_json["powerstate"]
                #self.logger.debug(f"Powerstate is: {powerstate}")

        value = self.get("activities/tv", verbose=self.verbose, err_count=0, print_response=False)
        #self.logger.debug(f"Response: {value}")
        value_json = json.loads(value)
        if value_json is not None:
            if 'channel' in value_json:
                channel_json = value_json["channel"]
                if 'name' in channel_json:
                    channel_name = channel_json["name"]
                    #self.logger.debug(f"Channel name is: {channel_name}")


        # copy information into smarthomeNG items:
        for item in self._rx_items:
            if (error_msg is not None) and (item.conf['philips_tv_rx_key'].upper() == 'ERROR'):
                item(str(error_msg), self.get_shortname())
            elif (muted is not None) and item.conf['philips_tv_rx_key'].upper() == 'MUTE':
                item(bool(muted), self.get_shortname())
            elif (volume is not None) and item.conf['philips_tv_rx_key'].upper() == 'VOLUME':
                item(volume, self.get_shortname())
            elif (powerstate is not None) and item.conf['philips_tv_rx_key'].upper() == 'POWERSTATE':
                item(bool(powerstate == 'On'), self.get_shortname())
            elif (powerstate is not None) and item.conf['philips_tv_rx_key'].upper() == 'POWERSTATEINFO':
                item(str(powerstate), self.get_shortname())
            elif (channel_name is not None) and item.conf['philips_tv_rx_key'].upper() == 'CHANNEL':
                item(str(channel_name), self.get_shortname())

        pass

    # creates signature
    def create_signature(self, secret_key, to_sign):
        sign = HMAC.new(secret_key, to_sign, SHA)
        return str(b64encode(sign.hexdigest().encode()))

    # creates device spec JSON
    def getDeviceSpecJson(self, config):
        device_spec =  { "device_name" : "heliotrope", "device_os" : "Android", "app_name" : "Pylips", "type" : "native"}
        device_spec["app_id"] = config["application_id"]
        device_spec["id"] = config["device_id"]
        return device_spec

    # send pair request to the TV
    def pair_request(self, data, err_count=0):

        response={}
        try:
            r = self.session.post('https://' + str(self.ip) + ':1926/6/pair/request', json=data, verify=False, timeout=4)
        except Exception as e:
            self.logger.error(f"Exception during sending in pair_request(): {e}")
            return None
        
        if r.json() is not None:
            if r.json()["error_id"] == "SUCCESS":
                response=r.json()
                self.logger.info(f"Request successfull: {response}")
                return response
            else:
                self.logger.error(f"Error {r.json()}")
                return None
        else:
            self.logger.error("Can not reach the API")
            return None

    # confirms pairing with a TV
    def pair_confirm(self, data, err_count=0):
        while err_count < 10:
            if err_count > 0:
                self.logger.info("Resending pair confirm request")
            try:
                r = self.session.post("https://" + str(self.ip) + ":1926/6/pair/grant", json=data, verify=False, auth=HTTPDigestAuth(self.deviceID, self.deviceKey), timeout=2)
                self.logger.debug(f"Username for subsequent calls is: {self.deviceID}")
                self.logger.debug(f"Password for subsequent calls is: {self.deviceKey}")
                return True
            except Exception:
                # try again
                err_count += 1
                continue
        else:
            return False

    def startPairing(self):
        self.logger.debug("Starting pairing process")

        payload = {}
        payload["application_id"] = "app.id"
        self.deviceID = self.createDeviceId()
        payload["device_id"] = self.deviceID
        self.logger.debug(f"New Device ID is {self.deviceID}")

        data = { "scope" :  [ "read", "write", "control"] }
        data["device"]  = self.getDeviceSpecJson(payload)

        self.logger.info("Sending pairing request")
        result = self.pair_request(data)

        if result:
            self.auth_Timestamp = result["timestamp"]
            self.deviceKey = result["auth_key"]
            self.logger.info(f"timestamp {self.auth_Timestamp}, auth_key {self.deviceKey}")

            self.logger.info("Writing token to plugin.yaml")
            param_dict = {"deviceID": str(self.deviceID), "deviceKey": str(self.deviceKey)}
            self.update_config_section(param_dict)

            return True
    
        return False

    def completePairing(self, code):
        self.logger.debug(f"Completing pairing process with code {code}")

        data = { "scope" :  [ "read", "write", "control"] }
        data["device_id"] = self.deviceID
        data["application_id"] = "app.id"

        data["device"]  = self.getDeviceSpecJson(data)
        data["device"]["auth_key"] = self.deviceKey

        auth = { "auth_AppId" : "1"}
        auth["pin"] = str(code)
        auth["auth_timestamp"] = self.auth_Timestamp
        auth["auth_signature"] = self.create_signature(b64decode(self.secret_key), str(self.auth_Timestamp).encode() + str(code).encode())
  
        grant_request = {}
        grant_request["auth"] = auth
        data["application_id"] = "app.id"
        data["device_id"] = self.deviceID
        grant_request["device"]  = self.getDeviceSpecJson(data)

        self.logger.debug("Attempting to pair")
        self.pair_confirm(grant_request)

        return True


    # sends a general GET request
    def get(self, path, verbose=True, err_count=0, print_response=True):
        while err_count < int(self._num_retries):
            if verbose:
                self.logger.info(f"Sending GET request to https://{str(self.ip)}':1926/6/'{str(path)}")
            try:
                r = self.session.get("https://" + str(self.ip) + ":1926/6/" + str(path), verify=False, auth=HTTPDigestAuth(str(self.deviceID), str(self.deviceKey)), timeout=2)
            except Exception:
                err_count += 1
                continue
            if verbose:
                self.logger.info("Request sent!")
            if len(r.text) > 0:
                if print_response:
                    self.logger.debug(r.text)
                return r.text
        else:
            return json.dumps({"error":"Can not reach the API"})

    # sends a general POST request
    def post(self, path, body, verbose=True, err_count=0):
        while err_count < int(self._num_retries):
            if type(body) is str:
                body = json.loads(body)
            if verbose:
                self.logger.info(f"Sending POST request to https://{str(self.ip)} ':1926/6/'{str(path)}")
            try:
                r = self.session.post("https://" + str(self.ip) + ":1926/6/" + str(path), json=body, verify=False, auth=HTTPDigestAuth(str(self.deviceID), str(self.deviceKey)), timeout=2)
            except Exception as e:
                #self.logger.debug(f"Exception during post command: {e}")
                err_count += 1
                continue
            if verbose:
                self.logger.info("Request sent!")
            if len(r.text) > 0:
                self.logger.info(r.text)
                return r.text
            elif r.status_code == 200:
                self.logger.info(json.dumps({"response":"OK"}))
                return json.dumps({"response":"OK"})
        else:
            self.logger.info(json.dumps({"error":"Can not reach the API"}))
            return json.dumps({"error":"Can not reach the API"})

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

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None, action=None, email=None, hashInput=None, code=None, tokenInput=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        
        codeRequestSuccessfull = None
        pairingCompleted = None

        if action is not None:
            if action == "requestCode":
                self.logger.info("Request code triggered via webinterface")
                codeRequestSuccessfull = self.plugin.startPairing()
            elif action == "confirmCode":
                self.logger.info("Confirm code triggered via webinterface")
                if (code is not None) and (not code == ''):
                    pairingCompleted = self.plugin.completePairing(code)
                elif (code is None) or (code == ''):
                    self.logger.error("Confirmation not possible: TV Paring code missing.")
                    pairingCompleted = False
                else:
                    self.logger.error("Confirmation no possible: Missing argument.")
                    pairingCompleted = False
            else:
                self.logger.error("Unknown command received via webinterface")

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, 
                           codeRequestSuccessfull=codeRequestSuccessfull,
                           pairingCompleted=pairingCompleted)


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error(f"get_data_html exception: {e}")
        return {}


