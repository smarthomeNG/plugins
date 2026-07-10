#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026 - Alexander Schwithal          alex.schwithal(a)web.de
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

from lib.item import Items
from .webif import WebInterface

import asyncio
import logging
import time
from lib.model.smartplugin import SmartPlugin
from CasambiBt import Casambi, discover, Unit
from CasambiBt.errors import AuthenticationError, BluetoothError, NetworkNotFoundError
# from ._unit import Group, Scene, Unit,


class Casambi_bt(SmartPlugin):
    """
    Main class of the Plugin derived from SmartPlugin.
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._rx_items = {}
        self._running = False
        self.numberDevices = 0
        self._devices = []
        self._casa = None
        self._set_casambi_bt_logger('INFO')
        # self._cmd_lock = asyncio.Lock()

        self._mac = self.get_parameter_value('mac')
        self._pwd = self.get_parameter_value('password')

        # Check plugin parameters:
        if (not self._mac) or (len(self._mac) < 1):
            self.logger.error('No valid bluetooth network mac adress specified. Aborting.')
            self._init_complete = False
            return

        if (not self._pwd) or (len(self._pwd) < 1):
            self.logger.error('No valid password specified. Aborting.')
            self._init_complete = False
            return

        self.init_webinterface(WebInterface)

        return

    def run(self):
        """
        Start method for the plugin
        """
        self.logger.info('Starting Casambi_bt plugin')
        self._devices = []
        self._running = True

        # Start the asyncio eventloop in it's own thread
        # and set self.alive to True when the eventloop is running
        self.start_asyncio(self.plugin_coro())

        # self.alive = True     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        while not self.alive:
            time.sleep(0.1)

        self.logger.info('Run function completed!')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.info('Stopping plugin')

        self._running = False

        self.stop_asyncio()

        # self.alive = False   # if using asyncio, do not set self.alive here. Set it in the session coroutine

    async def plugin_coro(self):

        # Connect to the selected network
        self._casa = Casambi()

        self.logger.debug('plugin_coro: Register handler...')
        self._casa.registerDisconnectCallback(self._casa_disconnect_handler)
        self._casa.registerUnitChangedHandler(self._unit_changed_handler)
        self.alive = True
        self._devices = []

        self.logger.debug('Starting discover() 1st')
        try:
            self._devices = await discover()
        except Exception as e:
            self.logger.warning(f'Exception occurred during discover: {e}')

        for d in self._devices:
            self.logger.info(f'Found Casambi device 1st: {d}')
        try:
            self.logger.debug(f'Connecting to bluetooth mac adress {self._mac}')
            await self._casa.connect(self._mac, self._pwd)
        except Exception as e:
            self.logger.warning(f'Exception occurred during casa.connect 1st: {e}, type: {type(e)}, args: {e.args}')
            self.numberDevices = 0

        while self._running:
            if not self._casa.connected:
                self.logger.debug('Not connected. Starting discover()')
                self._devices = []

                try:
                    self._devices = await discover()
                except BluetoothError:
                    self.logger.warning('Exception occurred during discover: BluetoothError')
                except NetworkNotFoundError:
                    self.logger.warning('Exception occurred during discover: NetworkNotFoundError')
                except AuthenticationError:
                    self.logger.warning('Exception occurred during discover: AuthenticationError')
                except Exception as e:
                    self.logger.warning(f'Exception occurred during discover: {e}')

                for d in self._devices:
                    self.logger.info(f'Found Casambi device: {d}')
                    # self.logger.debug(f"Found Casambi device options: {dir(d)}")

                self.logger.info('Now connecting...')

                try:
                    await self._casa.connect(self._mac, self._pwd)
                except BluetoothError:
                    self.logger.warning('Exception occurred during casa.connect: BluetoothError')
                except NetworkNotFoundError:
                    self.logger.warning('Exception occurred during casa.connect: NetworkNotFoundError')
                except AuthenticationError:
                    self.logger.warning('Exception occurred during casa.connect: AuthenticationError')
                except EOFError:
                    self.logger.warning('Exception occurred during casa.connect: EOFError ')
                except Exception as e:
                    self.logger.warning(f'Exception occurred during casa.connect: {e}, type: {type(e)}, args: {e.args}')
                else:
                    self.logger.info('Connect successfull')
            else:
                self.logger.debug('Casa already connected.')

            # Turn all lights on
            # await self._casa.turnOn(None)
            # await asyncio.sleep(5)

            # Turn all lights off
            # await self._casa.setLevel(None, 0)
            # await asyncio.sleep(1)

            # Print the state of all units
            # for u in self._casa.units:
            #    #self.logger.debug(f"{u.__repr__()}")
            #    self.logger.info(f"State Poll: {u.state}, isOn: {u.is_on}, online: {u.online}")
            #    self.logger.info(f"DeviceID Poll: {u.deviceId}, uuid: {u.uuid}, Name: {u.name}, firmwareVersion: {u.firmwareVersion}")
            #    #self.decodeCasambiUnit(u)

            if self._casa and self._casa.connected:
                self.numberDevices = len(self._casa.units)
            else:
                self.numberDevices = 0

            # Wait 100s:
            # await asyncio.sleep(100)
            # block: wait until a stop command is received by the queue
            # await self.wait_for_asyncio_termination()

            for _ in range(100):
                if not self._running:
                    break
                await asyncio.sleep(1)

        self.logger.info('plugin_coro: Stopping...')

        if self._casa is not None:
            self.logger.debug('plugin_coro: Unregister handler...')
            self._casa.unregisterUnitChangedHandler(self._unit_changed_handler)
            self._casa.unregisterDisconnectCallback(self._casa_disconnect_handler)

        if self._casa and self._casa.connected:
            self.logger.debug('plugin_coro: disconnecting casa...')
            await self._casa.disconnect()
            self.logger.debug('plugin_coro: disconnection done.')
        else:
            self.logger.warning('plugin_coro: No need to disconnected casa as it is not connected')

        self.alive = False
        self._devices = []
        self.logger.info('plugin_coro: Plugin is stopped (self.alive=False)')

    def decodeCasambiUnit(self, unit):
        if unit is None:
            self.logger.error('Decoding unit is none. Aborting')
            return
        self.logger.debug(f'Decoding unit {unit.name}, {unit.deviceId}')

        unitID = unit.deviceId
        state = unit.state
        dimValue = 0
        verticalValue = 0
        cctValue = 0
        if state is not None:
            if state.dimmer is not None:
                dimValue = state.dimmer
            if state.vertical is not None:
                verticalValue = state.vertical
            if state.white is not None:
                cctValue = state.white

        # Copy data into casambi item:
        if unitID and (unitID in self._rx_items):
            self.logger.debug('Casambi ID found in rx item list')
            # iterate over all items having this id
            for item in self._rx_items[unitID]:
                if item.conf['casambi_bt_rx_key'].upper() == 'ON':
                    item(unit.is_on, self.get_shortname())
                elif item.conf['casambi_bt_rx_key'].upper() == 'BACKEND_ONLINE_STAT':
                    item(unit.online, self.get_shortname())
                elif item.conf['casambi_bt_rx_key'].upper() == 'DIMMER':
                    item(dimValue, self.get_shortname())
                elif item.conf['casambi_bt_rx_key'].upper() == 'VERTICAL':
                    item(verticalValue, self.get_shortname())
                elif item.conf['casambi_bt_rx_key'].upper() == 'CCT':
                    item(cctValue, self.get_shortname())

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
        if self.get_iattr_value(item.conf, 'casambi_bt_rx_key'):
            # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
            id_item = item
            while not self.has_iattr(id_item.conf, 'casambi_bt_id'):
                id_item = id_item.return_parent()
                if id_item is self._sh:
                    self.logger.error(f'Could not find casambi_bt_id for item {item}')
                    return None
            id = int(id_item.conf['casambi_bt_id'])

            if id not in self._rx_items:
                self._rx_items[id] = []
            self._rx_items[id].append(item)
            # self.logger.debug(f"rx-items dict: {self._rx_items}")

        if self.has_iattr(item.conf, 'casambi_bt_tx_key'):
            # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
            id_item = item
            while not self.has_iattr(id_item.conf, 'casambi_bt_id'):
                id_item = id_item.return_parent()
                if id_item is self._sh:
                    self.logger.error(f'Could not find casambi_bt_id for item {item}')
                    return None

            tx_key = item.conf['casambi_bt_tx_key'].upper()
            id = int(id_item.conf['casambi_bt_id'])
            self.logger.info(f'New TX-item: {item} with casambi_bt ID: {id} and tx key: {tx_key}')

            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        #self.logger.debug("Call function << update_item >>")

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            # self.logger.debug(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'casambi_bt_tx_key'):
                # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
                id_item = item
                while not self.has_iattr(id_item.conf, 'casambi_bt_id'):
                    id_item = id_item.return_parent()
                    if id_item is self._sh:
                        self.logger.error(f'Could not find casambi_bt_id for tx item {item}')
                        return None

                tx_key = item.conf['casambi_bt_tx_key'].upper()
                id = int(id_item.conf['casambi_bt_id'])

                self.logger.debug(
                    f"update_item was called with item '{item}' from caller '{caller}', source '{source}' and dest '{dest}'"
                )
                self.controlDevice(item, id, tx_key)

    def get_rxItemLength(self):
        return len(self._rx_items)

    def get_casa_units(self):
        if self._casa:
            return self._casa.units
        else:
            return []

    def get_casa_units_length(self):
        if self._casa:
            return len(self._casa.units)
        else:
            return 0

    def get_asyncio_state_as_string(self):
        return self.asyncio_state()

    def get_cas_connection_status_as_bool(self):
        return self._casa and self._casa.connected

    def _unit_changed_handler(self, u):
        self.logger.info(f'Update Event from Casambi received for unit {u.deviceId}')
        self.logger.debug(f'State Event: {u.state}, isOn: {u.is_on}, online: {u.online}')
        self.logger.debug(
            f'DeviceID Event: {u.deviceId}, uuid: {u.uuid}, Name: {u.name}, firmwareVersion: {u.firmwareVersion}'
        )
        self.decodeCasambiUnit(u)

    def _casa_disconnect_handler(self):
        self.logger.warning('Disconnect handler triggered')
        # TODO: Implement reconnect

    def controlDevice(self, item, id, key, error_count=0):
        """
        Control message format for switching/dimming of casambi devices
        """

        if not self._casa or not self._casa.connected:
            self.logger.warning('Not connected. Command skipped.')
            return

        sendValue = 0
        unit_instance = Unit(
            _typeId=1,
            deviceId=id,
            uuid='abc-123',
            address='AA:BB:CC:DD:EE:FF',
            name='XYZ',
            firmwareVersion='1.0.5',
            unitType=None,
        )

        if key == 'ON':
            if item():
                self.logger.info('Switching on...')
                try:
                    self.run_asyncio_coro(self._casa.turnOn(unit_instance), return_exeption=True)
                except BluetoothError:
                    self.logger.warning('Exception during switch on command: BluetoothError')
                except NetworkNotFoundError:
                    self.logger.warning('Exception during switch on command: NetworkNotFoundError')
                except AuthenticationError:
                    self.logger.warning('Exception during switch on command: AuthenticationError ')
                except Exception as e:
                    self.logger.warning(f'Exception during switch on command: {e}, type: {type(e)}, args: {e.args}')
            else:
                # Turn all lights off
                self.logger.info('Switching off...')
                try:
                    self.run_asyncio_coro(self._casa.setLevel(unit_instance, 0), return_exeption=True)
                except BluetoothError:
                    self.logger.warning('Exception during switch off command: BluetoothError')
                except NetworkNotFoundError:
                    self.logger.warning('Exception during switch off command: NetworkNotFoundError')
                except AuthenticationError:
                    self.logger.warning('Exception during switch off command: AuthenticationError ')
                except Exception as e:
                    self.logger.warning(f'Exception during switch off command: {e}, type: {type(e)}, args: {e.args}')
        elif key == 'DIMMER':
            sendValue = item()
            try:
                self.run_asyncio_coro(self._casa.setLevel(unit_instance, sendValue), return_exeption=True)
            except Exception as e:
                self.logger.warning(f'Exception during dimmer command: {e}, type: {type(e)}, args: {e.args}')
        elif key == 'VERTICAL':
            sendValue = item()
            try:
                self.run_asyncio_coro(self._casa.setVertical(unit_instance, sendValue), return_exeption=True)
            except Exception as e:
                self.logger.warning(f'Exception during vertical command: {e}, type: {type(e)}, args: {e.args}')
        elif key == 'CCT':
            sendValue = item()
            try:
                self.run_asyncio_coro(self._casa.setWhite(unit_instance, sendValue), return_exeption=True)
            except Exception as e:
                self.logger.warning(f'Exception during CCT command: {e}, type: {type(e)}, args: {e.args}')
        else:
            self.logger.error(f'Unsupported tx key: {key}. Aborting')

    def _set_casambi_bt_logger(self, level: str = 'WARNING') -> None:
        """
        set all Casambi_bt loggers to given level
        """

        level = level.upper()
        # log_level = logging.getLevelName(level)
        log_level = getattr(logging, level, logging.WARNING)

        logging.getLogger('plugins.CasambiBt._client').setLevel(log_level)
        self.logger.info(f'Set all CasambiBt loglevel to {level}')
