#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 Nico P.
#  THX to arvehj for the communication procedure (jvcprojectortools)
#########################################################################
#  This file is part of SmartHomeNG.   
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
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import os.path as os_path
import json
import select
import socket
import binascii

import logging
from lib.model.smartplugin import SmartPlugin

"""JVC command and response headers
Header
The header can be one of 4 possible values. These are:
21 - (ASCII: "!") Operating Command (from PC/controller to projector)
3F - (ASCII: "?") Acknowledgement Response Return Code Request (from PC/controller to projector)
06 - Acknowledgement Response Return Code - Basic (from projector to PC/controller)
40 - (ASCII: "@") Acknowledgement Response Return Code - Detailed (from projector to PC/controller)

Unit ID
This is fixed at 89 01 for all models.
"""

UNIT_ID = '8901'
END = '0A'
OPE = '21'
REQ = '3F'
ACK = '06'

""" JVC custom gamma tables for
GA_CUSTOM1 = operation to switch to gamma custom 1
GA_CUSTOM2 = operation to switch to gamma custom 2
GA_CUSTOM3 = operation to switch to gamma custom 3

GA_CI_MPORT = operation to switch to import table (needed to transfer gammatable)

PMGammaRd = Gamma Red data table transfer activation
PMGammaGr = Gamma Green data table transfer activation
PMGammaBl = Gamma Blue data table transfer activation
"""

GA_CUSTOM1 = '218901504D4754340A'
GA_CUSTOM2 = '218901504D4754350A'
GA_CUSTOM3 = '218901504D4754360A'

GA_C_IMPORT = '218901504D474330340A'

PMGammaRd = '218901504D44520A'
PMGammaGr = '218901504D44470A'
PMGammaBl = '218901504D44420A'


class Error(Exception):
    """Error"""
    pass


class Closed(Exception):
    """Connection Closed"""
    pass


class Timeout(Exception):
    """Command Timout"""
    pass


class CommandNack(Exception):
    """JVC command not acknowledged"""
    pass


