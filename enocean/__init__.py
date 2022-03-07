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
import os
import sys
import logging
import struct
import time
import threading
from lib.item import Items         #what for?
from . import eep_parser
from . import prepare_packet_data
from lib.model.smartplugin import *

FCSTAB = [
    0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15,
    0x38, 0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d,
    0x70, 0x77, 0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65,
    0x48, 0x4f, 0x46, 0x41, 0x54, 0x53, 0x5a, 0x5d,
    0xe0, 0xe7, 0xee, 0xe9, 0xfc, 0xfb, 0xf2, 0xf5,
    0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 0xc3, 0xca, 0xcd,
    0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 0x82, 0x85,
    0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 0xbd,
    0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2,
    0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea,
    0xb7, 0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2,
    0x8f, 0x88, 0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a,
    0x27, 0x20, 0x29, 0x2e, 0x3b, 0x3c, 0x35, 0x32,
    0x1f, 0x18, 0x11, 0x16, 0x03, 0x04, 0x0d, 0x0a,
    0x57, 0x50, 0x59, 0x5e, 0x4b, 0x4c, 0x45, 0x42,
    0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 0x7d, 0x7a,
    0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b, 0x9c,
    0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
    0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec,
    0xc1, 0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4,
    0x69, 0x6e, 0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c,
    0x51, 0x56, 0x5f, 0x58, 0x4d, 0x4a, 0x43, 0x44,
    0x19, 0x1e, 0x17, 0x10, 0x05, 0x02, 0x0b, 0x0c,
    0x21, 0x26, 0x2f, 0x28, 0x3d, 0x3a, 0x33, 0x34,
    0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 0x5c, 0x5b,
    0x76, 0x71, 0x78, 0x7f, 0x6A, 0x6d, 0x64, 0x63,
    0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b,
    0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13,
    0xae, 0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb,
    0x96, 0x91, 0x98, 0x9f, 0x8a, 0x8D, 0x84, 0x83,
    0xde, 0xd9, 0xd0, 0xd7, 0xc2, 0xc5, 0xcc, 0xcb,
    0xe6, 0xe1, 0xe8, 0xef, 0xfa, 0xfd, 0xf4, 0xf3
    ]

################################
### --- Packet Sync Byte --- ###
################################
PACKET_SYNC_BYTE              = 0x55   # PACKET SYNC BYTE


############################
### --- Packet Types --- ###
############################

PACKET_TYPE_RADIO             = 0x01   # RADIO ERP1
PACKET_TYPE_RESPONSE          = 0x02   # RESPONSE
PACKET_TYPE_RADIO_SUB_TEL     = 0x03   # RADIO_SUB_TEL
PACKET_TYPE_EVENT             = 0x04   # EVENT
PACKET_TYPE_COMMON_COMMAND    = 0x05   # COMMON COMMAND
PACKET_TYPE_SMART_ACK_COMMAND = 0x06   # SMART ACK COMMAND
PACKET_REMOTE_MAN_COMMAND     = 0x07   # REMOTE MANAGEMENT COMMAND
PACKET_TYPE_RADIO_MESSAGE     = 0x09   # RADIO MESSAGE
PACKET_TYPE_RADIO_ERP2        = 0x0A   # RADIO ERP2
PACKET_TYPE_RADIO_802_15_4    = 0x10   # RADIO_802_15_4
PACKET_TYPE_COMMAND_2_4       = 0x11   # COMMAND_2_4


############################################
### --- List of Common Command Codes --- ###
############################################

