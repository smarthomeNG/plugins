#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#
#  DLMS plugin for SmartHomeNG.py.
#
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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
#  along with SmartHomeNG If not, see <http://www.gnu.org/licenses/>.
#########################################################################
__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import logging
if __name__ == '__main__':
    class SmartPlugin():
        pass
else:
    from lib.model.smartplugin import SmartPlugin
        
import time
import serial
import re
from threading import Semaphore

""" 
This module implements the questioning of a smartmeter using the DLMS protocol
#   Character Format: (1 start bit, 7 data bits, 1 parity bit, 1 stop bit) even parity 
#   for protocol mode A - D
#   in protocol mode E 1 start bit, 8 data bits, 1 stop bit is allowed, see Annex E of IEC62056-21
#   but mode E is not supported and implemented
#   Abbreviations
#   COSEM   COmpanion Specification for Energy Metering
#   OBIS    OBject Identification System                (see iec62056-61{ed1.0}en_obis_protocol.pdf)

Usage:
    There are two ways to use this module.
    1. You can use it standalone from the command line. This way you can test your serial link to the smartmeter and
       sniff the output for which values you want to have in your item structure lately
    2. You can use it as a plugin for SmarthomeNG.py

# Further Reading: search for

"""


class DLMS(SmartPlugin):
    PLUGIN_VERSION = "1.2.5"
    ALLOW_MULTIINSTANCE = False
    """
    This class provides a Plugin for SmarthomeNG.py which reads out a smartmeter.
    The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB
    It is possible to use the Plugin as a standalone program to check out the communication 
    prior to use it in SmarthomeNG.py
    
    The tag 'dlms_obis_code' identifies the items which are to be updated from the plugin
    """

    #ITEM_TAG = ['dlms_obis_code'] # we would take this approach if we had more tags to handle
    item_tag = 'dlms_obis_code'
    index_separator = '~'
    
    def __init__(self, smarthome, serialport, baudrate="auto", update_cycle="60", no_waiting = False, instance = 0, keep_obis_output_short = False, device_address = b'', suppress_obis_ab = True, timeout = 2 ):
        """
        This function initializes the DLMS plugin
        :param serialport: 
        """
        self.logger = logging.getLogger(__name__)
        if __name__ == '__main__':
            self.logger.setLevel( logging.DEBUG )
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            # create formatter and add it to the handlers
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
            formatter = logging.Formatter('%(message)s')
            ch.setFormatter(formatter)
            # add the handlers to the logger
            self.logger.addHandler(ch)        
        else:
            self.logger.debug("init dlms")
            
        self._sh = smarthome                                   # save a reference to the smarthome object
        self._serialport = serialport                          
        self._update_cycle = int(update_cycle)                 # the frequency in seconds how often the device should be accessed
        self._instance = instance                              # the instance of the plugin for questioning multiple smartmeter
        self._device_address = device_address                  # there is a possibility of using a named device.
                                                               # normally this will be empty since only one meter will be attached
                                                               # to one serial interface but the standard allows for it and we honor that.
        self._keep_obis_output_short = keep_obis_output_short  # dumping out in standalone mode will suppress older time stamp to keep the item list short
        self._suppress_obis_ab = suppress_obis_ab              # omits the optional A and B values of OBIS code, as well in dumping as in matching items
        self.timeout = timeout
        self._sema = Semaphore()                               # implement a semaphore to avoid multiple calls of the query function
        self._min_cycle_time = 0                               # we measure the time for the value query and add some security value of 10 seconds
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
            # if we are not running in console mode, we add a scheduler to let it call the _update_values function
            self._sh.scheduler.add('DLMS', self._save_update_values, prio=5, cycle=self._update_cycle)
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
        pass

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

    def _read_data_block_from_serial(self, the_serial, log_debug = "Response was '{}'", end_byte = 0x0a ):
        """
        This function reads some bytes from serial interface
        it returns an array of bytes if a timeout occurs or a given end byte is encountered
        and otherwise None if an error occurred
        """
        #self.logger.debug("Serial: {}".format(the_serial))
        response = bytes()
        try:
            while self.alive:
                ch = the_serial.read()
                if len(ch) == 0:
                    break;
                response += ch
                if ch == end_byte:
                    break;
                if (response[-1] == end_byte):
                    break
        except Exception as e:
            self.logger.debug("Warning {0}".format(e))
            return None
        return response

        
    def _save_update_values(self):
        """
        This function aquires a semphore and if possible it calls the update function.
        If it is not possible it passes on, issuing a warning about increasing the query interval
        """
        if(self._sema.acquire(blocking=False)):
            self._update_values()
            self._sema.release()
        else:
            self.logger.warning( "update is alrady running, maybe it really takes very long or you should use longer query interval time" )
    
    def _update_values(self):
        """
        This function will 
        1. open a serial communication line to the smartmeter
        2. sends a request for info
        3. parses the devices first (and maybe second) answer for capabilities of the device
        4. adjusts the speed of the communication accordingly
        5. reads out the block of OBIS information
        7. closes the serial communication
        6. checks line by line if items need to be updated
        """
        # for the performance of the serial read we need to save the actual time
        starttime = time.time()
        runtime = starttime

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

        try:
            dlms_serial = serial.Serial(self._serialport, InitialBaudrate, bytesize=serial.SEVENBITS, parity=serial.PARITY_EVEN, timeout=self.timeout)
            if not self._serialport == dlms_serial.name:
                self.logger.debug("Asked for {} as serial port, but really using now {}".format( self._serialport, dlms_serial.name))
        except Exception as e:
            self.logger.error("Error {0}".format(e))
            return

        self.logger.debug("Time to open serial port {}: {}".format(self._serialport,self.format_time(time.time()- runtime)))
        runtime = time.time()
        
        self.logger.debug("Sending request message {} to smartmeter".format(Request_Message))
        try:
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()            
            dlms_serial.write(Request_Message)
            dlms_serial.flush()                 # replaced dlms_serial.drainOutput()
            dlms_serial.reset_input_buffer()    # replaced dlms_serial.flushInput()            
            dlms_serial.timeout = self.timeout
        except Exception as e: 
            self.logger.warning("Error {0}".format(e))
            return

        self.logger.debug("Time to send first request to smartmeter: {}".format(self.format_time(time.time()- runtime)))
        
        # now get first response
        response = self._read_data_block_from_serial( dlms_serial, "read timeout! - response from meter device read so far: {}")
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
            response = self._read_data_block_from_serial( dlms_serial, "read timeout! - response from meter device read so far: {}")
        else:
            self.logger.debug("Request Message was echoed, need to read the identification message".format(response))
                

        self.logger.debug("Time to get first identification message from smartmeter: {}".format(self.format_time(time.time()- runtime)))
        runtime = time.time()

        Identification_Message = response
        self.logger.debug("Identification Message is {}".format(Identification_Message))
        
        if (len(Identification_Message) < 5):
            self.logger.warning("malformed identification message {}".format(Identification_Message))
            return

        if (Identification_Message[0] != StartChar):
            self.logger.warning("identification message {} does not start with '/', aborting".format(Identification_Message[0]))
            return

        # different smartmeters allow for different protocol modes. 
        # the protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
        # some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
        Protocol_Mode = 'A'
        Baudrates_Protocol_Mode_A = 300 # always stays at the same speed, Protocol indicator can be anything except for A-I, 0-9, /, ?
        Baudrates_Protocol_Mode_B = { 'A' : 600, 'B' : 1200, 'C' : 2400, 'D' : 4800, 'E' : 9600, 'F' : 19200, 'G' : "reserved", 'H' : "reserved", 'I' : "reserved" }
        Baudrates_Protocol_Mode_C = { '0' : 300, '1' : 600, '2' : 1200, '3' : 2400, '4' : 4800, '5' : 9600, '6' : 19200, '7' : "reserved", '8' : "reserved", '9' : "reserved" }
        Baudrates_Protocol_Mode_D = { '3' : 2400 } # always '3' but it is always initiated by the metering device so it can't be encountered here
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

        self.logger.debug("Baudrate id is '{}' thus Protocol Mode is {} and max Baudrate available is {} Bd".format(Baudrate_identification, Protocol_Mode, NewBaudrate))

        # for protocol C or E we now send an acknowledge and include the new baudrate parameter
        # maybe todo 
        # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
        # read out a smartmeter with broken communication
        Acknowledge = b'\x060' + Baudrate_identification.encode() + b'0\r\n'
        
        if Protocol_Mode == 'C':
            # the speed change in communication is initiated from the reading device
            time.sleep(wait_before_acknowledge)
            self.logger.debug("Using protocol mode C, send acknowledge {} and tell smartmeter to switch to {} Baud".format(Acknowledge, NewBaudrate))
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
            self.logger.debug("No change of readout baudrate, smartmeter and reader will stay at {} Baud".format(NewBaudrate))

        # now read the huge data block with all the OBIS codes
        self.logger.debug("Reading OBIS data from smartmeter")
        response = self._read_data_block_from_serial( dlms_serial, "read timeout! - response = {}", None)

        dlms_serial.close()
        self.logger.debug("Time for reading OBIS data: {}".format(self.format_time(time.time()- runtime)))
        runtime = time.time()

        # Display performance of the serial communication
        self.logger.debug("Whole communication with smartmeter took {}".format(self.format_time(time.time()- starttime)))

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
            if (checksum != BCC):
                self.logger.warning("checksum/protocol error: response={} checksum={}".format(' '.join(hex(i) for i in response), checksum))
                return
            else:
                self.logger.debug("checksum over data response was ok")
        else:
            self.logger.warning("STX - ETX not found")

        if len(response) > 5:
            data_block = str(response[1:-4], 'ascii')
            self._analyze_OBIS_codes( data_block )
            self.logger.debug("parsing OBIS codes took {}".format(self.format_time(time.time()- runtime)))
            self.logger.debug("the whole query took {}".format(self.format_time(time.time()- starttime)))
        else:
            self.logger.debug("not enough data for OBIS decode")

        suggested_cycle = (time.time() - starttime) + 10.0

        if (time.time() - runtime) > self._update_cycle and self._min_cycle_time < self._update_cycle:
            # if query takes longer than the given update_cycle then make a suggestion for an adjustment
            self.logger.warning("the update cycle should be increased to at least {}".format(self.format_time(suggested_cycle)))

        if suggested_cycle > self._min_cycle_time:
            self._min_cycle_time = suggested_cycle


    def _analyze_OBIS_codes( self, textblock ):
        """        
        OBIS codes are a combination of six value groups, which describe in a hierarchical way 
        the exact meaning of each data item
        A:  characteristic of the data item to be identified (abstract data, electricity-, gas-, heat-, water-related data)
        B:  channel number, i.e. the number of the input of a metering equipment having several inputs for the measurement 
            of energy of the same or different types (e.g. in data concentrators, registration units). 
            Data from different sources can thus be identified. The definitions for this value group are independent from the value group A.
        C:  abstract or physical data items related to the information source concerned, 
            e.g. current , voltage , power, volume, temperature. The definitions depend on the value of the value group A . 
            Measurement, tariff processing and data storage methods of these quantities are defined by value groups D, E and F
            For abstract data, the hierarchical structure of the 6 code fields is not applicable.
        D:  types, or the result of the processing of physical quantities identified with the 
            value groups A and C, according to various specific algorithms. The algorithms can deliver energy and
            demand quantities as well as other physical quantities.
        E:  further processing of measurement results identified with value groups A to D to tariff registers, 
            according to the tariff(s) in use. For abstract data or for measurement results for which tariffs are not relevant, 
            this value group can be used for further classification.
        F:  the storage of data, identified by value groups A to E, according to different billing periods.
            Where this is not relevant, this value group can be used for further classification.
        
        Manufacturer specific codes
        If any value group C to F contains a value between 128 and 254, the whole code is considered as manufacturer specific.
        
        Some value groups may be suppressed, if they are not relevant to an application, so optional value groups are A, B, E, F

        A-B:C.D.E*F
        
        OBIS lines         parsing results  A   B   C   D   E   Sep F   data[0]     data[1]
        ----------------------------------------------------------------------------------------
        1-1:F.F(00000000)                   1   1   F   F               (00000000)  
        1-1:0.0.0(50871031)                 1   1   0   0   0           (50871031)
        1-1:1.6.1(24.81*kW)(1604070900)     1   1   1   6   1           (24.81*kW)  (1604070900)
        1-1:1.6.1*03(26.14)(1510221000)     1   1   1   6   1   *   03  (26.14)     (1510221000)
        1-1:1.6.1&02(00.00)(0000000000)     1   1   1   6   1   &   02  (00.00)     (0000000000)
        1-1:3.8.2*08(00000372)              1   1   3   8   2   *   08  (00000372)
        """

        if __name__ == '__main__':
            if self._keep_obis_output_short:
                print("Saved values in meter for past values will not be shown to keep the list short")          
        else:
            # lets ask smarthome which items have the right attribute
            items_with_tag = []
            # todo: 
            # for multi instance of the plugin we need to extend the tag with the instance
            for item in self._sh.find_items(self.item_tag):
                items_with_tag.append(item)
                self.logger.debug("Item '{}' has attribute '{}'".format(item, self.item_tag))            
            self.logger.debug("checking now for {} items with tag for dlms obis codes".format(len(items_with_tag)))
        
        OBIS_A = { '0' : 'Abstract Objects', '1' : 'Electricity related objects' }
        
        for line in re.split('\r\n', textblock):
            A = ""
            B = "" 
            C = ""
            D = ""
            E = ""
            F = ""
            Sep = ""
            if line.startswith("!") or len(line) == 0:
                continue
                
            # Now check if we can split between values and OBIS code
            OBISCode = line.split('(',1)
            if len(OBISCode)==1:
                #no values in parentheses found!
                OBISCode = OBISCode[0]
                Values = ""
            elif len(OBISCode)==2:
                #ok, found some values to the right, lets isolate them
                Values = OBISCode[1]
                OBISCode = OBISCode[0]
            
            if len(Values)>1:
                # we must at least have a closing ')'
                TempValues = Values.split(')')
                Values = []
                for s in TempValues:
                    s = s.replace('(','')
                    if len(s) > 0:
                        sv = s.split('*',1)
                        Values.append(sv[0])
            
            
            # check if optional Values A and B are present
            AB = OBISCode.split(":",1)
            if len(AB) == 1:
                # the optional values A and B are not present
                A = ""
                B = ""
                CDEF = line
            elif len(AB) == 2:
                # We got A and/or B present
                CDEF = AB[1]
                AB = AB[0]
                A,B = AB.split("-")
            else:
                self.logger.error("parsing error for line {}".format(line, e))
            
            C = CDEF.split(".",1)
            if len(C) == 1:
                # seems as if there is only argument C available but D or more ist missing.
                # since D is not optional we should warn the user
                DEF = ""
                C = C[0]
                self.logger.warning("parsing line '{}' results in A:{}, B:{}, C:{} but non optional D not present! '{}'".format(line, A, B, C, DEF ))
                continue
            elif len(C) == 2:
                # We got C and some more present
                DEF = C[1]
                C = C[0]
            else:
                self.logger.error("parsing error for line {}".format(line, e))

            D = DEF.split(".",1)
            if len(D) == 1:
                # E or F are not present (they are optional however)
                D = D[0]
                E = ""
                F = ""
            elif len(D) == 2:
                # E and/or F are present. If F is present then the delimiter must be a * for a normal calculated 
                # value by the meter device or & if a value was reset by hand
                EF = D[1]
                D = D[0]
                if EF.find("*") > 0:
                    Sep = "*"
                    E,F = EF.split(Sep)
                elif EF.find("&") > 0:
                    Sep = "&"
                    E,F = EF.split(Sep)
                else:
                    E = EF
                    F = ""
            else:
                self.logger.error("parsing error for line {}".format(line, e))
            
            # construct the OBIS lookup string
            DLMS_OBIS_Code = ""
            if not self._suppress_obis_ab:
                DLMS_OBIS_Code = "{}-{}:".format(A,B)
            
            DLMS_OBIS_Code += "{}.{}".format( C, D )
            
            DLMS_OBIS_Code += "{}".format( "."+E if len(E)>0 else "" )
            
            # always add * as separator if F is present, otherwise manually reset values in meter could not be catched
            DLMS_OBIS_Code += "{}".format( "*"+F if len(F)>0 else "" )      
           
            if __name__ == '__main__':
                if not self._keep_obis_output_short:
                    print("{}{}".format(DLMS_OBIS_Code, ''.join([ "({})".format(i) for i in Values ])))
                elif len(F)==0:
                    print("{}{}".format(DLMS_OBIS_Code, ''.join([ "({})".format(i) for i in Values ])))
            else:
                # self.logger.debug("parsing line {} results in {} - {} : {} . {} . {} {} {}   '{}'".format(line, A, B, C, D, E, Sep, F, DLMS_OBIS_Code))
                for item in items_with_tag:
                    config_attribute_value = item.conf[self.item_tag]
                    #self.logger.debug(" item[self.item_tag] = {}".format(config_attribute_value))
                    if config_attribute_value.startswith(DLMS_OBIS_Code):
                        # item[item_tag] might be of form 1.8.1|0..n which means the value index
                        # if | is included, we need to partition it
                        # maybe todo: append a letter e.g. 'u' to the index. 
                        # This way the unit might be examined and transferred to an item
                        # a time code of an OBIS item will normally be at Values[1] if present
                        if config_attribute_value.find(self.index_separator) > 0:
                            FooCode, Index = config_attribute_value.split(self.index_separator)
                            Index = int(Index)
                        else:
                            Index = 0
                        item(Values[Index], 'DLMS', 'OBIS {}'.format(DLMS_OBIS_Code))
                        self.logger.debug("Set item {} for Obis Code {} to Value {}".format(item, DLMS_OBIS_Code, Values[Index]))
            

if __name__ == '__main__':
    import sys

    print("This is DLMS Plugin running in standalone mode")
    print("==============================================")
    if len(sys.argv) > 1:
        serial_to_use = sys.argv[1]
    else:
        print("You need to give the interface to query as first parameter, e.g. /dev/dlms0")
        exit()
        
    if len(sys.argv) > 2:
        keep_obis_output_short = False
        print("working in verbose mode")
    else:
        keep_obis_output_short = True
        
    dlms = DLMS( None, serial_to_use, baudrate = 300, update_cycle = 60, keep_obis_output_short = keep_obis_output_short, suppress_obis_ab = True )
    dlms._update_values()
