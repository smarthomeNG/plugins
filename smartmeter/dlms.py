#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 - 2022 Bernd Meiners              Bernd.Meiners@mail.de
#  Copyright 2024 -      Sebastian Helms         morg @ knx-user-forum.de
#########################################################################
#
#  DLMS plugin for SmartHomeNG
#
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#          https://smarthomeng.de
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
import time
import serial

from ruamel.yaml import YAML

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

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug(f"init standalone {__name__}")
else:
    logger = logging.getLogger(__name__)
    logger.debug(f"init plugin component {__name__}")

#
# protocol constants
#

SOH = 0x01  # start of header
STX = 0x02  # start of text
ETX = 0x03  # end of text
ACK = 0x06  # acknowledge
CR = 0x0D  # carriage return
LF = 0x0A  # linefeed
BCC = 0x00  # Block check Character will contain the checksum immediately following the data packet


#
# internal testing
#
TESTING = False
# TESTING = True

if TESTING:
    from .dlms_test import RESULT
    logger.error('DLMS testing mode enabled, no serial communication, no real results!')
else:
    RESULT = ''

manufacturer_ids = {}
exportfile = 'manufacturer.yaml'
try:
    with open(exportfile, 'r') as infile:
        y = YAML(typ='safe')
        manufacturer_ids = y.load(infile)
except Exception:
    pass


def discover(config: dict) -> bool:
    """ try to autodiscover SML protocol """
    # TODO: write this...
    return True


def format_time(timedelta: float) -> str:
    """
    returns a pretty formatted string according to the size of the timedelta
    :param timediff: time delta given in seconds
    :return: returns a string
    """
    if timedelta > 1000:
        return f"{timedelta:.2f} s"
    elif timedelta > 1:
        return f"{timedelta:.2f} s"
    elif timedelta > 1 / 10 ** 3:
        return f"{timedelta * 10 ** 3 :.2f} ms"
    elif timedelta > 1 / 10 ** 6:
        return f"{timedelta * 10 ** 6:.2f} µs"
    else:
        return f"{timedelta * 10 ** 9:.2f} ns"


def read_data_block_from_serial(the_serial: serial.Serial, end_byte: bytes = b'\n', start_byte: bytes = b'', max_read_time: int = -1) -> bytes:
    """
    This function reads some bytes from serial interface
    it returns an array of bytes if a timeout occurs or a given end byte is encountered
    and otherwise None if an error occurred

    If global var TESTING is True, only pre-stored data will be returned to test further processing!

    :param the_serial: interface to read from
    :param end_byte: the indicator for end of data, this will be included in response
    :param start_byte: the indicator for start of data, this will be included in response
    :param max_read_time:
    :returns the read data or None
    """
    if TESTING:
        return RESULT.encode()

    logger.debug("start to read data from serial device")
    response = bytes()
    starttime = time.time()
    start_found = False
    try:
        while True:
            ch = the_serial.read()
            # logger.debug(f"Read {ch}")
            runtime = time.time()
            if len(ch) == 0:
                break
            if start_byte != b'':
                if ch == start_byte:
                    response = bytes()
                    start_found = True
            response += ch
            if ch == end_byte:
                if start_byte is not None and not start_found:
                    response = bytes()
                    continue
                else:
                    break
            if (response[-1] == end_byte):
                break
            if max_read_time is not None:
                if runtime - starttime > max_read_time:
                    break
    except Exception as e:
        logger.debug(f"error occurred while reading data block from serial: {e} ")
        return b''
    logger.debug(f"finished reading data from serial device after {len(response)} bytes")
    return response


