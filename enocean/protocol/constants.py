#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
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

from enum import IntEnum


class PACKET(IntEnum):
    """ generic packet identifiers """
    SYNC_BYTE = 0x55
    SENT_RADIO = 0xFF
    SENT_ENCAPSULATED_RADIO = 0xA6


class RORG(IntEnum):
    """ encapsulates EEP types from EnOcean Equipment Profiles v2.61 """
    UNDEFINED = 0x00
    RPS = 0xF6
    BS1 = 0xD5
    BS4 = 0xA5
    VLD = 0xD2
    MSC = 0xD1
    ADT = 0xA6
    SM_LRN_REQ = 0xC6
    SM_LRN_ANS = 0xC7
    SM_REC = 0xA7
    SYS_EX = 0xC5
    SEC = 0x30
    SEC_ENCAPS = 0x31
    UTE = 0xD4


class PACKET_TYPE(IntEnum):
    """ encapsulates packet types """
    RESERVED = 0x00
    RADIO = 0x01               # RADIO ERP1
    RADIO_ERP1 = 0x01          # RADIO ERP1 => Kept for backwards compatibility reasons, for example custom packet. Generation shouldn't be affected...
    RESPONSE = 0x02            # RESPONSE
    RADIO_SUB_TEL = 0x03       # RADIO_SUB_TEL
    EVENT = 0x04               # EVENT
    COMMON_COMMAND = 0x05      # COMMON COMMAND
    SMART_ACK_COMMAND = 0x06   # SMART ACK COMMAND
    REMOTE_MAN_COMMAND = 0x07  # REMOTE MANAGEMENT COMMAND
    RADIO_MESSAGE = 0x09       # RADIO MESSAGE
    RADIO_ERP2 = 0x0A          # RADIO ERP2
    RADIO_802_15_4 = 0x10      # RADIO_802_15_4_RAW_Packet
    COMMAND_2_4 = 0x11         # COMMAND 2.4 GHz


class EVENT(IntEnum):
    """ encapsulates Event Codes """
    RECLAIM_NOT_SUCCESSFUL = 0x01  # Informs the backbone of a Smart Ack Client to not successful reclaim.
    CONFIRM_LEARN = 0x02           # Used for SMACK to confirm/discard learn in/out
    LEARN_ACK = 0x03               # Inform backbone about result of learn request
    READY = 0x04                   # Inform backbone about the readiness for operation
    EVENT_SECUREDEVICES = 0x05     # Informs about a secure device
    DUTYCYCLE_LIMIT = 0x06         # Informs about duty cycle limit
    TRANSMIT_FAILED = 0x07         # Informs that the device was not able to send a telegram.
    TX_DONE = 0x08                 # Informs the external host that the device has finished all transmissions.
    LRN_MODE_DISABLED = 0x09       # Informs the external host that the learn mode has been disabled due to timeout.


