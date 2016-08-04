#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Onkel Andy
#########################################################################
#  GPIO plugin for SmartHome.py http://mknx.github.com/smarthome/
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import datetime
import RPi.GPIO as GPIO
import logging
import threading
import time

logger = logging.getLogger('GPIO')

class Raspi_GPIO(object):
    _items = []
    
    def wait(self,time_lapse):
    	time_start = time.time()
    	time_end = (time_start + time_lapse)
     
    	while time_end > time.time():
    		pass
    
    def __init__(self,smarthome,cycle):
        self._sh = smarthome
        self._cycle = int(cycle)
        self.alive = 'False'
        self._lock = threading.Lock()
        GPIO.setmode(GPIO.BOARD)
     
    def run(self):
      self.alive = True
      if self._cycle > 0:
            self._sh.scheduler.add('Raspi_GPIO', self.get_sensors, prio=5, cycle=self._cycle)  
      else:
            self.get_sensors() 
            logger.debug("GPIO: No Cycle defined")
            
    def stop(self):
        self.alive = False
        GPIO.cleanup()
        try:
            self._sh.scheduler.remove('Raspi_GPIO')
        except:
            logger.error("GPIO: Removing of scheduler failed: {}".format(sys.exc_info()))
                
    def send(self, pin, value):
        self._lock.acquire()
        try:
            GPIO.output(pin, value)
            logger.info("GPIO: Pin {0} successfully set to {1}".format(pin, value))
        except:
            logger.error("GPIO: Send {0} failed for {1}!".format(value, pin))
        finally:
            self._lock.release()                
        
    def parse_item(self, item):
        if 'gpio_in' in item.conf:
            in_pin = int(item.conf['gpio_in'])
            GPIO.setup(in_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            logger.debug("GPIO INPUT: {0} assigned to pin \'{1}\'".format(item, in_pin))
            self._items.append(item)
            return self.update_item      
        if 'gpio_out' in item.conf:
            out_pin = int(item.conf['gpio_out'])
            GPIO.setup(out_pin, GPIO.OUT)
            logger.debug("GPIO OUTPUT: {0} assigned to \'{1}\'".format(item, out_pin))
            if (out_pin is None):
                return None
                logger.debug("GPIO: No out_pin set")
            else:
                self._items.append(item)
            return self.update_item
            
    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Raspi_GPIO':
            #if item():
                if 'gpio_out' in item.conf:
                    out_pin = int(item.conf['gpio_out'])
                    value = item()                   
                    logger.debug("GPIO OUTPUT: Setting pin {0} ({2}) to {1}.".format(out_pin, value, item.id()))
                    self.send(out_pin, value)
                else:
                    logger.debug("GPIO: No gpio_out")
               
    def get_sensors(self):
     try:         
           for item in self._items:
               if 'gpio_in' in item.conf:
                   sensor = int(item.conf['gpio_in']) 
                   value = GPIO.input(sensor)
                   item(value, 'GPIO', 'get_sensors')
                   logger.debug("GPIO SENSOR: {0}  VALUE: {1}".format(sensor,value))
                   self.wait(0.2)
               if 'gpio_out' in item.conf:
                   sensor = int(item.conf['gpio_out']) 
                   value = GPIO.input(sensor)
                   item(value, 'GPIO', 'get_sensors')
                   logger.debug("GPIO OUTPUT: {0}  VALUE: {1}".format(sensor,value))
                   self.wait(0.2)


     except Exception as e:
      logger.warning("GPIO ERROR: {0}".format(e))
