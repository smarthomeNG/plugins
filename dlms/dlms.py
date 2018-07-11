#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 - 2017 Bernd Meiners              Bernd.Meiners@mail.de
#########################################################################
#
#  DLMS plugin for SmartHomeNG.py.
#
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import logging
import datetime
from ruamel.yaml import YAML

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug("init standalone {}".format(__name__))
else:
    logger = logging.getLogger()
    logger.debug("init plugin component {}".format(__name__))

import time
import serial
import re
from threading import Semaphore
manufacturer_ids = {}

exportfile = 'manufacturer.yaml'
try:
    with open(exportfile, 'r') as infile:
        y = YAML(typ='safe')
        manufacturer_ids = y.load(infile)
except:
    pass
"""
This module implements the query of a smartmeter using the DLMS protocol.
The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB.

The Character Format for protocol mode A - D is defined as 1 start bit, 7 data bits, 1 parity bit, 1 stop bit and even parity 
In protocol mode E it is defined as 1 start bit, 8 data bits, 1 stop bit is allowed, see Annex E of IEC62056-21
For this plugin the protocol mode E is neither implemented nor supported.

Abbreviations
-------------
COSEM
   COmpanion Specification for Energy Metering

OBIS
   OBject Identification System (see iec62056-61{ed1.0}en_obis_protocol.pdf)

"""

SOH = 0x01  # start of header
STX = 0x02  # start of text        
ETX = 0x03  # end of text
ACK = 0x06  # acknowledge
CR  = 0x0D  # carriage return
LF  = 0x0A  # linefeed
BCC = 0x00  # Block check Character will contain the checksum immediately following the data packet


def format_time( timedelta ):
    """
    returns a pretty formatted string according to the size of the timedelta
    :param timediff: time delta given in seconds
    :return: returns a string
    """
    if timedelta > 1000.0:
        return "{:.2f} s".format(timedelta)
    elif timedelta > 1.0:
        return "{:.2f} s".format(timedelta)
    elif timedelta > 0.001:
        return "{:.2f} ms".format(timedelta*1000.0)
    elif timedelta > 0.000001:
        return "{:.2f} µs".format(timedelta*1000000.0)
    elif timedelta > 0.000000001:
        return "{:.2f} ns".format(timedelta * 1000000000.0)

        
def read_data_block_from_serial(the_serial, end_byte=0x0a):
    """
    This function reads some bytes from serial interface
    it returns an array of bytes if a timeout occurs or a given end byte is encountered
    and otherwise None if an error occurred
    :param the_serial: interface to read from
    :param end_byte: the indicator for end of data by source endpoint
    :returns the read data or None
    """
    response = bytes()
    try:
        while True:
            ch = the_serial.read()
            #logger.debug("Read {}".format(ch))
            if len(ch) == 0:
                break
            response += ch
            if ch == end_byte:
                break
            if (response[-1] == end_byte):
                break
    except Exception as e:
        logger.debug("Warning {0}".format(e))
        return None
    return response

