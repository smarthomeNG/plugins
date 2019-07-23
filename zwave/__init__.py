#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Thomas Creutz                    <thomas.creutz@gmx.de>
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from lib.model.smartplugin import SmartPlugin

import logging
import time

try:
    from openzwave.network import ZWaveNetwork
    from openzwave.option import ZWaveOption
    from pydispatch import dispatcher
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False

from bin.smarthome import VERSION

ITEMS = 'items'
ITEM = 'item'
LOGICS = 'logics'
NID = 'node_id'


class ZWave(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.4.2'

    def __init__(self, sh):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions **beyond** 1.3: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are implemented
        to support older plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method `get_parameter_value(parameter_name)` instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling `self.get_parameter_value(parameter_name)`. It
        returns the value in the datatype that is defined in the metadata.
        """

        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        try:
            self._sh = sh
            self.listenOn = {}
            self._device = self.get_parameter_value('device')
            self._config_path = self.get_parameter_value('config_path')
            self._logging = self.get_parameter_value('zlogging')
            logfile = self.get_parameter_value('loglevel')
            try:
                self._logfile = '{}/log/{}'.format(self.get_vardir(), logfile)
            except Exception:
                self._logfile = '{}/var/log/{}'.format(self._sh.get_basedir(), logfile)
            self._loglevel = self.get_parameter_value('loglevel')
            self._sec_strategy = self.get_parameter_value('sec_strategy')
            self._ready = False
            self.logger.debug('Initialized: logpath={}, loglevel={}, configpath={}, device={}, sec_strategy={}'.format(
                              self._logfile, self._loglevel, self._config_path, self._device, self._sec_strategy))
        except Exception as err:
            self.logger.error(err)
            self._init_complete = False
            return

        if not REQUIRED_PACKAGE_IMPORTED:
            self.logger.warning("Unable to import Python package 'openzwave'")
            self._init_complete = False

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug('run method called')
        self.alive = True

        try:
            options = ZWaveOption(self._device, config_path=self._config_path, user_path='./var/ozw', cmd_line='')
        except Exception as e:
            self.logger.error('error on create ZWaveOption - {}'.format(e))
            self.alive = False
            return

        try:
            options.set_log_file(self._logfile)
            options.set_save_log_level(self._loglevel)
            options.set_logging(self._logging)
            options.set_append_log_file(False)
            options.set_console_output(False)
            options.set_security_strategy(self._sec_strategy)
            options.lock()
        except Exception as e:
            self.logger.error('error on option.set_* - {}'.format(e))

        self.logger.debug('run -> create network')
        try:
            self._network = ZWaveNetwork(options, autostart=False)
        except Exception as e:
            self.logger.error('error on create Network Object - {}'.format(e))

        self.logger.debug('run -> connect event handler')
        try:
            dispatcher.connect(self.zwave_value_update, ZWaveNetwork.SIGNAL_VALUE_CHANGED)
        except Exception as e:
            self.logger.error('error on connect event handler - {}'.format(e))

        self.logger.debug('run -> start network')
        try:
            self._network.start()
        except Exception as e:
            self.alive = False
            self.logger.error('error on start network - {}'.format(e))

        self.logger.info('use openzwave library: {}'.format(self._network.controller.ozw_library_version))
        self.logger.info('use python library: {}'.format(self._network.controller.python_library_version))
        self.logger.info('use ZWave library: {}'.format(self._network.controller.library_description))

        while self.alive:

            if self._network.state != self._network.STATE_READY:

                self.logger.debug('wait until network is ready... current state is: {}'.format(self._network.state_str))
                if self._network.state == self._network.STATE_FAILED:
                    self.alive = False
                    return

            # Dump network information on STATE_READY
            if self._network.state == self._network.STATE_READY and self._ready is False:
                self.logger.info('controller ready : {} nodes were found.'.format(self._network.nodes_count))
                self.logger.info('controller node id : {}'.format(self._network.controller.node.node_id))
                self.logger.info('controller node version : {}'.format(self._network.controller.node.version))
                self.logger.info('Network home id : {}'.format(self._network.home_id_str))
                self.logger.info('Nodes in network : {}'.format(self._network.nodes_count))

                self.logger.info("zwave: Start refresh values")
                for __id in self.listenOn:
                    __val = self._network.get_value(__id)
                    self.logger.info("zwave: id : '{}', val: '{}'".format(__id, __val))
                    for __item in self.listenOn[__id][ITEMS]:
                        __item(__val.data, 'ZWave')

                self._ready = True

            time.sleep(3.0)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("zwave: stop method called")
        self._network.stop()
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
        if self.has_iattr(item.conf, 'zwave_node') and self.has_iattr(item.conf, 'zwave_value'):
            node_id = int(self.get_iattr_value(item.conf, 'zwave_node').strip())
            value_id = int(self.get_iattr_value(item.conf, 'zwave_value').strip())
            self.logger.debug('connecting item {} to node {} value {}'.format(item, node_id, value_id))
            if value_id not in self.listenOn:
                self.listenOn[value_id] = {NID: node_id, ITEMS: [item], LOGICS: []}
            elif item not in self.listenOn[value_id][ITEMS]:
                self.listenOn[value_id][ITEMS].append(item)
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.has_iattr(item.conf, 'zwave_node') and self.has_iattr(item.conf, 'zwave_value'):
            self.logger.debug("zwave: update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(
                              item, caller, source, dest))
            self.logger.debug("zwave: item value is '{}' from type '{}'".format(item(), type(item())))
        try:
            self._network._manager.setValue(int(item.conf['zwave_value']), item())
        except Exception as e:
            self.logger.error('update_item error - {}'.format(e))

    def zwave_value_update(self, network, node, value):
        """
        Dispatcher to Trigger Item Updates
        :param network: the network object
        :param node: the node object which is updated
        :param value: the value object which is updated
        """
        value_id = value.value_id
        self.logger.debug('zwave_value_update called for value_id={} and value={}'.format(value_id, value.data))
        self.logger.debug('self.listenOn={}'.format(self.listenOn))
        if value_id in self.listenOn:
            if self.listenOn[value_id][ITEMS] is not None:
                for item in self.listenOn[value_id][ITEMS]:
                    try:
                        item(value.data, 'ZWave')
                    except Exception as e:
                        self.logger.error('zwave_value_update error - {}'.format(e))
            else:
                self.logger.debug('listener found, but no items bound')
        else:
            self.logger.debug('no listener defined')
