#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Marcus Popp                         marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#########################################################################

import logging
import socket
import urllib.request
import urllib.parse
import urllib.error
#import lib.network to come soon, tidy up and document first
import lib.connection

from lib.model.smartplugin import SmartPlugin

# attribute keywords
NW              = 'nw'
NW_ACL          = 'nw_acl'
NW_UDP_LISTEN   = 'nw_udp_listen'
NW_TCP_LISTEN   = 'nw_tcp_listen'
NW_UDP_SEND     = 'nw_udp_send'


class TCPHandler(lib.connection.Stream):

    def __init__(self, parser, dest, sock, source):
        lib.connection.Stream.__init__(self, sock, source)
        self.terminator = b'\n'
        self.parser = parser
        self.dest = dest
        self.source = source

    def found_terminator(self, data):
        self.parser(self.source, self.dest, data.decode(errors="ignore").strip())
        self.close()


class TCPDispatcher(lib.connection.Server):

    def __init__(self, parser, ip, port):
        lib.connection.Server.__init__(self, ip, port)
        self.parser = parser
        self.dest = "tcp:%s:%s" % (ip, port)
        self.connect()

    def handle_connection(self):
        sock, address = self.accept()
        if sock is None:
            return
        TCPHandler(self.parser, self.dest, sock, address)


class HTTPHandler(lib.connection.Stream):

    def __init__(self, parser, dest, sock, source):
        lib.connection.Stream.__init__(self, sock, source)
        self.terminator = b"\r\n\r\n"
        self.parser = parser
        self.dest = dest
        self.source = source

    def found_terminator(self, data):
        for line in data.decode(errors="ignore").splitlines():
            if line.startswith('GET'):
                request = line.split(' ')[1].strip('/')
                if self.parser(self.source, self.dest, urllib.parse.unquote(request)) is not False:
                    self.send(b'HTTP/1.1 200 OK\r\n\r\n', close=True)
                else:
                    self.send(b'HTTP/1.1 400 Bad Request\r\n\r\n', close=True)
                break


class HTTPDispatcher(lib.connection.Server):

    def __init__(self, parser, ip, port):
        lib.connection.Server.__init__(self, ip, port)
        self.parser = parser
        self.dest = "http:%s:%s" % (ip, port)
        self.connect()

    def handle_connection(self):
        sock, address = self.accept()
        if sock is None:
            return
        HTTPHandler(self.parser, self.dest, sock, address)


class UDPDispatcher(lib.connection.Server):

    def __init__(self, parser, ip, port):
        self.logger = logging.getLogger(__name__)
        lib.connection.Server.__init__(self, ip, port, proto='UDP')
        self.dest = "udp:%s:%s" % (ip, port)
        self.parser = parser
        self.connect()

    def handle_connection(self):
        try:
            data, addr = self.socket.recvfrom(4096)
            ip = addr[0]
            addr = "{}:{}".format(addr[0], addr[1])
            self.logger.debug("{}: incoming connection from {} to {}".format(self._name, addr, self.address))
        except Exception as e:
            self.logger.exception("{}: {}".format(self._name, e))
            return
        self.parser(ip, self.dest, data.decode(errors="ignore").strip())


