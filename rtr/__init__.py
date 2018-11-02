#!/usr/bin/env python
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Thomas Creutz                      thomas.creutz@gmx.de
#  Copyright 2016 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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
#  along with SmartHomeNG If not, see <http://www.gnu.org/licenses/>.
#########################################################################

# Some useful docs:
# http://www.rn-wissen.de/index.php/Regelungstechnik#PI-Regler
# http://de.wikipedia.org/wiki/Regler#PI-Regler
# http://www.honeywell.de/fp/regler/Reglerparametrierung.pdf

import time
import datetime

from lib.module import Modules
from lib.item import Items
from lib.shtime import Shtime
from lib.model.smartplugin import *

class RTR(SmartPlugin):
    """
    Main class of the rtr plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.2.3"

    _controller = {}
    _defaults = {'currentItem' : None,
                'setpointItem' : None,
                'actuatorItem' : None,
                'stopItems' : None,
                'eSum' : 0,
                'Kp' : 0,
                'Ki' : 0,
                'Tlast' : 0,
                'tempDefault' : 0,
                'tempDrop' : 0,
                'tempBoost' : 0,
                'validated' : False}

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("rtr: init method called")

        sh = self.get_sh()
        self.path = sh.base_dir + '/var/rtr/timer/'
        self._items = Items.get_instance()

        # preset the controller defaults
        self._defaults['Tlast'] = time.time()
        self._defaults['Kp'] = self.get_parameter_value('default_Kp')
        self._defaults['Ki'] = self.get_parameter_value('default_Ki')
        self._cycle_time = self.get_parameter_value('cycle_time')
        self._defaultOnExpiredTimer = self.get_parameter_value('defaultOnExpiredTimer')

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method called")
        self.alive = True
        self.scheduler_add('cycle', self.update_items, prio=5, cycle=int(self._cycle_time))

        try:
            self._restoreTimer()
        except Exception as e:
            self.logger.error("Error in 'self._restoreTimer()': {}".format(e))

        return

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'rtr_current'):
            if not item.conf['rtr_current'].isdigit():
                self.logger.error("rtr: error in item {0}, rtr_current need to be the controller number".format(item.id()))
                return
            c = 'c' + item.conf['rtr_current']

            # init controller with defaults when it not exist
            if c not in self._controller:
                self.logger.debug("rtr: controller '{0}' does not exist yet. Init with default values".format(c))
                self._controller[c] = self._defaults.copy()

            # store currentItem into controller
            self._controller[c]['currentItem'] = item.id()
            self.logger.info("rtr: bound item '{1}' to currentItem for controller '{0}'".format(c, item.id()))

            if not self.has_iattr(item.conf, 'rtr_Kp'):
                self.logger.info("rtr: missing rtr_Kp in item {0}, setting to default: {1}".format(item.id(), self._controller[c]['Kp']))
            else:
                self._controller[c]['Kp'] = float(item.conf['rtr_Kp'])

            if not self.has_iattr(item.conf, 'rtr_Ki'):
                self.logger.info("rtr: missing rtr_Ki in item {0}, setting to default: {1}".format(item.id(), self._controller[c]['Ki']))
            else:
                self._controller[c]['Ki'] = float(item.conf['rtr_Ki'])


            if not self._controller[c]['validated']:
                self.validate_controller(c)

            return

        if self.has_iattr(item.conf, 'rtr_setpoint'):
            if not item.conf['rtr_setpoint'].isdigit():
                self.logger.error("rtr: error in item {0}, rtr_setpoint need to be the controller number".format(item.id()))
                return

            c = 'c' + item.conf['rtr_setpoint']

            # init controller with defaults when it not exist
            if c not in self._controller:
                self.logger.debug("rtr: controller '{0}' does not exist yet. Init with default values".format(c))
                self._controller[c] = self._defaults.copy()

            # store setpointItem into controller
            self._controller[c]['setpointItem'] = item.id()
            self.logger.info("rtr: bound item '{1}' to setpointItem for controller '{0}'".format(c, item.id()))

            if self.has_iattr(item.conf, 'rtr_temp_default'):
                self._controller[c]['tempDefault'] = float(item.conf['rtr_temp_default'])

            if self.has_iattr(item.conf, 'rtr_temp_drop'):
                self._controller[c]['tempDrop'] = float(item.conf['rtr_temp_drop'])

            if self.has_iattr(item.conf, 'rtr_temp_boost'):
                self._controller[c]['tempBoost'] = float(item.conf['rtr_temp_boost'])

            if not self._controller[c]['validated']:
                self.validate_controller(c)

            return self.update_item

        if self.has_iattr(item.conf, 'rtr_actuator'):
            if not item.conf['rtr_actuator'].isdigit():
                self.logger.error("rtr: error in item {0}, rtr_actuator need to be the controller number".format(item.id()))
                return

            c = 'c' + item.conf['rtr_actuator']

            # init controller with defaults when it not exist
            if c not in self._controller:
                self.logger.debug("rtr: controller '{0}' does not exist yet. Init with default values".format(c))
                self._controller[c] = self._defaults.copy()

            # store actuatorItem into controller
            self._controller[c]['actuatorItem'] = item.id()
            self.logger.info("rtr: bound item '{1}' to actuatorItem for controller '{0}'".format(c, item.id()))

            if not self._controller[c]['validated']:
                self.validate_controller(c)

            return

        if self.has_iattr(item.conf, 'rtr_stop'):
            self.logger.error("rtr: parse item {0}, found rtr_stop which is not supported anymore - use rtr_stops instead")
            return

        if self.has_iattr(item.conf, 'rtr_stops'):
            # validate this optional Item
            if item._type != 'bool':
                self.logger.error("rtr: error in item {0}, rtr_stops Item need to be bool (current {1})".format(item.id(), item._type))
                return

            self.logger.debug("rtr: parse item {0}, found rtr_stops={1}".format(item.id(), item.conf['rtr_stops']))

            cList = item.conf['rtr_stops']
            if isinstance(cList, str):
                cList = [cList, ]

            for cNum in cList:

                # validate controller number
                if not cNum.isdigit():
                    self.logger.error("rtr: error in {0}, rtr_stops need to be the controller number(s) - skip {1}".format(item.id(), cNum))
                    continue

                c = 'c' + cNum

                # init controller with defaults when it not exist
                if c not in self._controller:
                    self._controller[c] = self._defaults.copy()
                    self.logger.debug("rtr: create controller {0} for {1}".format(c, item.id()))

                # store stopItems into controller
                if self._controller[c]['stopItems'] is None:
                    self._controller[c]['stopItems'] = []
                self._controller[c]['stopItems'].append(item)

                # listen to item events
                item.add_method_trigger(self.stop_Controller)

                self.logger.debug("rtr: parse item {0}, controller {1} stop items: {2} ".format(item.id(), c, self._controller[c]['stopItems']))

            return

    def stop_Controller(self, item, caller=None, source=None, dest=None):
        for c in self._controller.keys():
            if self._controller[c]['stopItems'] is not None and len(self._controller[c]['stopItems']) > 0:
                for item in self._controller[c]['stopItems']:
                    if item():
                       if self._controller[c]['actuatorItem']() > 0:
                           logger.info("rtr: controller {0} stopped, because of item {1}".format(c, item.id()))
                       self._controller[c]['actuatorItem'](0)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        write item's values

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """

        self.logger.debug("rtr: update item {}, from caller = {}, with source={} and dest={}".format(item.id(), caller, source, dest))
        if item() and caller != 'plugin':
            if 'rtr_setpoint' in item.conf or 'rtr_current' in item.conf:
                c = 'c' + item.conf['rtr_setpoint']
                if self._controller[c]['validated']:
                    self.pi_controller(c)

    def update_items(self):
        """ this is the callback function for the scheduler """
        for c in self._controller.keys():
            if self._controller[c]['validated']:
                self.pi_controller(c)

    def validate_controller(self, c):
        """
        this function checks wether the needed parameters are set for a given controller
        :param c: controller to be checked
        """
        if self._controller[c]['setpointItem'] is None:
            return

        if self._controller[c]['currentItem'] is None:
            return

        if self._controller[c]['actuatorItem'] is None:
            return

        self.logger.info("rtr: all needed params are set, controller {0} validated".format(c))
        self._controller[c]['validated'] = True

    def pi_controller(self, c):
        """
        this function calculates a new actuator value for a given controller

        w    = setpoint value / Führungsgröße (Sollwert)
        x    = current value / Regelgröße (Istwert)
        e    = control error / Regelabweichung
        eSum = sum of error values / Summe der Regelabweichungen
        y    = output to actuator / Stellgröße
        z    = disturbance variable / Störgröße
        Kp   = proportional gain / Verstärkungsfaktor
        Ki   = integral gain / Integralfaktor
        Ta   = scanning time (given in seconds)/ Abtastzeit

        esum = esum + e
        y = Kp * e + Ki * Ta * esum

        p_anteil = error * p_gain;
        error_integral = error_integral + error
        i_anteil = error_integral * i_gain

        :param c: controller for the calculation
        """

        # check if controller is currently deactivated
        if self._controller[c]['stopItems'] is not None and len(self._controller[c]['stopItems']) > 0:
            for item in self._controller[c]['stopItems']:
                if item():
                   if self._items.return_item(self._controller[c]['actuatorItem'])() > 0:
                       self.logger.info("rtr: controller {0} currently deactivated, because of item {1}".format(c, item.id()))
                   self._items.return_item(self._controller[c]['actuatorItem'])(0)
                   return

        # calculate scanning time
        Ta = int(time.time()) - self._controller[c]['Tlast']
        self.logger.debug("{0} | Ta = Time() - Tlast | {1} = {2} - {3}".format(c, Ta, (Ta + self._controller[c]['Tlast']), self._controller[c]['Tlast']))
        self._controller[c]['Tlast'] = int(time.time())

        # get current and set point temp
        w = self._items.return_item(self._controller[c]['setpointItem'])()
        x = self._items.return_item(self._controller[c]['currentItem'])()

        # skip execution if x is 0
        if x == 0.00:
            self.logger.debug("{0} | skip uninitiated x value (currently zero)".format(c))
            return

        # calculate control error
        e = w - x
        self.logger.debug("{0} | e = w - x | {1} = {2} - {3}".format(c, e, w, x))

        Kp = 1.0 / self._controller[c]['Kp']
        self._controller[c]['eSum'] = self._controller[c]['eSum'] + e * Ta
        i = self._controller[c]['eSum'] / (60.0 * self._controller[c]['Ki'])
        y = 100.0 * Kp * (e + i);

        # limit the new actuator value to [0 ... 100]
        if y > 100:
            y = 100
            self._controller[c]['eSum'] = (1.0 / Kp) * 60.0 * self._controller[c]['Ki']

        if y < 0 or self._controller[c]['eSum'] < 0:
            if y < 0:
                y = 0
            self._controller[c]['eSum'] = 0

        self.logger.debug("{0} | eSum = {1}".format(c, self._controller[c]['eSum']))
        self.logger.debug("{0} | y = {1}".format(c, y))

        self._items.return_item(self._controller[c]['actuatorItem'])(y)

    def _restoreTimer(self):
        """
        scans folder for saved timer to restore them at startup
        """
        self.logger.info("check if we need to restore timer")

        if os.path.isdir(self.path):
            for filename in os.listdir(self.path):
                self.logger.info("need to restore '{}'".format(filename))

                if "boost_c" not in filename:
                    self.logger.error("file looks invalid! Skip it..")
                    return

                try:
                    f = open(self.path + filename, "r")
                    ts = f.read()
                    f.close()

                except OSError as e:
                    self.logger.error("cannot read '{}', error: {}".format(self.path + filename, e.args))
                    continue

                try:
                    ts = int(ts)
                except ValueError:
                    self.logger.error("file content '{}' is no timestamp".format(ts))

                name, c = filename.split('_')

                dt = datetime.datetime.fromtimestamp(ts)
                shtime = Shtime.get_instance()
                if dt < shtime.now():
                    self.logger.info("timer '{}' is already expired - restore default = {}".format(filename, self._defaultOnExpiredTimer))
                    if self._defaultOnExpiredTimer:
                        self.default(c)
                else:
                    self._createTimer(filename, c, dt)

    def _createTimer(self, name, c, timer):
        """
        this function changes setpoint to defined default temperature
        :param name: name of the timer
        :param c: controller to be used
        :param timer: datetime value for the timer
        """
        self.logger.debug("_createTimer(): called for name: '{}', controller: '{}', on '{}'".format(name, c, timer))

        try:
            # check if this scheduler already exist and delete it before create a new one
            if self.scheduler_get(name) is not None:
                self.scheduler_remove(name)
            # create scheduler
            self.scheduler_add(name, self.default, value={'c': c}, next=timer)
        except Exception as e:
            self.logger.error("_createTimer(): ': {}".format(e))

        try:
            if not os.path.isdir(self.path):
                os.makedirs(self.path)
        except OSError as e:
            self.logger.error("_createTimer(): cannot create '{}', error: {}".format(self.path, e.args))
            return

        try:
            f = open(self.path + name, "w")
            f.write(timer.strftime("%s"))
            f.close()
        except IOError as e:
            self.logger.error("_createTimer(): I/O error({}): {}".format(e.errno, e.strerror))

    def default(self, c, caller=None, source=None, dest=None):
        """
        this function changes setpoint of the given controller to defined default temperature
        :param c: controller to be used
        """
        self.logger.debug("default(): called for controller: '{}'".format(c))

        if c in self._controller:
            if self._controller[c]['tempDefault'] > 0:
                self._items.return_item(self._controller[c]['setpointItem'])(self._controller[c]['tempDefault'])

            try:
                if os.path.isfile(self.path + 'boost_' + c):
                    os.remove(self.path + 'boost_' + c)
            except IOError as e:
                self.logger.error("default(): I/O error({0}): {1}".format(e.errno, e.strerror))

            try:
                if self.scheduler_get('boost_' + c) is not None:
                    self.scheduler_remove('boost_' + c)
            except Exception as e:
                self.logger.error("default(): {}".format(e))

        else:
            self.logger.error("default(): unknown controller '{}' - we only have '{}'".format(c, self._controller.keys()))

    def boost(self, c):
        """
        this function changes setpoint of the given controller to defined boost temperature
        :param c: controller to be used
        """
        self.logger.debug("boost(): called for controller: '{}'".format(c))

        if c in self._controller:
            if self._controller[c]['tempBoost'] > 0:
                self._items.return_item(self._controller[c]['setpointItem'])(self._controller[c]['tempBoost'])
                shtime = Shtime.get_instance()
                self._createTimer('boost_' + c, c, shtime.now() + datetime.timedelta(minutes=1))

        else:
            self.logger.error("boost() unknown controller '{}' - we only have '{}'".format(c, self._controller.keys()))

    def drop(self, c):
        """
        this function changes setpoint of the given controller to defined drop temperature
        :param c: controller to be used
        """
        self.logger.debug("drop(): called for controller: '{}'".format(c))

        if c in self._controller:
            if self._controller[c]['tempDrop'] > 0:
                self._items.return_item(self._controller[c]['setpointItem'])(self._controller[c]['tempDrop'])
        else:
            self.logger.error("drop() unknown controller '{}' - we only have '{}'".format(c, self._controller.keys()))
