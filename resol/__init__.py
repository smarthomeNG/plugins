#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.          http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################
  
import socket
#from lib.network import Tcp_client
import time
from lib.model.smartplugin import *

class Resol(SmartPlugin):

    PLUGIN_VERSION = '1.0.7'    # (must match the version specified in plugin.yaml)


    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._items = []
        self._ip = self.get_parameter_value('ip')
        self._port = self.get_parameter_value('port')
        self._cycle = self.get_parameter_value('cycle')
        self._password = self.get_parameter_value('password')
        self._to_do = True
        #self._client = Tcp_client(name=name, host=self._ip, port=self._port, binary=True, autoreconnect=True, connect_cycle=5, retry_cycle=30)


    def run(self):
        self.alive = True
        self.scheduler_add('PollData', self.sock, prio=5, cycle=self._cycle, offset=2)
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.scheduler_remove('PollData')

        try:
            if self.sock: 
                self.sock.shutdown(0)
                self.sock.close()
        except:
            pass
        
        self.sock = None
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'resol_offset'): 
            resol_offset = self.get_iattr_value(item.conf, 'resol_offset')
            parentItem = item.return_parent()
            if self.has_iattr(parentItem.conf, 'resol_source'):
                resol_source = self.get_iattr_value(parentItem.conf, 'resol_source')
                self.logger.debug(f"Parent source: {resol_source}")
            else:
                self.logger.error(f"Attribute resol_source missing in parent item of item {item}")
                return

            if self.has_iattr(item.conf, 'resol_bituse'): 
                resol_bituse = self.get_iattr_value(item.conf, 'resol_bituse')
                self._items.append(item)
                self.logger.debug(f"Debug: added item {item} with resol_bituse {resol_bituse}")
                # As plugin is read-only, no need to register item for event handling via smarthomeNG core:
                        
            else:
                self.logger.error(f"resol_offset found in item {item} but no bitsize given, specify bitsize in item with resol_bitsize = ")

    def update_item(self, item, caller=None, source=None, dest=None):
        # do nothing if items are changed from outside the plugin
        pass

    def sock(self):
        if not self.alive:
            return
        self.logger.info("1) Starting sock function")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.info("2) Connecting socket")
        try:
            self.sock.connect((self._ip, self._port))
        except Exception as e:
            self.logger.error("Exception during socket connect: %s" % str(e))
            return
        self.logger.info("3) Logging in")
        if self.login():
            self.logger.info("4) Loading data")
            self.load_data()
        else:
            self.logger.warning("Cannot login")
        self.logger.info("5) Shutting down socket")
        try:
            if self.sock: 
                self.sock.shutdown(0)
                self.sock.close()
        except Exception as e:
            self.logger.warning("Exception during shutdown socket command: {0}".format(e))
            pass
        self.logger.info("6) Ending socket function")
        self.sock = None

    # Logs in onto the DeltaSol BS Plus over LAN. Also starts (and maintains) the
    # actual stream of data.
    def login(self):
        dat = self.recv()
        self.logger.debug("Login response: " + str(dat))

        #Check if device answered
        if dat != "+HELLO\n":
            self.logger.warning("WRONG REPLY FROM VBUS LAN: " + str(dat))
            return False

        #Send Password
        self.send("PASS %s\n" % self._password)

        dat = self.recv()
        if not dat:
            self.logger.warning("No data received following password send")
            return False

        self.logger.debug("Response to pwd: " + str(dat))

        #Check if device accepted password
        if not dat.startswith("+OK"):
            self.logger.warning("Password not accepted:" + str(dat))
            return False

        return True

    def load_data(self):
        #Request Data
        global new_data
        self.logger.info("Requesting data...") 
        self.send("DATA\n")
        dat = self.recv()

        if not dat:
            self.logger.warning("Could not receive data via socket")
            return

        self.logger.info("Response to data: " + str(dat))
    
        #Check if device is ready to send Data
        if not dat.startswith("+OK"):
          self.logger.warning("Vbus Lan is not ready, reply: " + str(dat))
          return
        buf = self.readstream()
        
        #self.logger.warning("Readstream {0} bytes as asci: {1}".format(len(buf),str(buf)))
        #self.logger.warning(40*"-")

        #self.logger.warning("Readstream hex {0} bytes:".format(len(buf)))
        #index = 0
        #for single_byte in buf:
        #    self.logger.warning("index {0}, content {1}".format(index, buf[index].encode('utf-8').hex() ))
        #    index = index + 1
        #self.logger.warning(40*"#")

        #s = buf.encode('utf-8')
        #self.logger.warning("Readstream hex {0} bytes: {1}".format(len(buf), s.hex()))

        if not buf: 
            return

        msgs = self.splitmsg(buf)
        for msg in msgs:
            #self.logger.debug("Msg protocol version {0}".format(self.get_protocolversion(msg)))
            if "PV1" == self.get_protocolversion(msg):
                self.parse_payload_pv1(msg)
            else:
                pass
                #self.logger.warning("Unknown protocol version {0}".format(self.get_protocolversion(msg)))

    # Receive 1024 bytes from stream
    def recv(self):
        if not self.sock:
            self.logger.error("Error during data reception: Socket is not valid")
            return None
        self.sock.settimeout(5)
        try:
            dat = self.sock.recv(1024).decode('Cp1252')
        except Exception as e:
            self.logger.error("Exception during socket recv.decode: %s" % str(e))
            return None

        return dat
    
    # Sends given bytes over the stream. Adds debug
    def send(self, dat):
        if not self.sock:
            return
        self.sock.send(dat.encode('utf-8'))
    
    # Read Data until minimum 1 message is received
    def readstream(self):
        data = self.recv()
        if data is None:
            # No error logging because error was logged in recv function
            return None
        if not data:
            self.logger.warning("No data received during readstream()")
            return None
        else:
            self.logger.debug("Readstream() received {0}".format(data))

        while data.count(chr(0xAA)) < 4:
            data_rcv = self.recv()
            if data_rcv is None:
                # No error logging because error was logged in recv function
                return None

            if not data_rcv:
                self.logger.warning("No data received during readstream() count")
                return None
            else:
                self.logger.debug("Readstream count received {0}".format(data_rcv))
            data += data_rcv
        return data
    
    #Split Messages on Sync Byte
    def splitmsg(self, buf):
        return buf.split(chr(0xAA))[1:-1]
    
    # Format 1 byte as String
    def format_byte(self, byte):
        return hex(ord(byte))[0:2] + '0' + hex(ord(byte))[2:] if len(hex(ord(byte))) < 4 else hex(ord(byte))
    
    # Extract protocol Version from msg
    def get_protocolversion(self, msg):
        if hex(ord(msg[4])) == '0x10': return "PV1"
        if hex(ord(msg[4])) == '0x20': return "PV2"
        if hex(ord(msg[4])) == '0x30': return "PV3"
        return "UNKNOWN"
    
    # Extract Destination from msg NOT USED AT THE MOMENT
    def get_destination(self, msg):
        return self.format_byte(msg[1]) + self.format_byte(msg[0])[2:]
    
    #Extract source from msg NOT USED AT THE MOMENT
    def get_source(self, msg):
        return self.format_byte(msg[3]) + self.format_byte(msg[2])[2:]
    
    # Extract command from msg NOT USED AT THE MOMENT
    def get_command(self, msg):
        return self.format_byte(msg[6]) + self.format_byte(msg[5:6])[2:]

    # Check header CRC byte:
    def check_header_crc(self, msg):
        #header_crc = hex(ord(msg[8]))
        calc_crc = self.calc_vbus_crc(msg, offset=0, length=8)
        
        if calc_crc == ord(msg[8]):
            return True
        else:
            return False 
    
    # Get count of frames in msg
    def get_frame_count(self, msg):
        return self.gb(msg, 7, 8)
    
    # Extract payload from msg
    def get_payload(self, msg):
        payload = ''
        frame_count = self.get_frame_count(msg)

        # Check if enough bytes are in message buffer:
        if (15+((frame_count-1)*6)) > len(msg):
            self.logger.warning(f"get_payload - Not enough data in msg buffer. Expected {15+((frame_count-1)*6)}, received {len(msg)}")
            return ''

        for i in range(frame_count):
            frame_data = msg[9+(i*6):15+(i*6)]
            #working test data: frame_data = str(b'\x38\x22\x38\x22\x05\x46', 'utf-8')
            isFrameCrc = ord(frame_data[5])
            frame_crc = self.calc_vbus_crc(frame_data, offset=0, length=5)

