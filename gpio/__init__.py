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
import RPi.GPIO as PiGPIO
from lib.utils import Utils


class GPIO(SmartPlugin, Utils):
    '''
    Main class of the plugin.
    '''

    PLUGIN_VERSION = '1.5.1'
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
            self._initretries = self.get_parameter_value('initretries')
            pud_param = self.get_parameter_value('pullupdown')
            if pud_param.upper() == 'UP':
                self._pullupdown = PiGPIO.PUD_UP
            elif pud_param.upper() == 'DOWN':
                self._pullupdown = PiGPIO.PUD_DOWN
            else:
                self._pullupdown = None

            # init gpio
            PiGPIO.setwarnings(False)
            if self._mode == 'BCM':
                PiGPIO.setmode(PiGPIO.BCM)
            else:
                PiGPIO.setmode(PiGPIO.BOARD)
            self.logger.debug('Mode set to {}, bouncetime is {}, {}'.format(self._mode, self._bouncetime, self._get_pud_msg(self._pullupdown, 'global ')))

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
            value = PiGPIO.input(pin)
            self._itemsdict[pin](value ^ self._is_item_inverted(None, pin), self.get_shortname(), 'pin_change')
            self.logger.info('Read pin {} with value {} after event_detection'.format(pin, value))
        except Exception as e:
            self.logger.error('Problem reading pin {} after event_detection'.format(e))

    def run(self):
        '''
        Run method for the plugin
        '''
        self.logger.debug('run method called')

        # initialize GPIO event detection
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                pin = int(self.get_iattr_value(item.conf, 'gpio_in'))

                # for some historical reason, maybe this has to be repeated
                # quit if successful or wrong values were passed

## as this may delay plugin startup considerably, anyone able to pinpoint possible
## reasons for first-time-failures please report this, thanks in advance! SH
                err = None
                for attempt in range(self._initretries):
                    time.sleep(1)
                    try:
                        PiGPIO.add_event_detect(pin, PiGPIO.BOTH, callback=self.process_gpio_event, bouncetime=self._bouncetime)
                        self.logger.info('Adding event detection for input pin {}, initial value is {}'.format(pin, item()))
                    except RuntimeError as err:
                        self.logger.warning('Problem adding event detection for input pin {}: {}. Retry {}/{}'.format(pin, err, attempt + 1, self._initretries))
                        time.sleep(2)
                    except ValueError as err:
                        self.logger.warning('Problem adding event detection for input pin {}: {}. Retry {}/{}'.format(pin, err, attempt + 1, self._initretries))
                        break
                    else:
                        self.logger.warning('Unspecific problem adding event detection for input pin {}. Retry {}/{}'.format(pin, attempt + 1, self._initretries))
                        break
                else:
                    self.logger.error('Not adding event detection for input pin {}, given up'.format(pin))
        self.alive = True

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.alive = False

        # reset used ouput pins
        PiGPIO.cleanup()
        self.logger.debug('Used GPIO ports cleaned up')

        # remove event detectors
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                try:
                    PiGPIO.remove_event_detect(int(self.get_iattr_value(item.conf, 'gpio_in')))
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
        pud_add = 'global '
        if self.has_iattr(item.conf, 'gpio_pud'):
            pud_param = self.get_iattr_value(item.conf, 'gpio_pud')
            if pud_param.upper() == 'UP':
                pullupdown = PiGPIO.PUD_UP
                pud_add = ''
            elif pud_param.upper() == 'DOWN':
                pullupdown = PiGPIO.PUD_DOWN
                pud_add = ''
            else:
                pullupdown = None

        # configure as input
        if self.has_iattr(item.conf, 'gpio_in'):
            in_pin = int(self.get_iattr_value(item.conf, 'gpio_in'))

            # if set, include pullupdown parameter
            if pullupdown:
                PiGPIO.setup(in_pin, PiGPIO.IN, pull_up_down=pullupdown)
            else:
                PiGPIO.setup(in_pin, PiGPIO.IN)
            # event_detection is setup on run()

            try:
                value = PiGPIO.input(in_pin)
                self._initdict[in_pin] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            except Exception:
                self._initdict[in_pin] = False
            item(value, self.get_shortname(), 'init')

            self.logger.debug('{} assigned to input on pin {}, {}'.format(item, in_pin, self._get_pud_msg(pullupdown, pud_add)))
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
                PiGPIO.setup(out_pin, PiGPIO.OUT, initial=pin_value)
                self.logger.debug('{} (output on pin {}) set to initial value {}'.format(item, out_pin, value))
            else:

                # no initial value set, try to read the current value from pin
                # by setting up as input, reading, and setting up as output
                if pullupdown:
                    PiGPIO.setup(out_pin, PiGPIO.IN, pull_up_down=pullupdown)
                else:
                    PiGPIO.setup(out_pin, PiGPIO.IN)
                value = self._get_gpio_value(PiGPIO.input(out_pin), item)
                self.logger.debug('{} (output on pin {}) reads initial value {}'.format(item, out_pin, value))
                PiGPIO.setup(out_pin, PiGPIO.OUT)
            # set item to initial value or current pin value
            item(value, self.get_shortname(), 'init')

            self.logger.debug('{} assigned to output on pin {}'.format(item, out_pin))
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
                self.logger.debug('{} updated by {}.'.format(item, caller))
                out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
                value = self._get_gpio_value(item(), item)
                self.logger.info('Setting pin {} to {} for {}'.format(out_pin, value, item))
                self._set_gpio(out_pin, value)
            else:
                self.logger.error('{} updated by {}, but no gpio_out set up'.format(item, caller))

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
                self.logger.error('is_item_inverted called with item=None and pin=None. Check your code...')
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
        self.logger.debug('Pin {0}, inverted: {1}, value:{2}'.format(pin, inverted, value))

        return (inverted ^ value)

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
            PiGPIO.output(pin, value)
            self.logger.debug('Pin {} successfully set to {}'.format(pin, value))
        except:
            self.logger.error('Setting pin {} to {} failed!'.format(pin, value))
        finally:
            self._lock.release()

    def _get_pud_msg(self, pud, add=''):
        if pud == PiGPIO.PUD_UP:
            return add + 'pullup enabled'
        elif pud == PiGPIO.PUD_DOWN:
            return add + 'pulldown enabled'
        else:
            return 'no ' + add + 'pullup/pulldown set'

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
            self.logger.error('mod_http not loaded, not initializing the web interface')
            return False

        import sys
        if 'SmartPluginWebIf' not in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.error('Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface')
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