CO_WR_SLEEP                     = 0x01     # Order to enter in energy saving mode
CO_WR_RESET                     = 0x02     # Order to reset the device
CO_RD_VERSION                   = 0x03     # Read the device (SW) version /(HW) version, chip ID etc.
CO_RD_SYS_LOG                   = 0x04     # Read system log from device databank
CO_WR_SYS_LOG                   = 0x05     # Reset System log from device databank
CO_WR_BIST                      = 0x06     # Perform built in self test
CO_WR_IDBASE                    = 0x07     # Write ID range base number
CO_RD_IDBASE                    = 0x08     # Read ID range base number
CO_WR_REPEATER                  = 0x09     # Write Repeater Level off,1,2
CO_RD_REPEATER                  = 0x0A     # Read Repeater Level off,1,2
CO_WR_FILTER_ADD                = 0x0B     # Add filter to filter list
CO_WR_FILTER_DEL                = 0x0C     # Delete filter from filter list
CO_WR_FILTER_DEL_ALL            = 0x0D     # Delete all filter
CO_WR_FILTER_ENABLE             = 0x0E     # Enable/Disable supplied filters
CO_RD_FILTER                    = 0x0F     # Read supplied filters
CO_WR_WAIT_MATURITY             = 0x10     # Waiting till end of maturity time before received radio telegrams will transmitted
CO_WR_SUBTEL                    = 0x11     # Enable/Disable transmitting additional subtelegram info
CO_WR_MEM                       = 0x12     # Write x bytes of the Flash, XRAM, RAM0 …
CO_RD_MEM                       = 0x13     # Read x bytes of the Flash, XRAM, RAM0 ….
CO_RD_MEM_ADDRESS               = 0x14     # Feedback about the used address and length of the configarea and the Smart Ack Table
CO_RD_SECURITY                  = 0x15     # Read own security information (level, key)
CO_WR_SECURITY                  = 0x16     # Write own security information (level, key)
CO_WR_LEARNMODE                 = 0x17     # Function: Enables or disables learn mode of Controller.
CO_RD_LEARNMODE                 = 0x18     # Function: Reads the learn-mode state of Controller.
CO_WR_SECUREDEVICE_ADD          = 0x19     # Add a secure device
CO_WR_SECUREDEVICE_DEL          = 0x1A     # Delete a secure device
CO_RD_SECUREDEVICE_BY_INDEX     = 0x1B     # Read secure device by index
CO_WR_MODE                      = 0x1C     # Sets the gateway transceiver mode
CO_RD_NUMSECUREDEVICES          = 0x1D     # Read number of taught in secure devices
CO_RD_SECUREDEVICE_BY_ID        = 0x1E     # Read secure device by ID
CO_WR_SECUREDEVICE_ADD_PSK      = 0x1F     # Add Pre-shared key for inbound secure device
CO_WR_SECUREDEVICE_SENDTEACHIN  = 0x20     # Send secure Teach-In message
CO_WR_TEMPORARY_RLC_WINDOW      = 0x21     # Set the temporary rolling-code window for every taught-in devic
CO_RD_SECUREDEVICE_PSK          = 0x22     # Read PSK
CO_RD_DUTYCYCLE_LIMIT           = 0x23     # Read parameters of actual duty cycle limit
CO_SET_BAUDRATE                 = 0x24     # Modifies the baud rate of the EnOcean device
CO_GET_FREQUENCY_INFO           = 0x25     # Reads Frequency and protocol of the Device
CO_GET_STEPCODE                 = 0x27     # Reads Hardware Step code and Revision of the Device


###################################
### --- List of Event Codes --- ###
###################################

SA_RECLAIM_NOT_SUCCESSFUL  = 0x01      # Informs the backbone of a Smart Ack Client to not successful reclaim.
SA_CONFIRM_LEARN           = 0x02      # Used for SMACK to confirm/discard learn in/out
SA_LEARN_ACK               = 0x03      # Inform backbone about result of learn request
CO_READY                   = 0x04      # Inform backbone about the readiness for operation
CO_EVENT_SECUREDEVICES     = 0x05      # Informs about a secure device
CO_DUTYCYCLE_LIMIT         = 0x06      # Informs about duty cycle limit
CO_TRANSMIT_FAILED         = 0x07      # Informs that the device was not able to send a telegram.


###########################################
###  --- Smart Acknowledge Defines: --- ###
###########################################

SA_WR_LEARNMODE        = 0x01          # Set/Reset Smart Ack learn mode
SA_RD_LEARNMODE        = 0x02          # Get Smart Ack learn mode state
SA_WR_LEARNCONFIRM     = 0x03          # Used for Smart Ack to add or delete a mailbox of a client
SA_WR_CLIENTLEARNRQ    = 0x04          # Send Smart Ack Learn request (Client)
SA_WR_RESET            = 0x05          # Send reset command to a Smart Ack client
SA_RD_LEARNEDCLIENTS   = 0x06          # Get Smart Ack learned sensors / mailboxes
SA_WR_RECLAIMS         = 0x07          # Set number of reclaim attempts
SA_WR_POSTMASTER       = 0x08          # Activate/Deactivate Post master functionality

SENT_RADIO_PACKET              = 0xFF
SENT_ENCAPSULATED_RADIO_PACKET = 0xA6

