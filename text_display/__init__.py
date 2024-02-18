#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Jens Höppner         mail[AT]jens-hoeppner[DOT]de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
#  upwards.
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
from .webif import WebInterface

from .models.TextDisplayModel import TextDisplayModel


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory

class TextDisplay(SmartPlugin):
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
        
        self.logger.debug("Init method called")

        self._model = TextDisplayModel()
        self._shng_items = Items.get_instance()
        self.init_webinterface(WebInterface)
        self.__sink_scheduler_names = []

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self._model.reset_sinks()

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
        if self.has_iattr(item.conf, 'text_display_target_ring'):
            target_ring = self.get_iattr_value(
                item.conf, 'text_display_target_ring')

            item.expand_relativepathes(
                'text_display_content_source_item', '', '')
            content_source_path = self.get_iattr_value(
                item.conf, 'text_display_content_source_item')

            self.logger.debug(
                f"trigger from {item}, content-src: {content_source_path}, to msg-ring {target_ring}")

            self._model.append_message_source_to_ring(
                ring=target_ring,
                content_source_path=content_source_path,
                content_source=lambda: self._shng_items.return_item(
                    content_source_path)(),
                is_relevant_path=item.property.path,
                is_relevant=lambda: item()
            )
            return self.update_item_message_source_relevance

        if self.has_iattr(item.conf, 'text_display_sink_for_rings'):
            source_rings = self.get_iattr_value(
                item.conf, 'text_display_sink_for_rings')
            default_value = self.get_iattr_value(
                item.conf, 'text_display_default_message')
            overruling_rings = self.get_iattr_value(
                item.conf, 'text_display_sink_rings_with_prio')
            cycle_time = self.get_iattr_value(
                item.conf, 'text_display_cycle_time')
            if cycle_time == None:
                cycle_time = 3
            sink_item_path = item.property.path

            self.logger.debug(
                f"{sink_item_path} shall be sink for rings {source_rings}, with default {default_value}, cycle-time {cycle_time}s")

            self._model.append_message_sink_to_rings(
                sink_item_path, source_rings, default_value, tick_time_hint=cycle_time)

            if overruling_rings is None:
                self.logger.debug(f"No overruling-rings")
            else:
                self.logger.debug(f"Overruling rings: {overruling_rings}")
                self._model.append_message_sink_to_overruling_rings(
                    sink_item_path, overruling_rings)

            scheduler_name = f"msg_sink-{sink_item_path}"
            self.scheduler_add(
                scheduler_name, lambda: self.tick_sink(sink_item_path), cycle=cycle_time, offset=.2)
            self.__sink_scheduler_names.append(scheduler_name)

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def tick_sink(self, sink_item_path):
        sink_item = self._shng_items.return_item(sink_item_path)
        if sink_item.property.type == 'bool':
            sink_item(self._model.sink_has_messages_present(
                sink_item_path), self.get_shortname(), "sink_has_messages_present")
        else:
            value = self._model.tick_sink(sink_item_path)
            if value is not None:
                sink_item(value, self.get_shortname(), "tick_sink")

    def retrigger_item_message_sink_cycle(self, sink_item_path):
        tth = self._model.get_sink_model(sink_item_path).tick_time_hint
        self.scheduler_change(f"msg_sink-{sink_item_path}", cycle=tth)
        self.tick_sink(sink_item_path)

    def update_item_message_source_relevance(self, item, caller=None, source=None, dest=None):
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
            if item.property.value and item.property.value != item.property.last_value:
                self._model.update_source_relevance(item.property.path)
                ring_name = self._model.get_ring_for_relevance_item(
                    item.property.path)
                sink_items = self._model.get_sink_item_paths_for_ring(
                    ring_name)
                for sink_item_path in sink_items:
                    self.retrigger_item_message_sink_cycle(sink_item_path)