def split_header(readout: str, break_at_eod: bool = True) -> list:
    """if there is an empty line at second position within readout then seperate this"""
    has_header = False
    obis = []
    endofdata_count = 0
    for linecount, line in enumerate(readout.splitlines()):
        if linecount == 0 and line.startswith("/"):
            has_header = True
            continue

        # an empty line separates the header from the codes, it must be suppressed here
        if len(line) == 0 and linecount == 1 and has_header:
            continue

        # if there is an empty line other than directly after the header
        # it is very likely that there is a faulty obis readout.
        # It might be that checksum is disabled an thus no error could be catched
        if len(line) == 0:
            logger.error("incorrect format: empty line was encountered unexpectedly, aborting!")
            break

        # '!' as single OBIS code line means 'end of data'
        if line.startswith("!"):
            logger.debug("end of data reached")
            if endofdata_count:
                logger.debug(f"found {endofdata_count} end of data marker '!' in readout")
                if break_at_eod:    # omit the rest of data here
                    break
            endofdata_count += 1
        else:
            obis.append(line)
    return obis


def query(config) -> dict:
    """
    This function will
    1. open a serial communication line to the smartmeter
    2. sends a request for info
    3. parses the devices first (and maybe second) answer for capabilities of the device
    4. adjusts the speed of the communication accordingly
    5. reads out the block of OBIS information
    6. closes the serial communication
    7. strip header lines from returned data
    8. extract obis data and format return dict

    config contains a dict with entries for
    'serial_port', 'device' and a sub-dict 'dlms' with entries for
    'querycode', 'baudrate', 'baudrate_fix', 'timeout', 'onlylisten', 'use_checksum'

    return: a dict with the response data formatted as follows:
        {
            'readout': <full readout lines>,
            '<obis1>': [{'value': <val0>, (optional) 'unit': '<unit0>'}, {'value': <val1>', 'unit': '<unit1>'}, ...],
            '<obis2>': [...],
            ...
        }

    The obis lines contain at least one value (index 0), possibly with a unit, and possibly more values in analogous format
    """

    # TODO: modularize; find components to reuse with SML?

    #
    # initialize module
    #

    # for the performance of the serial read we need to save the current time
    starttime = time.time()
    runtime = starttime
    result = None

    try:
        serial_port = config['serial_port']
        timeout = config['timeout']

        device = config['dlms']['device']
        initial_baudrate = config['dlms']['baudrate_min']
        # baudrate_fix = config['dlms']['baudrate_fix']
        query_code = config['dlms']['querycode']
        use_checksum = config['dlms']['use_checksum']
        only_listen = config['dlms'].get('onlylisten', False)    # just for the case that smartmeter transmits data without a query first
    except (KeyError, AttributeError) as e:
        logger.warning(f'configuration {config} is missing elements: {e}')
        return {}

    logger.debug(f"config='{config}'")
    start_char = b'/'

    request_message = b"/" + query_code.encode('ascii') + device.encode('ascii') + b"!\r\n"

    #
    # open the serial communication
    #

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
        dlms_serial = serial.Serial(serial_port,
                                    initial_baudrate,
                                    bytesize=serial.SEVENBITS,
                                    parity=serial.PARITY_EVEN,
                                    stopbits=serial.STOPBITS_ONE,
                                    timeout=timeout)
        if not serial_port == dlms_serial.name:
            logger.debug(f"Asked for {serial_port} as serial port, but really using now {dlms_serial.name}")

    except FileNotFoundError:
        logger.error(f"Serial port '{serial_port}' does not exist, please check your port")
        return {}
    except serial.SerialException:
        if dlms_serial is None:
            logger.error(f"Serial port '{serial_port}' could not be opened")
        else:
            logger.error(f"Serial port '{serial_port}' could be opened but somehow not accessed")
    except OSError:
        logger.error(f"Serial port '{serial_port}' does not exist, please check the spelling")
        return {}
    except Exception as e:
        logger.error(f"unforeseen error occurred: '{e}'")
        return {}

    if dlms_serial is None:
        # this should not happen...
        logger.error("unforeseen error occurred, serial object was not initialized.")
        return {}

    if not dlms_serial.is_open:
        logger.error(f"serial port '{serial_port}' could not be opened with given parameters, maybe wrong baudrate?")
        return {}

    logger.debug(f"time to open serial port {serial_port}: {format_time(time.time() - runtime)}")
    runtime = time.time()

    acknowledge = b''   # preset empty answer

    if not only_listen:
        # TODO: check/implement later
        response = b''

        # start a dialog with smartmeter
        try:
            # TODO: is this needed? when?
            # logger.debug(f"Reset input buffer from serial port '{serial_port}'")
            # dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
            logger.debug(f"writing request message {request_message} to serial port '{serial_port}'")
            dlms_serial.write(request_message)
            # TODO: same as above
            # logger.debug(f"Flushing buffer from serial port '{serial_port}'")
            # dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
        except Exception as e:
            logger.warning(f"error on serial write: {e}")
            return {}

        logger.debug(f"time to send first request to smartmeter: {format_time(time.time() - runtime)}")

        # now get first response
        response = read_data_block_from_serial(dlms_serial)
        if not response:
            logger.debug("no response received upon first request")
            return {}

        logger.debug(f"time to receive an answer: {format_time(time.time() - runtime)}")
        runtime = time.time()

        # We need to examine the read response here for an echo of the _Request_Message
        # some meters answer with an echo of the request Message
        if response == request_message:
            logger.debug("request message was echoed, need to read the identification message")
            # now read the capabilities and type/brand line from Smartmeter
            # e.g. b'/LGZ5\\2ZMD3104407.B32\r\n'
            response = read_data_block_from_serial(dlms_serial)
        else:
            logger.debug("request message was not equal to response, treating as identification message")

        logger.debug(f"time to get first identification message from smartmeter: {format_time(time.time() - runtime)}")
        runtime = time.time()

        identification_message = response
        logger.debug(f"identification message is {identification_message}")

        # need at least 7 bytes:
        # 1 byte "/"
        # 3 bytes short Identification
        # 1 byte speed indication
        # 2 bytes CR LF
        if len(identification_message) < 7:
            logger.warning(f"malformed identification message: '{identification_message}', abort query")
            return {}

        if (identification_message[0] != start_char):
            logger.warning(f"identification message '{identification_message}' does not start with '/', abort query")
            return {}

        manid = str(identification_message[1:4], 'utf-8')
        manname = manufacturer_ids.get(manid, 'unknown')
        logger.debug(f"manufacturer for {manid} is {manname} ({len(manufacturer_ids)} manufacturers known)")

        # Different smartmeters allow for different protocol modes.
        # The protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
        # Some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
        # However some meters specify a speed of 9600 Baud although they use protocol mode D (readonly)
        #
        # protocol_mode = 'A'
        #
        # The communication of the plugin always stays at the same speed,
        # Protocol indicator can be anything except for A-I, 0-9, /, ?
        #
        baudrates = {
            # mode A
            '': (300, 'A'),
            # mode B
            'A': (600, 'B'),
            'B': (1200, 'B'),
            'C': (2400, 'B'),
            'D': (4800, 'B'),
            'E': (9600, 'B'),
            'F': (19200, 'B'),
            # mode C & E
            '0': (300, 'C'),
            '1': (600, 'C'),
            '2': (1200, 'C'),
            '3': (2400, 'C'),
            '4': (4800, 'C'),
            '5': (9600, 'C'),
            '6': (19200, 'C'),
        }

        baudrate_id = chr(identification_message[4])
        if baudrate_id not in baudrates:
            baudrate_id = ''
        new_baudrate, protocol_mode = baudrates[baudrate_id]

        logger.debug(f"baudrate id is '{baudrate_id}' thus protocol mode is {protocol_mode} and suggested Baudrate is {new_baudrate} Bd")

        if chr(identification_message[5]) == '\\':
            if chr(identification_message[6]) == '2':
                logger.debug("HDLC protocol could be used if it was implemented")
            else:
                logger.debug(f"another protocol could probably be used if it was implemented, id is {identification_message[6]}")

        # for protocol C or E we now send an acknowledge and include the new baudrate parameter
        # maybe todo
        # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
        # read out a smartmeter with broken communication
        action = b'0'  # Data readout, possible are also b'1' for programming mode or some manufacturer specific
        acknowledge = b'\x060' + baudrate_id.encode() + action + b'\r\n'

        if protocol_mode == 'C':
            # the speed change in communication is initiated from the reading device
            time.sleep(wait_before_acknowledge)
            logger.debug(f"using protocol mode C, send acknowledge {acknowledge} and tell smartmeter to switch to {new_baudrate} baud")
            try:
                dlms_serial.write(acknowledge)
            except Exception as e:
                logger.warning(f"error on sending baudrate change: {e}")
                return {}
            time.sleep(wait_after_acknowledge)
            # dlms_serial.flush()
            # dlms_serial.reset_input_buffer()
            if (new_baudrate != initial_baudrate):
                # change request to set higher baudrate
                dlms_serial.baudrate = new_baudrate

        elif protocol_mode == 'B':
            # the speed change in communication is initiated from the smartmeter device
            time.sleep(wait_before_acknowledge)
            logger.debug(f"using protocol mode B, smartmeter and reader will switch to {new_baudrate} baud")
            time.sleep(wait_after_acknowledge)
            # dlms_serial.flush()
            # dlms_serial.reset_input_buffer()
            if (new_baudrate != initial_baudrate):
                # change request to set higher baudrate
                dlms_serial.baudrate = new_baudrate
        else:
            logger.debug(f"no change of readout baudrate, smartmeter and reader will stay at {new_baudrate} baud")

        # now read the huge data block with all the OBIS codes
        logger.debug("Reading OBIS data from smartmeter")
        response = read_data_block_from_serial(dlms_serial, b'')
    else:
        # only listen mode, starts with / and last char is !
        # data will be in between those two
        response = read_data_block_from_serial(dlms_serial, b'!', b'/')

        identification_message = str(response, 'utf-8').splitlines()[0]

        manid = identification_message[1:4]
        manname = manufacturer_ids.get(manid, 'unknown')
        logger.debug(f"manufacturer for {manid} is {manname} (out of {len(manufacturer_ids)} given manufacturers)")

    try:
        dlms_serial.close()
    except Exception:
        pass

    logger.debug(f"time for reading OBIS data: {format_time(time.time() - runtime)}")
    runtime = time.time()

    # Display performance of the serial communication
    logger.debug(f"whole communication with smartmeter took {format_time(time.time() - starttime)}")

    if response.startswith(acknowledge):
        if not only_listen:
            logger.debug("acknowledge echoed from smartmeter")
            response = response[len(acknowledge):]

    if use_checksum:
        # data block in response may be capsuled within STX and ETX to provide error checking
        # thus the response will contain a sequence of
        # STX Datablock ! CR LF ETX BCC
        # which means we need at least 6 characters in response where Datablock is empty
        logger.debug("trying now to calculate a checksum")

        if response[0] == STX:
            logger.debug("STX found")
        else:
            logger.warning(f"STX not found in response='{' '.join(hex(i) for i in response[:10])}...'")

        if response[-2] == ETX:
            logger.debug("ETX found")
        else:
            logger.warning(f"ETX not found in response='...{' '.join(hex(i) for i in response[-11:])}'")

        if (len(response) > 5) and (response[0] == STX) and (response[-2] == ETX):
            # perform checks (start with char after STX, end with ETX including, checksum matches last byte (BCC))
            BCC = response[-1]
            logger.debug(f"block check character BCC is {BCC}")
            checksum = 0
            for i in response[1:-1]:
                checksum ^= i
            if checksum != BCC:
                logger.warning(f"checksum/protocol error: response={' '.join(hex(i) for i in response[1:-1])} "
                                    "checksum={checksum}")
                return
            else:
                logger.debug("checksum over data response was ok, data is valid")
        else:
            logger.warning("STX - ETX not found")
    else:
        logger.debug("checksum calculation skipped")

    if not only_listen:
        if len(response) > 5:
            result = str(response[1:-4], 'ascii')
            logger.debug(f"parsing OBIS codes took {format_time(time.time() - runtime)}")
        else:
            logger.debug("response did not contain enough data for OBIS decode")
    else:
        result = str(response, 'ascii')

    suggested_cycle = (time.time() - starttime) + 10.0
    config['suggested_cycle'] = suggested_cycle
    logger.debug(f"the whole query took {format_time(time.time() - starttime)}, suggested cycle thus is at least {format_time(suggested_cycle)}")

    if not result:
        return {}

    rdict = {}  # {'readout': result}