class JVC_DILA_Control(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION='1.0.0'


    def __init__(self, smarthome, host='0.0.0.0', gammaconf_dir='/usr/local/smarthome/etc/jvcproj/'):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        :param host:               JVC DILA Projectors IP address
        :param gammaconf_dir:      location where the gamma.conf files are saved
        :port is fixed to 20554
        """
        self.logger = logging.getLogger(__name__)
        self._sh=smarthome
        self.host_port = (host, 20554))
        self.gammaconf_dir = gammaconf_dir
        self.logger.debug("Plugin '{}': configured for host: '{}'".format(self.get_fullname(), self.host_port))

    def run(self):
        """
        Run method for the plugin - called once to start the plugins processing
        """        
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
        self.alive = False

    def parse_item(self, item):
        """
        Plugin's parse_item method. Is called for every item when the plugin is initialized.
        
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        # normal items
        if self.has_iattr(item.conf, "jvcproj_cmd"):
            self.logger.debug("Plugin '{}': Item '{}' with value '{}' found!"
                              .format(self.get_fullname(), item, self.get_iattr_value(item.conf, 'jvcproj_cmd')))
            return self.update_item
        if self.has_iattr(item.conf, "jvcproj_gamma"):
            self.logger.debug("Plugin '{}': Item '{}' with value '{}' found!"
                              .format(self.get_fullname(), item, self.get_iattr_value(item.conf, 'jvcproj_gamma')))
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if item():
            if self.has_iattr(item.conf, 'jvcproj_cmd'):
                if self.get_iattr_value(item.conf, 'jvcproj_cmd') == 'None':
                    self.logger.debug("Plugin '{}': no command given for update_item '{}'. Please check jvcproj_cmd!"
                                      .format(self.get_fullname(), item))
                    return
                else:
                    self.logger.debug("Plugin '{}': update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'"
                                      .format(self.get_fullname(), item, caller, source, dest))
                self.check_cmd(item)
            elif self.has_iattr(item.conf, 'jvcproj_gamma'):
                if self.get_iattr_value(item.conf, 'jvcproj_gamma') == 'None':
                    self.logger.debug("Plugin '{}': no command given for update_item '{}'. Please check jvcproj_gamma!"
                                      .format(self.get_fullname(), item))
                    return
                else:
                    self.logger.debug("Plugin '{}': update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'"
                                      .format(self.get_fullname(), item, caller, source, dest))
                self.check_gamma_cmd(item)


    def check_gamma_cmd(self, item):
        """check gamma options to import new gammatable"""
        self.logger.debug("Plugin '{}': checking for gamma.conf an correct gamma input (must a custom gammatable) in '{}' : '{}'."
                          .format(self.get_fullname(), item, self.get_iattr_value(item.conf, 'jvcproj_gamma')))
        _checklist = (self.get_iattr_value(item.conf, 'jvcproj_gamma').replace(' ','')).split('|')
        if len(_checklist) != 2:
            self.logger.debug("Plugin '{}': ERROR! Item:'{}': exactly two arguments (file and custom gamma table) must be given!"
                              .format(self.get_fullname(), item))
            return
        _cmdlist=[]
        if self.gammaconf_dir[-1] != '/':
            self.gammaconf_dir = self.gammaconf_dir + '/'
        if os_path.isfile(self.gammaconf_dir + _checklist[0]) is False:
            self.logger.debug("Plugin '{}': ERROR! Gamma configuration file declared in item:'{}' not found."
                              .format(self.get_fullname(), item))
            return
        _cmdlist.append(self.gammaconf_dir + _checklist[0])
        if _checklist[1].upper() == 'CUSTOM1' or _checklist[1].upper() == GA_CUSTOM1:
            _cmdlist.append(GA_CUSTOM1)
        elif _checklist[1].upper() == 'CUSTOM2' or _checklist[1].upper() == GA_CUSTOM2:
            _cmdlist.append(GA_CUSTOM2)
        elif _checklist[1].upper() == 'CUSTOM3' or _checklist[1].upper() == GA_CUSTOM3:
            _cmdlist.append(GA_CUSTOM3)
        else:
            self.logger.debug("Plugin '{}': ERROR! No valid custom gamma table declared in item:'{}'."
                              .format(self.get_fullname(), item))
            return
        self.handleconn_gamma(_cmdlist)

    def handleconn_gamma(self, data):
        """handle connection and sending commands for jvcproj_gamma"""
        table = self.load_table(data[0])
        gammadata = self.check_gammadata(table)
        if gammadata is None:
            self.logger.debug("Plugin '{}': ERROR! No valid gammadata found in file. Aborting..."
                              .format(self.get_fullname()))
            return
        self.connect()
        self.logger.debug("Plugin '{}': set declared custom gamma table"
                          .format(self.get_fullname()))
        self.set(data[1])
        self.logger.debug("Plugin '{}': set gamma correction to import value"
                          .format(self.get_fullname()))
        self.set(GA_C_IMPORT)
        self.write_gammadata(gammadata)
        self.logger.debug("Plugin '{}': finished! Now disconnecting!"
                          .format(self.get_fullname()))
        self.disconnect()

    def load_table(self, data):
        """Load raw gamme table from declared file"""
        with open(data, 'r') as file:
            table = json.load(file).get('table')
            return table

    def check_gammadata(self, table):
        """Check gamma data from file"""
        gammadata = table
        if gammadata is None :
            return None
        if len(gammadata) == 256:
            gammadata = [gammadata, gammadata, gammadata]
        elif len(gammadata) == 3:
            if not len(gammadata[0]) == 256 or not len(gammadata[1]) == 256 or not len(gammadata[2]) == 256:
                return None
        else:
            return None
        return gammadata

    def write_gammadata(self, gammadata):
        """Write gamma data to the projector"""
        for colorcmd, colortable in zip([PMGammaRd, PMGammaGr, PMGammaBl], gammadata):
            self.set(colorcmd)
            self.send(bytes(self.le16_split(colortable)))
            self.expect(binascii.a2b_hex(ACK + colorcmd[2:10] + END), timeout=20)

    def le16_split(self, colortable):
        """Split table entries 16bit little-endian byte pairs"""
        for val in colortable:
            assert not val >> 16
            yield val % 256
            yield int(val / 256)


    def check_cmd(self, item):
        """create command list and execute low level string validation for each command"""
        self.logger.debug("Plugin '{}': create commandlist for item '{}' : '{}' and check command(s)."
                          .format(self.get_fullname(), item, self.get_iattr_value(item.conf, 'jvcproj_cmd')))
        _checklist = (self.get_iattr_value(item.conf, 'jvcproj_cmd').replace(' ','')).split('|')
        _cmdlist = []
        for _cmd in _checklist:
            if _cmd.upper()[2:6] == UNIT_ID and _cmd.upper()[-2:] == END:
                if _cmd.upper()[:2] == OPE or _cmd.upper()[:2] == REQ:
                    self.logger.debug("Plugin '{}': adding command '{}' to execution list."
                                      .format(self.get_fullname(), _cmd.upper()))
                    _cmdlist.append(_cmd.upper())
                else:
                    self.logger.debug("Plugin '{}': ERROR! Invalid Header found in command '{}'! Must be '{}' or '{}' !"
                                      .format(self.get_fullname(), _cmd.upper(), OPE, REQ))
            else:
                self.logger.debug("Plugin '{}': ERROR! Invalid UNIT-ID or END found in command '{}'! UNIT-ID must be '{}'! END must be '{}' !"
                                  .format(self.get_fullname(), _cmd.upper(), UNIT_ID, END))
        if _cmdlist ==[]:
            self.logger.debug("Plugin '{}': nothing to send..."
                              .format(self.get_fullname()))
            return
        self.handleconn_op(_cmdlist)

    def handleconn_op(self, cmdlist):
        """handle connection and sending commands for jvcproj_cmd"""
        self.connect()
        for cmd in cmdlist:
            if cmd[:2] == REQ: ##maybe in the future??
                self.logger.debug("Plugin '{}': WARNING! A request is not yet supported!"
                                  .format(self.get_fullname()))
            elif cmd[:2] == OPE:
                self.logger.debug("Plugin '{}': sending command '{}' to '{}'"
                                  .format(self.get_fullname(), cmd, self.host_port))
                self.set(cmd)
                self.logger.debug("Plugin '{}': operation command '{}' sent successfully!"
                                  .format(self.get_fullname(), cmd))
        self.disconnect('finished! Now disconnecting!')


    def connect(self):
        """Open network connection to projector and perform handshake"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.debug("Plugin '{}': Connecting to host: '{}'!"
                          .format(self.get_fullname(), self.host_port))
        try:
            self.socket.connect(self.host_port)
        except Exception as err:
            self.disconnect('ERROR! Connection failed!')
            raise Error('Connection failed', err)
        self.expect(b'PJ_OK')
        self.send(b'PJREQ')
        self.expect(b'PJACK')
        self.logger.debug("Plugin '{}': handshake with host: '{}' completed."
                          .format(self.get_fullname(), self.host_port))

    def set(self, cmd):
        try:
            self.send(binascii.a2b_hex(cmd))
            self.expect(binascii.a2b_hex(ACK + cmd[2:10] + END))
        except Timeout:
                self.disconnect('ERROR! Command not acknowledged! Aborting!')
                raise CommandNack('Command not acknowledged', cmd)

    def get(self):
        pass

    def disconnect(self, message ='disconnecting...'):
        """Close socket"""
        self.logger.debug("Plugin '{}': {}"
                          .format(self.get_fullname(), message))
        self.socket.close()

    def send(self, data):
        """Send data with optional"""
        try:
            self.socket.send(data)
        except ConnectionAbortedError as err:
            raise Closed(err)

    def recv(self, limit=1024, timeout=0):
        """Receive data with optional timeout"""
        if timeout:
            ready = select.select([self.socket], [], [], timeout)
            if not ready[0]:
                raise Timeout('{} second timeout expired'.format(timeout))
        data = self.socket.recv(limit)
        if not len(data):
            self.disconnect('ERROR! Connection closed by projector! Aborting!')
            raise Closed('Connection closed by projector')
        return data

    def expect(self, res, timeout=10):
        """Receive data and compare it against expected data"""
        data = self.recv(len(res), timeout)
        if data != res:
            self.disconnect('ERROR! Expected data is not equal to received data! Aborting!')
            raise Error('Expected', res)
