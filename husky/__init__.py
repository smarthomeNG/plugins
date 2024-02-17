#!/usr/bin/env python3
# vim: autoindent tabstop=4 shiftwidth=4 expandtab softtabstop=4 filetype=python
#########################################################################
#  Copyright 2019 Markus Garscha                               mg@gama.de 
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

import json
import requests 
import logging

from datetime import datetime, timedelta
from dateutil.parser import parse
from http.server import BaseHTTPRequestHandler
from collections import deque

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory

class Husky(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION   = '1.1.0'
    SCHEDULER_NAME   = "husky_poll_service"
    SCHEDULER_NAME_F = "husky_poll_service_fast"

    ITEM_INFO        = "husky_info"
    ITEM_CONTROL     = "husky_control"
    ITEM_STATE       = "husky_state"
    ITEM_OPDATA      = "husky_operating"

    VALID_INFOS      = ['name','id','model']
    VALID_STATES     = ['connection','activity','color','errormessage','message','batterypercent']
    VALID_COMMANDS   = ['start','start_3h','stop','park','park_timer']
    VALID_ACTIVITIES = ['parked','charging','moving','cutting','error']

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

        # If an package import with try/except is done, handle an import error like this:

        # Exit if the required package(s) could not be imported
        # if not REQUIRED_PACKAGE_IMPORTED:
        #     self.logger.error("Unable to import Python package '<exotic package>'")
        #     self._init_complete = False
        #     return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')

        self.COMMANDS = {
            'park'        : self._control_mower_park,
            'park_timer'  : self._control_mower_park_timer,
            'stop'        : self._control_mower_stop,
            'start_3h'    : self._control_mower_start_override_3h,
            # 'default'     : self.logger.error("husky: called undefined control function, no action method found!")
            'default'     : None 
        }

        self.userid = self.get_parameter_value('userid')
        self.password = self.get_parameter_value('password')
        self.device = self.get_parameter_value('device')

        self.use_token = True
        self.token = "" 
        self.provider = "" 
        self.expire_date = datetime(1900,1,1) 

        self._items_control = []
        self._items_state  = []
        self._items_opdata = []

        #### TODO: move the connection to the run() methond...


        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # Initialization code goes here
        self.mowapi = API()
        self.mymower = Mower()


        # On initialization error use:
        #   self._init_complete = False
        #   return

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # if plugin should start even without web interface
        # self.init_webinterface()

        # if plugin should not start without web interface
        if not self.init_webinterface():
            self._init_complete = False
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")


        if self.use_token and self.token and self.expire_date < datetime.now():
            # expired token found
            self.logger.warn("token expired. create new one")
            self.mowapi.logout()

        if self.use_token and self.expire_date > datetime.now():
            # valid token found
            self.logger.info("valid token found and used for authentification")
            self.mowapi.set_token(self.token, self.provider)
        else:
            # do (re-)login
            self.logger.info("login with userid: {0}".format(self.userid))
            lifetime = self.mowapi.login(self.userid, self.password)

            if (lifetime > 0):
                self.logger.info("login lifetime %d" % lifetime)
                if self.use_token:
                    self.token = self.mowapi.token
                    self.provider = self.mowapi.provider
                    self.expire_date = datetime.now() + timedelta(0, lifetime)
                    self.logger.info("token updated")
            else:
                self.logger.error("PLUGIN INIT ABORT: no liftetime returned, something went wrong")
                return


        self._select_mower()

        self.logger.debug("found {0} operation data items. Setting initial activity time from item".format(len(self._items_opdata)))
        for item in self._items_opdata:

            item_id = item.property.path
            item_value = "{0}".format(item())

            key = item.conf[self.ITEM_OPDATA] # husky_operation = MOVING 
            self.logger.debug("set activity {0} from item {1} to value {2}".format(key, item.property.path, item_value))
            self.mymower.set_mower_activity_time(key, item_value)


        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well
        self.scheduler_add(self.SCHEDULER_NAME  , self.poll_device, cycle=self._cycle)

        # self.scheduler_add(self.SCHEDULER_NAME_F, self.poll_device, cycle=10)
        # self.scheduler_change(self.SCHEDULER_NAME_F, active=False)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")

        #TODO: cleanup connection, e.g. remove running threads
        self.scheduler_remove('husky_poll_service')

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
        if self.has_iattr(item.conf, self.ITEM_CONTROL):
            self.logger.debug("parse CONTROL item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_CONTROL).lower()
            if value in self.VALID_COMMANDS:
                self.logger.debug("adding valid command item {0} to wachlist {1}={2} ".format(item, self.ITEM_CONTROL, item.conf[self.ITEM_CONTROL]))
                self._items_control.append(item)
                return self.update_item
            else:
                self.logger.error("command '{0}' invalid, use one of {1}".format(value, self.VALID_COMMANDS))

        if self.has_iattr(item.conf, self.ITEM_STATE):
            self.logger.debug("parse STATE item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_STATE).lower()
            if value in self.VALID_STATES:
                self.logger.debug("adding valid state item {0} to wachlist {1}={2} ".format(item, self.ITEM_STATE, item.conf[self.ITEM_STATE]))
                self._items_state.append(item)
                return self.update_item
            else:
                self.logger.error("value '{0}' invalid, use one of {1}".format(value, self.VALID_STATES))

        if self.has_iattr(item.conf, self.ITEM_OPDATA):
            self.logger.debug("parse OPDATA item: {}".format(item))

            value = self.get_iattr_value(item.conf, self.ITEM_OPDATA).lower()
            if value in self.VALID_ACTIVITIES:
                self.logger.debug("adding valid operation data item {0} to wachlist {1}={2} ".format(item, self.ITEM_OPDATA, item.conf[self.ITEM_OPDATA]))
                self._items_opdata.append(item)
                return self.update_item
            else:
                self.logger.error("value '{0}' invalid, use one of {1}".format(value, self.VALID_ACTIVITIES))




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
        if caller != self.get_shortname():
            # code to execute, only if the item has not been changed by this this plugin:
            item_value = "{0}".format(item())
            self.logger.info("Update item: {0}, item has been changed outside this plugin to value={1}".format(item.property.path, item_value))
            if self.has_iattr(item.conf, self.ITEM_CONTROL):
                self.logger.debug("update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))
                cmd = self.get_iattr_value(item.conf, self.ITEM_CONTROL).lower()

                # ret = {
                #    'park'        : self._control_mower_park,
                #    'park_timer'  : self._control_mower_park_timer,
                #    'stop'        : self._control_mower_stop,
                #    'start_3h'    : self._control_mower_start_override_3h,
                #    'default'     : self.logger.error("called undefined control function, no action method found!") 
                #}.get(cmd,'default')()

                if cmd in self.COMMANDS:
                    #TODO: generate new status with "sending..." 
                    ret = self.COMMANDS.get(cmd,'default')()

                    # lower cycle time to receive answer soon...
                    # self._change_fast_poll_cycle(True)
                else:
                    self.logger.error("available commands: {}".format(self.COMMANDS.keys()))
                

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler.
        """

        # TODO: Check valid token, reauthenticate
        # Method plugins.husky.husky_poll_service exception: 401 Client Error: Unauthorized for url: https://amc-api.dss.husqvarnagroup.net/app/v1/mowers/190101508-184934005/status

        if self.use_token and self.token and self.expire_date < datetime.now():
            # expired token found
            self.logger.warn("token expired. log out and create new one")
            self.mowapi.logout()

            # do (re-)login
            self.logger.info("(re-)login with userid: {0}".format(self.userid))
            lifetime = self.mowapi.login(self.userid, self.password)

            self.logger.info("login lifetime %d" % lifetime)
            if self.use_token:
                self.token = self.mowapi.token
                self.provider = self.mowapi.provider
                self.expire_date = datetime.now() + timedelta(0, lifetime)
                self.logger.info("token updated")

            self._select_mower()


        mower_status = self.mowapi.poll_status_v1()

        mower_status_v0 = self.mowapi.status()
        isnew = self.mymower.new_status_from_json(mower_status_v0)

        if isnew:
            self.logger.debug("--- new status received:")
            self.logger.debug(self.mymower)

            self.logger.debug("found {0} state items to update".format(len(self._items_state)))
            for item in self._items_state:

                item_id = item.property.path
                item_value = "{0}".format(item())

                key = item.conf[self.ITEM_STATE] # husky_state = activity
                self.logger.debug("update item {0} of type {1} and key {2}".format(item.property.path, item.type(), key))
                value = {
                    'connection'      : self.mymower.last_status().is_connected,
                    'activity'        : self.mymower.last_status().get_activity,
                    'color'           : self.mymower.last_status().get_activity_color,
                    'errormessage'    : self.mymower.last_status().get_last_error_message,
                    'message'         : self.mymower.last_status().get_status_message,
                    'batterypercent'  : self.mymower.last_status().get_battery_percent,
                    'default'         : None
                }.get(key)()


                self.logger.debug("update item: set {0} to {1}".format(key, value))

                # if the plugin is a gateway plugin which may receive updates from several external sources,
                # the source should be included when updating the the value:
                #     item(device_value, self.get_shortname(), source=device_source_id)
                item(value, self.get_shortname())


            self.logger.debug("activity time   PARKED: {0}".format(self.disp_age(self.mymower.get_mower_activity_time('PARKED')//1000)))
            self.logger.debug("activity time CHARGING: {0}".format(self.disp_age(self.mymower.get_mower_activity_time('CHARGING')//1000)))
            self.logger.debug("activity time   MOVING: {0}".format(self.disp_age(self.mymower.get_mower_activity_time('MOVING')//1000)))
            self.logger.debug("activity time  CUTTING: {0}".format(self.disp_age(self.mymower.get_mower_activity_time('CUTTING')//1000)))
            self.logger.debug("activity time    ERROR: {0}".format(self.disp_age(self.mymower.get_mower_activity_time('ERROR')//1000)))
            # self.logger.debug(json.dumps(self.mymower.get_mower_activity_time('PARKED', indent=4, sort_keys=True))
            self.logger.debug("found {0} operation data items to update".format(len(self._items_opdata)))
            for item in self._items_opdata:

                item_id = item.property.path
                item_value = "{0}".format(item())

                key = item.conf[self.ITEM_OPDATA] # husky_state = activity
                self.logger.debug("update item {0} of type {1} and key {2}".format(item.property.path, item.type(), key))

                value = self.mymower.get_mower_activity_time(key)
                self.logger.debug("update item: set {0} to {1}".format(key, value))

                # if the plugin is a gateway plugin which may receive updates from several external sources,
                # the source should be included when updating the the value:
                #     item(device_value, self.get_shortname(), source=device_source_id)
                item(value, self.get_shortname())

        else:
            self.logger.debug("status received - but same timestamp - no update needed ({0})".format(self.mymower.last_status().is_connected()))
            # self._change_fast_poll_cycle(False)
            # TODO: check if last update is < threshold to detect unconnected mower


    #def _change_fast_poll_cycle(self, fast=True):
    #    if fast == True:
    #        self.scheduler_change(self.SCHEDULER_NAME_F, active=True)
    #        self.scheduler_change(self.SCHEDULER_NAME, active=False)
    #    else:
    #        self.scheduler_change(self.SCHEDULER_NAME_F, active=False)
    #        self.scheduler_change(self.SCHEDULER_NAME, active=True)

        #if cycle != self._cycle:
        #    if cycle > 5:
        #        self._cycle = cycle
                # TODO: dosnt work
                # self.scheduler_change(self.SCHEDULER_NAME, cycle=self._cycle)
                # self.scheduler_change(self.SCHEDULER_NAME, cycle=60)
                # settings = {'cycle': self._cycle}
                # self.scheduler_change(self.SCHEDULER_NAME, **settings)
                # works but follow up error
                # self.scheduler_change(self.SCHEDULER_NAME, cycle={60: True})


    def _select_mower(self):
        self.mowers = self.mowapi.list_robots()
        selected_mower = None
        if not len(self.mowers):
            self.logger.error("No mower found.")
            self._init_complete = False
            return
        else:
            # list and select mower
            for mower in self.mowers:
                if mower['name'] == self.device or mower['id'] == self.device:
                    selected_mower = mower
                    self.logger.info("NAME: {0}, ID: {1}, MODEL: {2}".format(mower['name'], mower['id'], mower['model'])) 

            # select first, if no match
            if selected_mower is None:
                selected_mower = self.mowers[0]
	
            self.mowapi.select_robot(selected_mower['id'])		
            self.mymower.parse_mower_from_json(selected_mower)

            self.logger.info("SELECTED MOWER: NAME: {0}, ID: {1}".format(selected_mower['name'], selected_mower['id'])) 
            # self.logger.debug(json.dumps(selected_mower, indent=4, sort_keys=True))


    def _get_api_connection(self):
        return self.mowapi.connection()

    def _get_api_token(self):
        return self.token

    def _get_api_token_expire_date(self):
        return self.expire_date


    def _control_mower_park(self):
        self.logger.debug("_control_park() triggered")
        self.mowapi.control_v1('PARK')
        return True

    def _control_mower_park_timer(self):
        self.logger.debug("_control_park() triggered")
        self.mowapi.control_v1('PARK_TIMER')
        return True

    def _control_mower_start(self):
        self.logger.debug("_control_start() triggered")
        self.mowapi.control_v1('START')
        return True

    def _control_mower_start_override_3h(self):
        self.logger.debug("_control_start_override_3h() triggered")
        self.mowapi.control_v1('START_3H')
        return True

    def _control_mower_stop(self):
        self.logger.debug("_control_stop() triggered")
        self.mowapi.control_v1('STOP')
        return True

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


    def disp_age(self, age):
        days = 0
        hours = 0
        minutes = 0
        seconds = age
        if seconds >= 60:
            minutes = int(seconds / 60)
            seconds = seconds - 60 * minutes
            if minutes > 59:
                hours = int(minutes / 60)
                minutes = minutes - 60 * hours
                if hours > 23:
                    days = int(hours / 24)
                    hours = hours - 24 * days
        return self.age_to_string(days, hours, minutes, seconds)


    def age_to_string(self, days, hours, minutes, seconds):
        s = ''
        if days > 0:
            s += str(int(days)) + ' '
            if days == 1:
                s += self.translate('Tag')
            else:
                s += self.translate('Tage')
            s += ', '
        if (hours > 0) or (s != ''):
            s += str(int(hours)) + ' '
            if hours == 1:
                s += self.translate('Stunde')
            else:
                s += self.translate('Stunden')
            s += ', '
        if (minutes > 0) or (s != ''):
            s += str(int(minutes)) + ' '
            if minutes == 1:
                s += self.translate('Minute')
            else:
                s += self.translate('Minuten')
            s += ', '
        if days > 0:
            s += str(int(seconds))
        else:
            s += str("%.2f" % seconds)
        s += ' ' + self.translate('Sekunden')
        return s


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
        if not len(self.plugin.mowers):
            device_count = 0
        else:
            device_count = len(self.plugin.mowers) 

        return tmpl.render(p=self.plugin, device_count=device_count, items_control=self.plugin._items_control, items_state=self.plugin._items_state, items_opdata=self.plugin._items_opdata)
        #return tmpl.render(p=self.plugin, device_count=len(self.plugin.mowers), items_control=self.plugin._items_control, items_state=self.plugin._items_state)

    @cherrypy.expose
    def mower_park(self):
        self.plugin._control_mower_park()

    @cherrypy.expose
    def mower_park_timer(self):
        self.plugin._control_mower_park_timer()

    @cherrypy.expose
    def mower_start(self):
        self.plugin._control_mower_start()

    @cherrypy.expose
    def mower_start_3h(self):
        self.plugin._control_mower_start_override_3h()

    @cherrypy.expose
    def mower_stop(self):
        self.plugin._control_mower_stop()


# ------------------------------------------
#    Communication API of the plugin
# ------------------------------------------
# credits to pyhusmow

class API:
    _API_IM = 'https://iam-api.dss.husqvarnagroup.net/api/v3/'
    _API_TRACK = 'https://amc-api.dss.husqvarnagroup.net/v1/'
    _API_TRACK_APP_V1 = 'https://amc-api.dss.husqvarnagroup.net/app/v1/'
    
    _HEADERS = {'Accept': 'application/json', 'Content-type': 'application/json'}

    def __init__(self):
        # self.logger = logging.getLogger("main.automower")
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.device_id = None
        self.token = None
        self.provider = None
        self.connection = None

    def login(self, login, password):
        response = self.session.post(self._API_IM + 'token',
                                     headers=self._HEADERS,
                                     json={
                                         "data": {
                                             "attributes": {
                                                 "password": password,
                                                 "username": login
                                             },
                                             "type": "token"
                                         }
                                     })

        try:
            response.raise_for_status()
            self.logger.info('Logged in successfully')
            self.connection="CONNECTED"
        except requests.exceptions.HTTPError as e:
            # requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://iam-api.dss.husqvarnagroup.net/api/v3/token

            status_code = e.response.status_code
            status_msg  = e.response.text
            self.logger.error("LOGIN FAILED: Status Code {0}: {1}".format(status_code,status_msg))
            self.connection="LOGIN FAILED"

        json = response.json()
        if json.get('errors'):
            self.logger.error("LOGIN FAILD: json has error message - no token set")
            return
        else:
            self.set_token(json["data"]["id"], json["data"]["attributes"]["provider"])
            return json["data"]["attributes"]["expires_in"]

    def logout(self):
        response = self.session.delete(self._API_IM + 'token/%s' % self.token)
        response.raise_for_status()
        self.device_id = None
        self.token = None
        del (self.session.headers['Authorization'])
        self.logger.info('Logged out successfully')
        self.connection="LOGGED OUT"

    def set_token(self, token, provider):
        self.token = token
        self.provider = provider
        self.session.headers.update({
            'Authorization': "Bearer " + self.token,
            'Authorization-Provider': provider
        })

    def list_robots(self):
        response = self.session.get(self._API_TRACK + 'mowers', headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def select_robot(self, mower):
        result = self.list_robots()
        if not len(result):
            raise CommandException('No mower found')
        if mower:
            for item in result:
                if item['name'] == mower or item['id'] == mower:
                    self.device_id = item['id']
                    break
            if self.device_id is None:
                raise CommandException('Could not find a mower matching %s' % mower)
        else:
            self.device_id = result[0]['id']

    # old function
    def status(self):
        response = self.session.get(self._API_TRACK + 'mowers/%s/status' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def poll_status_v1(self):
        response = self.session.get(self._API_TRACK_APP_V1 + 'mowers/%s/status' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def geo_status(self):
        response = self.session.get(self._API_TRACK + 'mowers/%s/geofence' % self.device_id, headers=self._HEADERS)
        response.raise_for_status()

        return response.json()

    def control_v1(self, command, duration=0):

        CMD = {
            'PARK'        : { 'url' : 'mowers/{device_id}/control/park',                  'json' : None },
            'PARK_TIMER'  : { 'url' : 'mowers/{device_id}/control/park/duration/timer',   'json' : None },
            'PARK_3H'     : { 'url' : 'mowers/{device_id}/control/park/duration/period',  'json' : { 'period': 180} },
            'PARK_6H'     : { 'url' : 'mowers/{device_id}/control/park/duration/period',  'json' : { 'period': 360} },
            'PARK_12H'    : { 'url' : 'mowers/{device_id}/control/park/duration/period',  'json' : { 'period': 720} },
            'START'       : { 'url' : 'mowers/{device_id}/control/start',                 'json' : None },
            'START_3H'    : { 'url' : 'mowers/{device_id}/control/start/override/period', 'json' : { 'period': 180} },
            'START_6H'    : { 'url' : 'mowers/{device_id}/control/start/override/period', 'json' : { 'period': 360} },
            'START_12H'   : { 'url' : 'mowers/{device_id}/control/start/override/period', 'json' : { 'period': 720} },
            'STOP'        : { 'url' : 'mowers/{device_id}/control/stop',                  'json' : None }
        }

        if command not in CMD:
            raise CommandException("Unknown command")        
 
        #TODO: set mower status to "sending command..."

        response = self.session.post(self._API_TRACK_APP_V1 + CMD[command]['url'].format(device_id=self.device_id),
                                     headers=self._HEADERS,
                                     json=CMD[command]['json'])
        response.raise_for_status()
        
        if (response.json()['status']=='OK'):
            return True
        else:
            #  ERROR on posting action command 'START_3H': errorCode=device.not.connected
            self.logger.error("ERROR on posting action command '{0}': errorCode={1}".format(command, response.json()['errorCode']))
            # self.logger.debug(json.dumps(response.json(), indent=4, sort_keys=True))


    def control(self, command):
        if command not in ['PARK', 'STOP', 'START']:
            raise CommandException("Unknown command")

        CMD = {
            'PARK'        : { 'url' : 'mowers/{device_id}/control',                  'json' : { 'action': 'PARK'} },
            'START'       : { 'url' : 'mowers/{device_id}/control',                  'json' : { 'action': 'START'} },
            'STOP'        : { 'url' : 'mowers/{device_id}/control',                  'json' : { 'action': 'STOP'} }
        }

        #response = self.session.post(self._API_TRACK + 'mowers/%s/control' % self.device_id,
        #                            headers=self._HEADERS,
        #                            json={
        #                                "action": command
        #                            })
        response = self.session.post(self._API_TRACK + CMD[command]['url'].format(device_id=self.device_id),
                                     headers=self._HEADERS,
                                     json=CMD[command]['json'])
        response.raise_for_status()
        
        if (response.json()['status']=='OK'):
            return True
        else:
            self.logger.error("ERROR on posting action command '{0}': errorCode={1}".format(command, response.json()['errorCode']))
            # self.logger.debug(json.dumps(response.json(), indent=4, sort_keys=True))
            return False


class Mower:

    # performance: flächenleistung in qm/h
    # chargetime: durchschnittliche Ladezeit in Minuten
    # mowtime: durchschnittliche Mähzeit in Minuten

    MOWERMODEL = {
        "TBD-1"    :   {'product' : 'AM105',     'name' : 'AUTOMOWER® 105',      'performance' : 43,  'chargetime' : 50, 'mowtime' : 70},
        "E"        :   {'product' : 'AM420',     'name' : 'AUTOMOWER® 420',      'performance' : 92,  'chargetime' : 55, 'mowtime' : 105},
        "TBD-3"    :   {'product' : 'AM440',     'name' : 'AUTOMOWER® 440',      'performance' : 167, 'chargetime' : 75, 'mowtime' : 240},
        "TBD-4"    :   {'product' : 'AM310',     'name' : 'AUTOMOWER® 310',      'performance' : 56,  'chargetime' : 50, 'mowtime' : 60},
        "TBD-5"    :   {'product' : 'AM315',     'name' : 'AUTOMOWER® 315',      'performance' : 68,  'chargetime' : 50, 'mowtime' : 60},
        "L"        :   {'product' : 'AM315X',    'name' : 'AUTOMOWER® 315X',     'performance' : 73,  'chargetime' : 50, 'mowtime' : 60},
        "G"        :   {'product' : 'AM430X',    'name' : 'AUTOMOWER® 430X',     'performance' : 133, 'chargetime' : 65, 'mowtime' : 135},
        "TBD-7"    :   {'product' : 'AM435XAWD', 'name' : 'AUTOMOWER® 435X AWD', 'performance' : 146, 'chargetime' : -1, 'mowtime' : -1},
        "TBD-8"    :   {'product' : 'AM450X',    'name' : 'AUTOMOWER® 450X',     'performance' : 208, 'chargetime' : 75, 'mowtime' : 260},
        "TBD-9"    :   {'product' : 'AM520',     'name' : 'AUTOMOWER® 520',      'performance' : 92,  'chargetime' : -1, 'mowtime' : -1},
        "TBD-A"    :   {'product' : 'AM535AWD',  'name' : 'AUTOMOWER® 535 AWD',  'performance' : 146, 'chargetime' : -1, 'mowtime' : -1},
        "TBD-B"    :   {'product' : 'AM550',     'name' : 'AUTOMOWER® 550',      'performance' : 208, 'chargetime' : -1, 'mowtime' : -1},
        "UNKNOWN"  :   {'product' : 'UKN',       'name' : 'no name yet',         'performance' : 0,   'chargetime' : -1, 'mowtime' : -1}
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._mower_id           = None
        self._mower_name         = None
        self._mower_model        = 'UNKNOWN' 

        self._last_activity      = MowerStatus()
        self._last_status        = MowerStatus() 

        self._activity_que       = deque(maxlen=20) 

        self._activity_timer     = {}

    def __str__(self):
        return "{0} [{1}] - {2}% ({3})".format(self.get_mower_name(), self.last_status().get_activity(), self.last_status().get_battery_percent(), self.last_status().get_updated_at_time())

    def new_status_from_json(self, json):
        new_status = MowerStatus()
        new_status.parse_status_from_json(json)
        return self.set_new_status(new_status)

    def set_new_status(self, new_status):    
        if (new_status.get_updated_at_timestamp() == self.last_status().get_updated_at_timestamp()):
            # same timestamp - no changes
            return False
        else:
            # new timestamp
            new_activity = new_status.get_activity()
            old_activity = self.last_status().get_activity() 

            last_status_starttime = self.last_status().get_updated_at_timestamp()
            if last_status_starttime > 0:
                timedelta = new_status.get_updated_at_timestamp() - last_status_starttime
            else: 
                timedelta = 0

            # update activity sum
            if old_activity in self._activity_timer:
                self._activity_timer[old_activity] += timedelta
            else:
                self._activity_timer[old_activity] = timedelta

            if (new_activity == old_activity):
                # new timestamp, same activity 
                pass

            else:
                # activity changed

                if (old_activity == "MOVING" and new_activity == "CUTTING"):
                    # take-off point
                    pass

                # update last history entry with timedelta
                if self._activity_que:
                    last_que_activity = self._activity_que[-1]
                    ts_start = last_que_activity.get_updated_at_timestamp()
                    ts_stop = new_status.get_updated_at_timestamp()
                    last_que_activity.set_timeDelta(ts_stop - ts_start)

                self._last_activity = new_status
                self._activity_que.append(new_status)

            self._last_status = new_status
            return True

    def get_mower_activities(self):
        return list(self._activity_que)

    # activity time in ms
    def get_mower_activity_time(self, activity):
        if activity in self._activity_timer:
            return self._activity_timer[activity]
        else:
            return -1

    def get_mower_id(self):
        return self._mower_id

    def get_mower_name(self):
        return self._mower_name

    def get_mower_model_name(self):
        return self.MOWERMODEL.get(self._mower_model, self.MOWERMODEL['UNKNOWN']).get('name')

    def get_mower_product_code(self):
        return self.MOWERMODEL.get(self._mower_model, self.MOWERMODEL['UNKNOWN']).get('product')

    def last_status(self):
        return self._last_status

    def parse_mower_from_json(self, json):
        # self.logger.debug(json.dumps(json, indent=4, sort_keys=True))
        if 'id' in json:
            self._mower_id      = json['id'] 
        else:
            self.logger.error("Id attribute not found in json: {0}".format(json))
        if 'name' in json:
            self._mower_name    = json['name']
        else:
            self.logger.error("Name attribute not found in json: {0}".format(json))
        if 'model' in json:
            self._mower_model   = json['model']
        else:
            self.logger.debug("Model attribute not found in json: {0}".format(json))

    def set_mower_activity_time(self, activity, time):
        self._activity_timer[activity.upper()] = int(time)
        return True

    def is_mower_connected(self):
        return self._last_status.is_connected()

class MowerStatus:

    # V1
    # "mowerStatus": {
    #    "activity": "PARKED_IN_CS","CHARGING","LEAVING","MOWING","NOT_APPLICABLE","GOING_HOME","UNKNOWN"
    #    "mode": "MAIN_AREA","HOME"
    #    "restrictedReason": "WEEK_SCHEDULE","NOT_APPLICABLE"
    #    "state": "RESTRICTED","IN_OPERATION","PAUSED","STOPPED"
    #    "type": "NOT_APPLICABLE","WEEK_SCHEDULE","OVERRIDE"
    #}

    STATUS = {
        "PARKED_PARKED_SELECTED"       :   {'color' :  '1874CD', 'activity' : 'PARKED',   'msg' : 'GEPARKT - Bis auf Weiteres'},
        "PARKED_TIMER"                 :   {'color' :  '1874CD', 'activity' : 'PARKED',   'msg' : 'GEPARKT - Nächste Startzeit {starttime_HM}'},
        "PARKED_AUTOTIMER"             :   {'color' :  '1874CD', 'activity' : 'PARKED',   'msg' : 'GEPARKT - Wettertimer, nächste Startzeit {starttime_HM}'},
        "COMPLETED_CUTTING_TODAY_AUTO" :   {'color' :  '1874CD', 'activity' : 'PARKED',   'msg' : 'GEPARKT - Wettertimer'},
        "OK_CUTTING"                   :   {'color' :  '38761D', 'activity' : 'CUTTING',  'msg' : 'MÄHEN - Mäheinsatz endet HH:MM'},
        "OK_CUTTING_NOT_AUTO"          :   {'color' :  '38761D', 'activity' : 'CUTTING',  'msg' : 'MÄHEN - Timer aufheben'},
        "OK_SEARCHING"                 :   {'color' :  '38761D', 'activity' : 'MOVING',   'msg' : 'MÄHEN - Auf dem Weg zur Ladestation'},
        "OK_LEAVING"                   :   {'color' :  '38761D', 'activity' : 'MOVING',   'msg' : 'MÄHEN - Verlässt Ladestation'},
        "OK_CHARGING"                  :   {'color' :  '1874CD', 'activity' : 'CHARGING', 'msg' : 'LADEN - Nächste Startzeit {starttime_HM}'},
        "PAUSED"                       :   {'color' :  'FFA500', 'activity' : 'PAUSED',   'msg' : 'PAUSIERT'},
        "OFF_HATCH_OPEN"               :   {'color' :  'FF0000', 'activity' : 'DISABLED', 'msg' : 'OFF_HATCH_OPEN'},
        "OFF_HATCH_CLOSED"             :   {'color' :  'FF0000', 'activity' : 'DISABLED', 'msg' : 'OFF_HATCH_CLOSED'},
        "ERROR"                        :   {'color' :  'FF0000', 'activity' : 'ERROR',    'msg' : 'ERROR'},
        "SENDCMD"                      :   {'color' :  'AAAAAA', 'activity' : 'UNKNOWN',  'msg' : 'Sende Befehl...'},
        "UNKNOWN"                      :   {'color' :  'FF0000', 'activity' : 'UNKNOWN',  'msg' : 'n.a.' }
    }

    STARTSOURCE = {
        "NO_SOURCE"                    :   {'id' :  1, 'title' : ''},
        "WEEK_TIMER"                   :   {'id' :  2, 'title' : ''},
        "MOWER_CHARGING"               :   {'id' :  2, 'title' : ''},
        "COMPLETED_CUTTING_TODAY_AUTO" :   {'id' :  2, 'title' : ''},
        "UNKNOWN"                      :   {'id' :  0, 'title' : 'n.a.' }
    }

    OPERATINGMODE = {
        "HOME"                         :   {'id' :  1, 'title' : ''},
        "AUTO"                         :   {'id' :  2, 'title' : ''},
        "UNKNOWN"                      :   {'id' :  0, 'title' : 'n.a.' }
    }

    MOWERERROR = {
        0                              :   {'msg' : 'no error', 'color' : '00FF00'},
        1                              :   {'msg' : 'outside mowing area', 'color' : 'FFA500'},
        2                              :   {'msg' : 'no loop signal', 'color' : 'FF0000'},
        4                              :   {'msg' : 'Problem loop sensor front', 'color' : 'FF0000'},
        5                              :   {'msg' : 'Problem loop sensor rear', 'color' : 'FF0000'},
        6                              :   {'msg' : 'Problem loop sensor', 'color' : 'FF0000'},
        7                              :   {'msg' : 'Problem loop sensor', 'color' : 'FF0000'},
        8                              :   {'msg' : 'wrong PIN-code', 'color' : '9932CC'},
        9                              :   {'msg' : 'locked in', 'color' : '1874CD'},
       10                              :   {'msg' : 'upside down', 'color' : '1874CD'},
       11                              :   {'msg' : 'low battery', 'color' : '1874CD'},
       12                              :   {'msg' : 'battery empty', 'color' : 'FFA500'},
       13                              :   {'msg' : 'no drive', 'color' : '1874CD'},
       15                              :   {'msg' : 'Mower raised', 'color' : '1874CD'},
       16                              :   {'msg' : 'trapped in charging station', 'color' : 'FFA500'},
       17                              :   {'msg' : 'charging station blocked', 'color' : 'FFA500'},
       18                              :   {'msg' : 'Problem shock sensor rear', 'color' : 'FF0000'},
       19                              :   {'msg' : 'Problem shock sensor front', 'color' : 'FF0000'},
       20                              :   {'msg' : 'Wheel motor blocked on the right', 'color' : 'FF0000'},
       21                              :   {'msg' : 'Wheel motor blocked on the left', 'color' : 'FF0000'},
       22                              :   {'msg' : 'Drive problem left', 'color' : 'FF0000'},
       23                              :   {'msg' : 'Drive problem right', 'color' : 'FF0000'},
       24                              :   {'msg' : 'Problem mower engine', 'color' : 'FF0000'},
       25                              :   {'msg' : 'Cutting system blocked', 'color' : 'FFA500'},
       26                              :   {'msg' : 'Faulty component connection', 'color' : 'FF0000'},
       27                              :   {'msg' : 'default settings', 'color' : 'FF0000'},
       28                              :   {'msg' : 'Memory defective', 'color' : 'FF0000'},
       30                              :   {'msg' : 'battery problem', 'color' : 'FF0000'},
       31                              :   {'msg' : 'STOP-button problem', 'color' : 'FF0000'},
       32                              :   {'msg' : 'tilt sensor problem', 'color' : 'FF0000'},
       33                              :   {'msg' : 'Mower tilted', 'color' : '1874CD'},
       35                              :   {'msg' : 'Wheel motor overloaded right', 'color' : 'FF0000'},
       36                              :   {'msg' : 'Wheel motor overloaded left', 'color' : 'FF0000'},
       37                              :   {'msg' : 'Charging current too high', 'color' : 'FF0000'},
       38                              :   {'msg' : 'Temporary problem', 'color' : 'FF0000'},
       42                              :   {'msg' : 'limited cutting height range', 'color' : 'FF0000'},
       43                              :   {'msg' : 'unexpected cutting height adjustment', 'color' : 'FF0000'},
       44                              :   {'msg' : 'unexpected cutting height adjustment', 'color' : 'FF0000'},
       45                              :   {'msg' : 'Problem drive cutting height', 'color' : 'FF0000'},
       46                              :   {'msg' : 'limited cutting height range', 'color' : 'FF0000'},
       47                              :   {'msg' : 'Problem drive cutting height', 'color' : 'FF0000'},

       74                              :   {'msg' : 'Alarm! Außerhalb der geogr. Eingr.', 'color' : 'FF0000'},
       78                              :   {'msg' : 'Kein Antrieb, steckt fest', 'color' : 'FF0000'},

       99                              :   {'msg' : 'unkown Error code ({errorCode})', 'color' : 'FF0000'}
    }

    def __init__(self):
        self._batteryPercent     = -1
        self._connected          = False 
        self._lastErrorCode      = 0
        self._lastErrorTimestamp = None
        self._lastLocations      = []
        self._latitude           = None
        self._longitude          = None
        self._mowerStatus        = 'UNKNOWN'
        self._nextStartSource    = 'UNKNOWN'
        self._nextStartTimestamp = None 
        self._operatingMode      = 'UNKNOWN' 
        self._settingsUUID       = None
        self._showAsDisconnected = False
        self._updatedAtTimestamp = 0
        self._valueFound         = False

        self._timeDelta          = 0 

    def __str__(self):
        return "[{0}] - {1}% ({2})".format(self.get_activity(), self.get_battery_percent(), self.get_updated_at_time())

    def parse_status_from_json(self, json):
        # self.logger.debug(json.dumps(json, indent=4, sort_keys=True))
        self._batteryPercent     = json['batteryPercent']
        self._connected          = json['connected']
        self._lastErrorCode      = json['lastErrorCode']
        self._lastErrorTimestamp = json['lastErrorCodeTimestamp']
        self._lastLocations      = json['lastLocations']
        self._latitude           = json['lastLocations'][0]['latitude']
        self._longitude          = json['lastLocations'][0]['longitude']
        self._mowerStatus        = json['mowerStatus']
        self._nextStartSource    = json['nextStartSource']
        self._nextStartTimestamp = json['nextStartTimestamp']
        self._operatingMode      = json['operatingMode']
        self._settingsUUID       = json['cachedSettingsUUID']
        self._showAsDisconnected = json['showAsDisconnected']
        self._updatedAtTimestamp = json['storedTimestamp']
        self._valueFound         = json['valueFound']

        return True

    def get_activity(self):
        return self.STATUS.get(self._mowerStatus, self.STATUS['UNKNOWN']).get('activity')

    def get_activity_color(self):
        return self.STATUS.get(self._mowerStatus, self.STATUS['UNKNOWN']).get('color')

    def get_activity_msg(self):
        return self.STATUS.get(self._mowerStatus, self.STATUS['UNKNOWN']).get('msg')

    def get_battery_percent(self):
        return self._batteryPercent

    def get_last_coordinates(self):
        coordinates = []
        for location in self._lastLocations:
            coordinates.append("[{0},{1}]".format(location['longitude'],location['latitude']))
        return "[" + ",".join(coordinates) + "]"

    def get_last_error_message(self):
        return self.MOWERERROR.get(self._lastErrorCode, self.MOWERERROR[99]).get('msg').format(errorCode=self._lastErrorCode)

    def get_last_error_time(self):
        return datetime.utcfromtimestamp(self._lastErrorTimestamp).strftime('%Y-%m-%d %H:%M:%S')

    def get_latitude(self):
        return self._latitude

    def get_longitude(self):
        return self._longitude

    def get_next_start_time(self):
        return datetime.utcfromtimestamp(self._nextStartTimestamp).strftime('%Y-%m-%d %H:%M:%S') 

    def get_next_start_time_HMS(self):
        return datetime.utcfromtimestamp(self._nextStartTimestamp).strftime('%H:%M:%S')

    def get_next_start_time_HM(self):
        return datetime.utcfromtimestamp(self._nextStartTimestamp).strftime('%H:%M') 

    def get_status_message(self):
        if self._mowerStatus == "ERROR":
            message_template = self.get_last_error_message()
        else:
            message_template = self.STATUS.get(self._mowerStatus, self.STATUS['UNKNOWN']).get('msg')

        starttime_YMDHMS = self.get_next_start_time() 
        starttime_HMS = self.get_next_start_time_HMS() 
        starttime_HM = self.get_next_start_time_HM() 
        return message_template.format(starttime_YMDHMS=starttime_YMDHMS, starttime_HMS=starttime_HMS, starttime_HM=starttime_HM)

    def get_timeDelta(self):
        return self._timeDelta

    def get_updated_at_timestamp(self):
        return self._updatedAtTimestamp

    def get_updated_at_time(self):
        return datetime.fromtimestamp(self._updatedAtTimestamp/1000).strftime('%Y-%m-%d %H:%M:%S')

    def is_connected(self):
        return self._connected

    def set_timeDelta(self, timedelta):
        self._timeDelta = int(timedelta)
        return True


class MowerStatusV2(Mower):

    def __init__(self):
        super().__init__()

