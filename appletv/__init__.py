#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018- Serge Wagener                     serge@wagener.family
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

import asyncio
import datetime
import os
import pyatv
import threading
from random import randint

KNOWN_ATTRIBUTES = ['play_state', 'play_state_string', 'playing'
                    , 'media_type', 'media_type_string'
                    , 'title', 'album', 'artist', 'genre'
                    , 'position', 'total_time', 'position_percent'
                    , 'repeat', 'repeat_string', 'shuffle'
                    , 'artwork_url', 'name']

KNOWN_COMMANDS = ['rc_top_menu', 'rc_menu'
                    , 'rc_select', 'rc_left', 'rc_up', 'rc_down', 'rc_right'
                    , 'rc_previous', 'rc_play', 'rc_pause', 'rc_stop', 'rc_next']

MEDIA_TYPE = {1:'Unknown', 2:'Video', 3:'Music', 4:'TV'}
PLAY_STATE = {0:'idle', 1:'no media', 2:'loading', 3:'paused', 4:'playing', 5:'fast forward', 6:'fast backward'}
REPEAT_STATE = {0:'Off', 1:'Track', 2:'All'}

class AppleTV(SmartPlugin):

    PLUGIN_VERSION='1.5.1'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.yaml.
        """
        self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self._name = 'Unknown'
        self._device_id = None
        self._ip = self.get_parameter_value('ip')
        self._login_id = self.get_parameter_value('login_id')

        self._atv_scan_timeout = 5
        self._atv_reconnect_timeout = 10
        self._atv_device = pyatv.AppleTVDevice(self._name, self._ip, self._login_id)
        self._atv = None
        
        self._items = {}
        self._loop = asyncio.get_event_loop()
        self._push_listener_loop = None
        self._cycle = 5
        self._scheduler_running = False
        self._playstatus = None
        self._is_playing = False
        self._position = 0
        self._position_timestamp = None 
        self._credentials = None
        self._credentialsfile = None
        self._credentials_verified = False
        self.__push_listener_thread = None

        self.init_webinterface()
        return

    def run(self):
        """
        Run method for the plugin
        """        
        self._loop.run_until_complete(self.discover())
        self._loop.run_until_complete(self.connect())
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
        self._loop.stop()
        while self._loop.is_running():
            pass
        self._loop.run_until_complete(self.disconnect())
        self._loop.close()
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'atv'):
            attribute = self.get_iattr_value(item.conf, 'atv')
            self.logger.debug("Plugin '{}': parse item: {} info: {}".format(self.get_fullname(), item, attribute))
            if (attribute is None):
                return None
            elif (attribute not in KNOWN_ATTRIBUTES and attribute not in KNOWN_COMMANDS):
                self.logger.info("Unknown attribute {} for item {}".format(attribute, item))
                return None
            else:
                self._items[attribute] = item
                return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def execute_rc(self, command):
        if (command in KNOWN_COMMANDS):
            command = command[3:]
            self.logger.info("Sending remote command {} to Apple TV {}".format(command, self._name))
            if hasattr(self._atv_rc, command):
                self._loop.create_task(getattr(self._atv_rc, command)())
            else:
                self.logger.error("Coroutine {} not found".format(command))
        else:
            self.logger.warning("Unknown remote command {}, ignoring".format(command))
            return
 
    def update_item(self, item, caller=None, source=None, dest=None):
      if caller != self.get_shortname():
            if self.has_iattr(item.conf, 'atv'):
                # Plugin 'update_item was called with item 'atv.wohnzimmer.position_percent' and value 22 from caller 'Visu',
                self.logger.debug("update_item was called with item '{}' and value {} from caller '{}', source '{}' and dest '{}'".format(item, item(), caller, source, dest))
                attribute = self.get_iattr_value(item.conf, 'atv')  
                if (attribute == 'position_percent'):
                    if self._playstatus.total_time and self._playstatus.total_time > 0:
                        percentage = item()
                        playtime = self._playstatus.total_time
                        position = playtime * percentage / 100
                        self.logger.debug("Setting position to {}% = {}/{}".format(percentage, position, playtime))
                        self._loop.create_task(self._atv_rc.set_position(position))
                    else:
                        if 'position_percent' in self._items:
                            self._items['position_percent'](0, self.get_shortname(), self._name)
                elif (attribute == 'shuffle'):
                    self._loop.create_task(self._atv_rc.set_shuffle(item()))
                elif (attribute == 'repeat'):
                    self._loop.create_task(self._atv_rc.set_repeat(item()))
                elif (attribute in KNOWN_COMMANDS):
                    self.execute_rc(attribute)
                    item(False, self.get_shortname(), self._name)     
            pass

    async def discover(self):
        """
        Discovers Apple TV's on local mdns domain       
        """
        self.logger.debug("Discovering Apple TV's in your network")
        self._atvs = await pyatv.scan_for_apple_tvs(self._loop, timeout=self._atv_scan_timeout, only_home_sharing=False)
                
        if not self._atvs:
            self.logger.warning("No Apple TV found")
        else:
            self._atvs = sorted(self._atvs)
            self.logger.info("Found {} Apple TV's:".format(len(self._atvs)))
            for _atv in self._atvs:
                self.logger.info(" - {}, IP: {}, Login ID: {}".format(_atv.name, _atv.address, _atv.login_id))
                if str(_atv.address) == str(self._ip):
                    self._name = _atv.name
                    if self._login_id is None:
                        self._login_id = _atv.login_id
        
    async def connect(self):
        """
        Connects to this instance's Apple TV     
        """
        if str(self._ip) == '0.0.0.0':
            if len(self._atvs) > 0:
                self.logger.debug("No device given in plugin.yaml, using first autodetected device")
                self._atv_device = self._atvs[0]
                self._name = self._atv_device.name
                self._login_id = self._atv_device.login_id
                self._ip = self._atv_device.address
            else:
                return False
        self.logger.info("Connecting to '{0}' on ip '{1}'".format(self._name, self._ip))
        if 'name' in self._items:
            self._items['name'](self._name, self.get_shortname(), self._name)
        if self._login_id is None:
            self.logger.error("Cannot connect to Apple TV {}, homesharing seems to be disabled ?".format(self._name))
            return False
        else:
            self._atv = pyatv.connect_to_apple_tv(self._atv_device, self._loop)
            self._atv_rc = self._atv.remote_control
            self._device_id = self._atv.metadata.device_id
            self._credentialsfile = os.path.join(os.path.dirname(__file__), '{}.credentials'.format(self._device_id))
            try:
                _credentials = open(self._credentialsfile, 'r')
                self._credentials = _credentials.read()
                await self._atv.airplay.load_credentials(self._credentials)
                self.logger.debug("Credentials read: {}".format(self._credentials))
            except:
                _credentials = open(self._credentialsfile, 'w')
                self._credentials = await self._atv.airplay.generate_credentials()
                await self._atv.airplay.load_credentials(self._credentials)
                _credentials.write(self._credentials)
                self.logger.debug("Credentials written: {}".format(self._credentials))
            finally:
                try:
                    await self._atv.airplay.verify_authenticated()
                    self._credentials_verified = True
                except:
                    self._credentials_verified = False
                    self.logger.info("Credentials for {} are not yet verified, airplay not possible".format(self._name))
                _credentials.close()
            self._push_listener_thread = threading.Thread(target=self._push_listener_thread_worker, name='ATV listener')
            self._push_listener_thread.start()
        return True
    
    async def update_artwork(self):
        _url = await self._atv.metadata.artwork_url()
        self.logger.debug("Artwork: {}".format(_url))
        if 'artwork_url' in self._items:
            if self._items['play_state']() == pyatv.const.PLAY_STATE_PLAYING:
                self._items['artwork_url'](_url + '&rand=' + str(randint(10000, 99999)), self.get_shortname(), self._name)
            else:
                self._items['artwork_url']('//:0?rand=' + str(randint(10000, 99999)), self.get_shortname(), self._name)

    async def disconnect(self):
        """
        Stop listening to push updates and logout of this istances Apple TV     
        """
        self.logger.info("Disconnecting from '{0}'".format(self._name))
        await self._atv.push_updater.stop()
        await self._atv.logout()


    def update_position(self, new_position, from_device):
        self._position = new_position
        if from_device:
            self._position_timestamp = datetime.datetime.now()            
        if 'position' in self._items:
            self._items['position'](self._position, self.get_shortname(), self._name)
        if 'position_percent' in self._items:
            if self._position > 0:
                self._items['position_percent'](int(round(self._position / self._playstatus.total_time * 100)), self.get_shortname(), self._name)
            else:
                self._items['position_percent'](0, self.get_shortname(), self._name)

    def _push_listener_thread_worker(self):
        """
        Thread to run asyncio loop. This avoids blocking the main plugin thread
        """
        asyncio.set_event_loop(self._loop)
        self._atv.push_updater.listener = self
        self._atv.push_updater.start()
        while self._loop.is_running():
            pass
        try:
            self.logger.debug("Loop running")
            _cycle = 0
            while True:
                self._loop.run_until_complete(asyncio.sleep(0.25))
                _cycle += 1
                if _cycle >= 5:
                    if self._is_playing:
                        time_passed = int(round((datetime.datetime.now() - self._position_timestamp).total_seconds()))
                        self.update_position(self._playstatus.position + time_passed, False)
                    _cycle = 0
        except:
            return
            self.logger.debug('*** Error in loop.run_forever()')
            raise

    def playstatus_update(self, updater, playstatus):
        """
        Callback for pyatv, is called on currently playing update
        """
        self._loop.create_task(self.update_artwork())
        self._playstatus = playstatus
        if 'play_state' in self._items:
            self._items['play_state'](playstatus.play_state, self.get_shortname(), self._name)
        if 'play_state_string' in self._items:
            self._items['play_state_string'](PLAY_STATE[playstatus.play_state], self.get_shortname(), self._name)
        if 'media_type' in self._items:
            self._items['media_type'](playstatus.media_type, self.get_shortname(), self._name)
        if 'media_type_string' in self._items:
            self._items['media_type_string'](MEDIA_TYPE[playstatus.media_type], self.get_shortname(), self._name)
        if 'album' in self._items:
            self._items['album'](playstatus.album if playstatus.album is not None else 'No album', self.get_shortname(), self._name)
        if 'artist' in self._items:
            self._items['artist'](playstatus.artist if playstatus.artist is not None else 'No artist', self.get_shortname(), self._name)
        if 'genre' in self._items:
            self._items['genre'](playstatus.genre if playstatus.genre is not None else 'No genre', self.get_shortname(), self._name)
        if 'title' in self._items:
            self._items['title'](playstatus.title if playstatus.title is not None else 'No title', self.get_shortname(), self._name)
        if 'total_time' in self._items:
            self._items['total_time'](playstatus.total_time, self.get_shortname(), self._name)
        if 'repeat' in self._items:
            self._items['repeat'](playstatus.repeat, self.get_shortname(), self._name)
        if 'repeat_string' in self._items and playstatus.repeat is not None:
            self._items['repeat_string'](REPEAT_STATE[playstatus.repeat], self.get_shortname(), self._name)
        if 'shuffle' in self._items:
            self._items['shuffle'](playstatus.shuffle, self.get_shortname(), self._name)      
        if 'playing' in self._items:
            if playstatus.play_state == pyatv.const.PLAY_STATE_PLAYING:
                self._is_playing = True
            else:
                self._is_playing = False
            self._items['playing'](self._is_playing, self.get_shortname(), self._name)
        self.update_position(self._playstatus.position, True)

    def playstatus_error(self, updater, exception):
        """
        Callback for pyatv, is called on push update error
        """
        self.logger.warning("PushListener error, retrying in {0} seconds".format(self._atv_reconnect_timeout))
        updater.start(initial_delay=self._atv_reconnect_timeout)

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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
    #    Methods to be used in logics
    # ------------------------------------------

    def is_playing(self):
        return self._is_playing

    def pause(self):
        self._loop.create_task(self._atv_rc.pause())

    def play(self):
        self._loop.create_task(self._atv_rc.play())

    def play_url(self, url):
        self.logger.info('Playing {}'.format(url))
        try:
            self._loop.create_task(self._atv.airplay.play_url(url))
        except:
            pass


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
        self.pinentry = False

    def auth_callback(self, future):
        try:
            accepted = future.result()
            if accepted:
                self.plugin._credentials_verified = True
                self.plugin.logger.info("Authentication done")
        except  pyatv.exceptions.DeviceAuthenticationError as e:
            self.plugin._credentials_verified = False
            self.plugin.logger.error("Authentication error, wrong PIN ?")
        except Exception as e:
            self.plugin._credentials_verified = False
            self.plugin.logger.error("Authentication error: {}".format(str(e)))
 
    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy
        
        Render the template and return the html file to be delivered to the browser
            
        :return: contents of the template after beeing rendered 
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, pinentry=self.pinentry)

    @cherrypy.expose
    def button_pressed(self, button = None, pin = None):
        if button == "discover":
            self.plugin._loop.create_task(self.plugin.discover())
        elif button == "start_authorization":
            self.pinentry = True
            self.plugin._loop.create_task(self.plugin._atv.airplay.start_authentication())
        elif button == "finish_authorization":
            self.pinentry = False
            task = self.plugin._loop.create_task(self.plugin._atv.airplay.finish_authentication(pin))
            task.add_done_callback(self.auth_callback)
        else:
            self.logger.warning("Unknown button pressed in webif: {}".format(button))
        raise cherrypy.HTTPRedirect('index')