# TODO : adjust

    _, obis = split_header(result)

    try:
        for line in obis:
            # Now check if we can split between values and OBIS code
            arguments = line.split('(')
            if len(arguments) == 1:
                # no values found at all; that seems to be a wrong OBIS code line then
                arguments = arguments[0]
                values = ""
                logger.warning(f"OBIS code line without data item: {line}")
            else:
                # ok, found some values to the right, lets isolate them
                values = arguments[1:]
                obis_code = arguments[0]

                temp_values = values
                values = []
                for s in temp_values:
                    s = s.replace(')', '')
                    if len(s) > 0:
                        # we now should have a list with values that may contain a number
                        # separated from a unit by a '*' or a date
                        # so see, if there is an '*' within
                        vu = s.split('*')
                        if len(vu) > 2:
                            logger.error(f"too many '*' found in '{s}' of '{line}'")
                        elif len(vu) == 2:
                            # just a value and a unit
                            v = vu[0]
                            u = vu[1]
                            values.append({'value': v, 'unit': u})
                        else:
                            # just a value, no unit
                            v = vu[0]
                            values.append({'value': v})
                # uncomment the following line to check the generation of the values dictionary
                logger.debug(f"{line:40} ---> {values}")
                rdict[obis_code] = values
        logger.debug("finished processing lines")
    except Exception as e:
        logger.debug(f"error while extracting data: '{e}'")

    return rdict


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for DLMS output',
                                     usage='use "%(prog)s --help" for more information',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/dlms0')
    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0)
    parser.add_argument('-b', '--baudrate', help='initial baudrate to start the communication with the smartmeter', type=int, default=300)
    parser.add_argument('-d', '--device', help='give a device address to include in the query', default='')
    parser.add_argument('-q', '--querycode', help='define alternative query code\ndefault query code is ?\nsome smartmeters provide additional information when sending\nan alternative query code, e.g. 2 instead of ?', default='?')
    parser.add_argument('-l', '--onlylisten', help='only listen to serial, no active query', action='store_true')
    parser.add_argument('-f', '--baudrate_fix', help='keep baudrate speed fixed', action='store_false')
    parser.add_argument('-c', '--nochecksum', help='don\'t use a checksum', action='store_false')

    args = parser.parse_args()

    config = {}

    config['serial_port'] = args.port
    config['timeout'] = args.timeout
    config['dlms'] = {}
    config['dlms']['querycode'] = args.querycode
    config['dlms']['baudrate_min'] = args.baudrate
    config['dlms']['baudrate_fix'] = args.baudrate_fix
    config['dlms']['onlylisten'] = args.onlylisten
    config['dlms']['use_checksum'] = args.nochecksum
    config['dlms']['device'] = args.device

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
        # formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)
    else:
        logging.getLogger().setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # just like print
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)

    logger.info("This is Smartmeter Plugin, DLMS module, running in standalone mode")
    logger.info("==================================================================")

    result = query(config)

    if result is None:
        logger.info(f"No results from query, maybe a problem with the serial port '{config['serial_port']}' given.")
    elif len(result) > 0:
        logger.info("These are the results of the query:")
        logger.info(result)
    else:
        logger.info("The query did not get any results. Maybe the serial port was occupied or there was an error.")
