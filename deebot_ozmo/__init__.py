#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-      Serge Wagener                serge@wagener.family
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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

from jinja2 import Environment, FileSystemLoader
import cherrypy
from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items
from lib.network import Http
import datetime

#_LOGGER = logging.getLogger(__name__)

import string
import random
from deebotozmo import *


class DeebotOzmo(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    # (must match the version specified in plugin.yaml)
    PLUGIN_VERSION = '1.7.1'

# ----------------------------------------------------
#    SmartHomeNG plugin methods
# ----------------------------------------------------

    def __init__(self, sh):
        """
        Initalizes the plugin.
        """
        self.logger.debug("Init method called")
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._items = []
        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._account = self.get_parameter_value('account')
        self._password = EcoVacsAPI.md5(self.get_parameter_value('password'))
        self._wanted_device = self.get_parameter_value('device')

        self.mybot = {
            'nick': None,
            'did': None,
            'country': self.get_parameter_value('country').lower(),
            'continent': self.get_parameter_value('continent').lower(),
            'model': None,
            'iconURL': None,
            'live_map': None,
            'last_clean_logs': [],
            'last_clean_map': None,
            'available': False,
            'battery_level': 0,
            'state': None,
            'state_text': None,
            'fan_speed': None,
            'water_level': None,
            'components': [],
            'rooms': []
        }

        # Check if country and continent defined, if not try to autolocate
        http = Http()
        if not self.mybot['country'] or not self.mybot['continent']:
            _locate = http.get_json('http://ip-api.com/json?fields=continentCode,countryCode')
        if not self.mybot['country']:
            if _locate and _locate['countryCode']:
                self.logger.info('Autodetected country: {}'.format(_locate['countryCode']))
                self._update_items('country', _locate['countryCode'].lower())
            else:
                self.logger.error('No country defined and autolocate not possible, please specify country in plugin configuration !')
                self._init_complete = False
                return
        
        if not self.mybot['continent']:
            if _locate and _locate['continentCode']:
                self.logger.info('Autodetected continent: {}'.format(_locate['continentCode']))
                self._update_items('continent', _locate['continentCode'].lower())
            else:
                self.logger.error('No continent defined and autolocate not possible, please specify continent in plugin configuration !')
                self._init_complete = False
                return

        self.device = None
        self._device_id = "".join(random.choice(
            string.ascii_uppercase + string.digits) for _ in range(16))
        self._cycle = self.get_parameter_value('interval')
        self._items = {}

        if not self.init_webinterface():
            self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add('poll_device', self.poll_device, cycle=5)

        # Connect to API
        self.api = EcoVacsAPI(self._device_id, self._account,
                              self._password, self.mybot['country'], self.mybot['continent'])

        # Find wanted device, use first device if none specified
        self.devices = self.api.devices()
        for device in self.devices:
            if not device['nick']:
                device['nick'] = device['did']
            self.logger.info('Found device {} with ID {}'.format(
                device['nick'], device['did']))
            if (device['nick'].lower() == self._wanted_device.lower()):
                self.logger.info(
                    'Using wanted device {} for this instance !'.format(device['nick']))
                self.device = device
                break

        if not self.device:
            self.device = self.devices[0]
            if not self.device['nick']:
                self.device['nick'] = self.device['did']
            self.logger.info('Using device {} for this instance !'.format(device['nick']))
        #self.logger.debug(self.device)
        
        self._update_items('nick', self.device['nick'])
        self._update_items('did', self.device['did'])

        self.vacbot = VacBot(self.api.uid, self.api.REALM, self.api.resource,
                             self.api.user_access_token, self.device, self.mybot['continent'])
        self.vacbot.connect_and_wait_until_ready()
        self.iotProduct = self.getIotProduct()
        self.vacbot.request_all_statuses()
        self.vacbot.setScheduleUpdates(self._cycle)
        self.poll_device()

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.vacbot.disconnect()
        self.alive = False

    def parse_item(self, item):
        """
        Parse items into internal array on plugin startup
        """

        if self.has_iattr(item.conf, 'deebot_ozmo'):
            #self.logger.debug("parse item: {}".format(item.id()))
            _item = self.get_iattr_value(item.conf, 'deebot_ozmo')
            # Add items to internal array
            if not _item in self._items:
                self._items[_item] = []
            self._items[_item].append(item)
            return self.update_item

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

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            if self.has_iattr(item.conf, 'deebot_ozmo') and item():
                _cmd = self.get_iattr_value(item.conf,'deebot_ozmo')
                self.logger.debug('Command: {}'.format(_cmd))
                item(False, self.get_shortname())
                if _cmd == 'cmd_clean':
                    self.logger.info('Start cleaning')
                    self.clean()
                elif _cmd == 'cmd_pause':
                    self.logger.info('Pause cleaning')
                    self.pause()
                elif _cmd == 'cmd_stop':
                    self.logger.info('Stop cleaning')
                    self.stop()
                elif _cmd == 'cmd_charge':
                    self.logger.info('Returning to charging station')
                    self.charge()
                elif _cmd == 'cmd_locate':
                    self.logger.info('Locating device')
                    self.locate()
                else:
                    self.logger.warning('Unknown command {}'.format(_cmd))

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
            self.logger.warning(
                "Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
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

# ----------------------------------------------------
#    Commands to actively control the Deebot Ozmo
# ----------------------------------------------------

    def locate(self):
        """
        Play a sound to locate your Deebot
        """
        self.vacbot.PlaySound()
        return True

    def clean(self):
        """
        Start cleaning
        """
        self.vacbot.Clean()
        return True
    
    def clean_spot_area(self, area):
        """
        Start cleaning predefined area
        """
        self.vacbot.SpotArea(area)
        return True

    def pause(self):
        """
        Pause cleaning
        """
        self.vacbot.CleanPause()
        return True

    def resume(self):
        """
        Resume cleaning
        """
        self.vacbot.CleanResume()
        return True

    def charge(self):
        """
        Send Deebot back to charger
        """
        self.vacbot.Charge()
        return True

    def set_fan_speed(self, speed):
        """
        Change fan speed / suction power
        """
        try:
            _speed = FAN_SPEED_TO_ECOVACS[speed]
            self.logger.debug('Changing fan speed to {} - {}'.format(speed, _speed))
            self.vacbot.SetFanSpeed(speed)
        except KeyError:
            self.logger.warning('Unknown speed {}'.format(speed))
            return False
        return True

    def set_water_level(self, level):
        """
        Change water level
        """
        try:
            _level = WATER_LEVEL_TO_ECOVACS[level]
            self.logger.debug('Changing water level to {} - {}'.format(level, _level))
            self.vacbot.SetWaterLevel(level)
        except KeyError:
            self.logger.warning('Unknown water level {}'.format(level))
            return False
        return True

# ----------------------------------------------------
#    Methods to poll robot and update items
# ----------------------------------------------------

    def _update_items(self, attribute, value):
        # self.logger.debug('Updating {} with value {}'.format(attribute, value))
        self.mybot[attribute] = value
        if attribute in self._items:
            for _item in self._items[attribute]:
                _item(value, self.get_shortname())
    
    def getIotProduct(self):
        iotproducts = self.api.getiotProducts()
        for iotProduct in iotproducts:
            if self.device['class'] in iotProduct['classid']:
                if 'product' in iotProduct and 'name' in iotProduct['product']:
                    self._update_items('model', iotProduct['product']['name'])
                if 'product' in iotProduct and 'iconUrl' in iotProduct['product']:
                    self._update_items('iconURL', iotProduct['product']['iconUrl'])
                return iotProduct
        return None

    def poll_device(self):
        """
        Polls for updates of the device
        """
        self._update_items('available', self.vacbot.is_available)
        self._update_items('state', self.vacbot.vacuum_status)
        self._update_items('state_text', self.translate(self.vacbot.vacuum_status))
        self._update_items('battery_level', self.vacbot.battery_status)
        self._update_items('fan_speed', self.vacbot.fan_speed)
        self._update_items('fan_speed_text', self.translate(self.vacbot.fan_speed))
        self._update_items('water_level', self.vacbot.water_level)
        self._update_items('water_level_text', self.translate(self.vacbot.water_level))
        self._update_items('rooms', self.vacbot.getSavedRooms())
        self._update_items('last_clean_logs', self.vacbot.lastCleanLogs)
        self._update_items('last_clean_map', self.vacbot.last_clean_image)
    
        if self.vacbot.live_map:
            self._update_items('live_map', self.vacbot.live_map.decode("utf-8"))
       
        # Update components lifespan if available
        try:
            self._update_items('components', self.vacbot.components)
            self._update_items('brush', round(self.vacbot.components['brush']))
            self._update_items('sideBrush', round(self.vacbot.components['sideBrush']))
            self._update_items('filter', round(self.vacbot.components['heap']))
        except KeyError:
            pass

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------


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
        self.tplenv.filters['dateformat'] = self.dateformat
        self.tplenv.filters['timeformat'] = self.timeformat
        self.items = Items.get_instance()


    @cherrypy.expose
    def index(self, reload=None, cmd=None, speed=None, level=None, type=None, id=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if cmd:
            self.logger.debug('Command: {}'.format(cmd))
            if cmd == 'clean':
                self.logger.info("WebIf: Start cleaning")
                self.plugin.clean()
            elif cmd == 'clean_room':
                self.logger.info("WebIf: Start cleaning {} (id: {})".format(type, id))
                self.plugin.clean(id)
            elif cmd == 'pause':
                self.logger.info("WebIf: Pause cleaning")
                self.plugin.pause()
            elif cmd == 'charge':
                self.logger.info("WebIf: Return to charging station")
                self.plugin.charge()
            elif cmd == 'locate':
                self.logger.info("WebIf: Locating robot")
                self.plugin.locate()
            elif cmd == 'set_fan_speed':
                self.logger.info("WebIf: Update fan speed to {}".format(speed))
                self.plugin.set_fan_speed(speed)
            elif cmd == 'set_water_level':
                self.logger.info("WebIf: Update water level to {}".format(level))
                self.plugin.set_water_level(level)
            else:
                self.logger.warning('Unknown command: {}'.format(cmd))

        # get list of items with the attribute knx_dpt
        plgitems = []
        for item in self.items.return_items():
            if 'deebot_ozmo' in item.conf:
                plgitems.append(item)

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(plgitems, key=lambda k: str.lower(k['_path'])))

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            data = {}
            data['mybot'] = self.plugin.mybot
            # return it as json the the web page
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
        return {}

    # Jinja2 filter to format int timestamp as string
    def dateformat(self, timestamp):
        try:
            _datetime = datetime.datetime.fromtimestamp(timestamp)
            result = _datetime.strftime("%d/%m/%Y")
        except:
            result = 'ERROR'
        return result
    
    def timeformat(self, timestamp):
        try:
            _datetime = datetime.datetime.fromtimestamp(timestamp)
            result = _datetime.strftime("%H:%M:%S")
        except:
            result = 'ERROR'
        return result