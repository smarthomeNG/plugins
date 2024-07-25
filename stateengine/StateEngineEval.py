#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
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
from . import StateEngineDefaults
from random import randint
import subprocess
import datetime
from lib.shtime import Shtime
import threading


class SeEval(StateEngineTools.SeItemChild):
    # Initialize
    # abitem: parent SeItem instance
    def __init__(self, abitem):
        super().__init__(abitem)
        self._eval_lock = threading.Lock()
        self.shtime = Shtime.get_instance()

    def __repr__(self):
        return "SeEval"

    # Get lamella angle based on sun_altitude for sun tracking
    def sun_tracking(self, offset=None):
        def remap(_value, _minoutput):
            _value = 100 if _value > 100 else _value
            _value = 0 if _value < 0 else _value
            output_span = 100 - _minoutput
            scaled_thrust = float(_value) / float(100)
            return _minoutput + (scaled_thrust * output_span)

        if offset is None:
            offset = StateEngineDefaults.suntracking_offset
        else:
            try:
                offset = float(offset)
            except Exception as e:
                offset = 0
                self._log_warning("Problem handling offset {0}: {1}", offset, e)
        self._eval_lock.acquire()
        self._log_debug("Executing method 'SunTracking({0})'", offset)
        self._log_increase_indent()

        altitude = StateEngineCurrent.values.get_sun_altitude()
        self._log_debug("Current sun altitude is {0:.2f}°", altitude)
        _lamella_open_value = StateEngineDefaults.lamella_open_value
        _lamella_text = " (based on lamella open value of {0})".format(_lamella_open_value)
        value = remap(90 - altitude, _lamella_open_value) + offset
        self._log_debug("Blinds at right angle to the sun at {0}° with an offset of {1}°{2}",
                        value, offset, _lamella_text)

        self._log_decrease_indent()
        self._eval_lock.release()
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
        self._eval_lock.acquire()
        self._log_debug("Executing method 'get_variable({0})'", varname)
        try:
            if self._abitem.initactionname and varname == 'current.action_name':
                returnvalue = self._abitem.initactionname
                self._log_debug("Return '{}' for variable {} during init", returnvalue, varname)
            else:
                returnvalue = self._abitem.get_variable(varname)
                self._log_debug("Return '{}' for variable {}", returnvalue, varname)
        except Exception as ex:
            returnvalue = None
            self._log_exception(ex)
        finally:
            self._eval_lock.release()
        return returnvalue

    # Return the absolute id of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose absolute id should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemid(self, subitem_id):
        self._eval_lock.acquire()
        self._log_debug("Executing method 'get_relative_itemid({0})'", subitem_id)
        try:
            if self._abitem.initstate and subitem_id == '..state_name':
                returnvalue = self._abitem.return_item(self._abitem.initstate.id)[0].property.path
                self._log_debug("Return item path '{0}' during init", returnvalue)
            else:
                returnvalue = self._abitem.return_item(subitem_id)[0].property.path
                self._log_debug("Return item path '{0}'", returnvalue)
        except Exception as ex:
            returnvalue = None
            self._log_warning("Problem evaluating name of {0}: {1}", subitem_id, ex)
        finally:
            self._eval_lock.release()
        return returnvalue

    # Return the item object related to the StateEngine Object Item
    # item_id: Relative id of item whose absolute item object should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_item(self, subitem_id):
        self._eval_lock.acquire()
        self._log_debug("Executing method 'get_relative_item({0})'", subitem_id)
        try:
            if self._abitem.initstate and subitem_id == '..state_name':
                returnvalue, issue = self._abitem.return_item(self._abitem.initstate.id)
                self._log_debug("Return item '{0}' during init", returnvalue)
            else:
                returnvalue, issue = self._abitem.return_item(subitem_id)
                self._log_debug("Return item '{0}'", returnvalue)
        except Exception as ex:
            returnvalue = None
            self._log_warning("Problem evaluating item {0}: {1}", subitem_id, ex)
        finally:
            self._eval_lock.release()
        return returnvalue

    # Return the value of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose value should be returned
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemvalue(self, subitem_id):
        self._eval_lock.acquire()
        returnvalue = []
        self._log_debug("Executing method 'get_relative_itemvalue({0})'", subitem_id)
        try:
            if self._abitem.initstate and subitem_id == '..state_name':
                returnvalue = self._abitem.initstate.text
                self._log_debug("Return item value '{0}' during init", returnvalue)
            else:
                item, issue = self._abitem.return_item(subitem_id)
                returnvalue = item.property.value
                returnvalue = StateEngineTools.convert_str_to_list(returnvalue)
                issue = f" Issue: {issue}" if issue not in [[], None, [None]] else ""
                self._log_debug("Return item value '{0}' for item {1}.{2}",
                                returnvalue, subitem_id, issue)
        except Exception as ex:
            self._log_warning("Problem evaluating value of '{0}': {1}", subitem_id, ex)
        finally:
            self._eval_lock.release()
        returnvalue = returnvalue[0] if len(returnvalue) == 1 else None if len(returnvalue) == 0 else returnvalue
        return returnvalue

    # Return the property of an item related to the StateEngine Object Item
    # item_id: Relative id of item whose property should be returned
    # prop: name of property, e.g. last_change. See https://www.smarthomeng.de/user/konfiguration/items_properties.html
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_relative_itemproperty(self, subitem_id, prop):
        self._eval_lock.acquire()
        self._log_debug("Executing method 'get_relative_itemproperty({0}, {1})'", subitem_id, prop)
        try:
            item, _ = self._abitem.return_item(subitem_id)
        except Exception as ex:
            self._log_warning("Problem evaluating property of {0} - relative item might not exist. Error: {1}",
                              subitem_id, ex)
            self._eval_lock.release()
            return
        try:
            if self._abitem.initstate and subitem_id == '..state_name':
                returnvalue = getattr(self._abitem.return_item(self._abitem.initstate.id)[0].property, prop)
                self._log_debug("Return item property '{0}' from {1}: {2} during init", prop,
                                self._abitem.return_item(self._abitem.initstate.id)[0].property.path, returnvalue)
            else:
                returnvalue = getattr(item.property, prop)
                if prop == "value":
                    returnvalue = StateEngineTools.convert_str_to_list(returnvalue)
                    returnvalue = returnvalue[0] if len(returnvalue) == 1 else None if len(
                        returnvalue) == 0 else returnvalue
                self._log_debug("Return item property {0} from {1}: {2}", prop, item.property.path, returnvalue)
        except Exception as ex:
            returnvalue = None
            self._log_warning("Problem evaluating property {0} of {1} - property might not exist. Error: {2}",
                              prop, subitem_id, ex)
        finally:
            self._eval_lock.release()
        return returnvalue

    # Alias for get_attributevalue
    # item: can be a (relative) item or a stateengine variable
    # attrib: name of attribute, can actually be any attribute name you can think of ;)
    def get_attribute_value(self, item, attrib):
        self.get_attributevalue(item, attrib)

    # Return an attribute of the current state declaration
    # item: can be a (relative) item or a stateengine variable
    # attrib: name of attribute, can actually be any attribute name you can think of ;)
    #
    # See description of StateEngineItem.SeItem.return_item for details
    def get_attributevalue(self, item, attrib):
        self._eval_lock.acquire()
        self._log_debug("Executing method 'get_attributevalue({0}, {1})'", item, attrib)
        issue = None
        if ":" in item:
            var_type, item = StateEngineTools.partition_strip(item, ":")
            if var_type == "var":
                item, issue = self._abitem.return_item(self._abitem.get_variable(item))
        else:
            item, issue = self._abitem.return_item(item)
        try:
            if self._abitem.initstate and item == '..state_name':
                returnvalue, issue = self._abitem.return_item(self._abitem.initstate.id).conf[attrib]
                self._log_debug("Return item attribute '{0}' from {1}: {2} during init. Issue {3}", attrib,
                                self._abitem.return_item(self._abitem.initstate.id)[0].property.path, returnvalue, issue)
            else:
                returnvalue = item.conf[attrib]
                self._log_debug("Return item attribute {0} from {1}: {2}. Issue {3}",
                                attrib, item.property.path, returnvalue, issue)
        except Exception as ex:
            returnvalue = None
            self._log_warning("Problem evaluating attribute {0} of {1} - attribute might not exist. "
                              "Existing item attributes are: {3}. Error: {2}.",
                              attrib, item, ex, getattr(item.property, 'attributes'))
        finally:
            self._eval_lock.release()
        return returnvalue

    # Insert end time of suspension into text
    # suspend_item_id: Item whose age is used to determine how much of the suspend time is already over
    # suspend_text: Text to insert end time of suspension into. Use strftime/strptime format codes for the end time
    #               (see https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior)
    def insert_suspend_time(self, suspend_item_id, suspend_text="Ausgesetzt bis %X"):
        self._eval_lock.acquire()
        self._log_debug("Executing method 'insert_suspend_time({0}, {1})'", suspend_item_id, suspend_text)
        self._log_increase_indent()
        try:
            suspend_time = self._abitem.get_variable("item.suspend_time") or 0
            self._log_debug("Suspend time is {0}", suspend_time)
            suspend_item, issue = self._abitem.return_item(suspend_item_id)
            if suspend_item is None:
                text = "Eval-Method 'insert_suspend_time': Suspend Item {0} not found!"
                self._eval_lock.release()
                raise ValueError(text.format(suspend_item_id))
            self._log_debug("Suspend item is {0}", suspend_item.property.path)
            suspend_over = suspend_item.property.last_change_age
            self._log_debug("Current suspend age: {0}", suspend_over)
            suspend_remaining = suspend_time - suspend_over
            self._log_debug("Remaining suspend time: {0}", suspend_remaining)
            if suspend_remaining < 0:
                self._log_debug("Eval-Method 'insert_suspend_time': Suspend time already over.")
                self._eval_lock.release()
                return "Suspend already over."
            suspend_until = self._abitem.shtime.now() + datetime.timedelta(seconds=suspend_remaining)
            self._log_debug("Suspend finished at {0}", suspend_until)
        except Exception as ex:
            self._log_exception(ex)
            if self._eval_lock.locked():
                self._eval_lock.release()
            return "(Error while determining text. Check log)"
        finally:
            self._log_decrease_indent()
            if self._eval_lock.locked():
                self._eval_lock.release()
        return suspend_until.strftime(suspend_text)
