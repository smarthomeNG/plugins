#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

from enum import IntEnum

################################
### --- Packet Generic --- ###
################################
class PACKET(IntEnum):
    PACKET_SYNC_BYTE               = 0x55   # PACKET SYNC BYTE
    SENT_RADIO_PACKET              = 0xFF
    SENT_ENCAPSULATED_RADIO_PACKET = 0xA6


# EnOcean_Equipment_Profiles_EEP_V2.61_public.pdf / 8
class RORG(IntEnum):
    UNDEFINED   = 0x00
    RPS         = 0xF6
    BS1         = 0xD5
    BS4         = 0xA5
    VLD         = 0xD2
    MSC         = 0xD1
    ADT         = 0xA6
    SM_LRN_REQ  = 0xC6
    SM_LRN_ANS  = 0xC7
    SM_REC      = 0xA7
    SYS_EX      = 0xC5
    SEC         = 0x30
    SEC_ENCAPS  = 0x31
    UTE         = 0xD4



############################
### --- Packet Types --- ###
############################
class PACKET_TYPE(IntEnum):
    RESERVED           = 0x00
    RADIO              = 0x01   # RADIO ERP1
    RADIO_ERP1         = 0x01   # RADIO ERP1
    RESPONSE           = 0x02   # RESPONSE
    RADIO_SUB_TEL      = 0x03   # RADIO_SUB_TEL
    EVENT              = 0x04   # EVENT
    COMMON_COMMAND     = 0x05   # COMMON COMMAND
    SMART_ACK_COMMAND  = 0x06   # SMART ACK COMMAND
    REMOTE_MAN_COMMAND = 0x07   # REMOTE MANAGEMENT COMMAND
    RADIO_MESSAGE      = 0x09   # RADIO MESSAGE
    RADIO_ERP2         = 0x0A   # RADIO ERP2
    RADIO_802_15_4     = 0x10   # RADIO_802_15_4_RAW_Packet
    COMMAND_2_4        = 0x11   # COMMAND 2.4 GHz


###################################
### --- List of Event Codes --- ###
###################################
class EVENT(IntEnum):
    SA_RECLAIM_NOT_SUCCESSFUL  = 0x01      # Informs the backbone of a Smart Ack Client to not successful reclaim.
    SA_CONFIRM_LEARN           = 0x02      # Used for SMACK to confirm/discard learn in/out
    SA_LEARN_ACK               = 0x03      # Inform backbone about result of learn request
    CO_READY                   = 0x04      # Inform backbone about the readiness for operation
    CO_EVENT_SECUREDEVICES     = 0x05      # Informs about a secure device
    CO_DUTYCYCLE_LIMIT         = 0x06      # Informs about duty cycle limit
    CO_TRANSMIT_FAILED         = 0x07      # Informs that the device was not able to send a telegram.
    CO_TX_DONE                 = 0x08      # Informs the external host that the device has finished all transmissions.
    CO_LRN_MODE_DISABLED       = 0x09      # Informs the external host that the learn mode has been disabled due to timeout.


