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
from . import eep_parser
from lib.model.smartplugin import SmartPlugin

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
    PLUGIN_VERSION = "1.3.3"
    ALLOW_MULTIINSTANCE = False
    
    def __init__(self, smarthome, serialport, tx_id=''):
        self._sh = smarthome
        self.port = serialport
        self.logger = logging.getLogger(__name__)
        if (len(tx_id) < 8):
            self.tx_id = 0
            self.logger.warning('enocean: No valid enocean stick ID configured. Transmitting is not supported')
        else:
            self.tx_id = int(tx_id, 16)
            self.logger.info('enocean: Stick TX ID configured via plugin.conf to: {0}'.format(tx_id))
        self._tcm = serial.Serial(serialport, 57600, timeout=0.5)
        self._cmd_lock = threading.Lock()
        self._response_lock = threading.Condition()
        self._rx_items = {}
        self._block_ext_out_msg = False
        self.eep_parser = eep_parser.EEP_Parser()

    def eval_telegram(self, sender_id, data, opt):
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
                            self.logger.debug("Resulting value: {0} for {1}".format(value, item))
                            if value:  # not sure about this
                                item(value, 'EnOcean', 'RADIO')

    def _process_packet_type_event(self, data, optional):
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
        try:
            for step in sequence:
                event, relation, delay = step.split()             
                #self.logger.debug("waiting for {} {} {}".format(event, relation, delay))
                if item._enocean_rs_events[event.upper()].wait(float(delay)) != (relation.upper() == "WITHIN"):
                    self.logger.debug("NOT {} - aborting sequence!".format(step))
                    return
                else:
                    self.logger.debug("{}".format(step))
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
            self.logger.error("enocean: error handling enocean_rocker_sequence \"{}\" - {}".format(sequence, e))        

    def _process_packet_type_radio(self, data, optional):
        #self.logger.warning("enocean: processing radio message with data = [{}] / optional = [{}]".format(', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))

        choice = data[0]
        payload = data[1:-5]
        sender_id = int.from_bytes(data[-5:-1], byteorder='big', signed=False)
        status = data[-1]
        repeater_cnt = status & 0x0F
        self.logger.info("enocean: radio message: choice = {:02x} / payload = [{}] / sender_id = {:08X} / status = {} / repeat = {}".format(choice, ', '.join(['0x%02x' % b for b in payload]), sender_id, status, repeater_cnt))

        if (len(optional) == 7):
            subtelnum = optional[0]
            dest_id = int.from_bytes(optional[1:5], byteorder='big', signed=False)
            dBm = -optional[5]
            SecurityLevel = optional[6]
            self.logger.debug("enocean: radio message with additional info: subtelnum = {} / dest_id = {:08X} / signal = {}dBm / SecurityLevel = {}".format(subtelnum, dest_id, dBm, SecurityLevel))
            if (choice == 0xD4) and (self.UTE_listen == True):
                self.logger.info("call send_UTE_response")
                self._send_UTE_response(data, optional)
        if sender_id in self._rx_items:
            self.logger.debug("enocean: Sender ID found in item list")
            # iterate over all eep known for this id and get list of associated items
            for eep,items in self._rx_items[sender_id].items():
                # check if choice matches first byte in eep (this seems to be the only way to find right eep for this particular packet)
                if eep.startswith("{:02X}".format(choice)):
                    # call parser for particular eep - returns dictionary with key-value pairs
                    results = self.eep_parser.Parse(eep, payload, status)
                    #self.logger.debug("enocean: radio message results = {}".format(results))
                    for item in items:
                        rx_key = item.conf['enocean_rx_key'].upper()
                        if rx_key in results:
                            if 'enocean_rocker_sequence' in item.conf:
                                try:   
                                    if hasattr(item, '_enocean_rs_thread') and item._enocean_rs_thread.isAlive():
                                        if results[rx_key]:
                                            self.logger.debug("sending pressed event")
                                            item._enocean_rs_events["PRESSED"].set()
                                        else:
                                            self.logger.debug("sending released event")
                                            item._enocean_rs_events["RELEASED"].set()
                                    elif results[rx_key]:
                                        item._enocean_rs_events = {'PRESSED': threading.Event(), 'RELEASED': threading.Event()}
                                        item._enocean_rs_thread = threading.Thread(target=self._rocker_sequence, name="enocean-rs", args=(item, sender_id, item.conf['enocean_rocker_sequence'].split(','), ))
                                        #self.logger.info("starting enocean_rocker_sequence thread")
                                        item._enocean_rs_thread.daemon = True
                                        item._enocean_rs_thread.start()
                                except Exception as e:
                                    self.logger.error("enocean: error handling enocean_rocker_sequence - {}".format(e))
                            else:
                                item(results[rx_key], 'EnOcean', "{:08X}".format(sender_id))
        elif (sender_id <= self.tx_id + 127) and (sender_id >= self.tx_id):
            self.logger.debug("enocean: Received repeated enocean stick message")
        else:
            self.logger.info("unknown ID = {:08X}".format(sender_id))


    def _process_packet_type_smart_ack_command(self, data, optional):
        self.logger.warning("enocean: smart acknowledge command 0x06 received but not supported at the moment")


    def _process_packet_type_response(self, data, optional):
        RETURN_CODES = ['OK', 'ERROR', 'NOT SUPPORTED', 'WRONG PARAM', 'OPERATION DENIED']
        if (self._last_cmd_code == SENT_RADIO_PACKET) and (len(data) == 1):
            self.logger.debug("enocean: sending command returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_RESET) and (len(data) == 1):
            self.logger.info("enocean: Reset returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_LEARNMODE) and (len(data) == 1):
            self.logger.info("enocean: Write LearnMode returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_VERSION):
            if (data[0] == 0) and (len(data) == 33):
                self.logger.info("enocean: Chip ID = 0x{} / Chip Version = 0x{}".format(''.join(['%02x' % b for b in data[9:13]]), ''.join(['%02x' % b for b in data[13:17]])))
                self.logger.info("enocean: APP version = {} / API version = {} / App description = {}".format('.'.join(['%d' % b for b in data[1:5]]), '.'.join(['%d' % b for b in data[5:9]]), ''.join(['%c' % b for b in data[17:33]])))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("enocean: Reading version: No answer")
            else:
                self.logger.error("enocean: Reading version returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_IDBASE):
            if (data[0] == 0) and (len(data) == 5):
                self.logger.info("enocean: Base ID = 0x{}".format(''.join(['%02x' % b for b in data[1:5]])))
                if (self.tx_id == 0):
                    self.tx_id = int.from_bytes(data[1:5], byteorder='big', signed=False)
                    self.logger.info("enocean: Transmit ID set set automatically by reading chips BaseID")
                if (len(optional) == 1):
                    self.logger.info("enocean: Remaining write cycles for Base ID = {}".format(optional[0]))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("enocean: Reading Base ID: No answer")
            else:
                self.logger.error("enocean: Reading Base ID returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_WR_BIST):
            if (data[0] == 0) and (len(data) == 2):
                if (data[1] == 0):
                    self.logger.info("enocean: built in self test result: All OK")
                else:
                    self.logger.info("enocean: built in self test result: Problem, code = {}".format(data[1]))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("enocean: Doing built in self test: No answer")
            else:
                self.logger.error("enocean: Doing built in self test returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_LEARNMODE):
            if (data[0] == 0) and (len(data) == 2):
                self.logger.info("enocean: Reading LearnMode = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
                if (len(optional) == 1):
                    self.logger.info("enocean: learn channel = {}".format(optional[0]))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("enocean: Reading LearnMode: No answer")
        elif (self._last_packet_type == PACKET_TYPE_COMMON_COMMAND) and (self._last_cmd_code == CO_RD_NUMSECUREDEVICES):
            if (data[0] == 0) and (len(data) == 2):
                self.logger.info("enocean: Number of taught in devices = 0x{}".format(''.join(['%02x' % b for b in data[1]])))
            elif (data[0] == 0) and (len(data) == 0):
                self.logger.error("enocean: Reading NUMSECUREDEVICES: No answer")
            elif (data[0] == 2) and (len(data) == 1):
                self.logger.error("enocean: Reading NUMSECUREDEVICES: Command not supported")
            else:
                self.logger.error("enocean: Reading NUMSECUREDEVICES: Unknown error")
        elif (self._last_packet_type == PACKET_TYPE_SMART_ACK_COMMAND) and (self._last_cmd_code == SA_WR_LEARNMODE):
            self.logger.info("enocean: Setting SmartAck mode returned code = {}".format(RETURN_CODES[data[0]]))
        elif (self._last_packet_type == PACKET_TYPE_SMART_ACK_COMMAND) and (self._last_cmd_code == SA_RD_LEARNEDCLIENTS):
            if (data[0] == 0):
                self.logger.info("enocean: Number of smart acknowledge mailboxes = {}".format( int((len(data)-1)/9) ))
            else:
                self.logger.error("enocean: Requesting SmartAck mailboxes returned code = {}".format(RETURN_CODES[data[0]]))
        else:
            self.logger.error("enocean: processing unexpected response with return code = {} / data = [{}] / optional = [{}]".format(RETURN_CODES[data[0]], ', '.join(['0x%02x' % b for b in data]), ', '.join(['0x%02x' % b for b in optional])))
        self._response_lock.acquire()
        self._response_lock.notify()
        self._response_lock.release()

    def _startup(self):
        # request one time information
        self.logger.info("enocean: resetting device")
        self._send_common_command(CO_WR_RESET)
        self.logger.info("enocean: requesting id-base")
        self._send_common_command(CO_RD_IDBASE)
        self.logger.info("enocean: requesting version information")
        self._send_common_command(CO_RD_VERSION)
        self.logger.debug("enocean: ending connect-thread")

    def run(self):
        self.alive = True
        self.UTE_listen = False
        #self.learn_id = 0
        t = threading.Thread(target=self._startup, name="enocean-startup")
        t.daemon = True
        t.start()
        msg = []
        while self.alive:
            readin = self._tcm.read(1000)
            if readin:
                msg += readin
                #self.logger.debug("enocean: data received")
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
                        self.logger.debug("enocean: received header with data_length = {} / opt_length = 0x{:02x} / type = {}".format(data_length, opt_length, packet_type))

                        # break if msg is not yet complete:
                        if (len(msg) < msg_length):
                            break

                        # msg complete
                        if (self._calc_crc8(msg[6:msg_length - 1]) == msg[msg_length - 1]):
                            self.logger.debug("enocean: accepted package with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
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
                                self.logger.error("enocean: received packet with unknown type = 0x{:02x} - len = {} / data = [{}]".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        else:
                            self.logger.error("enocean: crc error - dumping packet with type = 0x{:02x} / len = {} / data = [{}]!".format(packet_type, msg_length, ', '.join(['0x%02x' % b for b in msg])))
                        msg = msg[msg_length:]
                    else:
                        #self.logger.warning("enocean: consuming [0x{:02x}] from input buffer!".format(msg[0]))
                        msg.pop(0)

    def stop(self):
        self.alive = False
        self.logger.info("enocean: Thread stopped")

        
    def _send_UTE_response(self, data, optional):
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
        self.logger.info("enocean: sending UTE response and end listening")

    def parse_item(self, item):
        if 'enocean_rx_key' in item.conf:
            # look for info from the most specific info to the broadest (key->eep->id) - one id might use multiple eep might define multiple keys
            eep_item = item
            while (not 'enocean_rx_eep' in eep_item.conf):
                eep_item = eep_item.return_parent()
                if (eep_item is self._sh):
                    self.logger.error("enocean: could not find enocean_rx_eep for item {}".format(item))
                    return None
            id_item = eep_item
            while (not 'enocean_rx_id' in id_item.conf):
                id_item = id_item.return_parent()
                if (id_item is self._sh):
                    self.logger.error("enocean: could not find enocean_rx_id for item {}".format(item))
                    return None

            rx_key = item.conf['enocean_rx_key'].upper()
            rx_eep = eep_item.conf['enocean_rx_eep'].upper()
            rx_id = int(id_item.conf['enocean_rx_id'],16)

            # check if there is a function to parse payload
            if not self.eep_parser.CanParse(rx_eep):
                return None

            if (rx_key in ['A0', 'A1', 'B0', 'B1']):
                self.logger.warning("enocean: key \"{}\" does not match EEP - \"0\" (Zero, number) should be \"O\" (letter) (same for \"1\" and \"I\") - will be accepted for now".format(rx_key))
                rx_key = rx_key.replace('0', 'O').replace("1", 'I')

            if (not rx_id in self._rx_items):
                self._rx_items[rx_id] = {rx_eep: [item]}
            elif (not rx_eep in self._rx_items[rx_id]):
                self._rx_items[rx_id][rx_eep] = [item]
            elif (not item in self._rx_items[rx_id][rx_eep]):
                self._rx_items[rx_id][rx_eep].append(item)

            self.logger.info("enocean: item {} listens to id {:08X} with eep {} key {}".format(item, rx_id, rx_eep, rx_key))
            #self.logger.info("enocean: self._rx_items = {}".format(self._rx_items))
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'EnOcean':
            self.logger.debug('enocean: item updated externally')
            if self._block_ext_out_msg:
                self.logger.debug('enocean: sending manually blocked by user. Aborting')
                return
            if 'enocean_tx_eep' in item.conf:
                if isinstance(item.conf['enocean_tx_eep'], str):
                    tx_eep = item.conf['enocean_tx_eep']
                    self.logger.debug('enocean: item has tx_eep')
                    id_offset = 0
                    if 'enocean_tx_id_offset' in item.conf and (isinstance(item.conf['enocean_tx_id_offset'], str)):
                        self.logger.debug('enocean: item has valid enocean_tx_id_offset')
                        id_offset = int(item.conf['enocean_tx_id_offset'])
                    #Identify send command based on tx_eep coding:
                    if(tx_eep == 'A5_20_04'):
                        self.send_radiator_valve(id_offset)
                        self.logger.debug('enocean: sent A5_20_04 radiator valve command')
                    elif(tx_eep == 'A5_38_08_02'):
                        self.logger.debug('enocean: item is A5_38_08_02 type')
                        if not item():
                            self.send_dim(id_offset, 0, 0)
                            self.logger.debug('enocean: sent off command')
                        else:
                            if 'ref_level' in item.level.conf:
                                dim_value = int(item.level.conf['ref_level'])
                                self.logger.debug('enocean: ref_level found')
                            else:
                                dim_value = 100
                                self.logger.debug('enocean: no ref_level found. Setting to default 100')
                            self.send_dim(id_offset, dim_value, 0)
                            self.logger.debug('enocean: sent dim on command')
                    elif(tx_eep == 'A5_38_08_03'):
                        self.logger.debug('enocean: item is A5_38_08_03 type')
                        self.send_dim(id_offset, item(), 0)
                        self.logger.debug('enocean: sent dim command')
                    elif(tx_eep == 'D2_01_07'):
                        if 'enocean_rx_id' in item.conf:
                            rx_id = int(item.conf['enocean_rx_id'],16)
                            self.logger.debug('enocean:  enocean_rx_id found')
                        else:
                            rx_id=0
                            self.logger.debug('enocean:  NO enocean_rx_id found')
                        if 'enocean_pulsewidth' in item.conf:
                            pulsew = float(item.conf['enocean_pulsewidth'])
                            self.logger.debug('enocean:  pulsewidth found')
                        else:
                            pulsew=0
                            self.logger.debug('enocean:  NO pulsewidth found')
                        self.logger.debug('enocean: item is D2_01_07_01 type')
                        self.send_switch_D2(id_offset, rx_id, pulsew, item())
                        self.logger.debug('enocean: sent switch command for D2 VLD')
                    elif(tx_eep == 'A5_38_08_01'):
                        self.logger.debug('enocean: item is A5_38_08_01 type')
                        self.send_switch(id_offset, item(), 0)
                        self.logger.debug('enocean: sent switch command')
                    elif(tx_eep == '07_3F_7F'):
                        self.logger.debug('enocean: item is 07_3F_7F type')
                        self.send_rgbw_dim(id_offset, item(), 0)
                        self.logger.debug('enocean: sent RGBW dim command')
                    elif(tx_eep == 'A5_3F_7F'):
                        rtime=5
                        if 'enocean_rtime' in item.conf:
                            rtime = int(item.conf['enocean_rtime'])
                            self.logger.debug('enocean:  actuator runtime specified.')
                        self.logger.debug('enocean: item is A5_3F_7F type')
                        self.send_generic_actuator_cmd(id_offset, rtime, item())
                        self.logger.debug('enocean: sent actuator command')
                    else:
                        self.logger.error('enocean: error: Unknown tx eep command')
                else:
                    self.logger.error('enocean: tx_eep is not a string value')
            else:
                self.logger.debug('enocean: item has no tx_eep value')

    def read_num_securedivices(self):
        self._send_common_command(CO_RD_NUMSECUREDEVICES)
        self.logger.info("enocean: Read number of secured devices")


        # Request all taught in smart acknowledge devices that have a mailbox
    def get_smart_ack_devices(self):
        self._send_smart_ack_command(SA_RD_LEARNEDCLIENTS)
        self.logger.info("enocean: Requesting all available smart acknowledge mailboxes")


    def reset_stick(self):
        self.logger.info("enocean: resetting device")
        self._send_common_command(CO_WR_RESET)

    def block_external_out_messages(self, block=True):
        if block:
            self.logger.info("enocean: Blocking of external out messages activated")
            self._block_ext_out_msg = True
        elif not block:
            self.logger.info("enocean: Blocking of external out messages deactivated")
            self._block_ext_out_msg = False
        else:
            self.logger.info("enocean: invalid argument. Must be True/False")

    def send_bit(self):
        self.logger.info("enocean: trigger Built-In Self Test telegram")
        self._send_common_command(CO_WR_BIST)

    def version(self):
        self.logger.info("enocean: request stick version")
        self._send_common_command(CO_RD_VERSION)

    def _send_packet(self, packet_type, data=[], optional=[]):
        length_optional = len(optional)
        if length_optional > 255:
            self.logger.error("enocean: optional too long ({} bytes, 255 allowed)".format(length_optional))
            return
        length_data = len(data)
        if length_data > 65535:
            self.logger.error("enocean: data too long ({} bytes, 65535 allowed)".format(length_data))
            return

        packet = bytearray([PACKET_SYNC_BYTE])
        packet += length_data.to_bytes(2, byteorder='big') + bytes([length_optional, packet_type])
        packet += bytes([self._calc_crc8(packet[1:5])])
        packet += bytes(data + optional)
        packet += bytes([self._calc_crc8(packet[6:])])
        self.logger.info("enocean: sending packet with len = {} / data = [{}]!".format(len(packet), ', '.join(['0x%02x' % b for b in packet])))
        self._tcm.write(packet)

    def _send_smart_ack_command(self, _code, data=[]):
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
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error("enocean: invalid base ID offset range. (Is {}, must be [0 127])".format(id_offset))
            return
        self._cmd_lock.acquire()
        self._last_cmd_code = SENT_RADIO_PACKET
        self._send_packet(PACKET_TYPE_RADIO, [_code] + data + list((self.tx_id + id_offset).to_bytes(4, byteorder='big')) + [0x00], optional)
        self._response_lock.acquire()
        # wait 5sec for response
        self._response_lock.wait(5)
        self._response_lock.release()
        self._cmd_lock.release()

    def send_radiator_valve(self,item, id_offset=0):
        self.logger.debug("enocean: sending valve command A5_20_04")
        temperature = item
        #define default values:
        MC  = 1 #off
        WUC = 3 # 120 seconds
        BLC = 0 # unlocked
        LRNB = 1# data
        DSO = 0 # 0 degree
        valve_position = 50

        for sibling in get_children(item.parent):
            if hasattr(sibling, "MC"):
                MC = sibling()
            if hasattr(sibling, "WUC"):
                WUC = sibling()
            if hasattr(sibling, "BLC"):
                BLC = sibling()
            if hasattr(sibling, "LRNB"):
                LRNB = sibling()
            if hasattr(sibling, "DSO"):
                DSO = sibling()
            if hasattr(sibling, "VALVE_POSITION"):
                valve_position = sibling()
        TSP = int((temperature -10)*255/30)
        status =  0 + (MC << 1) + (WUC << 2) 
        status2 = (BLC << 5) + (LRNB << 4) + (DSO << 2) 
        self._send_radio_packet(id_offset, 0xA5, [valve_position, TSP, status , status2])


    def send_dim(self,id_offset=0, dim=0, dimspeed=0):
        if (dimspeed < 0) or (dimspeed > 255):
            self.logger.error("enocean: sending dim command A5_38_08: invalid range of dimspeed")
            return
        self.logger.debug("enocean: sending dim command A5_38_08")
        if (dim == 0):
            self._send_radio_packet(id_offset, 0xA5, [0x02, 0x00, int(dimspeed), 0x08])
        elif (dim > 0) and (dim <= 100):
            self._send_radio_packet(id_offset, 0xA5, [0x02, int(dim), int(dimspeed), 0x09])
        else:
            self.logger.error("enocean: sending command A5_38_08: invalid dim value")

    def send_rgbw_dim(self,id_offset=0, color='red', dim=0, dimspeed=0):
        if(color == str(red)):
            color_hex_code = 0x10
        elif(color == str(green)):
            color_hex_code = 0x11
        elif(color == str(blue)):
            color_hex_code = 0x12
        elif(color == str(white)):
            color_hex_code = 0x13
        else:
            self.logger.error("enocean: sending rgbw dim command: invalid color")
            return
        if (dim < 0) or (dim > 1023):
            self.logger.error("enocean: sending rgb dim command: invalid dim value range. Only 10 bit allowed")
            return
        self._send_radio_packet(id_offset, 0x07, [ list(dim.to_bytes(2, byteorder='big')), color_hex_code, 0x0F])
        self.logger.debug("enocean: sent dim command 07_3F_7F")

    def send_generic_actuator_cmd(self,id_offset=0, rtime=0, command=0):
        if (rtime < 0) or (rtime > 255):
            self.logger.error("enocean: sending switch command A5_3F_7F: invalid runtime range (0-255)")
            return
        if(command == 0):
            command_hex_code = 0x00
        elif(command == 1):
            command_hex_code = 0x01
        elif(command == 2):
            command_hex_code = 0x02
        else:
            self.logger.error("enocean: sending actuator command failed: invalid command" + command)
            return
        self._send_radio_packet(id_offset, 0xA5, [0x00, rtime, command_hex_code, 0x0c])
        self.logger.debug("enocean: sending actuator command A5_3F_7F")

    def send_switch(self,id_offset=0, on=0, block=0):
        if (block < 0) and (block > 1):
            self.logger.error("enocean: sending switch command A5_38_08: invalid range of block (0,1)")
            return
        self.logger.debug("enocean: sending switch command A5_38_08")
        if (on == 0):
            self._send_radio_packet(id_offset, 0xA5, [0x01, 0x00, 0x00, 0x08])
        elif (on == 1) and (block == 0):
            self._send_radio_packet(id_offset, 0xA5, [0x01, 0x00, 0x00, 0x09])
        else:
            self.logger.error("enocean: sending command A5_38_08: error")


    def send_switch_D2(self, id_offset=0, rx_id=0, pulsew=0, on=0):
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error("enocean: ID offset out of range (0-127). Aborting.")
            return
        if (rx_id < 0) or (rx_id > 0xFFFFFFFF):
            self.logger.error("enocean: ID offset out of range (0-127). Aborting.")
            return
        SubTel = 0x03
        db = 0xFF
        Secu = 0x0
        #self._send_radio_packet(id_offset, 0xD2, [0x01, 0x1E, 0x01],[0x03, 0xFF, 0xBA, 0xD0, 0x00, 0xFF, 0x0])
        self.logger.info("enocean: sending switch command D2_01_07")
        if (on == 0):
            self._send_radio_packet(id_offset, 0xD2, [0x01, 0x1E, 0x00],[0x03, rx_id, 0xFF, 0x0])
        elif (on == 1):
            self._send_radio_packet(id_offset, 0xD2, [0x01, 0x1E, 0x01],[0x03, rx_id, 0xFF, 0x0])
            if (pulsew  > 0):
                time.sleep(pulsew)
                self._send_radio_packet(id_offset, 0xD2, [0x01, 0x1E, 0x00],[0x03, rx_id, 0xFF, 0x0])
        else:
            self.logger.error("enocean: sending command D2_01_07: error")
        

####################################################
### --- START - Definitions of Learn Methods --- ###
####################################################
    def send_learn_protocol(self, id_offset=0, device=10):
        # define RORG
        rorg = 0xA5
        
        # check offset range between 0 and 127
        if (id_offset < 0) or (id_offset > 127):
            self.logger.error('enocean: ID offset with value = {} out of range (0-127). Aborting.'.format(id_offset))
            return None
        # device range 10 - 19 --> Learn protocol for switch actuators
        elif (device == 10):
            # Prepare Data for Eltako switch FSR61
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
            self.logger.info('enocean: sending learn telegram for radiator valve with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        # device range 40 - 49 --> Learn protocol for other actuators
        elif (device == 40):
            # Eltako shutter actor FSB14, FSB61, FSB71
             payload = [0xFF, 0xF8, 0x0D, 0x80]
             self.logger.info('enocean: sending learn telegram for actuator with [Device], [ID-Offset], [RORG], [payload] / [{}], [{:#04x}], [{:#04x}], [{}]'.format(device, id_offset, rorg, ', '.join('{:#04x}'.format(x) for x in payload)))
        else:
            self.logger.error('enocean: sending learn telegram with invalid device! Device {} actually not defined!'.format(device))
            return None
        # Send radio package
        self._send_radio_packet(id_offset, rorg, payload)
        return None


    def start_UTE_learnmode(self, id_offset=0):
        self.UTE_listen = True
        self.learn_id = id_offset
        self.logger.info("enocean: Listeining for UTE package ('D4')")
        
        
    def enter_learn_mode(self, onoff=1):
        if (onoff == 1):
            self._send_common_command(CO_WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00],[0xFF])
            self.logger.info("enocean: entering learning mode")
            return None
        else:
            self._send_common_command(CO_WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00],[0xFF])
            self.logger.info("enocean: leaving learning mode")
            return None

            
    # This function enables/disables the controller's smart acknowledge mode
    def set_smart_ack_learn_mode(self, onoff=1):
        if (onoff == 1):
            self._send_smart_ack_command(SA_WR_LEARNMODE, [0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("enocean: enabling smart acknowledge learning mode")
            return None
        else:
            self._send_smart_ack_command(SA_WR_LEARNMODE, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
            self.logger.info("enocean: disabling smart acknowledge learning mode")
            return None

##################################################
### --- END - Definitions of Learn Methods --- ###
##################################################


#################################
### --- START - Calc CRC8 --- ###
#################################
    def _calc_crc8(self, msg, crc=0):
        for i in msg:
            crc = FCSTAB[crc ^ i]
        return crc

###############################
### --- END - Calc CRC8 --- ###
###############################
