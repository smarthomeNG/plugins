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
import time
from lib.model.smartplugin import *

class Resol(SmartPlugin):

    PLUGIN_VERSION = '1.0.3'    # (must match the version specified in plugin.yaml)


    def __init__(self, sh, *args, **kwargs):
        self._sh = sh
        self._items = []
        self._ip = self.get_parameter_value('ip')
        self._port = self.get_parameter_value('port')
        self._cycle = self.get_parameter_value('cycle')
        self._password = self.get_parameter_value('password')
        self._to_do = True

    def run(self):
        #logging.warning("run function")
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
        if 'resol_offset' in item.conf:
          self.logger.debug("ELTERN Source: " + str(item.return_parent().conf['resol_source']))
          if 'resol_bituse' in item.conf:
            self._items.append(item)
            # As plugin is read-only, no need to register item for event handling via smarthomeNG core:
                        
          else:
            self.logger.error("resol_offset found in: " + str(item) + " but no bitsize given, specify bitsize in item with resol_bitsize = ")

    def update_item(self, item, caller=None, source=None, dest=None):
        #logging.warning("update function")
        if caller != self.get_shortname():
          #logger.warning("update item: {0}".format(item.id()))
          value = str(int(item()))
          #logger.warning(value)

    def sock(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


        try:
            self.sock.connect((self._ip, self._port))
        except Exception as e:
            self.logger.error("Exception during socket connect: %s" % str(e))
            return

        self.login()
        self.load_data()
        try:
            self.sock.shutdown(0)
            self.sock.close()
        except Exception as e:
            self.logger.warning("Exception during shutdown socket command: {0}".format(e))
            pass
        
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
        self.logger.debug("Response to pwd: " + str(dat))

        #Check if device accepted password
        if not dat.startswith("+OK"):
            self.logger.warning("Password not accepted:" + str(dat))
            return False

        return True

    def load_data(self):
        #Request Data
        global new_data
        self.send("DATA\n")
        dat = self.recv()

        if not dat:
            self.logger.warning("Could not receive data via socket")
            return

        self.logger.debug("Response to data: " + str(dat))

    
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
            #self.logger.warning("Msg protocol version {0}".format(self.get_protocolversion(msg)))
            if "PV1" == self.get_protocolversion(msg):
                self.parse_payload(msg)

    # Receive 1024 bytes from stream
    def recv(self):
        if not self.sock:
            return None
        dat = self.sock.recv(1024).decode('Cp1252')
        return dat
    
    # Sends given bytes over the stream. Adds debug
    def send(self, dat):
        if not self.sock:
            return
        self.sock.send(dat.encode('utf-8'))
    
    # Read Data until minimum 1 message is received
    def readstream(self):
        data = self.recv()
        if not data:
            return None
        while data.count(chr(0xAA)) < 4:
            data_rcv = self.recv()
            if not data_rcv:
                return None
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
    
    # Get count of frames in msg
    def get_frame_count(self, msg):
        return self.gb(msg, 7, 8)
    
    # Extract payload from msg
    def get_payload(self, msg):
        payload = ''
        for i in range(self.get_frame_count(msg)):
            if (15+(i*6)) <= len(msg): 
                payload += self.integrate_septett(msg[9+(i*6):15+(i*6)])
            else:
                self.logger.error("get_payload: index {0} out of range {1} for i={2}".format((15+(i*6)), len(msg), i))
                return ''
        return payload
    
    # parse payload and set item value
    def parse_payload(self, msg):
        logger_debug = self.logger.isEnabledFor(logging.DEBUG)

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
        #self.logger.warning("Length payload: {0}".format(len(payload)))



        if payload == '':
            return
        for item in self._items:
            if 'resol_source' in item.return_parent().conf:
                if item.return_parent().conf['resol_source'] != self.get_source(msg):
                    if logger_debug:
                        self.logger.debug("source if item " + str(item) + " does not match msg source " + str(item.return_parent().conf['resol_source']) + " not matches msg source: " + str(self.get_source(msg)))
                    continue
            if 'resol_destination' in item.return_parent().conf:
                if item.return_parent().conf['resol_destination'] != self.get_destination(msg):
                    if logger_debug:
                        self.logger.debug("destination if item " + str(item) + " does not match msg destination " + str(item.return_parent().conf['resol_destination']) + " not matches msg destination: " + str(self.get_destination(msg)))
                    continue
            if 'resol_command' in item.return_parent().conf:
                if item.return_parent().conf['resol_command'] != self.get_command(msg):
                    if logger_debug:
                        self.logger.debug("destination if item " + str(item) + " does not match msg destination " + str(item.return_parent().conf['resol_command']) + " not matches msg destination: " + str(self.get_command(msg)))
                    continue
            end = int(item.conf['resol_offset']) + int( (item.conf['resol_bituse'] + 1) / 8)
            #self.logger.warning("Start: " + str(item.conf['resol_offset']) + " ENDE: " + str(end))
            
            #resol_factors = item.conf['resol_factor']
            #if resol_factors:
            #    for factor in resol_factors:
            #        self.logger.warning("Factor: {0}".format(factor))
            wert = 0
            count = 0
            #self.logger.debug("starting for loop with {0},{1}".format(int(item.conf['resol_offset']), int( (item.conf['resol_bituse'] + 1) / 8)))
            for byte_position in range(int(item.conf['resol_offset']), int(item.conf['resol_offset'] + (item.conf['resol_bituse'] + 1) / 8)):
                byte_value = ord(payload[byte_position])

                factor = 1
                resol_factors = {}
                if 'resol_factor' in item.conf:
                    resol_factors = item.conf['resol_factor']
                if len(resol_factors) > count:
                    factor = resol_factors[count]

                if logger_debug:
                    self.logger.debug("count {0} Index {1}, bytevalue {2}, factor {3}".format(count, byte_position, byte_value, factor))

                wert = wert + byte_value * float(factor)
                count = count + 1
            if logger_debug:
                self.logger.debug("payload: of item " + str(item) + ": " + str(wert))
            self._sh.return_item(str(item))(wert, self.get_shortname(), str(source), str(destination))

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
