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

import gpiod
from lib.utils import Utils
from .webif import WebInterface
CONSUMER = "SmarthomeNG"


class GPIO(SmartPlugin, Utils):
    PLUGIN_VERSION = '3.0.0'
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh):
        super().__init__()
        self.init_webinterface(WebInterface)
        self.chip_path = f"/dev/gpiochip{self.get_parameter_value('chip')}"
        self._item_values = {'in': {}, 'out': {}}
        self._lock = threading.Lock()
        self.alive = False
        self._initdict = {}
        self._items = []
        self._buttons = {}
        self._leds = {}
        self._itemsdict = {}
        self._callbacks = {}

        self._mode = self.get_parameter_value('mode').upper()
        self._bouncetime = self.get_parameter_value('bouncetime') / 1000
        pud_param = self.get_parameter_value('pullupdown')
        if pud_param.upper() == 'UP':
                self._pullupdown = gpiod.line.Bias.PULL_UP
        elif pud_param.upper() == 'DOWN':
                self._pullupdown = gpiod.line.Bias.PULL_DOWN
        else:
                self._pullupdown = gpiod.line.Bias.AS_IS
        try:
            self.chip = gpiod.Chip(self.chip_path)
        except Exception as e:
            self.logger.error(f"Error opening GPIO chip {self.chip_path}: {e}")
            self._init_complete = False
        updown = self._get_pud_msg(self._pullupdown, 'global ')
        self.logger.debug(f'Mode set to {self._mode}, bouncetime is {self._bouncetime}, {updown}')

    def physical_to_gpio(self, pin):
        '''
        Convert GPIO numbering based on setting.

        :param pin: Pin number according to GPIO mode configured in plugin.yaml
        :type pin: int
        :return: Converted pin number converted from BOARD to BCM
        :rtype: int
        '''
        BOARD_TO_GPIO = {
            3:2,5:3,7:4,8:14,10:15,
            11:17,12:18,13:27,15:22,16:23,
            18:24,19:10,21:9,22:25,23:11,
            24:8,26:7,27:0,28:1,29:5,
            31:6,32:12,33:13,35:19,36:16,
            37:26,38:20,40:21
        }
        return BOARD_TO_GPIO.get(pin)

    def process_gpio_event(self, pin, pressed):
        '''
        Callback method for GPIO event detection. Sets associated item to gpio pin value.

        :param pin: Pin number according to GPIO mode configured in plugin.yaml
        :type pin: int
        :param pressed: True or False depending on button.is_pressed or not
        :type pressed: bool
        '''
        if not self.alive:
            return

        try:
            value = pressed
            self._itemsdict[pin](value ^ self._is_item_inverted(None, pin), self.get_shortname(), 'pin_change')
            self.logger.info(f'Read pin {pin} with value {value} after event_detection')
        except Exception as e:
            self.logger.error(f'Problem reading pin {pin} after event_detection: {e}')

    def _get_pud_msg(self, pud, add=''):
        '''
        Create log message for pullup/pulldown
        :param pud: Pullop or Pulldown
        :type pud: bool
        :param add: additional log entry
        :type pud: str
        :return: log text with correct info about pullup/down
        :rtype: str
        '''
        if pud is True or pud == gpiod.line.Bias.PULL_UP:
            return add + 'pullup enabled'
        elif pud is False or pud == gpiod.line.Bias.PULL_DOWN:
            return add + 'pulldown enabled'
        else:
            return 'no ' + add + 'pullup/pulldown set'

    def _to_gpiod_value(self, value):
        """
        Convert truth-ish value to gpiod.line.Value.
        Accepts bool, int, str.
        """
        val = self._to_bool(value)
        return gpiod.line.Value.ACTIVE if val else gpiod.line.Value.INACTIVE

    def _to_bool(self, value):
        '''
        Normalize GPIO values to real bool.
        Works with gpiod Value, int, str, bool.
        :param value: status of GPIO pin, most likely Active or Inactive
        :type value: str
        :return: boolean value True or False
        :rtype: bool
        '''
        if isinstance(value, bool):
            return value

        if value is None:
            return False

        # gpiod Value.ACTIVE / INACTIVE
        val = str(value).upper()
        if "ACTIVE" in val:
            return True
        if "INACTIVE" in val:
            return False

        try:
            return bool(int(value))
        except Exception:
            return False

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

        inverted = self.has_iattr(item.conf, 'gpio_invert') and self._to_bool(self.get_iattr_value(item.conf, 'gpio_invert'))
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
        value = self._to_bool(value)
        inverted = self._is_item_inverted(item, pin)
        gpio_pin = pin
        if self._mode == "BOARD":
            gpio_pin = self.physical_to_gpio(pin)
        self.logger.debug(f'Pin: {pin} (GPIO: {gpio_pin}), inverted: {inverted}, value:{value}')

        return (inverted ^ value)

    def _update_item_values(self, item, in_out, pin, payload):
        '''
        Update dict for periodic updates of the web interface

        :param item: item getting updated
        :type item: item
        :param in_out: whether it's an input (for reading) or output (for writing) pin
        :type in_out: str
        :param pin: pin number
        :type pin: int
        :param payload: result from GPIO
        :type payload: bool or str
        '''
        if not self._item_values[in_out].get(item.property.path):
            self._item_values[in_out][item.property.path] = {}
        self._item_values[in_out][item.property.path]['pin'] = pin
        if isinstance(payload, bool):
            self._item_values[in_out][item.property.path]['value'] = str(payload)
        else:
            self._item_values[in_out][item.property.path]['value'] = payload
        return

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
                pullupdown = gpiod.line.Bias.PULL_UP
                pud_add = ''
            elif pud_param.upper() == 'DOWN':
                pullupdown = gpiod.line.Bias.PULL_DOWN
                pud_add = ''
            else:
                pullupdown = gpiod.line.Bias.AS_IS

        # Input
        if self.has_iattr(item.conf, 'gpio_in'):
            in_pin = int(self.get_iattr_value(item.conf, 'gpio_in'))
            gpio_pin = in_pin

            # BOARD → GPIO umrechnen
            if self._mode == "BOARD":
                gpio_pin = self.physical_to_gpio(in_pin)

            # LineSettings bauen (ersetzt Button())
            settings = gpiod.LineSettings(
                direction=gpiod.line.Direction.INPUT,
                bias=pullupdown,
                active_low=False,
                edge_detection=gpiod.line.Edge.BOTH,
                debounce_period=datetime.timedelta(seconds=self._bouncetime)
            )

            try:
                request = gpiod.request_lines(
                    self.chip_path,
                    consumer=CONSUMER,
                    config={gpio_pin: settings}
                )
            except Exception as e:
                self.logger.error(f"Failed to request GPIO {gpio_pin}: {e}")
                return

            self._buttons[gpio_pin] = request

            # Initialwert
            try:
                pin_value = bool(request.get_value(gpio_pin))
                value = self._get_gpio_value(pin_value, item, in_pin)
                self._initdict[gpio_pin] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            except Exception:
                value = False
                self._initdict[gpio_pin] = False

            # Item initial setzen
            item(value, self.get_shortname(), 'init')

            updown = self._get_pud_msg(pullupdown, pud_add)
            self.logger.debug(f'{item} assigned to input on pin {in_pin} (GPIO: {gpio_pin}), init value {value}, {updown}')

            self._items.append(item)
            self._update_item_values(item, 'in', gpio_pin, value)
            self._itemsdict[gpio_pin] = item
            return

        # Output
        if self.has_iattr(item.conf, 'gpio_out'):
            out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
            gpio_pin = out_pin

            # BOARD → GPIO umrechnen
            if self._mode == "BOARD":
                gpio_pin = self.physical_to_gpio(out_pin)

            # LineSettings für OUTPUT (ersetzt LED())
            settings = gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                drive=gpiod.line.Drive.PUSH_PULL
            )

            try:
                request = gpiod.request_lines(
                    self.chip_path,
                    consumer=CONSUMER,
                    config={gpio_pin: settings}
                )
            except Exception as e:
                self.logger.error(f"Failed to request GPIO {gpio_pin} as output: {e}")
                return

            # Initialwert setzen
            if self.has_iattr(item.conf, 'gpio_init'):
                value = self.to_bool(self.get_iattr_value(item.conf, 'gpio_init'))
                pin_value = self._get_gpio_value(value, item, out_pin)
                request.set_value(gpio_pin, self._to_gpiod_value(pin_value))
                self._update_item_values(item, 'out', gpio_pin, pin_value)
                self.logger.debug(f'{item} (output on pin {out_pin} - GPIO {gpio_pin}) set to initial value {value}')
            else:
                # aktuellen Pin-Zustand lesen
                try:
                    pin_value = bool(request.get_value(gpio_pin))
                except Exception:
                    pin_value = False
                value = self._get_gpio_value(pin_value, item, out_pin)

            # Item initialisieren
            item(value, self.get_shortname(), 'init')

            self.logger.debug(f'{item} assigned to output on pin {out_pin} (GPIO: {gpio_pin})')

            self._items.append(item)
            self._itemsdict[gpio_pin] = item
            self._leds[gpio_pin] = request

            return self.update_item

    def _set_gpio(self, pin, value):
        '''
        Set GPIO pin to value, prevent concurrent access

        :param pin: Pin to modify
        :type pin: int
        :param value: Value to assign to pin
        :type value: bool
        '''
        self._lock.acquire()
        gpio_pin = pin
        if self._mode == "BOARD":
            gpio_pin = self.physical_to_gpio(pin)
        try:
            request = self._leds.get(gpio_pin)
            if request:
                request.set_value(gpio_pin, self._to_gpiod_value(value))
                self.logger.debug(f'Pin {pin} (GPIO: {gpio_pin}) successfully set to {value}')
            else:
                self.logger.error(f'No GPIO request for pin {pin} (GPIO: {gpio_pin})')
        except:
            self.logger.error(f'Setting GPIO pin {pin} (GPIO: {gpio_pin}) to {value} failed!')
        finally:
            self._lock.release()

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
                self.logger.debug(f'{item} updated by {caller}.')
                out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
                gpio_pin = out_pin
                if self._mode == "BOARD":
                    gpio_pin = self.physical_to_gpio(out_pin)
                value = self._get_gpio_value(item(), item, out_pin)
                self.logger.info(f'Setting pin {out_pin} (GPIO: {gpio_pin}) to {value} for {item}')
                self._update_item_values(item, 'out', gpio_pin, value)
                self._set_gpio(out_pin, value)
            else:
                self.logger.error(f'{item} updated by {caller}, but no gpio_out set up')

    def _gpio_event_worker(self, pin, request):
        self.logger.debug(f"GPIO event worker started for pin {pin}")
        while self.alive:
            try:
                if not request.wait_edge_events(timeout=1.0):
                    continue

                events = request.read_edge_events()
            except Exception as e:
                self.logger.error(f"GPIO {pin} event wait failed: {e}")
                continue

            for event in events:
                try:
                    pin_value = bool(request.get_value(pin))
                    value = self._get_gpio_value(pin_value, None, pin)
                    self.process_gpio_event(pin, value)
                    #self.logger.debug(f"GPIO {pin} event={event.event_type} value={value}")

                except Exception as e:
                    self.logger.error(f"GPIO {pin} read failed: {e}")


    def run(self):
        """
        run
        """
        self.logger.debug('run method called')
        self.alive = True
        self._event_threads = []

        for pin, request in self._buttons.items():
            t = threading.Thread(
                target=self._gpio_event_worker,
                args=(pin, request),
                daemon=True
            )
            t.start()
            self._event_threads.append(t)

        self.logger.info("GPIO event threads started")


    def stop(self):
        """
        Stops plugin, releases pins
        """
        self.logger.info('Stop method called')
        self.alive = False

        # Threads sauber beenden
        if hasattr(self, '_event_threads'):
            for t in self._event_threads:
                t.join(timeout=2.0)

        # Input GPIOs freigeben
        for pin, request in list(self._buttons.items()):
            try:
                request.release()
                self.logger.debug(f'Released input GPIO {pin}')
            except Exception as e:
                self.logger.warning(f'Failed to release input GPIO {pin}: {e}')

        # Output GPIOs freigeben
        for pin, request in list(self._leds.items()):
            try:
                request.release()
                self.logger.debug(f'Released output GPIO {pin}')
            except Exception as e:
                self.logger.warning(f'Failed to release output GPIO {pin}: {e}')

        self._buttons.clear()
        self._leds.clear()
        self.logger.debug('Stop method done')