class EnOcean(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.3.6"

    
    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self.port = self.get_parameter_value("serialport")
        self.logger = logging.getLogger(__name__)
        tx_id = self.get_parameter_value("tx_id")
        if (len(tx_id) < 8):
            self.tx_id = 0
            self.logger.warning('enocean: No valid enocean stick ID configured. Transmitting is not supported')
        else:
            self.tx_id = int(tx_id, 16)
            self.logger.info(f"Stick TX ID configured via plugin.conf to: {tx_id}")
        self._log_unknown_msg = self.get_parameter_value("log_unknown_messages")
        self._tcm = serial.Serial(self.port, 57600, timeout=1.5)
        self._cmd_lock = threading.Lock()
        self._response_lock = threading.Condition()
        self._rx_items = {}
        self._used_tx_offsets = []
        self._unused_tx_offset = None
        self.UTE_listen = False
        self.unknown_sender_id = 'None'
        self._block_ext_out_msg = False
        # call init of eep_parser
        self.eep_parser = eep_parser.EEP_Parser()
        # call init of prepare_packet_data
        self.prepare_packet_data = prepare_packet_data.Prepare_Packet_Data(self)

        if not self.init_webinterface():
            self._init_complete = False

    def eval_telegram(self, sender_id, data, opt):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("enocean: call function << eval_telegram >>")
        for item in self._items:
            # validate id for item id:
            if item.conf['enocean_id'] == sender_id:
                #print ("validated {0} for {1}".format(sender_id,item))
                #print ("try to get value for: {0} and {1}".format(item.conf['enocean_rorg'][0],item.conf['enocean_rorg'][1]))
                rorg = item.conf['enocean_rorg']
                eval_value = item.conf['enocean_value']
                if rorg in RADIO_PAYLOAD_VALUE:  # check if RORG exists
                    pl = eval(RADIO_PAYLOAD_VALUE[rorg]['payload_idx'])
                    #could be nicer
                    for entity in RADIO_PAYLOAD_VALUE:
                        if (rorg == entity) and (eval_value in RADIO_PAYLOAD_VALUE[rorg]['entities']):
                            value_dict = RADIO_PAYLOAD_VALUE[rorg]['entities']
                            value = eval(RADIO_PAYLOAD_VALUE[rorg]['entities'][eval_value])
                            if logger_debug:
                                self.logger.debug(f"Resulting value: {value} for {item}")
                            if value:  # not sure about this
                                item(value, 'EnOcean', 'RADIO')

    def _process_packet_type_event(self, data, optional):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("enocean: call function << _process_packet_type_event >>")
        event_code = data[0]
        if(event_code == SA_RECLAIM_NOT_SUCCESSFUL):
            self.logger.error("enocean: SA reclaim was not successful")
        elif(event_code == SA_CONFIRM_LEARN):
            self.logger.info("enocean: Requesting how to handle confirm/discard learn in/out")
        elif(event_code == SA_LEARN_ACK):
            self.logger.info("enocean: SA lern acknowledged")
        elif(event_code == CO_READY):
            self.logger.info("enocean: Controller is ready for operation")
        elif(event_code == CO_TRANSMIT_FAILED):
            self.logger.error("enocean: Telegram transmission failed")
        elif(event_code == CO_DUTYCYCLE_LIMIT):
            self.logger.warning("enocean: Duty cycle limit reached")
        elif(event_code == CO_EVENT_SECUREDEVICES):
            self.logger.info("enocean: secure device event packet received")
        else:
            self.logger.warning("enocean: unknown event packet received")

    def _rocker_sequence(self, item, sender_id, sequence):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("enocean: call function << _rocker_sequence >>")
        try:
            for step in sequence:
                event, relation, delay = step.split()             
                #self.logger.debug("waiting for {} {} {}".format(event, relation, delay))
                if item._enocean_rs_events[event.upper()].wait(float(delay)) != (relation.upper() == "WITHIN"):
                    if logger_debug:
                        self.logger.debug(f"NOT {step} - aborting sequence!")
                    return
                else:
                    if logger_debug:
                        self.logger.debug(f"{step}")
                    item._enocean_rs_events[event.upper()].clear()
                    continue          
            value = True
            if 'enocean_rocker_action' in item.conf:
                if item.conf['enocean_rocker_action'].upper() == "UNSET":
                    value = False
                elif item.conf['enocean_rocker_action'].upper() == "TOGGLE":
                    value = not item()
            item(value, 'EnOcean', "{:08X}".format(sender_id))
        except Exception as e:
            self.logger.error(f'Error handling enocean_rocker_sequence \"{sequence}\" - {e}'.format(sequence, e))        

    def _process_packet_type_radio(self, data, optional):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("Call function << _process_packet_type_radio >>")
        #self.logger.warning("Processing radio message with data = [{}] / optional = [{}]".format(', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))

        choice = data[0]
        payload = data[1:-5]
        sender_id = int.from_bytes(data[-5:-1], byteorder='big', signed=False)
        status = data[-1]
        repeater_cnt = status & 0x0F
        self.logger.info("Radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))

        if (len(optional) == 7):
            subtelnum = optional[0]
            dest_id = int.from_bytes(optional[1:5], byteorder='big', signed=False)
            dBm = -optional[5]
            SecurityLevel = optional[6]
            if logger_debug:
                self.logger.debug("Radio message with additional info: subtelnum = {} / dest_id = {:08X} / signal = {}dBm / SecurityLevel = {}".format(subtelnum, dest_id, dBm, SecurityLevel))
            if (choice == 0xD4) and (self.UTE_listen == True):
                self.logger.info("Call send_UTE_response")
                self._send_UTE_response(data, optional)
        if sender_id in self._rx_items:
            if logger_debug:
                self.logger.debug("Sender ID found in item list")
            # iterate over all eep known for this id and get list of associated items
            for eep,items in self._rx_items[sender_id].items():
                # check if choice matches first byte in eep (this seems to be the only way to find right eep for this particular packet)
                if eep.startswith("{:02X}".format(choice)):
                    # call parser for particular eep - returns dictionary with key-value pairs
                    results = self.eep_parser.Parse(eep, payload, status)
                    if logger_debug:
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
                                            if logger_debug:
                                                self.logger.debug("Sending pressed event")
                                            item._enocean_rs_events["PRESSED"].set()
                                        else:
                                            if logger_debug:
                                                self.logger.debug("Sending released event")
                                            item._enocean_rs_events["RELEASED"].set()
                                    elif results[rx_key]:
                                        item._enocean_rs_events = {'PRESSED': threading.Event(), 'RELEASED': threading.Event()}
                                        item._enocean_rs_thread = threading.Thread(target=self._rocker_sequence, name="enocean-rs", args=(item, sender_id, item.conf['enocean_rocker_sequence'].split(','), ))
                                        #self.logger.info("starting enocean_rocker_sequence thread")
                                        item._enocean_rs_thread.daemon = True
                                        item._enocean_rs_thread.start()
                                except Exception as e:
                                    self.logger.error(f"Error handling enocean_rocker_sequence: {e}")
                            else:
                                item(results[rx_key], 'EnOcean', "{:08X}".format(sender_id))
        elif (sender_id <= self.tx_id + 127) and (sender_id >= self.tx_id):
            if logger_debug:
                self.logger.debug("Received repeated enocean stick message")
        else:
            self.unknown_sender_id = "{:08X}".format(sender_id)
            if self._log_unknown_msg:
                self.logger.info("Unknown ID = {:08X}".format(sender_id))
                self.logger.warning("Unknown device sent radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))


    def _process_packet_type_smart_ack_command(self, data, optional):
        self.logger.warning("Smart acknowledge command 0x06 received but not supported at the moment")


    def _process_packet_type_response(self, data, optional):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("Call function << _process_packet_type_response >>")
        RETURN_CODES = ['OK', 'ERROR', 'NOT SUPPORTED', 'WRONG PARAM', 'OPERATION DENIED']
        if (self._last_cmd_code == SENT_RADIO_PACKET) and (len(data) == 1):
            if logger_debug:
                self.logger.debug(f"Sending command returned code = {RETURN_CODES[data[0]]}")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_RESET) and (len(data) == 1):
            self.logger.info(f"Reset returned code = {RETURN_CODES[data[0]]}")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_LEARNMODE) and (len(data) == 1):
            self.logger.info(f"Write LearnMode returned code = {RETURN_CODES[data[0]]}")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_VERSION):
            if (data[0] == 0) and (len(data) == 33):
                self.logger.info("Chip ID = 0x{} / Chip Version = 0x{}".format(''.join(['%02x' % b for b in data[9:13]]), ''.join(['%02x' % b for b in data[13:17]])))
                self.logger.info("APP version = {} / API version = {} / App description = {}".format('.'.join(['%d' % b for b in data[1:5]]), '.'.join(['%d' % b for b in data[5:9]]), ''.join(['%c' % b for b in data[17:33]])))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("Reading version: No answer")
            else:
                self.logger.error(f"Reading version returned code = {RETURN_CODES[data[0]]}, length = {len(data)}")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_IDBASE):
            if (data[0] == 0) and (len(data) == 5):
                self.logger.info("Base ID = 0x{}".format(''.join(['%02x' % b for b in data[1:5]])))
                if (self.tx_id == 0):
                    self.tx_id = int.from_bytes(data[1:5], byteorder='big', signed=False)
                    self.logger.info("Transmit ID set set automatically by reading chips BaseID")
                if (len(optional) == 1):
                    self.logger.info(f"Remaining write cycles for Base ID = {optional[0]}")
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("Reading Base ID: No answer")
            else:
                self.logger.error(f"Reading Base ID returned code = {RETURN_CODES[data[0]]} and {len(data)} bytes")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_BIST):
            if (data[0] == 0) and (len(data) == 2):
                if (data[1] == 0):
                    self.logger.info("Built in self test result: All OK")
                else:
                    self.logger.info(f"Built in self test result: Problem, code = {data[1]}")
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("Doing built in self test: No answer")
            else:
                self.logger.error(f"Doing built in self test returned code = {RETURN_CODES[data[0]]}")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_LEARNMODE):
            if (data[0] == 0) and (len(data) == 2):
                self.logger.info("Reading LearnMode = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
                if (len(optional) == 1):
                    self.logger.info("enocean: learn channel = {}".format(optional[0]))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("Reading LearnMode: No answer")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_NUMSECUREDEVICES):
            if (data[0] == 0) and (len(data) == 2):
                self.logger.info("Number of taught in devices = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("Reading NUMSECUREDEVICES: No answer")
            elif (data[0] == 2) and (len(data) == 1):
                self.logger.error("Reading NUMSECUREDEVICES: Command not supported")
            else:
                self.logger.error("Reading NUMSECUREDEVICES: Unknown error")
        elif (self._last_packet_type == PACKET_TYPE_SMART_ACK_COMMAND) and (self._last_cmd_code == SA_WR_LEARNMODE):
            self.logger.info(f"Setting SmartAck mode returned code = {RETURN_CODES[data[0]]}")
        elif (self._last_packet_type == PACKET_TYPE_SMART_ACK_COMMAND) and (self._last_cmd_code == SA_RD_LEARNEDCLIENTS):
            if (data[0] == 0):
                self.logger.info(f"Number of smart acknowledge mailboxes = {int((len(data)-1)/9)}")
            else:
                self.logger.error(f"Requesting SmartAck mailboxes returned code = {RETURN_CODES[data[0]]}")
        else:
            self.logger.error("Processing unexpected response with return code = {} / data = [{}] / optional = [{}]".format(RETURN_CODES[data[0]], ', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))
        self._response_lock.acquire()
        self._response_lock.notify()
        self._response_lock.release()

    def _startup(self):
        self.logger.debug("Call function << _startup >>")
        # request one time information
        self.logger.info("Resetting device")
        self._send_common_command(CO_WR_RESET)
        self.logger.info("Requesting id-base")
        self._send_common_command(CO_RD_IDBASE)
        self.logger.info("Requesting version information")
        self._send_common_command(CO_RD_VERSION)
        self.logger.debug("Ending connect-thread")

    def run(self):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("Call function << run >>")
        self.alive = True
        self.UTE_listen = False
        #self.learn_id = 0
        t = threading.Thread(target=self._startup, name="enocean-startup")
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)
        t.daemon = False
        t.start()
        msg = []
        while self.alive:
            readin = self._tcm.read(1000)
            if readin:
                msg += readin
                if logger_debug:
                    self.logger.debug("Data received")
                # check if header is complete (6bytes including sync)
                # 0x55 (SYNC) + 4bytes (HEADER) + 1byte(HEADER-CRC)
                while (len(msg) >= 6):
                    #check header for CRC
                    if (msg[0] == PACKET_SYNC_BYTE) and (self._calc_crc8(msg[1:5]) == msg[5]):
                        # header bytes: sync; length of data (2); optional length; packet type; crc
                        data_length = (msg[1] << 8) + msg[2]
                        opt_length = msg[3]
                        packet_type = msg[4]
                        msg_length = data_length + opt_length + 7
                        if logger_debug:
                            self.logger.debug("Received header with data_length = {} / opt_length = 0x{:02x} / type = {}".format(data_length, opt_length, packet_type))

                        # break if msg is not yet complete:
                        if (len(msg) < msg_length):
                            break

                        # msg complete
                        if (self._calc_crc8(msg[6:msg_length - 1]) == msg[msg_length - 1]):
                            if logger_debug:
                                self.logger.debug("Accepted package with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                            data = msg[6:msg_length - (opt_length + 1)]
                            optional = msg[(6 + data_length):msg_length - 1]
                            if (packet_type == PACKET_TYPE_RADIO):
                                self._process_packet_type_radio(data, optional)
                            elif (packet_type == PACKET_TYPE_SMART_ACK_COMMAND):
                                self._process_packet_type_smart_ack_command(data, optional)
                            elif (packet_type == PACKET_TYPE_RESPONSE):
                                self._process_packet_type_response(data, optional)
                            elif (packet_type == PACKET_TYPE_EVENT):
                                self._process_packet_type_event(data, optional)
                            else:
                                self.logger.error("Received packet with unknown type = 0x{:02x} - len = {} / data = [{}]".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        else:
                            self.logger.error("Crc error - dumping packet with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        msg = msg[msg_length:]
                    else:
                        #self.logger.warning("Consuming [0x{:02x}] from input buffer!".format(msg[0]))
                        msg.pop(0)
        self._tcm.close()
        self.logger.info("Run method stopped")

    def stop(self):
        self.logger.debug("Call function << stop >>")
        self.alive = False
        

    def get_tx_id_as_hex(self):
        hexstring = "{:08X}".format(self.tx_id)
        return hexstring

    def get_log_unknown_msg(self):
        return self._log_unknown_msg

    def toggle_log_unknown_msg(self):
        self._log_unknown_msg = not self._log_unknown_msg
    
    def _send_UTE_response(self, data, optional):
        self.logger.debug("enocean: call function << _send_UTE_response >>")
        choice = data[0]
        payload = data[1:-5]
        #sender_id = int.from_bytes(data[-5:-1], byteorder='big', signed=False)
        #status = data[-1]
        #repeater_cnt = status & 0x0F
        SubTel = 0x03
        db = 0xFF
        Secu = 0x0

        self._send_radio_packet(self.learn_id, choice, [0x91, payload[1], payload[2], payload[3], payload[4], payload[5], payload[6]],[SubTel, data[-5], data[-4], data[-3], data[-2], db, Secu] )#payload[0] = 0x91: EEP Teach-in response, Request accepted, teach-in successful, bidirectional
        self.UTE_listen = False
        self.logger.info("Sending UTE response and end listening")

    def parse_item(self, item):
        self.logger.debug("Call function << parse_item >>")
        if 'enocean_rx_key' in item.conf:
            # look for info from the most specific info to the broadest (key->eep->id) - one id might use multiple eep might define multiple keys
            eep_item = item
            found_eep = True

            while (not 'enocean_rx_eep' in eep_item.conf):
                eep_item = eep_item.return_parent()
                if (eep_item is self._sh):
                    self.logger.error(f"Could not find enocean_rx_eep for item {item}")
                    found_eep = False

            id_item = eep_item
            found_rx_id = True
            while (not 'enocean_rx_id' in id_item.conf):
                id_item = id_item.return_parent()
                if (id_item is self._sh):
                    self.logger.error(f"Could not find enocean_rx_id for item {item}")
                    found_rx_id = False

            # Only proceed, if valid rx_id and eep could be found:
            if found_rx_id and found_eep:

                rx_key = item.conf['enocean_rx_key'].upper()
                rx_eep = eep_item.conf['enocean_rx_eep'].upper()
                rx_id = int(id_item.conf['enocean_rx_id'],16)

                # check if there is a function to parse payload
                if self.eep_parser.CanParse(rx_eep):
               
                    if (rx_key in ['A0', 'A1', 'B0', 'B1']):
                        self.logger.warning(f"Key \"{rx_key}\" does not match EEP - \"0\" (Zero, number) should be \"O\" (letter) (same for \"1\" and \"I\") - will be accepted for now")
                        rx_key = rx_key.replace('0', 'O').replace("1", 'I')

                    if (not rx_id in self._rx_items):
                        self._rx_items[rx_id] = {rx_eep: [item]}
                    elif (not rx_eep in self._rx_items[rx_id]):
                        self._rx_items[rx_id][rx_eep] = [item]
                    elif (not item in self._rx_items[rx_id][rx_eep]):
                        self._rx_items[rx_id][rx_eep].append(item)

                    self.logger.info("Item {} listens to id {:08X} with eep {} key {}".format(item, rx_id, rx_eep, rx_key))
                    #self.logger.info(f"self._rx_items = {self._rx_items}")
    
        if 'enocean_tx_eep' in item.conf:
            self.logger.debug(f"TX eep found in item {item._name}")
            
            tx_offset = item.conf['enocean_tx_id_offset']
            if not (tx_offset in self._used_tx_offsets):
                self._used_tx_offsets.append(tx_offset)
                self._used_tx_offsets.sort()
                self.logger.debug(f"Debug offset list: {self._used_tx_offsets}")
                for x in range(1, 127):
                    if not x in self._used_tx_offsets:
                        self._unused_tx_offset = x
                        self.logger.debug(f"Next free offset set to {self._unused_tx_offset}")
                        break
            else:
                self.logger.debug(f"tx_offset {tx_offset} of item {item._name} already used.")

            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item



    def update_item(self, item, caller=None, source=None, dest=None):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)
        if logger_debug:
            self.logger.debug("Call function << update_item >>")
        if caller != 'EnOcean':
            if logger_debug:
                self.logger.debug(f'Item << {item} >> updated externally.')
            if self._block_ext_out_msg:
                self.logger.warning('Sending manually blocked by user. Aborting')
                return None
            if 'enocean_tx_eep' in item.conf:
                if isinstance(item.conf['enocean_tx_eep'], str):
                    tx_eep = item.conf['enocean_tx_eep']
                    if logger_debug:
                        self.logger.debug(f'item << {item} >> has tx_eep')
                    # check if Data can be Prepared
                    if not self.prepare_packet_data.CanDataPrepare(tx_eep):
                        self.logger.error(f'enocean-update_item: method missing for prepare telegram data for {tx_eep}')
                    else:
                        # call method prepare_packet_data(item, tx_eep)
                        id_offset, rorg, payload, optional = self.prepare_packet_data.PrepareData(item, tx_eep)
                        self._send_radio_packet(id_offset, rorg, payload, optional)
                else:
                    self.logger.error(f'tx_eep {tx_eep} is not a string value')
            else:
                if logger_debug:
                    self.logger.debug(f'enocean: item << {item} >>has no tx_eep value')

    def read_num_securedivices(self):
        self.logger.debug("Call function << read_num_securedivices >>")
        self._send_common_command(CO_RD_NUMSECUREDEVICES)
        self.logger.info("Read number of secured devices")


        # Request all taught in smart acknowledge devices that have a mailbox
    def get_smart_ack_devices(self):
        self.logger.debug("Call function << get_smart_ack_devices >>")
        self._send_smart_ack_command(SA_RD_LEARNEDCLIENTS)
        self.logger.info("Requesting all available smart acknowledge mailboxes")


    def reset_stick(self):
        self.logger.debug("Call function << reset_stick >>")
        self.logger.info("Resetting device")
        self._send_common_command(CO_WR_RESET)

    def block_external_out_messages(self, block=True):
        self.logger.debug("enocean: call function << block_external_out_messages >>")
        if block:
            self.logger.info("Blocking of external out messages activated")
            self._block_ext_out_msg = True
        elif not block:
            self.logger.info("Blocking of external out messages deactivated")
            self._block_ext_out_msg = False
        else:
            self.logger.error("Invalid argument. Must be True/False")

    def toggle_block_external_out_messages(self):
        self.logger.debug("Call function << toggle block_external_out_messages >>")
        if self._block_ext_out_msg == False:
            self.logger.info("Blocking of external out messages activated")
            self._block_ext_out_msg = True
        else:
            self.logger.info("Blocking of external out messages deactivated")
            self._block_ext_out_msg = False

    def toggle_UTE_mode(self,id_offset=0):
        self.logger.debug("enocean: toggle UTE mode")
        if self.UTE_listen == True:
            self.logger.info("enocean: UTE mode deactivated")
            self.UTE_listen = False
        elif (id_offset is not None) and not (id_offset == 0):
            self.start_UTE_learnmode(id_offset)
            self.logger.info("UTE mode activated for ID offset")

    def send_bit(self):
        self.logger.info("Trigger Built-In Self Test telegram")
        self._send_common_command(CO_WR_BIST)

    def version(self):
        self.logger.info("Request stick version")
        self._send_common_command(CO_RD_VERSION)

    def _send_packet(self, packet_type, data=[], optional=[]):
        #self.logger.debug("enocean: call function << _send_packet >>")
        length_optional = len(optional)
        if length_optional > 255:
            self.logger.error(f"Optional too long ({length_optional} bytes, 255 allowed)")
            return None
        length_data = len(data)
        if length_data > 65535:
            self.logger.error(f"Data too long ({length_data} bytes, 65535 allowed)")
            return None

        packet = bytearray([PACKET_SYNC_BYTE])
        packet += length_data.to_bytes(2, byteorder='big') + bytes([length_optional, packet_type])
        packet += bytes([self._calc_crc8(packet[1:5])])
        packet += bytes(data + optional)
        packet += bytes([self._calc_crc8(packet[6:])])
        self.logger.info("Sending packet with len = {} / data = [{}]!".format(len(packet), ', '.join(['0x%02x' % b for b in packet])))
        self._tcm.write(packet)

    def _send_smart_ack_command(self, _code, data=[]):
        #self.logger.debug("enocean: call function << _send_smart_ack_command >>")
        self._cmd_lock.acquire()
        self._last_cmd_code = _code
        self._last_packet_type = PACKET_TYPE_SMART_ACK_COMMAND
        self._send_packet(PACKET_TYPE_SMART_ACK_COMMAND, [_code] + data)
        self._response_lock.acquire()
        # wait 5sec for response
        self._response_lock.wait(5)
        self._response_lock.release()
        self._cmd_lock.release()

    def _send_common_command(self, _code, data=[], optional=[]):
        #self.logger.debug("Call function << _send_common_command >>")
        self._cmd_lock.acquire()
        self._last_cmd_code = _code
        self._last_packet_type = PACKET_TYPE_COMMON_COMMAND
        self._send_packet(PACKET_TYPE_COMMON_COMMAND, [_code] + data, optional)
        self._response_lock.acquire()
        # wait 5sec for response
        self._response_lock.wait(5)
        self._response_lock.release()
        self._cmd_lock.release()

    def _send_radio_packet(self, id_offset, _code, data=[], optional=[]):
        #self.logger.debug("Call function << _send_radio_packet >>")
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error(f"Invalid base ID offset range. (Is {id_offset}, must be [0 127])")
            return
        self._cmd_lock.acquire()
        self._last_cmd_code = SENT_RADIO_PACKET
        self._send_packet(PACKET_TYPE_RADIO, [_code] + data + list((self.tx_id + id_offset).to_bytes(4, byteorder='big')) + [0x00], optional)
        self._response_lock.acquire()
        # wait 1sec for response
        self._response_lock.wait(1)
        self._response_lock.release()
        self._cmd_lock.release()

    
        

####################################################
### --- START - Definitions of Learn Methods --- ###
####################################################
    def send_learn_protocol(self, id_offset=0, device=10):
        self.logger.debug("enocean: call function << send_learn_protocol >>")
        # define RORG
        rorg = 0xA5
        
        # check offset range between 0 and 127
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error(f'ID offset with value = {id_offset} out of range (0-127). Aborting.')
            return False
        # device range 10 - 19 --> Learn protocol for switch actuators
        elif (device == 10):
            # Prepare Data for Eltako switch FSR61, Eltako FSVA-230V
            payload = [0xE0, 0x40, 0x0D, 0x80]
            self.logger.info('enocean: sending learn telegram for switch command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        # device range 20 - 29 --> Learn protocol for dim actuators
        elif (device == 20):
            # Only for Eltako FSUD-230V
            payload = [0x02, 0x00, 0x00, 0x00]
            self.logger.info('enocean: sending learn telegram for dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        elif (device == 21):
            # For Eltako FHK61SSR dim device (EEP A5-38-08)
            payload = [0xE0, 0x40, 0x0D, 0x80]
            self.logger.info('enocean: sending learn telegram for dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        elif (device == 22):
            # For Eltako FRGBW71L RGB dim devices (EEP 07-3F-7F)
            payload = [0xFF, 0xF8, 0x0D, 0x87]
            self.logger.info('enocean: sending learn telegram for rgbw dim command with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        # device range 30 - 39 --> Learn protocol for radiator valves
        elif (device == 30):
            # Radiator Valve
            payload = [0x00, 0x00, 0x00, 0x00]
            self.logger.info('Sending learn telegram for radiator valve with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        # device range 40 - 49 --> Learn protocol for other actuators
        elif (device == 40):
            # Eltako shutter actor FSB14, FSB61, FSB71
            payload = [0xFF, 0xF8, 0x0D, 0x80]
            self.logger.info('Sending learn telegram for actuator with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        else:
            self.logger.error(f'Sending learn telegram with invalid device! Device {device} actually not defined!')
            return False
        # Send radio package
        self._send_radio_packet(id_offset, rorg, payload)
        return True


    def start_UTE_learnmode(self, id_offset=0):
        self.logger.debug("Call function << start_UTE_learnmode >>")
        self.UTE_listen = True
        self.learn_id = id_offset
        self.logger.info("Listening for UTE package ('D4')")
        
        
    def enter_learn_mode(self, onoff=1):
        self.logger.debug("Call function << enter_learn_mode >>")
        if (onoff == 1):
            self._send_common_command(CO_WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00],[0xFF])
            self.logger.info("Entering learning mode")
            return None
        else:
            self._send_common_command(CO_WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00],[0xFF])
            self.logger.info("Leaving learning mode")
            return None

            
    # This function enables/disables the controller's smart acknowledge mode
    def set_smart_ack_learn_mode(self, onoff=1):
        self.logger.debug("Call function << set_smart_ack_learn_mode >>")
        if (onoff == 1):
            self._send_smart_ack_command(SA_WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("Enabling smart acknowledge learning mode")
            return None
        else:
            self._send_smart_ack_command(SA_WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("Disabling smart acknowledge learning mode")
            return None

##################################################
### --- END - Definitions of Learn Methods --- ###
##################################################


#################################
### --- START - Calc CRC8 --- ###
#################################
    def _calc_crc8(self, msg, crc=0):
        #self.logger.debug("enocean: call function << _calc_crc8 >>")
        for i in msg:
            crc = FCSTAB[crc ^ i]
        return crc

###############################
### --- END - Calc CRC8 --- ###
###############################

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error(f"Plugin '{self.get_shortname()}': Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface
        
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()


    @cherrypy.expose
    def index(self, reload=None, action=None, item_id=None, item_path=None, device_id=None, device_offset=None,
              time_orig=None, changed_orig=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        learn_triggered = False

        if action is not None:
            if action == "toggle_tx_blocking":
                self.plugin.toggle_block_external_out_messages()
            elif action == "toggle_UTE":
                self.plugin.toggle_UTE_mode(device_offset)
                self.logger.warning(f"UTE mode triggered via webinterface (Offset: {device_offset})")
            elif action == "toggle_log_unknown":
                self.plugin.toggle_log_unknown_msg()
                self.logger.info(f"Toogle state of log unknown messages triggered via webinterface")
            elif action == "send_learn" and (device_id is not None) and not (device_id=="") and (device_offset is not None) and not(device_offset==""):
                self.logger.warning(f"Learn telegram triggered via webinterface (ID:{device_id} Offset:{device_offset})")
                ret = self.plugin.send_learn_protocol(int(device_offset), int(device_id))
                if ret == True:
                    learn_triggered = True
            else:
                self.logger.error("Unknown comman received via webinterface")

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path']), reverse=False),
                           tabcount=1, item_id=item_id, learn_triggered=learn_triggered, action='')


