#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
#########################################################################
#  Finite state machine plugin for SmartHomeNG
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
from . import StateEngineTools
from . import StateEngineCurrent
from random import randint
import subprocess
import datetime
from lib.shtime import Shtime


class SeEval(StateEngineTools.SeItemChild):
    # Initialize
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        super().__init__(abitem)
        self.shtime = Shtime.get_instance()

    # Get lamella angle based on sun_altitute for sun tracking
    def sun_tracking(self):
        self._log_debug("Executing method 'SunTracking()'")
        self._log_increase_indent()

        altitude = StateEngineCurrent.values.get_sun_altitude()
        self._log_debug("Current sun altitude is {0}°", altitude)

        value = 90 - altitude
        self._log_debug("Blinds at right angle to the sun at {0}°", value)

        self._log_decrease_indent()
        return value

    # Return random integer
    # min_value: minimum value for random integer (default 0)
    # max_value: maximum value for random integer (default 255)
    def get_random_int(self, min_value=0, max_value=255):
        self._log_debug("Executing method 'GetRandomInt({0},{1})'", min_value, max_value)
        return randint(min_value, max_value)

    # Execute a command
    # command: command to execute
    def execute(self, command):
        self._log_debug("Executing method 'execute({0})'", command)
        try:
            return subprocess.call(command, shell=True)
        except Exception as ex:
            self._log_exception(ex)

    # Return a variable
    # varname: name of variable to return
    def get_variable(self, varname):
        self._log_debug("Executing method 'get_variable({0})'", varname)
        try:
            return self._abitem.get_variable(varname)
        except Exception as ex:
            self._log_exception(ex)

    # Return the absolute id of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose absolute id should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemid(self, subitem_id):
        self._log_debug("Executing method 'get_relative_itemid({0})'", subitem_id)
        try:
            item = self._abitem.return_item(subitem_id)
            return item.property.path
        except Exception as ex:
            self._log_warning("Problem evaluating name of {0}: {1}", subitem_id, ex)

    # Return the item object related to the StateEngine Object Item
    # item_id: Relative id of item whose absolute item object should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_item(self, subitem_id):
        self._log_debug("Executing method 'get_relative_item({0})'", subitem_id)
        try:
            item = self._abitem.return_item(subitem_id)
            return item
        except Exception as ex:
            self._log_warning("Problem evaluating item {0}: {1}", subitem_id, ex)

    # Return the value of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose value should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemvalue(self, subitem_id):
        self._log_debug("Executing method 'get_relative_itemvalue({0})'", subitem_id)
        try:
            item = self._abitem.return_item(subitem_id)
            self._log_info("Return '{0}' for item {1}", item.property.value, subitem_id)
            return item.property.value
        except Exception as ex:
            self._log_warning("Problem evaluating value of '{0}': {1}", subitem_id, ex)

    # Return the property of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose property should be returned
    # prop: name of property, e.g. last_change. See https://www.smarthomeng.de/user/konfiguration/items_properties.html?highlight=property
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemproperty(self, subitem_id, prop):
        self._log_debug("Executing method 'get_relative_itemproperty({0}, {1})'", subitem_id, prop)
        try:
            item = self._abitem.return_item(subitem_id)
        except Exception as ex:
            self._log_warning("Problem evaluating property of {0} - relative item might not exist. Error: {1}", subitem_id, ex)
            return
        try:
            propvalue = getattr(item.property, prop)
            self._log_debug("Item property {0} from {1} is: {2}", prop, item.property.path, propvalue)
            return propvalue
        except Exception as ex:
            self._log_warning("Problem evaluating property {0} of {1} - property might not exist. Error: {2}", prop, subitem_id, ex)

    # Return an attribute of the current state declaration
    # item: can be a (relative) item or a stateengine variable
    # attrib: name of attribute, can actually be any attribute name you can think of ;)
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_attributevalue(self, item, attrib):
        self._log_debug("Executing method 'get_attributevalue({0}, {1})'", item, attrib)
        if ":" in item:
            type, item = StateEngineTools.partition_strip(item, ":")
            item = self._abitem.return_item(self._abitem.get_variable(item)) if type =="var" else item
            #item = self._abitem.return_item(item) if type == "item" else item
        else:
            item = self._abitem.return_item(item)
        try:
            attribvalue = item.conf[attrib]
            #attribvalue = getattr(item.property.attributes, attrib)
            self._log_debug("Item attribute {0} from {1} is: {2}", attrib, item.property.path, attribvalue)
            return attribvalue
        except Exception as ex:
            self._log_warning("Problem evaluating attribute {0} of {1} - attribute might not exist. "
                              "Existing item attributes are: {3}. Error: {2}.", attrib, item, ex, getattr(item.property, 'attributes'))

    # Insert end time of suspension into text
    # suspend_item_id: Item whose age is used to determine how much of the suspend time is already over
    # suspend_text: Text to insert end time of suspension into. Use strftime/strptime format codes for the end time
    #               (see https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
    def insert_suspend_time(self, suspend_item_id, suspend_text="Ausgesetzt bis %X"):
        self._log_debug("Executing method 'insert_suspend_time({0}, {1})'", suspend_item_id, suspend_text)
        self._log_increase_indent()
        try:
            suspend_time = self._abitem.get_variable("item.suspend_time")
            self._log_debug("Suspend time is {0}", suspend_time)
            suspend_item = self._abitem.return_item(suspend_item_id)
            if suspend_item is None:
                text = "Eval-Method 'insert_suspend_time': Suspend Item {0} not found!"
                raise ValueError(text.format(suspend_item_id))
            self._log_debug("Suspend item is {0}", suspend_item.property.path)
            suspend_over = suspend_item.age()
            self._log_debug("Current suspend age: {0}", suspend_over)
            suspend_remaining = suspend_time - suspend_over
            self._log_debug("Remaining suspend time: {0}", suspend_remaining)
            if suspend_remaining < 0:
                self._log_debug("Eval-Method 'insert_suspend_time': Suspend should alredy be finished!")
                return "Suspend already over."
            suspend_until = self._abitem.shtime.now() + datetime.timedelta(seconds=suspend_remaining)
            self._log_debug("Suspend finished at {0}", suspend_until)
            return suspend_until.strftime(suspend_text)
        except Exception as ex:
            self._log_exception(ex)
            return "(Error while determining text. Check log)"
        finally:
            self._log_decrease_indent()
