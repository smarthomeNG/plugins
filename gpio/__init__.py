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
from lib.model.smartplugin import SmartPlugin
import RPi.GPIO as GPIO
import threading

class Raspi_GPIO(SmartPlugin):
    PLUGIN_VERSION = "1.0.1"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, mode="board"):
        self.logger = logging.getLogger(__name__)
        self._sh = sh
        self._items = []
        self._itemsdict = {}
        self._mode = mode.upper()
        GPIO.setwarnings(False)
        if self._mode == "BCM":
            GPIO.setmode(GPIO.BCM)
        else:
            GPIO.setmode(GPIO.BOARD)    
        self.logger.debug("GPIO: Mode set to {0}".format(self._mode))
        self.alive = False
        self._lock = threading.Lock() 
        
    def get_sensors(self, sensor):
        try:
            value = GPIO.input(sensor)
            self._itemsdict[sensor](value, 'GPIO', 'get_sensors')
            self.logger.info("GPIO: SENSOR READ: {0}  VALUE: {1}".format(sensor,value))
        except Exception as e:
            self.logger.warning("GPIO: Problem reading sensor: {0}".format(e))

    def run(self):
        self.logger.debug("GPIO: run method called")
        self.alive = True   
        for item in self._items:
            if self.has_iattr(item.conf, 'gpio_in'):
                sensor = int(self.get_iattr_value(item.conf, 'gpio_in')) 
                value = GPIO.input(sensor)
                item(value, 'GPIO', 'gpio_init')
                GPIO.add_event_detect(sensor, GPIO.BOTH, callback=self.get_sensors)
                self.logger.info("GPIO: Adding Event Detection for Pin {}. Initial value is {}".format(sensor, value))           

    def stop(self):
        self.alive = False
        GPIO.cleanup()
        self.logger.debug("GPIO: cleaned up")
        

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'gpio_in'):
            in_pin = int(item.conf['gpio_in'])
            GPIO.setup(in_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.logger.debug("GPIO: INPUT {0} assigned to pin \'{1}\'".format(item, in_pin))
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
            self.logger.info("GPIO: Adding Event Detection for Output Pin {}. Initial value is {}".format(out_pin, value))
            GPIO.setup(out_pin, GPIO.OUT)
            self.logger.debug("GPIO: OUTPUT {0} assigned to \'{1}\'".format(item, out_pin))
            if (out_pin is None):
                return None
                self.logger.debug("GPIO: No out_pin set for item {}".format(item))
            else:
                self._items.append(item)
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        self.logger.debug("GPIO: Trying to update {}.".format(item))
        if self.has_iattr(item.conf, 'gpio_out'):
            out_pin = int(self.get_iattr_value(item.conf, 'gpio_out'))
            value = item()                   
            self.logger.debug("GPIO: OUTPUT Setting pin {0} ({2}) to {1}.".format(out_pin, value, item.id()))
            self.send(out_pin, value)
        else:
            self.logger.debug("GPIO: No gpio_out")

    def send(self, pin, value):
        self._lock.acquire()
        try:
            GPIO.output(pin, value)
            self.logger.info("GPIO: Pin {0} successfully set to {1}".format(pin, value))
        except:
            self.logger.error("GPIO: Send {0} failed for {1}!".format(value, pin))
        finally:
            self._lock.release()                

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    FooClass(None).run()
