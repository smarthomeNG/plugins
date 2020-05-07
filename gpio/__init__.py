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
import time
from bin.smarthome import VERSION
import RPi.GPIO as GPIO
from lib.utils import Utils


class Raspi_GPIO(SmartPlugin, Utils):
    '''
    Main class of the plugin.
    '''

    PLUGIN_VERSION = '1.5.0'
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh):
        '''
        Initializes the plugin.
        '''
        super().__init__()
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self.init_webinterface()

        try:
            # initialize variables
            self.alive = False
            self._items = []
            self._itemsdict = {}
            self._initdict = {}
            self._lock = threading.Lock()

            # read parameters
            self._mode = self.get_parameter_value('mode').upper()
            self._bouncetime = self.get_parameter_value('bouncetime')
            pud_param = self.get_parameter_value('pullupdown')
            if pud_param.upper() == 'UP':
                self._pullupdown = GPIO.PUD_UP
            elif pud_param.upper() == 'DOWN':
                self._pullupdown = GPIO.PUD_DOWN
            else:
                self._pullupdown = None

            # init gpio
            GPIO.setwarnings(False)
            if self._mode == 'BCM':
                GPIO.setmode(GPIO.BCM)
            else:
                GPIO.setmode(GPIO.BOARD)
            self.log_debug('Mode set to {}. Bouncetime: {}'.format(self._mode, self._bouncetime))

        except Exception:
            self._init_complete = False

    def process_gpio_event(self, pin):
        '''
        Callback method for GPIO event detection. Sets associated item to gpio pin value.

        :param sensor: Pin number according to GPIO mode configured in plugin.yaml
        :type sensor: int
        '''
        if not self.alive:
            return

        try:
            value = GPIO.input(pin)
            self._itemsdict[pin](value ^ self._is_item_inverted(None, pin), 'GPIO', 'get_sensors')
            self.log_info('GPIO read pin {} with value {}'.format(pin, value))
        except Exception as e:
            self.log_warn('Problem reading pin: {}'.format(e))

    def run(self):
        '''
        Run method for the plugin
        '''
        self.log_debug('run method called')

        # initialize GPIO event detection
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                pin = int(self.get_iattr_value(item.conf, 'gpio_in'))
                try:
                    value = GPIO.input(pin)
                    self._initdict[pin] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                except Exception:
                    self._initdict[pin] = False
                item(value, self.get_shortname(), 'run')

                # for some historical reason, maybe this has to be repeated
                # quit if successful or wrong values were passed
                err = None
                for attempt in range(10):
                    try:
                        GPIO.add_event_detect(pin, GPIO.BOTH, callback=self.process_gpio_event, bouncetime=self._bouncetime)
                        self.log_info('Adding event detection for input pin {}. Initial value is {}'.format(pin, value))
                    except RuntimeError as err:
                        self.log_debug('Problem adding event detection for input pin {}: {}. Retry {}/10'.format(pin, err, attempt))
                        time.sleep(3)
                    except ValueError as err:
                        self.log_err('Problem adding event detection for input pin {}: {}'.format(pin, err))
                        break
                    else:
                        break
                else:
                    self.log_err('Not adding event detection for input pin {}, given up: {}'.format(pin, err))
        self.alive = True

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.alive = False

        # reset used ouput pins
        GPIO.cleanup()
        self.log_debug('GPIO ports cleaned up')

        # remove event detectors
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                try:
                    GPIO.remove_event_detect(int(self.get_iattr_value(item.conf, 'gpio_in')))
                except:
                    pass

    def parse_item(self, item):
        '''
        Default plugin parse_item method

        :param item: The item to process
        :return:    Callback method for item updates
        '''

        # set pullup/pulldown for item
        pullupdown = self._pullupdown
        if self.has_iattr(item.conf, 'gpio_pud'):
            pud_param = self.get_iattr_value(item.conf, 'gpio_pud')
            if pud_param.upper() == 'UP':
                pullupdown = GPIO.PUD_UP
            elif pud_param.upper() == 'DOWN':
                pullupdown = GPIO.PUD_DOWN
            else:
                pullupdown = None

        # configure as input
        if self.has_iattr(item.conf, 'gpio_in'):
            in_pin = int(self.get_iattr_value(item.conf, 'gpio_in'))

            # if set, include pullupdown parameter
            if pullupdown:
                GPIO.setup(in_pin, GPIO.IN, pull_up_down=pullupdown)
            else:
                GPIO.setup(in_pin, GPIO.IN)
            # event_detection is setup on run()

            self.log_debug('INPUT {} assigned to pin {}'.format(item, in_pin))
            self._items.append(item)
            self._itemsdict[in_pin] = item
            return

        # configure as output
        if self.has_iattr(item.conf, 'gpio_out'):
            out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))

            # test if initial value is set
            if self.has_iattr(item.conf, 'gpio_init'):

                # as gpio_init is set, force output to initial_value
                value = self.to_bool(self.get_iattr_value(item.conf, 'gpio_init'))
                pin_value = self._get_gpio_value(value, item)
                GPIO.setup(out_pin, GPIO.OUT, initial=pin_value)
                self.log_debug('OUTPUT {} (pin {}) set to initial value {}'.format(item, out_pin, value))
            else:

                # no initial value set, try to read the current value from pin
                # by setting up as input, reading, and setting up as output
                if pullupdown:
                    GPIO.setup(out_pin, GPIO.IN, pull_up_down=pullupdown)
                else:
                    GPIO.setup(out_pin, GPIO.IN)
                value = self._get_gpio_value(GPIO.input(out_pin), item)
                GPIO.setup(out_pin, GPIO.OUT)
            # set item to initial value or current pin value
            item(value, 'GPIO Plugin', 'parse')

            self.log_debug('OUTPUT {} assigned to pin {}'.format(item, out_pin))
            self._items.append(item)
            self._itemsdict[out_pin] = item
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        '''
        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        '''
        if item is not None and caller != self.get_shortname():
            if self.has_iattr(item.conf, 'gpio_out'):
                self.log_debug('Trying to update {} by {}.'.format(item, caller))
                out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
                value = self._get_gpio_value(item(), item)
                self.log_debug('OUTPUT Setting pin {} ({}) to {}.'.format(out_pin, item.id(), value))
                self._set_gpio(out_pin, value)
            else:
                self.log_debug('Item {} has no gpio_out'.format(item))

    def _is_item_inverted(self, item, pin=None):
        '''
        Check if item has gpio_invert set. Item can be referred by item parameter or by
        GPIO pin associated to it.

        :param item: Item to check for gpio_invert set
        :param pin: Pin to check for gpio_invert set in corresponding item
        :type pin: int
        :return: True if gpio_invert set for item, False otherwise
        :rtype: bool
        '''
        if item is None:
            if pin is None:
                # reaching this point usually means coding error.
                self.log_err('is_item_inverted called with item=None and pin=None. Check your code...')
                raise ValueError('Both values are None, one needed')
            item = self._itemsdict[pin]

        inverted = self.has_iattr(item.conf, 'gpio_invert') and self.to_bool(self.get_iattr_value(item.conf, 'gpio_invert'))
        return inverted

    def _get_gpio_value(self, value, item=None, pin=None):
        '''
        Return valid GPIO value for output and setup methods. Calculate value
        with respect to gpio_invert parameter

        :param value: shng value to assign to GPIO pin. Accepts truth-ish values
        :type value: bool
        :param item: Item to check for gpio_invert set
        :param pin: Pin to check for gpio_invert set in corresponding item
        :type pin: int
        :return: Value safe for GPIO output/setup methods
        '''
        inverted = self._is_item_inverted(item, pin)

        if value ^ inverted:
            return 1
        else:
            return 0

    def _set_gpio(self, pin, value):
        '''
        Set GPIO pin to value, prevent concurrent access

        :param pin: Pin to modify
        :type pin: int
        :param value: Value to assign to pin
        :type value: bool
        '''
        self._lock.acquire()
        try:
            GPIO.output(pin, value)
            self.log_info('Pin {} successfully set to {}'.format(pin, value))
        except:
            self.log_err('Send {} failed for {}!'.format(value, pin))
        finally:
            self._lock.release()

    def log_debug(self, text):
        self.logger.debug('{}: {}'.format(self.get_shortname(), text))

    def log_info(self, text):
        self.logger.info('{}: {}'.format(self.get_shortname(), text))

    def log_err(self, text):
        self.logger.error('{}: {}'.format(self.get_shortname(), text))

    def log_warn(self, text):
        self.logger.warning('{}: {}'.format(self.get_shortname(), text))

    def init_webinterface(self):
        ''''
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        '''
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http is None:
            self.log_err('Not initializing the web interface')
            return False

        import sys
        if 'SmartPluginWebIf' not in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.log_warn('Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface')
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
        '''
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        '''
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, action=None, item_id=None, item_path=None, reload=None):
        '''
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        '''
        # item = self.plugin.get_sh().return_item(item_path)

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           language=self.plugin._sh.get_defaultlanguage(), now=self.plugin.shtime.now())