#           self.logger.debug(f"frame {i}: {hex(ord(frame_data[0]))},{hex(ord(frame_data[1]))},{hex(ord(frame_data[2]))},{hex(ord(frame_data[3]))},{hex(ord(frame_data[4]))},{hex(ord(frame_data[5]))}")
#           self.logger.debug(f"frame {i}: isFrameCRC= {hex(isFrameCrc)}, calcFrame_crc={hex(frame_crc)}")

            if frame_crc != isFrameCrc:
                self.logger.warning(f"Wrong frame CRC in frame {i}")
                return ''

            #Integrate septett byte into all frames:
            payload += self.integrate_septett(msg[9+(i*6):15+(i*6)])

        return payload

    def calc_vbus_crc(self, msg, offset, length):
        Crc = 0x7F
        for i in range(length):
            Crc = (Crc - ord(msg[offset + i]) ) & 0x7F
        return Crc
    
    # parse payload and set item value
    def parse_payload_pv1(self, msg):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)

        if not self.check_header_crc(msg):
            self.logger.warning("Header crc error")
            return
        
        command = self.get_command(msg)
        source = self.get_source(msg)
        destination = self.get_destination(msg)
        if logger_debug:
            self.logger.debug("command: " + str(command))
            self.logger.debug("source: " + str(source))
            self.logger.debug("destination: " + str(destination))
        #self.logger.warning("Frame count: {0}".format(self.get_frame_count(msg)))
        #self.logger.warning("Length msg: {0}".format(len(msg)))

        payload = self.get_payload(msg)

        if payload == '':
            self.logger.warning("Payload is empty")
            return
       
        for item in self._items:
            parentItem = item.return_parent()
            if self.has_iattr(parentItem.conf, 'resol_source'):
                resol_source = self.get_iattr_value(parentItem.conf, 'resol_source')
                if resol_source != self.get_source(msg):
                    if logger_debug:
                        self.logger.debug(f"Attribute resol source {resol_source} of parent of item {item} does not match msg source {self.get_source(msg)}")
                    continue
            if self.has_iattr(parentItem.conf, 'resol_destination'):
                resol_destination= self.get_iattr_value(parentItem.conf, 'resol_destination')
                if resol_destination != self.get_destination(msg):
                    if logger_debug:
                        self.logger.debug(f"Attribute destination {resol_destination} of parent of item {item} does not match msg destination {self.get_destination(msg)}")
                    continue
            if self.has_iattr(parentItem.conf, 'resol_command'):
                resol_command= self.get_iattr_value(parentItem.conf, 'resol_command')
                if resol_command != self.get_command(msg):
                    if logger_debug:
                        self.logger.debug(f"Attribute command {resol_command} of parent of item {item} does not match msg command {self.get_command(msg)}")
                    continue
            else:
                self.logger.error(f"resol command not found in parent of item {item}")
            
            if self.has_iattr(item.conf, 'resol_offset'):
                resol_offset= self.get_iattr_value(item.conf, 'resol_offset')
            else:
                self.logger.error(f"Resol item {item} missing attribute resol_offset")

            if self.has_iattr(item.conf, 'resol_bituse'):
                resol_bituse= self.get_iattr_value(item.conf, 'resol_bituse')
            else:
                self.logger.error(f"Resol item {item} missing attribute resol_bituse")

            resol_factors = {}
            if self.has_iattr(item.conf, 'resol_factor'):
                resol_factors = self.get_iattr_value(item.conf, 'resol_factor')

            resol_isSigned = {}
            if self.has_iattr(item.conf, 'resol_isSigned'):
                resol_isSigned = self.get_iattr_value(item.conf, 'resol_isSigned')

            end = int(resol_offset) + int((resol_bituse + 1) / 8)
            #self.logger.warning(f"Debug Start: {resol_offset}, End: {end}")
            
            value = 0
            count = 0
            #self.logger.debug(f"Starting for loop with {int(resol_offset)},{int((resol_bituse + 1) / 8)}")
            for byte_position in range(int(resol_offset), int(resol_offset + (resol_bituse + 1) / 8)):
                byte_value = ord(payload[byte_position])

                if len(resol_factors) > count:
                    factor = resol_factors[count]
                else:
                    factor = 1
                    self.logger.warning(f"No attribute resol_factor defined for byte {count}. Using factor=1 instead")

                if len(resol_isSigned) > count:
                    isSigned = resol_isSigned[count]
                else:
                    isSigned = False

                if logger_debug:
                    self.logger.debug("count {0} Index {1}, bytevalue {2}, factor {3}".format(count, byte_position, byte_value, factor))

                if isSigned:
                    byte_value = int.from_bytes(bytes([byte_value]), "little", signed=True)

                value = value + byte_value * float(factor)
                count = count + 1
            if logger_debug:
                self.logger.debug(f"Value of item {item} is {value}, Source {source}, Destination {destination}")
            
            item(value, self.get_shortname(), str(source), str(destination))

    def integrate_septett(self, frame):
        data = ''
        septet = ord(frame[4])
    
        for j in range(4):
          if septet & (1 << j):
              data += chr(ord(frame[j]) | 0x80)
          else:
              data += frame[j]
    
        return data
    
    # Gets the numerical value of a set of bytes (respect Two's complement by value Range)
    def gb(self, data, begin, end):  # GetBytes
        wbg = sum([0xff << (i * 8) for i, b in enumerate(data[begin:end])])
        s = sum([ord(b) << (i * 8) for i, b in enumerate(data[begin:end])])
                
        if s >= wbg/2:
          s = -1 * (wbg - s)
        return s