############################################
### --- List of Common Command Codes --- ###
############################################
class COMMON_COMMAND(IntEnum):
    CO_WR_SLEEP                     = 0x01      # Enter in energy saving mode
    CO_WR_RESET                     = 0x02      # Reset the device
    CO_RD_VERSION                   = 0x03      # Read the device (SW) version /(HW) version, chip ID etc.
    CO_RD_SYS_LOG                   = 0x04      # Read system log from device databank
    CO_WR_SYS_LOG                   = 0x05      # Reset System log from device databank
    CO_WR_BIST                      = 0x06      # Perform built in self test
    CO_WR_IDBASE                    = 0x07      # Write ID range base number
    CO_RD_IDBASE                    = 0x08      # Read ID range base number
    CO_WR_REPEATER                  = 0x09      # Write Repeater Level off,1,2
    CO_RD_REPEATER                  = 0x0A      # Read Repeater Level off,1,2
    CO_WR_FILTER_ADD                = 0x0B      # Add filter to filter list
    CO_WR_FILTER_DEL                = 0x0C      # Delete filter from filter list
    CO_WR_FILTER_DEL_ALL            = 0x0D      # Delete all filter
    CO_WR_FILTER_ENABLE             = 0x0E      # Enable/Disable supplied filters
    CO_RD_FILTER                    = 0x0F      # Read supplied filters
    
    CO_WR_WAIT_MATURITY             = 0x10      # Waiting till end of maturity time before received radio telegrams will transmitted    
    CO_WR_SUBTEL                    = 0x11      # Enable/Disable transmitting additional subtelegram info
    CO_WR_MEM                       = 0x12      # Write x bytes of the Flash, XRAM, RAM0 …
    CO_RD_MEM                       = 0x13      # Read x bytes of the Flash, XRAM, RAM0 ….
    CO_RD_MEM_ADDRESS               = 0x14      # Feedback about the used address and length of the configarea and the Smart Ack Table
    CO_RD_SECURITY                  = 0x15      # Read own security information (level, key)
    CO_WR_SECURITY                  = 0x16      # Write own security information (level, key)
    CO_WR_LEARNMODE                 = 0x17      # Function: Enables or disables learn mode of Controller.
    CO_RD_LEARNMODE                 = 0x18      # Function: Reads the learn-mode state of Controller.
    CO_WR_SECUREDEVICE_ADD          = 0x19      # Add a secure device
    CO_WR_SECUREDEVICE_DEL          = 0x1A      # Delete a secure device
    CO_RD_SECUREDEVICE_BY_INDEX     = 0x1B      # Read secure device by index
    CO_WR_MODE                      = 0x1C      # Sets the gateway transceiver mode
    CO_RD_NUMSECUREDEVICES          = 0x1D      # Read number of taught in secure devices
    CO_RD_SECUREDEVICE_BY_ID        = 0x1E      # Read secure device by ID
    CO_WR_SECUREDEVICE_ADD_PSK      = 0x1F      # Add Pre-shared key for inbound secure device
    
    CO_WR_SECUREDEVICE_SENDTEACHIN      = 0x20      # Send secure Teach-In message
    CO_WR_TEMPORARY_RLC_WINDOW          = 0x21      # Set the temporary rolling-code window for every taught-in devic
    CO_RD_SECUREDEVICE_PSK              = 0x22      # Read PSK
    CO_RD_DUTYCYCLE_LIMIT               = 0x23      # Read parameters of actual duty cycle limit
    CO_SET_BAUDRATE                     = 0x24      # Modifies the baud rate of the EnOcean device
    CO_GET_FREQUENCY_INFO               = 0x25      # Reads Frequency and protocol of the Device
    CO_GET_STEPCODE                     = 0x27      # Reads Hardware Step code and Revision of the Device
    CO_WR_REMAN_CODE                    = 0x2E      # Set the security code to unlock Remote Management functionality via radio
    CO_WR_STARTUP_DELAY                 = 0x2F      # Set the startup delay (time from power up until start of operation)
    
    CO_WR_REMAN_REPEATING               = 0x30      # Select if REMAN telegrams originating from this module can be repeated
    CO_RD_REMAN_REPEATING               = 0x31      # Check if REMAN telegrams originating from this module can be repeated
    CO_SET_NOISETHRESHOLD               = 0x32      # Set the RSSI noise threshold level for telegram reception
    CO_GET_NOISETHRESHOLD               = 0x33      # Read the RSSI noise threshold level for telegram reception
    CO_WR_RLC_SAVE_PERIOD               = 0x36      # Set the period in which outgoing RLCs are saved to the EEPROM
    CO_WR_RLC_LEGACY_MODE               = 0x37      # Activate the legacy RLC security mode allowing roll-over and using the RLC acceptance window for 24bit explicit RLC
    CO_WR_SECUREDEVICEV2_ADD            = 0x38      # Add secure device to secure link table
    CO_RD_SECUREDEVICEV2_BY_INDEX       = 0x39      # Read secure device from secure link table using the table index
    CO_WR_RSSITEST_MODE                 = 0x3A      # Control the state of the RSSI-Test mode
    CO_RD_RSSITEST_MODE                 = 0x3B      # Read the state of the RSSI-Test mode
    CO_WR_SECUREDEVICE_MAINTENANCEKEY   = 0x3C      # Add the maintenance key information into the secure link table
    CO_RD_SECUREDEVICE_MAINTENANCEKEY   = 0x3D      # Read by index the maintenance key information from the secure link table
    CO_WR_TRANSPARENT_MODE              = 0x3E      # Control the state of the transparent mode
    CO_RD_TRANSPARENT_MODE              = 0x3F      # Read the state of the transparent mode
    CO_WR_TX_ONLY_MODE                  = 0x40      # Control the state of the TX only mode
    CO_RD_TX_ONLY_MODE                  = 0x41      # Read the state of the TX only mode


###########################################
###  --- Smart Acknowledge Defines: --- ###
###########################################
class SMART_ACK(IntEnum):
    SA_WR_LEARNMODE        = 0x01          # Set/Reset Smart Ack learn mode
    SA_RD_LEARNMODE        = 0x02          # Get Smart Ack learn mode state
    SA_WR_LEARNCONFIRM     = 0x03          # Used for Smart Ack to add or delete a mailbox of a client
    SA_WR_CLIENTLEARNRQ    = 0x04          # Send Smart Ack Learn request (Client)
    SA_WR_RESET            = 0x05          # Send reset command to a Smart Ack client
    SA_RD_LEARNEDCLIENTS   = 0x06          # Get Smart Ack learned sensors / mailboxes
    SA_WR_RECLAIMS         = 0x07          # Set number of reclaim attempts
    SA_WR_POSTMASTER       = 0x08          # Activate/Deactivate Post master functionality


# Results for message parsing
class PARSE_RESULT(IntEnum):
    OK              = 0x00
    INCOMPLETE      = 0x01
    CRC_MISMATCH    = 0x03
