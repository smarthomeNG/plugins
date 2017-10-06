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

if __name__ == '__main__':
    # just needed for standalone mode
    class SmartPlugin():
        pass
    import os
    import sys
    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)    
    from lib.utils import Utils
else:
    # just needed for plugin mode
    from lib.model.smartplugin import SmartPlugin
    from lib.utils import Utils

import time
import serial
import re
from threading import Semaphore

"""
This module implements the query of a smartmeter using the DLMS protocol.


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

class DLMS(SmartPlugin):
    PLUGIN_VERSION = "1.2.6"
    ALLOW_MULTIINSTANCE = False
    """
    This class provides a Plugin for SmarthomeNG.py which reads out a smartmeter.
    The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB
    It is possible to use the Plugin as a standalone program to check out the communication 
    prior to use it in SmarthomeNG.py
    
    The tag 'dlms_obis_code' identifies the items which are to be updated from the plugin
    """

    # tags this plugin handles
    ITEM_TAG = [
        'dlms_obis_code',           # a single code in form of '1-1:1.8.1'
        'dlms_obis_readout']        # complete readout from smartmeter, if you want to examine codes yourself in a logic

    def __init__(self, smarthome, serialport, baudrate="auto", update_cycle="60", instance = 0, device_address = b'', timeout = 2, use_checksum = True, reset_baudrate = True, no_waiting = False ):
        """
        Initializes the DLMS plugin
        :param serialport: 
        """
        self.logger = logging.getLogger(__name__)
        self.logger.debug("init dlms")

        self._sh = smarthome                                    # save a reference to the smarthome object
        self._serialport = serialport
        self._update_cycle = int(update_cycle)                  # the frequency in seconds how often the device should be accessed
        self._instance = instance                               # the instance of the plugin for questioning multiple smartmeter
        self._device_address = device_address                   # there is a possibility of using a named device.
                                                                # normally this will be empty since only one meter will be attached
                                                                # to one serial interface but the standard allows for it and we honor that.
        self.timeout = timeout
        self._sema = Semaphore()                                # implement a semaphore to avoid multiple calls of the query function
        self._min_cycle_time = 0                                # we measure the time for the value query and add some security value of 10 seconds

        self.dlms_obis_code_items = []                          # this is a list of items to be updated
        self.dlms_obis_codes = []                               # this is a list of codes that are to be parsed

        self.dlms_obis_readout_items = []                       # this is a list of items that receive the full readout

 		# obsolete parameters, kept for compatability with previous versions
        self._use_checksum = Utils.to_bool(use_checksum)
        self._reset_baudrate = Utils.to_bool(reset_baudrate)
        self._no_waiting = Utils.to_bool(no_waiting)


        self.logger.debug("Instance {} of DLMS configured to use serialport '{}' with update cycle {} seconds".format( self._instance if self._instance else 0,self._serialport, self._update_cycle))
        if __name__ == '__main__':
            self.alive = True
        else:
            self.logger.debug("init done")

    def run(self):
        """
        This is called when the plugins thread is about to run
        """
        self.alive = True
        if __name__ != '__main__':
            # if we are not running in console mode, we add a scheduler to let it call the _update_values_callback function
            self._sh.scheduler.add('DLMS', self._update_values_callback, prio=5, cycle=self._update_cycle)
        self.logger.debug("run dlms")

    def stop(self):
        """
        This is called when the plugins thread is about to stop
        """
        self.alive = False
        if __name__ != '__main__':
            # clean up means to remove the scheduler for the update function
            self._sh.scheduler.remove('DLMS')
        self.logger.debug("stop dlms")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, self.ITEM_TAG[0]):
            self.dlms_obis_code_items.append(item)
            self.logger.debug("Item '{}' has Attribute '{}' so it is added to the list of items "
                              "to receive OBIS Code Values".format(item, self.ITEM_TAG[0]))
            obis_code = self.get_iattr_value(item.conf, self.ITEM_TAG[0])
            if isinstance(obis_code, list):
                obis_code = obis_code[0]
            self.dlms_obis_codes.append( obis_code )
            self.logger.debug("The OBIS Code '{}' is added to the list of codes to inspect".format(obis_code))
        elif self.has_iattr(item.conf, self.ITEM_TAG[1]):
            self.dlms_obis_readout_items.append(item)
            self.logger.debug("Item '{}' has Attribute '{}' so it is added to the list of items "
                              "to receive full OBIS Code readout".format(item, self.ITEM_TAG[1]))

    def format_time(self, timedelta ):
        """
        function returns a pretty formatted string according to the size of the timedelta
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

    def _read_data_block_from_serial(self, the_serial, end_byte=0x0a):
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
            while self.alive:
                ch = the_serial.read()
                if len(ch) == 0:
                    break
                response += ch
                if ch == end_byte:
                    break
                if (response[-1] == end_byte):
                    break
        except Exception as e:
            self.logger.debug("Warning {0}".format(e))
            return None
        return response

    def _update_values_callback(self):
        """
        This function aquires a semphore, queries the serial interface and upon successful data readout
        it calls the update function
        If it is not possible it passes on, issuing a warning about increasing the query interval
        """
        if self._sema.acquire(blocking=False):
            try:
                result = self._query_smartmeter()
                if len(result) > 5:
                    self._update_values( result )
                else:
                    self.logger.error( "no results from smartmeter query received" )
            except Exception as e:
                    self.logger.debug("Uncaught Exception {0} occurred, please inform plugin author!".format(e))
            finally:
                    self._sema.release()
        else:
            self.logger.warning("update is alrady running, maybe it really takes very long or you should use longer "
                                "query interval time")

    def _query_smartmeter(self):
        """
        This function will
        1. open a serial communication line to the smartmeter
        2. sends a request for info
        3. parses the devices first (and maybe second) answer for capabilities of the device
        4. adjusts the speed of the communication accordingly
        5. reads out the block of OBIS information
        6. closes the serial communication
        return: a textblock with the data response from smartmeter
        """
        # for the performance of the serial read we need to save the actual time
        starttime = time.time()
        runtime = starttime
        result = None

        StartChar = b'/'[0]
        InitialBaudrate = 300
        Request_Message = b"/?"+self._device_address+b"!\r\n"

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
            dlms_serial = serial.Serial(self._serialport,
                                        InitialBaudrate,
                                        bytesize=serial.SEVENBITS,
                                        parity=serial.PARITY_EVEN,
                                        timeout=self.timeout)
            if not self._serialport == dlms_serial.name:
                self.logger.debug("Asked for {} as serial port, but really using now {}".format(
                    self._serialport, dlms_serial.name))
        except FileNotFoundError as e:
            self.logger.error("Serial port '{0}' does not exist, please check your port".format( self._serialport))
            return
        except OSError as e:
            self.logger.error("Serial port '{0}' does not exist, please check the spelling".format(self._serialport))
            return
        except serial.SerialException as e:
            if dlms_serial is None:
                self.logger.error("Serial port '{0}' could not be opened".format(self._serialport))
            else:
                self.logger.error("Serial port '{0}' could be opened but somehow not accessed".format(self._serialport))
        except Exception as e:
            self.logger.error("Another unknown error occurred: '{0}'".format(e))
            return

        if not dlms_serial.isOpen():
            self.logger.error("Serial port '{0}' could not be opened with given parameters, maybe wrong baudrate?".format(self._serialport))
            return

        self.logger.debug("Time to open serial port {}: {}".format(self._serialport,self.format_time(time.time()- runtime)))
        runtime = time.time()

        try:
            self.logger.debug("Reset input buffer from serial port '{}'".format(self._serialport))
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
            self.logger.debug("Writing request message {} to serial port '{}'".format(Request_Message, self._serialport))
            dlms_serial.write(Request_Message)
            self.logger.debug("Flushing buffer from serial port '{}'".format(self._serialport))
            dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
            self.logger.debug("Reset input buffer from serial port '{}'".format(self._serialport))
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
        except Exception as e:
            self.logger.warning("Error {}".format(e))
            return

        self.logger.debug("Time to send first request to smartmeter: {}".format(self.format_time(time.time()- runtime)))

        # now get first response
        response = self._read_data_block_from_serial(dlms_serial)
        if response is None:
            return

        self.logger.debug("Time to receive an answer: {}".format(self.format_time(time.time()- runtime)))
        runtime = time.time()

        # We need to examine the read response here for an echo of the _Request_Message
        # some meters answer if appropriate meter is available for answering with an echo of the request Message
        if response == Request_Message:
            self.logger.debug("Request Message was echoed, need to read the identification message".format(response))
            # read Identification message if Request was echoed
            # now read the capabilities and type/brand line from Smartmeter
            # e.g. b'/LGZ5\\2ZMD3104407.B32\r\n'
            response = self._read_data_block_from_serial(dlms_serial)
        else:
            self.logger.debug("Request Message was echoed, need to read the identification message".format(response))

        self.logger.debug("Time to get first identification message from smartmeter: "
                          "{}".format(self.format_time(time.time() - runtime)))
        runtime = time.time()

        Identification_Message = response
        self.logger.debug("Identification Message is {}".format(Identification_Message))

        if (len(Identification_Message) < 5):
            self.logger.warning("malformed identification message {}".format(Identification_Message))
            return

        if (Identification_Message[0] != StartChar):
            self.logger.warning("identification message {} does not start with '/',"
                                "aborting".format(Identification_Message[0]))
            return

        """
        Different smartmeters allow for different protocol modes. 
        The protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
        Some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
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
        #Baudrates_Protocol_Mode_E is the same as Mode_C

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

        self.logger.debug("Baudrate id is '{}' thus Protocol Mode is {} and "
                          "max Baudrate available is {} Bd".format(Baudrate_identification, Protocol_Mode, NewBaudrate))

        # for protocol C or E we now send an acknowledge and include the new baudrate parameter
        # maybe todo
        # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
        # read out a smartmeter with broken communication
        Acknowledge = b'\x060' + Baudrate_identification.encode() + b'0\r\n'

        if Protocol_Mode == 'C':
            # the speed change in communication is initiated from the reading device
            time.sleep(wait_before_acknowledge)
            self.logger.debug("Using protocol mode C, send acknowledge {} "
                              "and tell smartmeter to switch to {} Baud".format(Acknowledge, NewBaudrate))
            try:
                dlms_serial.write( Acknowledge )
            except Exception as e:
                self.logger.warning("Warning {0}".format(e))
                return
            time.sleep(wait_after_acknowledge)
            dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
            if (NewBaudrate != InitialBaudrate):
                # change request to set higher baudrate
                dlms_serial.baudrate = NewBaudrate

        elif Protocol_Mode == 'B':
            # the speed change in communication is initiated from the smartmeter device
            time.sleep(wait_before_acknowledge)
            self.logger.debug("Using protocol mode C, smartmeter and reader will switch to {} Baud".format(NewBaudrate))
            time.sleep(wait_after_acknowledge)
            dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()
            if (NewBaudrate != InitialBaudrate):
                # change request to set higher baudrate
                dlms_serial.baudrate = NewBaudrate
        else:
            self.logger.debug("No change of readout baudrate, "
                              "smartmeter and reader will stay at {} Baud".format(NewBaudrate))

        # now read the huge data block with all the OBIS codes
        self.logger.debug("Reading OBIS data from smartmeter")
        response = self._read_data_block_from_serial( dlms_serial, None)

        dlms_serial.close()
        self.logger.debug("Time for reading OBIS data: {}".format(self.format_time(time.time()- runtime)))
        runtime = time.time()

        # Display performance of the serial communication
        self.logger.debug("Whole communication with "
                          "smartmeter took {}".format(self.format_time(time.time() - starttime)))

        if self._use_checksum:
            # data block in repsonse may be capsuled within STX and ETX to provide error checking
            # thus the response will contain a sequence of
            # STX Datablock ! CR LF ETX BCC
            # which means we need at least 6 characters in response where Datablock is empty

            STX = 0x02
            ETX = 0x03
            BCC = 0x00  # Block check Character

            if (len(response) > 5) and (response[0] == STX) or (response[-2] == ETX):
                # perform checks (start with STX, end with ETX, checksum match)
                self.logger.debug("calculating checksum over data response")
                checksum = 0
                for i in response[1:]:
                    checksum ^= i
                if checksum != BCC:
                    self.logger.warning("checksum/protocol error: response={} "
                                        "checksum={}".format(' '.join(hex(i) for i in response), checksum))
                    return
                else:
                    self.logger.debug("checksum over data response was ok")
            else:
                self.logger.warning("STX - ETX not found")

        if len(response) > 5:
            result = str(response[1:-4], 'ascii')
            self.logger.debug("parsing OBIS codes took {}".format(self.format_time(time.time()- runtime)))
            self.logger.debug("the whole query took {}".format(self.format_time(time.time()- starttime)))
        else:
            self.logger.debug("Sorry response did not caontain enough data for OBIS decode")

        suggested_cycle = (time.time() - starttime) + 10.0

        if (time.time() - runtime) > self._update_cycle and self._min_cycle_time < self._update_cycle:
            # if query takes longer than the given update_cycle then make a suggestion for an adjustment
            self.logger.warning("the update cycle should be "
                                "increased to at least {}".format(self.format_time(suggested_cycle)))

        if suggested_cycle > self._min_cycle_time:
            self._min_cycle_time = suggested_cycle

        return result

    def _to_datetime_ZST10(self, text):
        """
        this function converts a string of form "YYMMDDhhmm" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 10:
            self.logger.error("too few characters for date/time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date/time code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            hour = int(text[6:8])
            minute = int(text[8:10])
            return datetime.datetime(year,month,day,hour,minute,0)

    def _to_datetime_ZST12(self, text):
        """
        this function converts a string of form "YYMMDDhhmmss" into a datetime object
        :param text: string to convert
        :return: a datetime object upon success or None if error found by malformed string
        """
        if len(text) != 12:
            self.logger.error("too few characters for date/time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date/time code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            hour = int(text[6:8])
            minute = int(text[8:10])
            second = int(text[10:12])
            return datetime.datetime(year,month,day,hour,minute,second)

    def _to_date_D6(self, text):
        """
        this function converts a string of form "YYMMDD" into a datetime.date object
        :param text: string to convert
        :return: a datetime.date object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            self.logger.error("too few characters for date code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for date code from OBIS")
            return None
        else:
            year = int(text[0:2])+2000
            month = int(text[2:4])
            day = int(text[4:6])
            return datetime.date(year,month,day)

    def _to_time_Z4(self, text):
        """
        this function converts a string of form "hhmm" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 4:
            self.logger.error("too few characters for time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for time code from OBIS")
            return None
        else:
            hour = int(text[0:2])
            minute = int(text[2:4])
            return datetime.time(hour,minute)

    def _to_time_Z6(self, text):
        """
        this function converts a string of form "hhmmss" into a datetime.time object
        :param text: string to convert
        :return: a datetime.time object upon success or None if error found by malformed string
        """
        if len(text) != 6:
            self.logger.error("too few characters for time code from OBIS")
            return None
        if not text.isdigit():
            self.logger.error("only digits allowed for time code from OBIS")
            return None
        else:
            hour = int(text[0:2])
            minute = int(text[2:4])
            second = int(text[4:6])
            return datetime.time(hour,minute,second)

    def _convert_value( self, v, converter = 'str'):
        """
        This function converts the OBIS value to a user chosen value
        :param v: the value to convert from given as string
        :param converter: should contain one of ['str','float', 'int','ZST10', 'ZST12', 'D6', 'Z6', 'Z4', 'num']
        :return: after successful conversion the value in converted form
        """

        if converter == 'str' or len(converter) == 0:
            return v

        if converter == 'float':
            try:
                return float(v)
            except ValueError:
                self.logger.error("Could not convert from '{}' to a float".format(v))
                return None

        if converter == 'int':
            try:
                return int(v)
            except ValueError:
                self.logger.error("Could not convert from '{}' to an integer".format(v))
                return None

        if converter == 'ZST10':
            if len(v) == 10 and v.isdigit():
                # this is a date!
                v = self._to_datetime_ZST10(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'ZST12':
            if len(v) == 12 and v.isdigit():
                # this is a date!
                v = self._to_datetime_ZST12(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'D6':
            if len(v) == 6 and v.isdigit():
                # this is a date!
                v = self._to_date_D6(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'Z6':
            if len(v) == 6 and v.isdigit():
                # this is a date!
                v = self._to_time_Z6(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'Z4':
            if len(v) == 4 and v.isdigit():
                # this is a date!
                v = self._to_time_Z4(v)
                return v
            else:
                self.logger.error("Could not convert from '{}' to a Datetime".format(v))

        if converter == 'num':
            try:
                return int(v)
            except ValueError:
                pass

            try:
                return float(v)
            except ValueError:
                pass

        return v

    def _update_dlms_obis_readout_items(self, textblock):
        """
        Sets all items with attribute to the full readout text given in textblock
        :param textblock: the result of the latest query
        """
        if __name__ != '__main__':
            for item in self.dlms_obis_readout_items:
                item(textblock, 'DLMS')


    def _is_obis_code_wanted( self, code):
        """
        this stub function detects whether code is in the list of user defined OBIS codes to scan for
        :param code:
        :return: returns true if code is in user defined OBIS codes to scan for
        """
        if __name__ == '__main__':
            return True
        elif code in self.dlms_obis_codes:
            #self.logger.debug("Wanted OBIS Code found: '{}'".format(code))
            return True
        #self.logger.debug("OBIS Code '{}' is not interesting...".format(code))
        return False


    def _update_items( self, Code, Values):
        """
        this function takes the OBIS Code as text and accepts a list of dictionaries with Values
        :param Code: OBIS Code
        :param Values: list of dictionaries with Value / Unit entries
        """
        if __name__ != '__main__':
            for item in self.dlms_obis_code_items:
                if self.has_iattr(item.conf, self.ITEM_TAG[0]):
                    attribute = self.get_iattr_value(item.conf, self.ITEM_TAG[0])
                    if not isinstance(attribute, list):
                        self.logger.warning("Attribute '{}' is a single argument, not a list".format(attribute))
                        attribute = [attribute]
                    obis_code = attribute[0]
                    if obis_code == Code:
                        #todo: error handling for key errors
                        Index = int(attribute[1]) if len(attribute)>1 else 0
                        Key = attribute[2] if len(attribute)>2 else 'Value'
                        if not Key in ['Value', 'Unit']: Key = 'Value'
                        Converter = attribute[3] if len(attribute)>3 else ''
                        try:
                            itemValue = Values[Index][Key]
                            itemValue = self._convert_value(itemValue, Converter )
                            item(itemValue, 'DLMS')
                            self.logger.debug("Set item {} for Obis Code {} to Value {}".format(item, Code, itemValue))
                        except IndexError as e:
                            self.logger.warning("Index Error '{}' while setting item {} for Obis Code {} to Value "
                                                "with Index '{}' in '{}'".format(str(e), item, Code, Index, Values))
                        except KeyError as e:
                            self.logger.warning("Key error '{}' while setting item {} for Obis Code {} to "
                                                "Key '{}' in '{}'".format(str(e), item, Code, Key, Values[Index]))

    def _update_values(self, readout):
        """
        Takes the readout from smart meter with one OBIS code per line, 
        splits up the line into OBIS code itself and all values behind that will start encapsulated in parentheses

        If the OBIS code was included in one of the items attributes then the values will be parsed and assigned
        to the corresponding item.
        
        :param readout: readout from smart meter with one OBIS code per line
        :return: nothing
        """

        # update all items marked for a full readout
        self._update_dlms_obis_readout_items(readout)

        for line in re.split('\r\n', readout):
            # '!' as single OBIS code line means 'end of data'
            if line.startswith("!"):
                self.logger.debug("No more data available to read")
                break

            # if there is an empty line it is very likely that an error occurred.
            # It might be that checksum is disabled an thus no error could be catched
            if len(line) == 0:
                self.logger.error("An empty line was encountered!")
                break

            # Now check if we can split between values and OBIS code
            arguments = line.split('(')
            if len(arguments)==1:
                # no values found at all; that seems to be a wrong OBIS code line then
                arguments = arguments[0]
                values = ""
                self.logger.warning("Any line with OBIS Code should have at least one data item")
            else:
                # ok, found some values to the right, lets isolate them
                values = arguments[1:]
                obis_code = arguments[0]

                if self._is_obis_code_wanted(obis_code):
                    TempValues = values
                    values = []
                    for s in TempValues:
                        s = s.replace(')','')
                        if len(s) > 0:
                            # we now should have a list with values that may contain a number
                            # separated from a unit by a '*' or a date
                            # so see, if there is an '*' within
                            vu = s.split('*')
                            if len(vu) > 2:
                                self.logger.error("Too many entries found in '{}' of '{}'".format(s, line))
                            elif len(vu) == 2:
                                # just a value and a unit
                                v = vu[0]
                                u = vu[1]
                                values.append( { 'Value': v, 'Unit': u} )
                            else:
                                # just a value, no unit
                                v = vu[0]
                                values.append( { 'Value': v } )
                    # uncomment the following line to check the generation of the values dictionary
                    # self.logger.debug("{:40} ---> {}".format(line, Values))
                    self._update_items(obis_code, values)


if __name__ == '__main__':
    import sys

    usage = """
    Usage:
    ----------------------------------------------------------------------------------------------------

    There are two ways to use this module:
    1. You can use it as a plugin for SmartHomeNG
    2. You can use it standalone from the command line.
       This way you can test your serial link to the smartmeter and
       sniff the output for which values you want to have in your item structure lately

       You need to give the interface to query as first parameter, e.g. /dev/dlms0
       If you like to receive verbose information just append '-v' to the latter as well.

    """
    logging.getLogger().setLevel( logging.DEBUG )
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
    #formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logging.getLogger().addHandler(ch)
    serial_to_use = ""

    if len(sys.argv) > 1:
        serial_to_use = sys.argv[1]
    else:
        print(usage)
        exit()

    print("This is DLMS Plugin running in standalone mode")
    print("==============================================")

    dlms_plugin = DLMS(None, serial_to_use )
    result = dlms_plugin._query_smartmeter()
    if result is None:
        print()
        print("No results from query, maybe a problem with the serial port '{}' given ".format(serial_to_use))
        print("==============================================")
    elif len(result) > 0:
        print()
        print("These are the results of the query")
        print("==============================================")
        print(result)
        print("==============================================")
    else:
        print()
        print("The query did not get any results!")
        print("Maybe the serial was occupied or there was an error")
