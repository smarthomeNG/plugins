#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG.
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
#########################################################################

import logging
from lib.model.smartplugin import *
import threading
import datetime

try:
    import RPi.GPIO as GPIO
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False

class Raspi_GPIO(SmartPlugin):
    PLUGIN_VERSION = "1.4.1"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh):
        self.logger = logging.getLogger(__name__)
        self.init_webinterface()
        self._name = self.get_fullname()
        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error("{}: Unable to import Python package 'GPIO'".format(self._name))
            self._init_complete = False
            return
        try:
            self._items = []
            self._itemsdict = {}
            self._initdict = {}
            self._mode = self.get_parameter_value('mode').upper()
            GPIO.setwarnings(False)
            if self._mode == "BCM":
                GPIO.setmode(GPIO.BCM)
            else:
                GPIO.setmode(GPIO.BOARD)
            self.logger.debug("{}: Mode set to {}".format(self._name, self._mode))
            self.alive = False
            self._lock = threading.Lock()
        except Exception:
            self._init_complete = False
            return


    def get_sensors(self, sensor):
        try:
            value = GPIO.input(sensor)
            self._itemsdict[sensor](value, 'GPIO', 'get_sensors')
            self.logger.info("{}: SENSOR READ: {}  VALUE: {}".format(self._name, sensor, value))
        except Exception as e:
            self.logger.warning("{}: Problem reading sensor: {}".format(self._name, e))

    def run(self):
        self.logger.debug("{}: run method called")
        self.alive = True
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                sensor = int(self.get_iattr_value(item.conf, 'gpio_in'))
                try:
                    value = GPIO.input(sensor)
                    self._initdict[sensor] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                except Exception:
                    self._initdict[sensor] = False
                item(value, 'GPIO', 'gpio_init')
                GPIO.add_event_detect(sensor, GPIO.BOTH, callback=self.get_sensors)
                self.logger.info("{}: Adding Event Detection for Pin {}. Initial value is {}".format(
                    self._name, sensor, value))

    def stop(self):
        self.alive = False
        GPIO.cleanup()
        self.logger.debug("{}: cleaned up".format(self._name))


    def parse_item(self, item):
        if self.has_iattr(item.conf, 'gpio_in'):
            in_pin = int(item.conf['gpio_in'])
            GPIO.setup(in_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.logger.debug("{}: INPUT {} assigned to pin \'{}\'".format(self._name, item, in_pin))
            self._items.append(item)
            self._itemsdict[in_pin] = item
            return self.update_item
        if self.has_iattr(item.conf, 'gpio_out'):
            out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
            GPIO.setup(out_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._itemsdict[out_pin] = item
            value = GPIO.input(out_pin)
            item(value, 'GPIO', 'gpio_init')
            GPIO.add_event_detect(out_pin, GPIO.BOTH, callback=self.get_sensors)
            self.logger.info("{}: Adding Event Detection for Output Pin {}. Initial value is {}".format(
                self._name, out_pin, value))
            GPIO.setup(out_pin, GPIO.OUT)
            self.logger.debug("{}: OUTPUT {} assigned to \'{}\'".format(self._name, item, out_pin))
            if (out_pin is None):
                return None
                self.logger.debug("{}: No out_pin set for item {}".format(self._name, item))
            else:
                self._items.append(item)
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        self.logger.debug("{}: Trying to update {}.".format(self._name, item))
        if self.has_iattr(item.conf, 'gpio_out'):
            out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
            value = item()
            self.logger.debug("{}: OUTPUT Setting pin {} ({}) to {}.".format(self._name, out_pin, value, item.id()))
            self.send(out_pin, value)
        else:
            self.logger.debug("{}: No gpio_out".format(self._name))

    def send(self, pin, value):
        self._lock.acquire()
        try:
            GPIO.output(pin, value)
            self.logger.info("{}: Pin {} successfully set to {}".format(self._name, pin, value))
        except:
            self.logger.error("{}: Send {} failed for {}!".format(self._name, value, pin))
        finally:
            self._lock.release()

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
    def index(self, action=None, item_id=None, item_path=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        item = self.plugin.get_sh().return_item(item_path)

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           language=self.plugin._sh.get_defaultlanguage(), now=self.plugin.shtime.now())
