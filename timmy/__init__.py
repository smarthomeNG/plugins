#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Jens Höppner         shng[AT]jens-hoeppner[DOT]de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
#
#########################################################################

from lib.model.smartplugin import *
from lib.item import Items
from datetime import timedelta

from .models.TimmyModel import TimmyModel


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory

class Timmy(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release
    PLUGIN_VERSION = '1.8.1'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._model = TimmyModel()
        self._shng_items = Items.get_instance()
        self.__delay_scheduler_names = []
        self.__blink_scheduler_names = []

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        """
        Create relevant Schedulers
        """

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")

        """
        Perform pending intents:
        for pending_delay_model in self.get_pending_intents():
            ... pending_delay_model ...
            self.scheduler_remove(#delay#)

        Remove Sink Schedulers
        """
        # self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'timmy_delay_target_item'):
            item.expand_relativepathes('timmy_delay_target_item', '', '')

            on_seconds = self.get_iattr_value(
                item.conf, 'timmy_delay_on_delay_seconds')
            off_seconds = self.get_iattr_value(
                item.conf, 'timmy_delay_off_delay_seconds')
            target_item = self.get_iattr_value(
                item.conf, 'timmy_delay_target_item')

            scheduler_name = f"delay-{item.path()}"
            self.scheduler_add(
                scheduler_name, self.__perform_last_intent, value=None)
            self.__delay_scheduler_names.append(scheduler_name)

            self._model.append_delay_item(
                item.path(), target_item, on_seconds, off_seconds)
            self.logger.debug(
                f"parsed item '{item.path()}' targeting '{target_item}' on: {on_seconds}s / off: {off_seconds}s")
            return self.__update_item_trigger_delay
        elif self.has_iattr(item.conf, 'timmy_blink_target'):
            item.expand_relativepathes('timmy_blink_target', '', '')

            target_item = self.get_iattr_value(
                item.conf, 'timmy_blink_target')

            blink_pattern = self.get_iattr_value(
                item.conf, 'timmy_blink_pattern')
            if blink_pattern is None:
                blink_pattern = [False, True]

            blink_cycles = self.get_iattr_value(
                item.conf, 'timmy_blink_cycles')
            if blink_cycles is None:
                blink_cycles = [1, 1]

            blink_loops = self.get_iattr_value(
                item.conf, 'timmy_blink_loops')
            if blink_loops is None:
                blink_loops = 0
            else:
                blink_loops = int(blink_loops)

            if len(blink_cycles) != len(blink_pattern):
                self.logger.error(
                    f"{item.path()} - length of timmy_blink_cycles ({len(blink_cycles)} entries) must match length of timmy_blink_pattern ({len(blink_pattern)} entries)")
                return

            scheduler_name = f"blink-{item.path()}"
            self.scheduler_add(
                scheduler_name, self.__perform_blink, offset=0, value=None)
            self.__blink_scheduler_names.append(scheduler_name)

            self._model.append_blink_item(
                item.path(), target_item, blink_pattern, blink_cycles, blink_loops)
            self.logger.debug(
                f"parsed item '{item.path()}' targeting '{target_item}', {'infinite' if blink_loops == 0 else blink_loops} times, pattern: {blink_pattern}, cycles: {blink_cycles}")
            return self.__update_item_trigger_blink

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def __perform_blink(self, source_item_path):
        self.logger.debug(f"__perform_blink from '{source_item_path}' Start")
        blink_model = self._model.get_blink_model_for_item(source_item_path)
        targetted_item = self._shng_items.return_item(blink_model.target_item)
        if blink_model.enabled:
            next_value, seconds, index = blink_model.tick()
            targetted_item(next_value)
            self.scheduler_change(
                f"blink-{source_item_path}", next=self.now() + timedelta(seconds=seconds), prio=1, value={"source_item_path": source_item_path})
            self.logger.debug(
                f"__perform_blink from '{source_item_path}' Cycle {index} to {next_value}")
        else:
            targetted_item(blink_model.return_to)
            self.scheduler_change(
                f"blink-{source_item_path}", next=None, value={"source_item_path": source_item_path})
            self.logger.debug(
                f"__perform_blink from '{source_item_path}' ended to {blink_model.return_to}")

        self.logger.debug(f"__perform_blink from '{source_item_path}' Done")

    def __perform_last_intent(self, source_item_path):
        self.logger.debug(f"__perform_last_intent from '{source_item_path}'")
        delay_model = self._model.get_delay_for_item(source_item_path)
        targetted_item = self._shng_items.return_item(
            delay_model.target_item)

        delay_model.intent_pending = False
        if delay_model.intended_target_state is None:
            self.logger.debug(
                f"__perform_last_intent towards '{targetted_item}' has NO target_state returning without action")
            return

        targetted_item(delay_model.intended_target_state, self.get_shortname(),
                       f"trigger from {source_item_path}")
        self.logger.debug(
            f"__perform_last_intent towards '{targetted_item}' target_state: '{delay_model.intended_target_state}'")

    def schedule_delayed_trigger_in(self, seconds, source_item_path):
        next_time = self.now() + timedelta(seconds=seconds)
        next_time = next_time - timedelta(microseconds=next_time.microsecond)
        self.scheduler_change(
            f"delay-{source_item_path}", next=next_time, value={"source_item_path": source_item_path})
        return next_time

    def __update_item_trigger_blink(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            blink_model = self._model.get_blink_model_for_item(item.path())
            blink_model.enabled = item()
            targetted_item = self._shng_items.return_item(
                blink_model.target_item)
            if blink_model.enabled:
                blink_model.return_to = targetted_item()
            self.scheduler_change(
                f"blink-{item.path()}", next=self.now(), value={"source_item_path": item.path()})

    def __update_item_trigger_delay(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            delay_model = self._model.get_delay_for_item(item.path())
            delay_model.intended_target_state = item.property.value
            delay_model.intent_pending = True

            self.logger.debug(
                f"Launching delay for {delay_model.target_item}")

            if item.property.value == item.property.last_value:
                self.logger.debug(
                    f"No change in intent for {delay_model.target_item}, continuing with previous setting")
                return

            if item.property.value:
                if delay_model.delay_on == 0:
                    self.logger.debug(
                        f"Switching {delay_model.target_item} on immediately")
                    self.__perform_last_intent(item.path())
                else:
                    next_time = self.schedule_delayed_trigger_in(
                        delay_model.delay_on, item.path())
                    self.logger.debug(
                        f"Launching delay_on for {delay_model.target_item}, to be on in {delay_model.delay_on}s, which is at {next_time}")
            else:
                if delay_model.delay_off == 0:
                    self.logger.debug(
                        f"Switching {delay_model.target_item} off immediately")
                    self.__perform_last_intent(item.path())
                else:
                    next_time = self.schedule_delayed_trigger_in(
                        delay_model.delay_off, item.path())
                    self.logger.debug(
                        f"Launching delay_off for {delay_model.target_item}, to be off in {delay_model.delay_off}s, which is at {next_time}")