def query( config ):
    """
    This function will
    1. open a serial communication line to the smartmeter
    2. sends a request for info
    3. parses the devices first (and maybe second) answer for capabilities of the device
    4. adjusts the speed of the communication accordingly
    5. reads out the block of OBIS information
    6. closes the serial communication
    
    config contains a dict with entries for        
    'serialport', 'device', 'timeout','use_checksum', 'reset_baudrate', 'no_waiting'
    
    return: a textblock with the data response from smartmeter
    """
    # for the performance of the serial read we need to save the actual time
    starttime = time.time()
    runtime = starttime
    result = None

    SerialPort = config.get('serialport')
    Device = config.get('device','')
    InitialBaudrate = config.get('speed', 300)
    QueryCode = config.get('querycode', '?')
    use_checksum = config.get('use_checksum', True)
    timeout = config.get('timeout', 3)

    StartChar = b'/'[0]

    Request_Message = b"/"+QueryCode.encode('ascii')+Device.encode('ascii')+b"!\r\n"

    
    # open the serial communication
    # about timeout: time tr between sending a request and an answer needs to be
    # 200ms < tr < 1500ms for protocol mode A or B
    # inter character time must be smaller than 1500 ms
    # The time between the reception of a message and the transmission of an answer is:
    # (20 ms) 200 ms = tr = 1 500 ms (see item 12) of 6.3.14).
    # If a response has not been received, the waiting time of the transmitting equipment after
    # transmission of the identification message, before it continues with the transmission, is:
    # 1 500 ms < tt = 2 200 ms
    # The time between two characters in a character sequence is:
    # ta < 1 500 ms
    wait_before_acknowledge = 0.4   # wait for 400 ms before sending the request to change baudrate
    wait_after_acknowledge = 0.4    # wait for 400 ms after sending acknowledge
    dlms_serial = None

    try:
        dlms_serial = serial.Serial(SerialPort,
                                    InitialBaudrate,
                                    bytesize=serial.SEVENBITS,
                                    parity=serial.PARITY_EVEN,
                                    stopbits=serial.STOPBITS_ONE,
                                    timeout=timeout)
        if not SerialPort == dlms_serial.name:
            logger.debug("Asked for {} as serial port, but really using now {}".format(
                SerialPort, dlms_serial.name))
    except FileNotFoundError as e:
        logger.error("Serial port '{0}' does not exist, please check your port".format( SerialPort))
        return
    except OSError as e:
        logger.error("Serial port '{0}' does not exist, please check the spelling".format(SerialPort))
        return
    except serial.SerialException as e:
        if dlms_serial is None:
            logger.error("Serial port '{0}' could not be opened".format(SerialPort))
        else:
            logger.error("Serial port '{0}' could be opened but somehow not accessed".format(SerialPort))
    except Exception as e:
        logger.error("Another unknown error occurred: '{0}'".format(e))
        return

    if not dlms_serial.isOpen():
        logger.error("Serial port '{0}' could not be opened with given parameters, maybe wrong baudrate?".format(SerialPort))
        return

    logger.debug("Time to open serial port {}: {}".format(SerialPort, format_time(time.time()- runtime)))
    runtime = time.time()

    try:
        #logger.debug("Reset input buffer from serial port '{}'".format(SerialPort))
        #dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
        logger.debug("Writing request message {} to serial port '{}'".format(Request_Message, SerialPort))
        dlms_serial.write(Request_Message)
        #logger.debug("Flushing buffer from serial port '{}'".format(SerialPort))
        #dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
    except Exception as e:
        logger.warning("Error {}".format(e))
        return

    logger.debug("Time to send first request to smartmeter: {}".format( format_time(time.time()- runtime)))

    # now get first response
    response = read_data_block_from_serial(dlms_serial)
    if response is None:
        logger.debug("No response received upon first request")
        return

    logger.debug("Time to receive an answer: {}".format(format_time(time.time()- runtime)))
    runtime = time.time()

    # We need to examine the read response here for an echo of the _Request_Message
    # some meters answer with an echo of the request Message
    if response == Request_Message:
        logger.debug("Request Message was echoed, need to read the identification message".format(response))
        # read Identification message if Request was echoed
        # now read the capabilities and type/brand line from Smartmeter
        # e.g. b'/LGZ5\\2ZMD3104407.B32\r\n'
        response = read_data_block_from_serial(dlms_serial)
    else:
        logger.debug("Request Message was not equal to response, treating as identification message".format(response))

    logger.debug("Time to get first identification message from smartmeter: "
                      "{}".format(format_time(time.time() - runtime)))
    runtime = time.time()

    Identification_Message = response
    logger.debug("Identification Message is {}".format(Identification_Message))

    # need at least 7 bytes:
    # 1 byte "/"
    # 3 bytes short Identification
    # 1 byte speed indication
    # 2 bytes CR LF
    if (len(Identification_Message) < 7):
        logger.warning("malformed identification message: '{}', abort query".format(Identification_Message))
        return

    if (Identification_Message[0] != StartChar):
        logger.warning("identification message '{}' does not start with '/',"
                            "abort query".format(Identification_Message))
        return

    manid = str(Identification_Message[1:4],'utf-8')
    manname = manufacturer_ids.get(manid,'unknown')
    logger.debug("The manufacturer for {} is {} (out of {} given manufacturers)".format(manid,manname,len(manufacturer_ids)))
    
    """
    Different smartmeters allow for different protocol modes. 
    The protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
    Some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
    However some meters specify a speed of 9600 Baud although they use protocol mode D (readonly)
    """
    Protocol_Mode = 'A'

    """
    The communication of the plugin always stays at the same speed, 
    Protocol indicator can be anything except for A-I, 0-9, /, ?
    """
    Baudrates_Protocol_Mode_A = 300
    Baudrates_Protocol_Mode_B = { 'A': 600, 'B': 1200, 'C': 2400, 'D': 4800, 'E': 9600, 'F': 19200,
                                  'G': "reserved", 'H': "reserved", 'I': "reserved" }
    Baudrates_Protocol_Mode_C = { '0': 300, '1': 600, '2': 1200, '3': 2400, '4': 4800, '5': 9600, '6': 19200,
                                  '7': "reserved", '8': "reserved", '9': "reserved"}

    # always '3' but it is always initiated by the metering device so it can't be encountered here
    Baudrates_Protocol_Mode_D = { '3' : 2400}
    Baudrates_Protocol_Mode_E = Baudrates_Protocol_Mode_C

    Baudrate_identification = chr(Identification_Message[4])
    if Baudrate_identification in Baudrates_Protocol_Mode_B:
        NewBaudrate = Baudrates_Protocol_Mode_B[Baudrate_identification]
        Protocol_Mode = 'B'
    elif Baudrate_identification in Baudrates_Protocol_Mode_C:
        NewBaudrate = Baudrates_Protocol_Mode_C[Baudrate_identification]
        Protocol_Mode = 'C' # could also be 'E' but it doesn't make any difference here
    else:
        NewBaudrate = Baudrates_Protocol_Mode_A
        Protocol_Mode = 'A'

    logger.debug("Baudrate id is '{}' thus Protocol Mode is {} and "
                      "max Baudrate available is {} Bd".format(Baudrate_identification, Protocol_Mode, NewBaudrate))

    if chr(Identification_Message[5]) == '\\':
        if chr(Identification_Message[6]) == '2':
            logger.debug("HDLC protocol could be used if it was implemented")
        else:
            logger.debug("Another protocol could probably be used if it was implemented")

    # for protocol C or E we now send an acknowledge and include the new baudrate parameter
    # maybe todo
    # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
    # read out a smartmeter with broken communication
    Action = b'0' # Data readout, possible are also b'1' for programming mode or some manufacturer specific
    
    Acknowledge = b'\x060'+ Baudrate_identification.encode() + Action + b'\r\n'

    if Protocol_Mode == 'C':
        # the speed change in communication is initiated from the reading device
        time.sleep(wait_before_acknowledge)
        logger.debug("Using protocol mode C, send acknowledge {} "
                          "and tell smartmeter to switch to {} Baud".format(Acknowledge, NewBaudrate))
        try:
            dlms_serial.write( Acknowledge )
        except Exception as e:
            logger.warning("Warning {0}".format(e))
            return
        time.sleep(wait_after_acknowledge)
        #dlms_serial.flush()
        #dlms_serial.reset_input_buffer()
        if (NewBaudrate != InitialBaudrate):
            # change request to set higher baudrate
            dlms_serial.baudrate = NewBaudrate

    elif Protocol_Mode == 'B':
        # the speed change in communication is initiated from the smartmeter device
        time.sleep(wait_before_acknowledge)
        logger.debug("Using protocol mode B, smartmeter and reader will switch to {} Baud".format(NewBaudrate))
        time.sleep(wait_after_acknowledge)
        #dlms_serial.flush()
        #dlms_serial.reset_input_buffer()
        if (NewBaudrate != InitialBaudrate):
            # change request to set higher baudrate
            dlms_serial.baudrate = NewBaudrate
    else:
        logger.debug("No change of readout baudrate, "
                          "smartmeter and reader will stay at {} Baud".format(NewBaudrate))

    # now read the huge data block with all the OBIS codes
    logger.debug("Reading OBIS data from smartmeter")
    response = read_data_block_from_serial( dlms_serial, None)

    dlms_serial.close()
    logger.debug("Time for reading OBIS data: {}".format(format_time(time.time()- runtime)))
    runtime = time.time()

    # Display performance of the serial communication
    logger.debug("Whole communication with "
                      "smartmeter took {}".format(format_time(time.time() - starttime)))

    if response.startswith(Acknowledge):
        logger.debug("Acknowledge echoed from smartmeter")
        response = response[len(Acknowledge):]
        
    if use_checksum:
        # data block in response may be capsuled within STX and ETX to provide error checking
        # thus the response will contain a sequence of
        # STX Datablock ! CR LF ETX BCC
        # which means we need at least 6 characters in response where Datablock is empty
        logger.debug("trying now to calculate a checksum")

        if response[0] == STX:
            logger.debug("STX found")
        else:
            logger.warning("STX not found in response='{}...'".format(' '.join(hex(i) for i in response[:10])))

        if response[-2] == ETX:
            logger.debug("ETX found")
        else:
            logger.warning("ETX not found in response='...{}'".format(' '.join(hex(i) for i in response[-11])))

        if (len(response) > 5) and (response[0] == STX) and (response[-2] == ETX):
            # perform checks (start with char after STX, end with ETX including, checksum matches last byte (BCC))
            BCC = response[-1]
            logger.debug("block check character BCC is {}".format(BCC))
            checksum = 0
            for i in response[1:-1]:
                checksum ^= i
            if checksum != BCC:
                logger.warning("checksum/protocol error: response={} "
                                    "checksum={}".format(' '.join(hex(i) for i in response[1:-1]), checksum))
                return
            else:
                logger.debug("checksum over data response was ok, data is valid")
        else:
            logger.warning("STX - ETX not found")
    else:
        logger.debug("checksum calculation")

    if len(response) > 5:
        result = str(response[1:-4], 'ascii')
        logger.debug("parsing OBIS codes took {}".format(format_time(time.time()- runtime)))
    else:
        logger.debug("Sorry response did not contain enough data for OBIS decode")

    suggested_cycle = (time.time() - starttime) + 10.0
    config['suggested_cycle'] = suggested_cycle
    logger.debug("the whole query took {}, suggested cycle thus is at least {}".format(format_time(time.time()- starttime), format_time(suggested_cycle)))


    return result