class COMMON_COMMAND(IntEnum):
    """ encapsulates Common Command Codes """
    WR_SLEEP = 0x01                        # Enter in energy saving mode
    WR_RESET = 0x02                        # Reset the device
    RD_VERSION = 0x03                      # Read the device (SW) version /(HW) version, chip ID etc.
    RD_SYS_LOG = 0x04                      # Read system log from device databank
    WR_SYS_LOG = 0x05                      # Reset System log from device databank
    WR_BIST = 0x06                         # Perform built in self test
    WR_IDBASE = 0x07                       # Write ID range base number
    RD_IDBASE = 0x08                       # Read ID range base number
    WR_REPEATER = 0x09                     # Write Repeater Level off,1,2
    RD_REPEATER = 0x0A                     # Read Repeater Level off,1,2
    WR_FILTER_ADD = 0x0B                   # Add filter to filter list
    WR_FILTER_DEL = 0x0C                   # Delete filter from filter list
    WR_FILTER_DEL_ALL = 0x0D               # Delete all filter
    WR_FILTER_ENABLE = 0x0E                # Enable/Disable supplied filters
    RD_FILTER = 0x0F                       # Read supplied filters
    WR_WAIT_MATURITY = 0x10                # Waiting till end of maturity time before received radio telegrams will transmitted    
    WR_SUBTEL = 0x11                       # Enable/Disable transmitting additional subtelegram info
    WR_MEM = 0x12                          # Write x bytes of the Flash, XRAM, RAM0 …
    RD_MEM = 0x13                          # Read x bytes of the Flash, XRAM, RAM0 ….
    RD_MEM_ADDRESS = 0x14                  # Feedback about the used address and length of the configarea and the Smart Ack Table
    RD_SECURITY = 0x15                     # Read own security information (level, key)
    WR_SECURITY = 0x16                     # Write own security information (level, key)
    WR_LEARNMODE = 0x17                    # Function: Enables or disables learn mode of Controller.
    RD_LEARNMODE = 0x18                    # Function: Reads the learn-mode state of Controller.
    WR_SECUREDEVICE_ADD = 0x19             # Add a secure device
    WR_SECUREDEVICE_DEL = 0x1A             # Delete a secure device
    RD_SECUREDEVICE_BY_INDEX = 0x1B        # Read secure device by index
    WR_MODE = 0x1C                         # Sets the gateway transceiver mode
    RD_NUMSECUREDEVICES = 0x1D             # Read number of taught in secure devices
    RD_SECUREDEVICE_BY_ID = 0x1E           # Read secure device by ID
    WR_SECUREDEVICE_ADD_PSK = 0x1F         # Add Pre-shared key for inbound secure device
    WR_SECUREDEVICE_SENDTEACHIN = 0x20     # Send secure Teach-In message
    WR_TEMPORARY_RLC_WINDOW = 0x21         # Set the temporary rolling-code window for every taught-in devic
    RD_SECUREDEVICE_PSK = 0x22             # Read PSK
    RD_DUTYCYCLE_LIMIT = 0x23              # Read parameters of actual duty cycle limit
    SET_BAUDRATE = 0x24                    # Modifies the baud rate of the EnOcean device
    GET_FREQUENCY_INFO = 0x25              # Reads Frequency and protocol of the Device
    GET_STEPCODE = 0x27                    # Reads Hardware Step code and Revision of the Device
    WR_REMAN_CODE = 0x2E                   # Set the security code to unlock Remote Management functionality via radio
    WR_STARTUP_DELAY = 0x2F                # Set the startup delay (time from power up until start of operation)
    WR_REMAN_REPEATING = 0x30              # Select if REMAN telegrams originating from this module can be repeated
    RD_REMAN_REPEATING = 0x31              # Check if REMAN telegrams originating from this module can be repeated
    SET_NOISETHRESHOLD = 0x32              # Set the RSSI noise threshold level for telegram reception
    GET_NOISETHRESHOLD = 0x33              # Read the RSSI noise threshold level for telegram reception
    WR_RLC_SAVE_PERIOD = 0x36              # Set the period in which outgoing RLCs are saved to the EEPROM
    WR_RLC_LEGACY_MODE = 0x37              # Activate the legacy RLC security mode allowing roll-over and using the RLC acceptance window for 24bit explicit RLC
    WR_SECUREDEVICEV2_ADD = 0x38           # Add secure device to secure link table
    RD_SECUREDEVICEV2_BY_INDEX = 0x39      # Read secure device from secure link table using the table index
    WR_RSSITEST_MODE = 0x3A                # Control the state of the RSSI-Test mode
    RD_RSSITEST_MODE = 0x3B                # Read the state of the RSSI-Test mode
    WR_SECUREDEVICE_MAINTENANCEKEY = 0x3C  # Add the maintenance key information into the secure link table
    RD_SECUREDEVICE_MAINTENANCEKEY = 0x3D  # Read by index the maintenance key information from the secure link table
    WR_TRANSPARENT_MODE = 0x3E             # Control the state of the transparent mode
    RD_TRANSPARENT_MODE = 0x3F             # Read the state of the transparent mode
    WR_TX_ONLY_MODE = 0x40                 # Control the state of the TX only mode
    RD_TX_ONLY_MODE = 0x41                 # Read the state of the TX only mode


class SMART_ACK(IntEnum):
    """ encapsulates Smart Acknowledge codes """
    WR_LEARNMODE = 0x01       # Set/Reset Smart Ack learn mode
    RD_LEARNMODE = 0x02       # Get Smart Ack learn mode state
    WR_LEARNCONFIRM = 0x03    # Used for Smart Ack to add or delete a mailbox of a client
    WR_CLIENTLEARNRQ = 0x04   # Send Smart Ack Learn request (Client)
    WR_RESET = 0x05           # Send reset command to a Smart Ack client
    RD_LEARNEDCLIENTS = 0x06  # Get Smart Ack learned sensors / mailboxes
    WR_RECLAIMS = 0x07        # Set number of reclaim attempts
    WR_POSTMASTER = 0x08      # Activate/Deactivate Post master functionality


class RETURN_CODE(IntEnum):
    """ encapsulates return codes """
    OK = 0x00
    ERROR = 0x01
    NOT_SUPPORTED = 0x02
    WRONG_PARAM = 0x03
    OPERATION_DENIED = 0x04


class PARSE_RESULT(IntEnum):
    """ encapsulates parsing return codes """
    OK = 0x00
    INCOMPLETE = 0x01
    CRC_MISMATCH = 0x03
