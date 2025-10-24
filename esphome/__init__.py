#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin display info about ESPHome devices
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

import asyncio
#import sys

from zeroconf import IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf

import aioesphomeapi

from lib.shtime import Shtime

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class EspHome(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.0.2'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

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
        self.shtime = Shtime.get_instance()

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        # self._cycle = 60

        # if you want to use an item to toggle plugin execution, enable the
        # definition in plugin.yaml and uncomment the following line
        #self._pause_item_path = self.get_parameter_value('pause_item')

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

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
        #self.scheduler_add(self.get_fullname() + '_poll', self.poll_device, cycle=self._cycle)

        # Start the asyncio eventloop in it's own thread
        # and set self.alive to True when the eventloop is running
        # (enable the following line, if you need to use asyncio in the plugin)
        self.start_asyncio(self.plugin_coro())

        #self.alive = True     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # let the plugin change the state of pause_item
        #if self._pause_item:
        #    self._pause_item(False, self.get_fullname())

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
        self.stop_asyncio()

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

        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug(f"parse item: {item}")

        # todo
        # if interesting item for sending values:
        #   self._itemlist.append(item)
        #   return self.update_item

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
            self.logger.info(f"update_item: '{item.property.path}' has been changed outside this plugin by caller '{self.callerinfo(caller, source)}'")

            pass

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # # get the value from the device
        # device_value = ...
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item by calling item(value, caller, source=None, dest=None)
        #     # - value and caller must be specified, source and dest are optional
        #     #
        #     # The simple case:
        #     item(device_value, self.get_fullname())
        #     # if the plugin is a gateway plugin which may receive updates from several external sources,
        #     # the source should be included when updating the value:
        #     item(device_value, self.get_fullname(), source=device_source_id)
        pass

    async def plugin_coro(self):
        """
        Coroutine for the plugin session (only needed, if using asyncio)

        This coroutine is run as the PluginTask and should
        only terminate, when the plugin is stopped
        """
        self.logger.info("plugin_coro started")

        self.alive = True
        self.logger.info("plugin_coro: Plugin is running (self.alive=True)")

        # ...
        #await self.retrieve_details_main('esphome-test2')
        #await self.retrieve_details_main('wb-aircon')
        #await self.retrieve_details_main('wb-aircon-s3-pins')

        self.logger.info("plugin_coro: Initiating device discovery")
        await self.discover_main()


        #await self.wait_for_asyncio_termination()
        #self.logger.notice("plugin_coro: Plugin termination was signaled (by stop() method)")

        self.alive = False
        self.logger.info("plugin_coro: Plugin is stopped (self.alive=False)")

        self.logger.info("plugin_coro finished")
        return

    # ==========================================================================================
    # Code for esphome - discover
    #

    discovered_devices = {}

    FORMAT = "{: <7}|{: <32}|{: <15}|{: <12}|{: <16}|{: <10}|{: <32}"
    COLUMN_NAMES = ("Status", "Name", "Address", "MAC", "Version", "Platform", "Board")

    def decode_bytes_or_none(self, data: str | bytes | None) -> str | None:
        """Decode bytes or return None."""
        if data is None:
            return None
        if isinstance(data, bytes):
            return data.decode()
        return data

    def async_service_update(self,
            zeroconf: Zeroconf,
            service_type: str,
            name: str,
            state_change: ServiceStateChange,
    ) -> None:
        """Service state changed."""
        short_name = name.partition(".")[0]
        if state_change is ServiceStateChange.Removed:
            state = "OFFLINE"
        else:
            state = "ONLINE"
            if self.discovered_devices.get('short_name') is not None:
                if self.discovered_devices[short_name].get('state', '') != 'ONLINE':
                    if state_change != 'Added':
                        self.logger.notice(f"Device re-discovered: {short_name:15} {state_change=}")


        info = AsyncServiceInfo(service_type, name)
        info.load_from_cache(zeroconf)
        properties = info.properties

        address = ""
        if addresses := info.ip_addresses_by_version(IPVersion.V4Only):
            address = str(addresses[0])

        if self.discovered_devices.get(short_name, None) is None:
            self.discovered_devices[short_name] = {}
        self.discovered_devices[short_name]['state'] = state
        self.discovered_devices[short_name]['state_change'] = state_change.name
        self.discovered_devices[short_name]['address'] = address
        self.discovered_devices[short_name]['mac'] = self.decode_bytes_or_none(properties.get(b"mac"))
        self.discovered_devices[short_name]['version'] = self.decode_bytes_or_none(properties.get(b"version"))
        self.discovered_devices[short_name]['platform'] = self.decode_bytes_or_none(properties.get(b"platform"))
        self.discovered_devices[short_name]['board'] = self.decode_bytes_or_none(properties.get(b"board"))
        self.discovered_devices[short_name]['timestamp'] = self.shtime.now()
        self.discovered_devices[short_name]['package_import_url'] = self.decode_bytes_or_none(properties.get(b"package_import_url"))
        self.discovered_devices[short_name]['project_version'] = self.decode_bytes_or_none(properties.get(b"project_version"))
        self.discovered_devices[short_name]['project_name'] = self.decode_bytes_or_none(properties.get(b"project_name"))
        self.discovered_devices[short_name]['network'] = self.decode_bytes_or_none(properties.get(b"network"))
        self.discovered_devices[short_name]['friendly_name'] = self.decode_bytes_or_none(properties.get(b"friendly_name"))
        #self.logger.notice(f"{properties}")
        #self.discovered_devices[short_name]['properties'] = properties

        if self.discovered_devices[short_name]['state_change'] == 'Added':
            self.discovered_devices[short_name]['details'] = {}
            self.logger.notice(f"Device discovered: {short_name:15} (ESPHome={self.discovered_devices[short_name]['version']}, board={self.discovered_devices[short_name]['board']})")
            loop = asyncio.get_event_loop()
            #self.logger.notice(f"- event loop: {loop}")
            # try:
            #     self.run_asyncio_coro(self.retrieve_details_main(short_name), timeout=90, return_exeption=True)
            # except asyncio.TimeoutError:
            #     self.logger.error(f"While retrieving details for {short_name}, a timeout error occured")
            # except Exception as ex:
            #     self.logger.exception(f"While retrieving details for {short_name}, an exception occured: '{ex}'")
            #loop.run_until_complete(self.retrieve_details_main(short_name))

#            try:
#                asyncio.ensure_future(self.retrieve_details_main(short_name), loop=loop)
#            except Exception as ex:
#                self.logger.error(f"{short_name}: While retrieving details, an exception occured: {ex}")

        if self.discovered_devices[short_name]['state_change'] == 'Removed':
            self.discovered_devices[short_name]['details'] = {}
            self.logger.warning(f"{short_name}: Connection to Device lost")
        self.logger.info(f"{short_name}: {self.discovered_devices[short_name]}")

    async def discover_main(self) -> None:
        aiozc = AsyncZeroconf()
        browser = AsyncServiceBrowser(
            aiozc.zeroconf, "_esphomelib._tcp.local.", handlers=[self.async_service_update]
        )

        #try:
        #    await asyncio.Event().wait()
        #finally:
        #    await browser.async_cancel()
        #    await aiozc.async_close()

        await self.wait_for_asyncio_termination()

        await browser.async_cancel()
        await aiozc.async_close()


    def store_entities(self, device_name, entities):

        self.discovered_devices[device_name]['details']['entities'] = {}
        for entity in entities[0]:
            id = entity.object_id
            self.discovered_devices[device_name]['details']['entities'][id] = {}
            self.discovered_devices[device_name]['details']['entities'][id]['entity_type'] = type(entity).__name__
            self.discovered_devices[device_name]['details']['entities'][id]['key'] = entity.key
            self.discovered_devices[device_name]['details']['entities'][id]['name'] = entity.name
            self.discovered_devices[device_name]['details']['entities'][id]['disabled_by_default'] = entity.disabled_by_default
        return


    async def retrieve_details_main(self, device_name):
        """Connect to an ESPHome device and get details."""

        #await asyncio.sleep(5)

        device_address = device_name + '.local'
        # Establish connection
        api = aioesphomeapi.APIClient(device_address, 6053, None)
        await api.connect(login=True)

        # Get API version of the device's firmware
        #print(api.api_version)

        # Show device details
        device_info = await api.device_info()
        #print(device_info)

        # List all entities of the device
        entities = await api.list_entities_services()
        #print(entities)
        self.logger.notice(f"{device_name} details:")
        self.logger.notice(f"{device_name}: - api_version=v{str(api.api_version.major) + '.' + str(api.api_version.minor)}")
        self.logger.notice(f"{device_name}: - {device_info}")
        self.logger.notice(f"{device_name}: - entities={entities}")

        #await self.wait_for_asyncio_termination()
        self.discovered_devices[device_name]['details'] = {}
        self.discovered_devices[device_name]['details']['api_version'] = 'v' + str(api.api_version.major) + '.' + str(api.api_version.minor)
        #self.discovered_devices[device_name]['details']['device_info'] = device_info
        #self.discovered_devices[device_name]['details']['entities_raw'] = entities

        self.store_entities(device_name, entities)

    #loop = asyncio.get_event_loop()
    #loop.run_until_complete(main())
