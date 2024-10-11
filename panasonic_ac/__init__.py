#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin to control Panasonic air conditioning systems via the
#  Panasonic comfort cloud
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

import os
import json

from lib.model.smartplugin import SmartPlugin
from lib.item import Items


mapping_delimiter = '|'

# optionally import package 'pcomfcloud' from local plugin folder
LOCAL_PACKAGE_IMPORTED = False
EXCEPTION_TEXT = ''
if os.path.isfile(os.path.join('plugins', 'panasonic_ac', 'packages', 'pcomfortcloud', '__init__.py')):
    try:
        import plugins.panasonic_ac.packages.pcomfortcloud as pcomfortcloud
        LOCAL_PACKAGE_IMPORTED = True
    except Exception as ex:
        EXCEPTION_TEXT = str(ex)
else:
    import pcomfortcloud

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class PanComfortCloud(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.3.1'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

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

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 30

        # if you want to use an item to toggle plugin execution, enable the
        # definition in plugin.yaml and uncomment the following line
        #self._pause_item_path = self.get_parameter_value('pause_item')

        # create the var directory for this plugin
        var_plugin_dir = os.path.join(self.get_sh()._var_dir, self.get_shortname())
        try:
            os.mkdir(var_plugin_dir, 0o775 )
        except FileExistsError:
            pass

        # Initialization code goes here
        self._username = self.get_parameter_value('username')
        self._password = self.get_parameter_value('password')

        self._raw = False
        self._token = os.path.join(var_plugin_dir, 'token.json')
        self._skipVerify = False
        self.session = None

        if LOCAL_PACKAGE_IMPORTED:
            self.logger.notice("Using local installation of 'pcomfortcloud' package")
        if EXCEPTION_TEXT != "":
            self.logger.error(f"Exception while importing LOCAL package: {EXCEPTION_TEXT}")
            self._init_complete = False
            return

        if not self.pcc_login():
            # Do not load Plugin, if login fails due to wrong 'pcomfortcloud' package
            self._init_complete = False
            return

        self._devices = {}                    # devices reported by comfort cloud

        self.pcc_readdevicelist()
        for idx, device in enumerate(self._devices):
            index = idx + 1
            self.poll_device()
            #self.logger.notice(f"- Device {index} status: {self._devices[str(index)]['parameters']}")


        self.init_webinterface(WebInterface)
        return


    def _check_plugin_var_dir(self):

        var_dir = os.path.join(self.get_sh()._var_dir, self.get_shortname())
        try:
            os.mkdir(var_dir, 0o775 )
        except FileExistsError:
            pass


    def pcc_getdevicestatus(self, index):
        # index: 1, ...
        if int(index) <= 0 or int(index) > len(self._devices):
            self.logger.error(f"Device with index={index} not found in device list")

        id = self._devices[str(index)]['id']
        try:
            device_status = self.session.get_device(id)['parameters']
        except Exception as ex:
            device_status = {}
            self.logger.dbghigh(f"- Status of device (index={index}) cannot be read - Exception {ex}")
        return device_status


    def pcc_readdevicelist(self):

        for idx, device in enumerate(self.session.get_devices()):
            self._devices[str(idx+1)] = device


    def pcc_login(self):

        if os.path.isfile(self._token):
            with open(self._token, "r") as token_file:
                json_token = json.load(token_file)
        else:
            json_token = None

        try:
            auth = pcomfortcloud.Authentication(
                self._username, self._password,
                json_token,
                self._raw
            )
        except:
            self.logger.error("The installed verson of 'pcomfortcloud' package is not compatible with this plugin")
            self._init_complete = False
            return

        try:
            auth.login()
        except Exception as ex:
            self.logger.notice(f"Exception on auth.login: {ex}")
            self.logger.notice(f"Retrying login without old token")
            json_token = None
            auth = pcomfortcloud.Authentication(
                self._username, self._password,
                json_token,
                self._raw
            )
            auth.login()

        json_token = auth.get_token()
        self.session = pcomfortcloud.ApiClient(
            auth,
            self._raw
        )
        with open(self._token, "w") as token_file:
            json.dump(json_token, token_file, indent=4)
        return True


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'run()'}))

        # connect to network / web / serial device
        # (enable the following lines if you want to open a connection
        #  don't forget to implement a connect (and disconnect) method.. :) )
        #self.connect()

        # setup scheduler for device poll loop
        # (enable the following line, if you need to poll the device.
        #  Rember to un-comment the self._cycle statement in __init__ as well)
        self.scheduler_add(self.get_fullname() + '_poll', self.poll_device, cycle=self._cycle)

        # Start the asyncio eventloop in it's own thread
        # and set self.alive to True when the eventloop is running
        # (enable the following line, if you need to use asyncio in the plugin)
        #self.start_asyncio(self.plugin_coro())

        self.alive = True     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # let the plugin change the state of pause_item
        if self._pause_item:
            self._pause_item(False, self.get_fullname())

        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)
        # Also, don't create the thread in __init__() and start them here, but
        # create and start them here. Threads can not be restarted after they
        # have been stopped...

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'stop()'}))
        self.alive = False     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # let the plugin change the state of pause_item
        if self._pause_item:
            self._pause_item(True, self.get_fullname())

        # this stops all schedulers the plugin has started.
        # you can disable/delete the line if you don't use schedulers
        self.scheduler_remove_all()

        # stop the asyncio eventloop and it's thread
        # If you use asyncio, enable the following line
        #self.stop_asyncio()

        # If you called connect() on run(), disconnect here
        # (remember to write a disconnect() method!)
        #self.disconnect()

        # also, clean up anything you set up in run(), so the plugin can be
        # cleanly stopped and started again

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
        # check for pause item
        if item.property.path == self._pause_item_path:
            self.logger.debug(f'pause item {item.property.path} registered')
            self._pause_item = item
            self.add_item(item, updating=True)
            return self.update_item

        if self.has_iattr(item.conf, 'pcc_index') and self.has_iattr(item.conf, 'pcc_parameter'):
            index = str(self.get_iattr_value(item.conf, 'pcc_index'))
            parameter = self.get_iattr_value(item.conf, 'pcc_parameter')
            config_data = {}
            config_data['index'] = index
            config_data['parameter'] = parameter
            config_data['item'] = item
            mapping = config_data['index'] + mapping_delimiter + config_data['parameter']
            self.add_item(item, mapping=mapping, config_data_dict=config_data, updating=True)
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
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        To prevent a loop, the changed value should only be written to the device, if the plugin is running and
        the value was changed outside of this plugin(-instance). That is checked by comparing the caller parameter
        with the fullname (plugin name & instance) of the plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        # check for pause item
        if item is self._pause_item:
            if caller != self.get_shortname():
                self.logger.debug(f'pause item changed to {item()}')
                if item() and self.alive:
                    self.stop()
                elif not item() and not self.alive:
                    self.run()
            return

        if self.alive and caller != self.get_fullname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this plugin:
            self.logger.dbghigh(f"update_item: '{item.property.path}' has been changed outside this plugin by caller '{self.callerinfo(caller, source)}'")

            config_data = self.get_item_config(item)
            #self.logger.notice(f"update_item: Sending '{item()}' of '{config_data['item']}' to comfort cloud  ->  {config_data=}")

            self.update_pcc_from_item(config_data, item)

        return


    def update_pcc_from_item(self, config_data, item):
        value = item()
        #self.logger.notice(f"update_pcc_from_item: config_data = {config_data}")

        try:
            index = config_data['index']
            kwargs = {}
            if config_data['parameter'] == 'temperature':
                kwargs['temperature'] = float(value)
                self.logger.info(f" -> Device {index}: Setting '{config_data['parameter']}' to {value}°C")
            else:
                if config_data['parameter'] == 'power':
                    kwargs['power'] = pcomfortcloud.constants.Power(int(value))
                elif config_data['parameter'] == 'mode':
                    kwargs['mode'] = pcomfortcloud.constants.OperationMode(int(value))
                elif config_data['parameter'] == 'fanSpeed':
                    kwargs['fanSpeed'] = pcomfortcloud.constants.FanSpeed(int(value))
                elif config_data['parameter'] == 'airSwingHorizontal':
                    kwargs['airSwingHorizontal'] = pcomfortcloud.constants.AirSwingLR(int(value))
                elif config_data['parameter'] == 'airSwingVertical':
                    kwargs['airSwingVertical'] = pcomfortcloud.constants.AirSwingUD(int(value))
                elif config_data['parameter'] == 'eco':
                    kwargs['eco'] = pcomfortcloud.constants.EcoMode(int(value))
                elif config_data['parameter'] == 'nanoe':
                    kwargs['nanoe'] = pcomfortcloud.constants.NanoeMode(int(value))
                else:
                    self.logger.notice(f"update_pcc_from_item: Updating the parameter {config_data['parameter']} is not supported/implemented")
                if kwargs != {}:
                    self.logger.info(f" -> Device {index=}: Setting '{config_data['parameter']}' to {value} ({kwargs[config_data['parameter']].name})")
            if kwargs != {}:
                self.session.set_device(self._devices[config_data['index']]['id'], **kwargs)
        except Exception as ex:
            self.logger.warning(f"Cannot set parameter '{config_data['parameter']}' of device index={config_data['index']} - Exception: {ex}")

        return


    def update_items_with_mapping(self, mapping_root, mapping_key, value=None, value_enum=None):

        update_items = self.get_items_for_mapping(mapping_root + mapping_key)
        if value_enum is None:
            for item in update_items:
                item(value, self.get_fullname())
        else:
            val_num = int(value_enum.value)
            val_str = value_enum.name
            for item in update_items:
                if item.property.type == 'num':
                    item(val_num, self.get_fullname())
                else:
                    item(val_str, self.get_fullname())


    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        for idx, device in enumerate(self._devices):
            index = idx + 1
            self._devices[str(index)]['parameters'] = self.pcc_getdevicestatus(index)

            # Items updaten
            mapping_root = str(index) + mapping_delimiter
            self.update_items_with_mapping(mapping_root, 'name', self._devices[str(index)]['name'])
            if self._devices[str(index)]['parameters'] != {}:
                self.update_items_with_mapping(mapping_root, 'connected', True)
                for key in self._devices[str(index)]['parameters'].keys():
                    try:
                        value = int(self._devices[str(index)]['parameters'][key].value)
                        self.update_items_with_mapping(mapping_root, key, value_enum=self._devices[str(index)]['parameters'][key])
                    except:
                        value = self._devices[str(index)]['parameters'][key]
                        self.update_items_with_mapping(mapping_root, key, value)
            else:
                self.update_items_with_mapping(mapping_root, 'connected', False)

    async def plugin_coro(self):
        """
        Coroutine for the plugin session (only needed, if using asyncio)

        This coroutine is run as the PluginTask and should
        only terminate, when the plugin is stopped
        """
        self.logger.notice("plugin_coro started")

        self.alive = True

        # ...

        self.alive = False

        self.logger.notice("plugin_coro finished")
        return