if __name__ == '__main__':
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for DLMS output')
    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/dlms0')    
    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0 )
    parser.add_argument('-s', '--speed', help='initial baudrate to start the communication with the smartmeter', type=int, default=300 )
    parser.add_argument('-d', '--device', help='give a device address to include in the query', default='' )
    parser.add_argument('-q', '--querycode', help='give query code, e.g. 2 instead of ?', default='?' )
    args = parser.parse_args()
        
    config = {}

    config['serialport'] = args.port
    config['device'] = args.device
    config['querycode'] = args.querycode
    config['speed'] = args.speed
    config['timeout'] = args.timeout
    
    if args.verbose:
        logging.getLogger().setLevel( logging.DEBUG )
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
        #formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)
    else:
        logging.getLogger().setLevel( logging.DEBUG )
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # just like print
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)


    logger.info("This is DLMS Plugin running in standalone mode")
    logger.info("==============================================")

    result = query(config)
    
    if result is None:
        logger.info("No results from query, maybe a problem with the serial port '{}' given ".format(config['serialport']))
        logger.info("==============================================")
    elif len(result) > 0:
        logger.info("These are the results of the query")
        logger.info("==============================================")
        logger.info(result)
        logger.info("==============================================")
    else:
        logger.info("The query did not get any results!")
        logger.info("Maybe the serial was occupied or there was an error")