class Network(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    PLUGIN_VERSION = "1.4.1"

    generic_listeners = {}
    special_listeners = {}
    input_seperator = '|'
    socket_warning = 10
    socket_warning = 2

    def __init__(self, sh ):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.tcp_acl = self.parse_acl(self.get_parameter_value('tcp_acl'))
        self.udp_acl = self.parse_acl(self.get_parameter_value('udp_acl'))
        self.http_acl = self.parse_acl(self.get_parameter_value('http_acl'))
        if self.get_parameter_value('tcp') == 'yes':
            self.add_listener('tcp', self.get_parameter_value('ip'), self.get_parameter_value('port'), self.tcp_acl,
                              generic=True)
        if self.get_parameter_value('udp') == 'yes':
            self.add_listener('udp', self.get_parameter_value('ip'), self.get_parameter_value('port'), self.udp_acl,
                              generic=True)
        if self.get_parameter_value('http') != 'no':
            self.add_listener('http', self.get_parameter_value('ip'), self.get_parameter_value('http'), self.http_acl,
                              generic=True)

    def udp(self, host, port, data):
        """
        This function writes given data to a host with specified port

        :param host: a host or an ip for destination
        :param port: a port number
        :param data: a string containing data
        """
        try:
            family, type, proto, canonname, sockaddr = socket.getaddrinfo(host, port)[0]
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data.encode(), (sockaddr[0], sockaddr[1]))
            sock.close()
            del (sock)
        except Exception as e:
            self.logger.warning("UDP: Problem sending data to {}:{}: {}".format(host, port, e))
            pass
        else:
            self.logger.debug("UDP: Sending data to {}:{}: {}".format(host, port, data))

    def add_listener(self, proto, ip, port, acl='*', generic=False):
        dest = "%s:%s:%s" % (proto, ip, port)
        self.logger.debug("Adding listener on: {}".format(dest))
        if proto == 'tcp':
            dispatcher = TCPDispatcher(self.parse_input, ip, port)
        elif proto == 'udp':
            dispatcher = UDPDispatcher(self.parse_input, ip, port)
        elif proto == 'http':
            dispatcher = HTTPDispatcher(self.parse_input, ip, port)
        else:
            return

        if not dispatcher.connected:
            return False

        acl = self.parse_acl(acl)
        if generic:
            self.generic_listeners[dest] = {'items': {}, 'logics': {}, 'acl': acl}
        else:
            self.special_listeners[dest] = {'items': {}, 'logics': {}, 'acl': acl}
        return True

    def parse_acl(self, acl):
        """
        Parse an acl which can contain either
            '*' which means accept data from all connection requests or
            a list of one or more ip which are allowed to connect
        """
        self.logger.debug("parse_acl called with acl='{}'".format(acl))
        if acl == ['*']:
            return False
        if isinstance(acl, str):
            return [acl]
        return acl

    def parse_input(self, source, dest, data):
        """
        :param: source
        :param: dest
        :param: data either
                        * `item|item.path|value`
                        * `logic|logic_name|value`
                        * `log|loglevel|message` # loglevel could be info, warning or error
        """
        self.logger.debug("parse_input called with source={}, dest={} and data={}".format(source, dest, data))
        if dest in self.generic_listeners:
            inp = data.split(self.input_seperator, 2)  # max 3 elements
            if len(inp) < 3:
                self.logger.info("Ignoring input {}. Format not recognized.".format(data))
                return False
            typ, name, value = inp
            proto = dest.split(':')[0].upper()
            source, __, port = source.partition(':')
            gacl = self.generic_listeners[dest]['acl']

            if typ == 'item':
                if name not in self.generic_listeners[dest]['items']:
                    self.logger.error("Item '{}' not available in the generic listener.".format(name))
                    return False
                iacl = self.generic_listeners[dest]['items'][name]['acl']
                if iacl:
                    if source not in iacl:
                        self.logger.error("Item '{}' acl doesn't permit updates from {}.".format(name, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("Generic network acl doesn't permit updates from {}.".format(source))
                        return False
                item = self.generic_listeners[dest]['items'][name]['item']
                item(value, proto, source)

            elif typ == 'logic':
                if name not in self.generic_listeners[dest]['logics']:
                    self.logger.error("Logic '{}' not available in the generic listener.".format(name))
                    return False
                lacl = self.generic_listeners[dest]['logics'][name]['acl']
                if lacl:
                    if source not in lacl:
                        self.logger.error("Logic '{}' acl doesn't permit triggering from {}.".format(name, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("Generic network acl doesn't permit triggering from {}.".format(source))
                        return False
                logic = self.generic_listeners[dest]['logics'][name]['logic']
                logic.trigger(proto, source, value)

            elif typ == 'log':
                if gacl:
                    if source not in gacl:
                        self.logger.error("Generic network acl doesn't permit log entries from {}".format(source))
                        return False
                if name == 'info':
                    self.logger.info(value)
                elif name == 'warning':
                    self.logger.warning(value)
                elif name == 'error':
                    self.logger.error(value)
                else:
                    self.logger.warning("Unknown logging priority '{}'. Data: '{}'".format(name, data))
            else:
                self.logger.error("Unsupporter key element {}. Data: {}".format(typ, data))
                return False

        elif dest in self.special_listeners:
            proto, t1, t2 = dest.partition(':')
            if proto == 'udp':
                gacl = self.udp_acl
            elif proto == 'tcp':
                gacl = self.tcp_acl
            else:
                return
            for entry in self.special_listeners[dest]['logics']:
                lacl = self.special_listeners[dest]['logics'][entry]['acl']
                logic = self.special_listeners[dest]['logics'][entry]['logic']
                if lacl:
                    if source not in lacl:
                        self.logger.error(
                            "Logic '{}' acl doesn't permit triggering from {}.".format(logic.name, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("Generic network acl doesn't permit triggering from {}.".format(source))
                        return False
                logic.trigger('network', source, data)
            for entry in self.special_listeners[dest]['items']:
                lacl = self.special_listeners[dest]['items'][entry]['acl']
                item = self.special_listeners[dest]['items'][entry]['item']
                if lacl:
                    if source not in lacl:
                        self.logger.error("Item {0} acl doesn't permit triggering from {1}.".format(item.property.path, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("Generic network acl doesn't permit triggering from {0}.".format(source))
                        return False
                item(data, 'network', source)
        else:
            self.logger.error("Destination {}, not in listeners!".format(dest))
            return False
        return True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_logic(self, logic):
        """
        Called when the plugin is initialized to parse a logic
        """
        self.parse_obj(logic, 'logic')

    def parse_item(self, item):
        """
        This is called when the plugin is initialized and 
        a param item is given to decide wether to act on it or not
        """
        self.parse_obj(item, 'item')

        if self.has_iattr(item.conf, NW_UDP_SEND):
            self.logger.debug("parse item: {}".format(item))
            return self.update_item


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))

            if self.has_iattr(item.conf, NW_UDP_SEND):
                # nw_udp_send: "11.11.11.11:7777=command: itemvalue"    ## sends an UDP packet with 'command: ' and the current item value as payload
                # instead of "command" any text may be chosen. If somewhere right from equal sign
                # the word ``itemvalue``` appears, it will be replaced by the items value
                addr, __, message = self.get_iattr_value(item.conf, NW_UDP_SEND).partition('=')
                if not message:
                    message = str(item())
                else:
                    message = message.replace('itemvalue', str(item()))
                host, __, port = addr.partition(':')
                self.udp(host, port, message)

    def parse_obj(self, obj, obj_type):
        """
        parses either an item with item.conf or a logic with logic.conf
        """
        # NW_ACL, NW_UDP, NW_TCP
        if obj_type == 'item':
            oid = obj.id()
        elif obj_type == 'logic':
            oid = obj.id()
        else:
            return

        if NW_ACL in obj.conf:
            acl = obj.conf[NW_ACL]
        else:
            acl = False

        if NW in obj.conf:  # adding object to generic listeners
            if self.to_bool(obj.conf[NW]):
                for dest in self.generic_listeners:
                    self.generic_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}

        if NW_UDP_LISTEN in obj.conf:
            ip, sep, port = obj.conf[NW_UDP_LISTEN].rpartition(':')
            if not ip:
                ip = '0.0.0.0'
            dest = 'udp:' + ip + ':' + port
            if dest not in self.special_listeners:
                if self.add_listener('udp', ip, port):
                    self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}
                else:
                    self.logger.warning("Could not add listener {} for {}".format(dest, oid))
            else:
                self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}

        if NW_TCP_LISTEN in obj.conf:
            ip, sep, port = obj.conf[NW_TCP_LISTEN].rpartition(':')
            if not ip:
                ip = '0.0.0.0'
            dest = 'tcp:' + ip + ':' + port
            if dest not in self.special_listeners:
                if self.add_listener('tcp', ip, port):
                    self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}
                else:
                    self.logger.warning("Could not add listener {} for {}".format(dest, oid))
            else:
                self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}
