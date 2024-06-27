#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013-2014 Robert Budde                   robert@ing-budde.de
#  Copyright 2014 Alexander Schwithal                 aschwith
#########################################################################
#  Enocean plugin for SmartHomeNG.      https://github.com/smarthomeNG//
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

import serial
import logging
import threading
from time import sleep

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .protocol import CRC
from .protocol.eep_parser import EEP_Parser
from .protocol.packet_data import Packet_Data
from .protocol.constants import (
    PACKET, PACKET_TYPE, COMMON_COMMAND, SMART_ACK, EVENT, RETURN_CODE, RORG
)
from .webif import WebInterface


class EnOcean(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.4.2"

    def __init__(self, sh):
        """ Initializes the plugin. """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.port = self.get_parameter_value("serialport")
        self._log_unknown_msg = self.get_parameter_value("log_unknown_messages")
        self._connect_retries = self.get_parameter_value("retry")
        self._retry_cycle = self.get_parameter_value("retry_cycle")
        tx_id = self.get_parameter_value("tx_id")
        if len(tx_id) < 8:
            self.tx_id = 0
            self.logger.warning('No valid enocean stick ID configured. Transmitting is not supported')
        else:
            self.tx_id = int(tx_id, 16)
            self.logger.info(f"Stick TX ID configured via plugin.conf to: {tx_id}")
#
        self._items = []
        self._tcm = None
        self._cmd_lock = threading.Lock()
        self._response_lock = threading.Condition()
        self._rx_items = {}
        self._used_tx_offsets = []
        self._unused_tx_offset = None
        self.UTE_listen = False
        self.unknown_sender_id = 'None'
        self._block_ext_out_msg = False
        self.log_for_debug = self.logger.isEnabledFor(logging.DEBUG)

        # init eep_parser
        self.eep_parser = EEP_Parser(self.logger)

        # init prepare_packet_data
        self.prepare_packet_data = Packet_Data(self)

        # init crc parser
        self.crc = CRC()

        self.init_webinterface(WebInterface)

    def run(self):
        if self.log_for_debug:
            self.logger.debug("Run method called")

        self.alive = True
        self.UTE_listen = False
        msg = []

        while self.alive:

            # just try connecting anytime the serial object is not initialized
            connect_count = 0
            while self._tcm is None and self.alive:
                if self._connect_retries > 0 and connect_count >= self._connect_retries:
                    self.alive = False
                    break
                if not self.connect():
                    connect_count += 1
                    self.logger.info(f'connecting failed {connect_count} times. Retrying after 5 seconds...')
                    sleep(self._retry_cycle)

            # main loop, read from device
            readin = None
            try:
                readin = self._tcm.read(1000)
            except Exception as e:
                if self.alive:
                    self.logger.error(f"Exception during tcm read occurred: {e}")
                # reset serial device
                try:
                    self._tcm.close()
                except Exception:
                    pass
                self._tcm = None
                continue

            if readin:
                msg += readin
                if self.log_for_debug:
                    self.logger.debug(f"Data received: {readin}")
                # check if header is complete (6bytes including sync)
                # 0x55 (SYNC) + 4bytes (HEADER) + 1byte(HEADER-CRC)
                while len(msg) >= 6:
                    # check header for CRC
                    if msg[0] == PACKET.SYNC_BYTE and msg[5] == self.crc(msg[1:5]):
                        # header bytes: sync; length of data (2); optional length; packet type; crc
                        data_length = (msg[1] << 8) + msg[2]
                        opt_length = msg[3]
                        packet_type = msg[4]
                        msg_length = data_length + opt_length + 7
                        if self.log_for_debug:
                            self.logger.debug(f"Received header with data_length = {data_length} / opt_length = 0x{opt_length:02x} / type = {packet_type}")

                        # break if msg is not yet complete:
                        if len(msg) < msg_length:
                            break

                        # msg complete
                        if self.crc(msg[6:msg_length - 1]) == msg[msg_length - 1]:
                            if self.log_for_debug:
                                self.logger.debug("Accepted package with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                            data = msg[6:msg_length - (opt_length + 1)]
                            optional = msg[data_length + 6:msg_length - 1]
                            if packet_type == PACKET_TYPE.RADIO:
                                self._process_packet_type_radio(data, optional)
                            elif packet_type == PACKET_TYPE.SMART_ACK_COMMAND:
                                self._process_packet_type_smart_ack_command(data, optional)
                            elif packet_type == PACKET_TYPE.RESPONSE:
                                self._process_packet_type_response(data, optional)
                            elif packet_type == PACKET_TYPE.EVENT:
                                self._process_packet_type_event(data, optional)
                            else:
                                self.logger.error("Received packet with unknown type = 0x{:02x} - len = {} / data = [{}]".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        else:
                            self.logger.error("Crc error - dumping packet with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        msg = msg[msg_length:]
                    else:
                        # self.logger.warning("Consuming [0x{:02x}] from input buffer!".format(msg[0]))
                        msg.pop(0)

        # self.alive is False or connect error caused loop exit
        self.stop()

    def stop(self):
        self.logger.debug("Stop method called")
        self.alive = False
        self.disconnect()

    def parse_item(self, item):
        self.logger.debug("parse_item method called")
        if 'enocean_rx_key' in item.conf:
            # look for info from the most specific info to the broadest (key->eep->id) - one id might use multiple eep might define multiple keys
            eep_item = item
            found_eep = True

            while 'enocean_rx_eep' not in eep_item.conf:
                eep_item = eep_item.return_parent()
                if eep_item is Items.get_instance():
                    self.logger.error(f"Could not find enocean_rx_eep for item {item}")
                    found_eep = False
                    break

            id_item = eep_item
            found_rx_id = True
            while 'enocean_rx_id' not in id_item.conf:
                id_item = id_item.return_parent()
                if id_item is Items.get_instance():
                    self.logger.error(f"Could not find enocean_rx_id for item {item}")
                    found_rx_id = False
                    break

            # Only proceed, if valid rx_id and eep could be found:
            if found_rx_id and found_eep:

                rx_key = item.conf['enocean_rx_key'].upper()
                rx_eep = eep_item.conf['enocean_rx_eep'].upper()
                rx_id = int(id_item.conf['enocean_rx_id'], 16)

                # check if there is a function to parse payload
                if self.eep_parser.CanParse(rx_eep):

                    if (rx_key in ['A0', 'A1', 'B0', 'B1']):
                        self.logger.warning(f'Key "{rx_key}" does not match EEP - "0" (Zero, number) should be "O" (letter) (same for "1" and "I") - will be accepted for now')
                        rx_key = rx_key.replace('0', 'O').replace("1", 'I')

                    if rx_id not in self._rx_items:
                        self._rx_items[rx_id] = {rx_eep: [item]}
                    elif rx_eep not in self._rx_items[rx_id]:
                        self._rx_items[rx_id][rx_eep] = [item]
                    elif item not in self._rx_items[rx_id][rx_eep]:
                        self._rx_items[rx_id][rx_eep].append(item)

                    self.logger.info(f"Item {item} listens to id {rx_id:08X} with eep {rx_eep} key {rx_key}")
                    # self.logger.info(f"self._rx_items = {self._rx_items}")

        if 'enocean_tx_eep' in item.conf:
            self.logger.debug(f"TX eep found in item {item._name}")

            if 'enocean_tx_id_offset' not in item.conf:
                self.logger.error(f"TX eep found for item {item._name} but no tx id offset specified.")
                return

            tx_offset = item.conf['enocean_tx_id_offset']
            if tx_offset not in self._used_tx_offsets:
                self._used_tx_offsets.append(tx_offset)
                self._used_tx_offsets.sort()
                self.logger.debug(f"Debug offset list: {self._used_tx_offsets}")
                for x in range(1, 127):
                    if x not in self._used_tx_offsets:
                        self._unused_tx_offset = x
                        self.logger.debug(f"Next free offset set to {self._unused_tx_offset}")
                        break
            else:
                self.logger.debug(f"tx_offset {tx_offset} of item {item._name} already used.")

            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        if self.log_for_debug:
            self.logger.debug("update_item method called")

        # self.logger.warning(f"Debug: update item: caller: {caller}, shortname: {self.get_shortname()}, item: {item.id()}")
        if caller != self.get_shortname():

            if self.log_for_debug:
                self.logger.debug(f'Item {item} updated externally.')
            if self._block_ext_out_msg:
                self.logger.warning('Transmitting manually blocked by user. Aborting')
                return
            if 'enocean_tx_eep' in item.conf:
                if isinstance(item.conf['enocean_tx_eep'], str):
                    tx_eep = item.conf['enocean_tx_eep']
                    if self.log_for_debug:
                        self.logger.debug(f'item << {item} >> has tx_eep')
                    # check if Data can be Prepared
                    if not self.prepare_packet_data.CanPrepareData(tx_eep):
                        self.logger.error(f'enocean-update_item: method missing for prepare telegram data for {tx_eep}')
                    else:
                        # call method prepare_packet_data(item, tx_eep)
                        id_offset, rorg, payload, optional = self.prepare_packet_data.PrepareData(item, tx_eep)
                        self._send_radio_packet(id_offset, rorg, payload, optional)
                else:
                    self.logger.error('tx_eep is not a string value')
            else:
                if self.log_for_debug:
                    self.logger.debug(f'Item {item} has no tx_eep value')

    def connect(self, startup=True):
        """ open serial or serial2TCP device """
        self.logger.debug(f'trying to connect to device at {self.port}')
        try:
            self._tcm = serial.serial_for_url(self.port, 57600, timeout=1.5)
        except Exception as e:
            self._tcm = None
            self.logger.error(f"Exception occurred during serial open: {e}")
            return False
        else:
            self.logger.info(f"Serial port successfully opened at port {self.port}")

# why startup in separate thread? time to startup? collision with receiving?
            if startup:
                t = threading.Thread(target=self._startup, name="enocean-startup")
                t.daemon = False
                t.start()

            return True

    def disconnect(self):
        """ close serial or serial2TCP device """
        try:
            self._tcm.close()
        except Exception:
            pass
        self.logger.info("Enocean serial device closed")

    def _startup(self):
        """ send startup sequence to device """
        self.logger.debug("_startup method called")

        # request one time information
        self.logger.info("Resetting device")
        self._send_common_command(COMMON_COMMAND.WR_RESET)
        self.logger.info("Requesting id-base")
        self._send_common_command(COMMON_COMMAND.RD_IDBASE)
        self.logger.info("Requesting version information")
        self._send_common_command(COMMON_COMMAND.RD_VERSION)
        self.logger.debug("Ending startup-thread")

#
# public EnOcean interface methods
#

    def read_num_securedevices(self):
        """ read number of secure devices """
        self.logger.debug("read_num_securedevices method called")
        self._send_common_command(COMMON_COMMAND.RD_NUMSECUREDEVICES)
        self.logger.info("Read number of secured devices")

    def get_smart_ack_devices(self):
        """ request all smart acknowledge devices """
        self.logger.debug("get_smart_ack_devices method called")
        self._send_smart_ack_command(SMART_ACK.RD_LEARNEDCLIENTS)
        self.logger.info("Requesting all available smart acknowledge mailboxes")

    def reset_stick(self):
        """ reset EnOcean transmitter """
        self.logger.debug("reset_stick method called")
        self.logger.info("Resetting device")
        self._send_common_command(COMMON_COMMAND.WR_RESET)

    def block_external_out_messages(self, block=True):
        self.logger.debug("block_external_out_messages method called")
        if block:
            self.logger.info("Blocking of external out messages activated")
            self._block_ext_out_msg = True
        elif not block:
            self.logger.info("Blocking of external out messages deactivated")
            self._block_ext_out_msg = False
        else:
            self.logger.error("Invalid argument. Must be True/False")

    def toggle_block_external_out_messages(self):
        self.logger.debug("toggle block_external_out_messages method called")
        if not self._block_ext_out_msg:
            self.logger.info("Blocking of external out messages activated")
            self._block_ext_out_msg = True
        else:
            self.logger.info("Blocking of external out messages deactivated")
            self._block_ext_out_msg = False

    def toggle_UTE_mode(self, id_offset=0):
        self.logger.debug("Toggle UTE mode")
        if self.UTE_listen:
            self.logger.info("UTE mode deactivated")
            self.UTE_listen = False
        elif id_offset:
            self.start_UTE_learnmode(id_offset)
            self.logger.info(f"UTE mode activated for ID offset {id_offset}")

    def send_bit(self):
        self.logger.info("Trigger Built-In Self Test telegram")
        self._send_common_command(COMMON_COMMAND.WR_BIST)

    def version(self):
        self.logger.info("Request stick version")
        self._send_common_command(COMMON_COMMAND.RD_VERSION)

#
# Utility methods
#

    def get_tx_id_as_hex(self):
        hexstring = "{:08X}".format(self.tx_id)
        return hexstring

    def is_connected(self):
        return self._tcm and self._tcm.is_open

    def get_serial_status_as_string(self):
        return "open" if self.is_connected() else "not connected"

    def get_log_unknown_msg(self):
        return self._log_unknown_msg

    def toggle_log_unknown_msg(self):
        self._log_unknown_msg = not self._log_unknown_msg

#
# (private) packet / protocol methods
#

    def _send_smart_ack_command(self, code, data=[]):
        # self.logger.debug("_send_smart_ack_command method called")
        self._cmd_lock.acquire()
        self._last_cmd_code = code
        self._last_packet_type = PACKET_TYPE.SMART_ACK_COMMAND
        self._send_packet(PACKET_TYPE.SMART_ACK_COMMAND, [code] + data)
        self._response_lock.acquire()
        # wait 5sec for response
        self._response_lock.wait(5)
        self._response_lock.release()
        self._cmd_lock.release()

    def _send_common_command(self, code, data=[], optional=[]):
        # self.logger.debug("_send_common_command method called")
        self._cmd_lock.acquire()
        self._last_cmd_code = code
        self._last_packet_type = PACKET_TYPE.COMMON_COMMAND
        self._send_packet(PACKET_TYPE.COMMON_COMMAND, [code] + data, optional)
        self._response_lock.acquire()
        # wait 5sec for response
        self._response_lock.wait(5)
        self._response_lock.release()
        self._cmd_lock.release()

    def _send_radio_packet(self, id_offset, code, data=[], optional=[]):
        # self.logger.debug("_send_radio_packet method called")
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error(f"Invalid base ID offset range. (Is {id_offset}, must be [0 127])")
            return
        self._cmd_lock.acquire()
        self._last_cmd_code = PACKET.SENT_RADIO
        self._send_packet(PACKET_TYPE.RADIO, [code] + data + list((self.tx_id + id_offset).to_bytes(4, byteorder='big')) + [0x00], optional)
        self._response_lock.acquire()
        # wait 1sec for response
        self._response_lock.wait(1)
        self._response_lock.release()
        self._cmd_lock.release()

    def _send_UTE_response(self, data, optional):
        self.logger.debug("_send_UTE_response method called")
        choice = data[0]
        payload = data[1:-5]
        # sender_id = int.from_bytes(data[-5:-1], byteorder='big', signed=False)
        # status = data[-1]
        # repeater_cnt = status & 0x0F
        db = 0xFF
        Secu = 0x0
        # payload[0] = 0x91: EEP Teach-in response, Request accepted, teach-in successful, bidirectional
        self._send_radio_packet(self.learn_id, choice, [0x91, payload[1], payload[2], payload[3], payload[4], payload[5], payload[6]], [PACKET_TYPE.RADIO_SUB_TEL, data[-5], data[-4], data[-3], data[-2], db, Secu] )
        self.UTE_listen = False
        self.logger.info("Sent UTE response and ended listening")

    def _rocker_sequence(self, item, sender_id, sequence):
        if self.log_for_debug:
            self.logger.debug("_rocker_sequence method called")
        try:
            for step in sequence:
                event, relation, delay = step.split()
                # self.logger.debug("waiting for {} {} {}".format(event, relation, delay))
                if item._enocean_rs_events[event.upper()].wait(float(delay)) != (relation.upper() == "WITHIN"):
                    if self.log_for_debug:
                        self.logger.debug(f"NOT {step} - aborting sequence!")
                    return
                else:
                    if self.log_for_debug:
                        self.logger.debug(f"{step}")
                    item._enocean_rs_events[event.upper()].clear()
                    continue
            value = True
            if 'enocean_rocker_action' in item.conf:
                if item.conf['enocean_rocker_action'].upper() == "UNSET":
                    value = False
                elif item.conf['enocean_rocker_action'].upper() == "TOGGLE":
                    value = not item()
            item(value, self.get_shortname(), "{:08X}".format(sender_id))
        except Exception as e:
            self.logger.error(f'Error handling enocean_rocker_sequence \"{sequence}\" - {e}')

    def _send_packet(self, packet_type, data=[], optional=[]):
        # self.logger.debug("_send_packet method called")
        length_optional = len(optional)
        if length_optional > 255:
            self.logger.error(f"Optional too long ({length_optional} bytes, 255 allowed)")
            return
        length_data = len(data)
        if length_data > 65535:
            self.logger.error(f"Data too long ({length_data} bytes, 65535 allowed)")
            return

        packet = bytearray([PACKET.SYNC_BYTE])
        packet += length_data.to_bytes(2, byteorder='big') + bytes([length_optional, packet_type])
        packet += bytes([self.crc(packet[1:5])])
        packet += bytes(data + optional)
        packet += bytes([self.crc(packet[6:])])
        self.logger.info("Sending packet with len = {} / data = [{}]!".format(len(packet), ', '.join(['0x%02x' % b for b in packet])))

        # check connection, reconnect
        if not self.is_connected():
            self.logger.debug("Trying serial reinit")
            if not self.connect(startup=False):
                self.logger.error('Connection failed, not sending.')
                return
        try:
            self._tcm.write(packet)
            return
        except Exception as e:
            self.logger.error(f"Exception during tcm write occurred: {e}")
            self.logger.debug("Trying serial reinit after failed write")

        if not self.connect(startup=False):
            self.logger.error('Connection failed again, not sending. Giving up.')
            return

        try:
            self._tcm.write(packet)
        except Exception as e:
            self.logger.error(f"Writing failed twice, giving up: {e}")

    def _process_packet_type_event(self, data, optional):
        if self.log_for_debug:
            self.logger.debug("_process_packet_type_event method called")
        event_code = data[0]
        if event_code == EVENT.RECLAIM_NOT_SUCCESSFUL:
            self.logger.error("SA reclaim was not successful")
        elif event_code == EVENT.CONFIRM_LEARN:
            self.logger.info("Requesting how to handle confirm/discard learn in/out")
        elif event_code == EVENT.LEARN_ACK:
            self.logger.info("SA lern acknowledged")
        elif event_code == EVENT.READY:
            self.logger.info("Controller is ready for operation")
        elif event_code == EVENT.TRANSMIT_FAILED:
            self.logger.error("Telegram transmission failed")
        elif event_code == EVENT.DUTYCYCLE_LIMIT:
            self.logger.warning("Duty cycle limit reached")
        elif event_code == EVENT.EVENT_SECUREDEVICES:
            self.logger.info("Secure device event packet received")
        else:
            self.logger.warning("Unknown event packet received")

    def _process_packet_type_radio(self, data, optional):
        if self.log_for_debug:
            self.logger.debug("_process_packet_type_radio method called")
        # self.logger.warning("Processing radio message with data = [{}] / optional = [{}]".format(', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))

        choice = data[0]
        payload = data[1:-5]
        sender_id = int.from_bytes(data[-5:-1], byteorder='big', signed=False)
        status = data[-1]
        repeater_cnt = status & 0x0F
        self.logger.info("Radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))

        if len(optional) == 7:
            subtelnum = optional[0]
            dest_id = int.from_bytes(optional[1:5], byteorder='big', signed=False)
            dBm = -optional[5]
            SecurityLevel = optional[6]
            if self.log_for_debug:
                self.logger.debug(f"Radio message with additional info: subtelnum = {subtelnum} / dest_id = {dest_id:08X} / signal = {dBm} dBm / SecurityLevel = {SecurityLevel}")
            if choice == 0xD4 and self.UTE_listen:
                self.logger.info("Call send_UTE_response")
                self._send_UTE_response(data, optional)

        if sender_id in self._rx_items:
            if self.log_for_debug:
                self.logger.debug("Sender ID found in item list")
            # iterate over all eep known for this id and get list of associated items
            for eep, items in self._rx_items[sender_id].items():
                # check if choice matches first byte in eep (this seems to be the only way to find right eep for this particular packet)
                if eep.startswith("{:02X}".format(choice)):
                    # call parser for particular eep - returns dictionary with key-value pairs
                    results = self.eep_parser(eep, payload, status)
                    if self.log_for_debug:
                        self.logger.debug(f"Radio message results = {results}")
                    if 'DEBUG' in results:
                        self.logger.warning("DEBUG Info: processing radio message with data = [{}] / optional = [{}]".format(', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))
                        self.logger.warning(f"Radio message results = {results}")
                        self.logger.warning("Radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))

                    for item in items:
                        rx_key = item.conf['enocean_rx_key'].upper()
                        if rx_key in results:
                            if 'enocean_rocker_sequence' in item.conf:
                                try:
                                    if hasattr(item, '_enocean_rs_thread') and item._enocean_rs_thread.is_alive():
                                        if results[rx_key]:
                                            if self.log_for_debug:
                                                self.logger.debug("Sending pressed event")
                                            item._enocean_rs_events["PRESSED"].set()
                                        else:
                                            if self.log_for_debug:
                                                self.logger.debug("Sending released event")
                                            item._enocean_rs_events["RELEASED"].set()
                                    elif results[rx_key]:
                                        item._enocean_rs_events = {'PRESSED': threading.Event(), 'RELEASED': threading.Event()}
                                        item._enocean_rs_thread = threading.Thread(target=self._rocker_sequence, name="enocean-rs", args=(item, sender_id, item.conf['enocean_rocker_sequence'].split(','), ))
                                        # self.logger.info("starting enocean_rocker_sequence thread")
                                        item._enocean_rs_thread.start()
                                except Exception as e:
                                    self.logger.error(f"Error handling enocean_rocker_sequence: {e}")
                            else:
                                item(results[rx_key], self.get_shortname(), f"{sender_id:08X}")
        elif sender_id <= self.tx_id + 127 and sender_id >= self.tx_id:
            if self.log_for_debug:
                self.logger.debug("Received repeated enocean stick message")
        else:
            self.unknown_sender_id = f"{sender_id:08X}"
            if self._log_unknown_msg:
                self.logger.info(f"Unknown ID = {sender_id:08X}")
                self.logger.warning("Unknown device sent radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))

    def _process_packet_type_smart_ack_command(self, data, optional):
        self.logger.warning("Smart acknowledge command 0x06 received but not supported at the moment")

    def _process_packet_type_response(self, data, optional):
        if self.log_for_debug:
            self.logger.debug("_process_packet_type_response method called")

        # handle sent packet
        if self._last_cmd_code == PACKET.SENT_RADIO and len(data) == 1:

            if self.log_for_debug:
                self.logger.debug(f"Sending command returned code = {RETURN_CODE(data[0])}")

        # handle common commands
        elif self._last_packet_type == PACKET_TYPE.COMMON_COMMAND:

            if self._last_cmd_code == COMMON_COMMAND.WR_RESET and len(data) == 1:
                self.logger.info(f"Reset returned code = {RETURN_CODE(data[0])}")

            elif self._last_cmd_code == COMMON_COMMAND.WR_LEARNMODE and len(data) == 1:
                self.logger.info(f"Write LearnMode returned code = {RETURN_CODE(data[0])}")

            elif self._last_cmd_code == COMMON_COMMAND.RD_VERSION:
                if data[0] == 0 and len(data) == 33:
                    self.logger.info("Chip ID = 0x{} / Chip Version = 0x{}".format(''.join(['%02x' % b for b in data[9:13]]), ''.join(['%02x' % b for b in data[13:17]])))
                    self.logger.info("APP version = {} / API version = {} / App description = {}".format('.'.join(['%d' % b for b in data[1:5]]), '.'.join(['%d' % b for b in data[5:9]]), ''.join(['%c' % b for b in data[17:33]])))
                elif data[0] == 0 and len(data) == 0:
                    self.logger.error("Reading version: No answer")
                else:
                    self.logger.error(f"Reading version returned code = {RETURN_CODE(data[0])}, length = {len(data)}")

            elif self._last_cmd_code == COMMON_COMMAND.RD_IDBASE:
                if data[0] == 0 and len(data) == 5:
                    self.logger.info("Base ID = 0x{}".format(''.join(['%02x' % b for b in data[1:5]])))
                    if self.tx_id == 0:
                        self.tx_id = int.from_bytes(data[1:5], byteorder='big', signed=False)
                        self.logger.info("Transmit ID set set automatically by reading chips BaseID")
                    if len(optional) == 1:
                        self.logger.info(f"Remaining write cycles for Base ID = {optional[0]}")
                elif data[0] == 0 and len(data) == 0:
                    self.logger.error("Reading Base ID: No answer")
                else:
                    self.logger.error(f"Reading Base ID returned code = {RETURN_CODE(data[0])} and {len(data)} bytes")

            elif self._last_cmd_code == COMMON_COMMAND.WR_BIST:
                if data[0] == 0 and len(data) == 2:
                    if data[1] == 0:
                        self.logger.info("Built in self test result: All OK")
                    else:
                        self.logger.info(f"Built in self test result: Problem, code = {data[1]}")
                elif data[0] == 0 and len(data) == 0:
                    self.logger.error("Doing built in self test: No answer")
                else:
                    self.logger.error(f"Doing built in self test returned code = {RETURN_CODE(data[0])}")

            elif self._last_cmd_code == COMMON_COMMAND.RD_LEARNMODE:
                if data[0] == 0 and len(data) == 2:
                    self.logger.info("Reading LearnMode = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
                    if len(optional) == 1:
                        self.logger.info("Learn channel = {}".format(optional[0]))
                elif data[0] == 0 and len(data) == 0:
                    self.logger.error("Reading LearnMode: No answer")

            elif self._last_cmd_code == COMMON_COMMAND.RD_NUMSECUREDEVICES:
                if data[0] == 0 and len(data) == 2:
                    self.logger.info("Number of taught in devices = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
                elif data[0] == 0 and len(data) == 0:
                    self.logger.error("Reading NUMSECUREDEVICES: No answer")
                elif data[0] == 2 and len(data) == 1:
                    self.logger.error("Reading NUMSECUREDEVICES: Command not supported")
                else:
                    self.logger.error("Reading NUMSECUREDEVICES: Unknown error")
        elif self._last_packet_type == PACKET_TYPE.SMART_ACK_COMMAND:

            # handle SmartAck commands
            if self._last_cmd_code == SMART_ACK.WR_LEARNMODE:
                self.logger.info(f"Setting SmartAck mode returned code = {RETURN_CODE(data[0])}")

            elif self._last_cmd_code == SMART_ACK.RD_LEARNEDCLIENTS:
                if data[0] == 0:
                    self.logger.info(f"Number of smart acknowledge mailboxes = {int((len(data)-1)/9)}")
                else:
                    self.logger.error(f"Requesting SmartAck mailboxes returned code = {RETURN_CODE(data[0])}")
        else:
            self.logger.error("Processing unexpected response with return code = {} / data = [{}] / optional = [{}]".format(RETURN_CODE(data[0]), ', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))

        self._response_lock.acquire()
        self._response_lock.notify()
        self._response_lock.release()

#
# Definitions of Learn Methods
#

    def send_learn_protocol(self, id_offset=0, device=10):
        self.logger.debug("send_learn_protocol method called")
        # define RORG
        rorg = RORG.BS4

        # check offset range between 0 and 127
        if not 0 <= id_offset <= 127:
            self.logger.error(f'ID offset with value = {id_offset} out of range (0-127). Aborting.')
            return False

        # device range 10 - 19 --> Learn protocol for switch actuators
        if device == 10:

            # Prepare Data for Eltako switch FSR61, Eltako FSVA-230V
            payload = [0xE0, 0x40, 0x0D, 0x80]
            self.logger.info('Sending learn telegram for switch command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))

        # device range 20 - 29 --> Learn protocol for dim actuators
        elif device == 20:

            # Only for Eltako FSUD-230V
            payload = [0x02, 0x00, 0x00, 0x00]
            self.logger.info('Sending learn telegram for dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        elif device == 21:

            # For Eltako FHK61SSR dim device (EEP A5-38-08)
            payload = [0xE0, 0x40, 0x0D, 0x80]
            self.logger.info('Sending learn telegram for dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        elif device == 22:

            # For Eltako FRGBW71L RGB dim devices (EEP 07-3F-7F)
            payload = [0xFF, 0xF8, 0x0D, 0x87]
            self.logger.info('Sending learn telegram for rgbw dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))

        # device range 30 - 39 --> Learn protocol for radiator valves
        elif device == 30:

            # Radiator Valve
            payload = [0x00, 0x00, 0x00, 0x00]
            self.logger.info('Sending learn telegram for radiator valve with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))

        # device range 40 - 49 --> Learn protocol for other actuators
        elif device == 40:

            # Eltako shutter actor FSB14, FSB61, FSB71
            payload = [0xFF, 0xF8, 0x0D, 0x80]
            self.logger.info('Sending learn telegram for actuator with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        else:
            self.logger.error(f'Sending learn telegram with invalid device! Device {device} currently not defined!')
            return False

        # Send radio package
        self._send_radio_packet(id_offset, rorg, payload)
        return True

    def start_UTE_learnmode(self, id_offset=0):
        self.logger.debug("start_UTE_learnmode method called")
        self.UTE_listen = True
        self.learn_id = id_offset
        self.logger.info("Listening for UTE package ('D4')")

    def enter_learn_mode(self, onoff=1):
        self.logger.debug("enter_learn_mode method called")
        if onoff == 1:
            self._send_common_command(COMMON_COMMAND.WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00], [0xFF])
            self.logger.info("Entering learning mode")
        else:
            self._send_common_command(COMMON_COMMAND.WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00], [0xFF])
            self.logger.info("Leaving learning mode")

    # This function enables/disables the controller's smart acknowledge mode
    def set_smart_ack_learn_mode(self, onoff=1):
        self.logger.debug("set_smart_ack_learn_mode method called")
        if onoff == 1:
            self._send_smart_ack_command(SMART_ACK.WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("Enabling smart acknowledge learning mode")
        else:
            self._send_smart_ack_command(SMART_ACK.WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("Disabling smart acknowledge learning mode")
