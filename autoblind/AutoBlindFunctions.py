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
import logging
import threading
from . import AutoBlindLogger


class AbFunctions:
    # return instance of smarthome.py class
    @property
    def ab_alive(self):
        return self.__ab_alive

    @ab_alive.setter
    def ab_alive(self, value):
        self.__ab_alive = value

    def __init__(self, smarthome):
        self.logger = logging.getLogger(__name__)
        self.__sh = smarthome
        self.__locks = {}
        self.__ab_alive = False

    # get a lock object
    # lock_id: Id of the lock object to return
    def __get_lock(self, lock_id):
        if lock_id not in self.__locks:
            self.__locks[lock_id] = threading.Lock()
        return self.__locks[lock_id]

    # return new item value for "manual" item
    # item_id: Id of "manual" item
    # caller: Caller that triggered the update
    # source: Source that triggered the update
    # The Method will determine the original caller/source and then check if this original caller/source is not
    # contained in as_manual_exclude list (if given) and is contained in as_manual_include list (if given).
    # If the original caller/source should be consiedered, the method returns the inverted value of the item.
    # Otherwise, the method returns the current value of the item, so that no change will be made
    def manual_item_update_eval(self, item_id, caller=None, source=None):
        item = self.__sh.return_item(item_id)
        if item is None:
            self.logger.error("manual_item_update_eval: item {0} not found!".format(item_id))

        # Leave immediately in case AutoBlind Plugin is not yet fully running
        if not self.__ab_alive:
            return item()

        lock = self.__get_lock(item_id)
        try:
            lock.acquire()

            if "as_manual_logitem" in item.conf:
                elog_item_id = item.conf["as_manual_logitem"]
                elog_item = self.__sh.return_item(elog_item_id)
                if elog_item is None:
                    self.logger.error("manual_item_update_item: as_manual_logitem {0} not found!".format(elog_item_id))
                    elog = AutoBlindLogger.AbLoggerDummy()
                else:
                    elog = AutoBlindLogger.AbLogger.create(elog_item)
            else:
                elog = AutoBlindLogger.AbLoggerDummy()
            elog.header("manual_item_update_eval")
            elog.debug("running for item '{0}' source '{1}' caller '{2}'", item_id, caller, source)

            retval_no_trigger = item()
            retval_trigger = not item()
            elog.debug("Current value of item {0} is {1}", item_id, retval_no_trigger)

            original_caller, original_source = self.get_original_caller(elog, caller, source)
            elog.debug("original trigger by caller '{0}' source '{1}'", original_caller, original_source)

            if "as_manual_exclude" in item.conf:
                # get list of exclude entries
                exclude = item.conf["as_manual_exclude"]

                if isinstance(exclude, str):
                    exclude = [exclude, ]
                elif not isinstance(exclude, list):
                    elog.error("Item '{0}', Attribute 'as_manual_exclude': Value must be a string or a list!", item_id)
                    return retval_no_trigger
                elog.debug("checking exclude values: {0}", exclude)
                elog.increase_indent()

                # If current value is in list -> Return "NoTrigger"
                for entry in exclude:
                    entry_caller, __, entry_source = entry.partition(":")
                    if (entry_caller == original_caller or entry_caller == "*") and (
                            entry_source == original_source or entry_source == "*"):
                        elog.debug("{0}: matching. Writing value {1}", entry, retval_no_trigger)
                        return retval_no_trigger
                    elog.debug("{0}: not matching", entry)
                elog.decrease_indent()

            if "as_manual_include" in item.conf:
                # get list of include entries
                include = item.conf["as_manual_include"]
                if isinstance(include, str):
                    include = [include, ]
                elif not isinstance(include, list):
                    elog.error("Item '{0}', Attribute 'as_manual_include': Value must be a string or a list!", item_id)
                    return retval_no_trigger
                elog.debug("checking include values: {0}", include)
                elog.increase_indent()

                # If current value is in list -> Return "Trigger"
                for entry in include:
                    entry_caller, __, entry_source = entry.partition(":")
                    if (entry_caller == original_caller or entry_caller == "*") and (
                            entry_source == original_source or entry_source == "*"):
                        elog.debug("{0}: matching. Writing value {1}", entry, retval_trigger)
                        return retval_trigger
                    elog.debug("{0}: not matching", entry)

                # Current value not in list -> Return "No Trigger
                elog.debug("No include values matching. Writing value {0}", retval_no_trigger)
                return retval_no_trigger
            else:
                # No include-entries -> return "Trigger"
                elog.debug("No include limitation. Writing value {0}", retval_trigger)
                return retval_trigger
        finally:
            lock.release()

    # determine original caller/source
    # elog: instance of logging class
    # caller: caller
    # source: source
    def get_original_caller(self, elog, caller, source):
        original_caller = caller
        original_source = source
        while original_caller == "Eval":
            original_item = self.__sh.return_item(original_source)
            if original_item is None:
                elog.debug("get_original_caller({0}, {1}): original item not found", original_caller, original_source)
                break
            original_changed_by = original_item.changed_by()
            if ":" not in original_changed_by:
                text = "get_original_caller({0}, {1}): changed by {2} -> separator missing"
                elog.debug(text, original_caller, original_source, original_changed_by)
                break
            oc = original_caller
            os = original_source
            original_caller, __, original_source = original_changed_by.partition(":")
            elog.debug("get_original_caller({0}, {1}): changed by {2}, {3} at {4}", oc, os, original_caller, original_source, original_item.last_change())

        elog.debug("get_original_caller: returning {0}, {1}", original_caller, original_source)
        return original_caller, original_source
