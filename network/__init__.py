#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Marcus Popp                         marcus@popp.mx
#  Copyright 2020- Sebastian Helms                  Morg @ knx-user-forum
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
import urllib.parse
import lib.network

from lib.model.smartplugin import SmartPlugin

# attribute keywords
NW              = 'nw'
NW_ACL          = 'nw_acl'
NW_UDP_LISTEN   = 'nw_udp_listen'
NW_TCP_LISTEN   = 'nw_tcp_listen'
NW_HTTP_LISTEN  = 'nw_http_listen'
NW_UDP_SEND     = 'nw_udp_send'


class TCPDispatcher(lib.network.Tcp_server):
    '''
    Encapsulation class for using lib.network.Tcp_server class
    '''
    def __init__(self, parser, ip, port, plugin_name):
        '''
        Initializes the class

        :param parser: callback function for handling data, called as parser(remoteip, 'tcp:<localip>:<localport>', '<data>')
        :type parser: function
        :param ip: local ip address to bind to
        :type ip: str
        :param port: local port to bind to
        :type port: int
        '''
        self.dest = f'tcp:{ip}:{port}'
        super().__init__(port, ip, 'plugins.' + plugin_name + '_' + self.dest, b'\n')
        self.parser = parser
        self.set_callbacks(data_received=self.handle_received_data, incoming_connection=self.handle_connection)

    def handle_connection(self, server, client):
        '''
        Handle incoming connection. Just used for debugging

        :param server: Tcp_server object serving the connection
        :type server: lib.network.Tcp_server
        :param client: Client object for connection
        :type client: lib.network.Client
        '''
        self.logger.debug(f'Incoming TCP connection from {client.name}')

    def handle_received_data(self, server, client, data):
        '''
        Forward received data to parser callback

        :param server: Tcp_server object serving the connection
        :type server: lib.network.Tcp_server
        :param client: Client object for connection
        :type addr: lib.network.Client
        :param data: received data
        :type data: string
        '''
        self.logger.debug(f'Received packet from {client.ip}:{client.port} to {self.dest} with content "{data}"')
        self.parser(client.ip, self.dest, data.strip())


class HTTPDispatcher(lib.network.Tcp_server):
    '''
    Encapsulation class for using lib.network.Tcp_server class with HTTP GET support
    '''
    def __init__(self, parser, ip, port, plugin_name):
        '''
        Initializes the class

        :param parser: callback function for handling data, called as parser(remoteip, 'tcp:<localip>:<localport>', '<data>')
        :type parser: function
        :param ip: local ip address to bind to
        :type ip: str
        :param port: local port to bind to
        :type port: int
        '''

        self.dest = f'http:{ip}:{port}'
        super().__init__(port, ip, 'plugins.' + plugin_name + '_' + self.dest, b'\n')
        self.parser = parser
        self.set_callbacks(data_received=self.handle_received_data, incoming_connection=self.handle_connection)

    def handle_connection(self, server, client):
        '''
        Handle incoming connection. Just used for debugging

        :param server: Tcp_server object serving the connection
        :type server: lib.network.Tcp_server
        :param client: Client object for connection
        :type client: lib.network.Client
        '''
        self.logger.debug(f'Incoming HTTP connection from {client.name}')

    def handle_received_data(self, server, client, data):
        '''
        Forward received data to parser callback

        :param server: Tcp_server object serving the connection
        :type server: lib.network.Tcp_server
        :param client: Client object for connection
        :type addr: lib.network.Client
        :param data: received data
        :type data: string
        '''
        self.logger.debug(f'Received packet from {client.ip}:{client.port} to {self.dest} via HTTP with content: "{data}"')

        # find lines starting with GET or POST and return remaining lines "HTTP-like" and return status
        data_lines = data.splitlines()
        for line in data_lines:
            if line.startswith('GET'):
                request = line.split(' ')[1].strip('/')
                if self.parser(client.ip, self.dest, urllib.parse.unquote(request)) is not False:
                    client.send(b'HTTP/1.1 200 OK\r\n\r\n')
                else:
                    client.send(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                client.close()
            elif line.startswith('POST'):
                #lines 0 - 5 contain the http post header. The data string begins with in line 6:
                request = data_lines[6]
                self.logger.debug(f'POST datastring: {request}')
                if self.parser(client.ip, self.dest, urllib.parse.unquote(request)) is not False:
                    client.send(b'HTTP/1.1 200 OK\r\n\r\n')
                else:
                    client.send(b'HTTP/1.1 400 Bad Request\r\n\r\n')
                client.close()



class UDPDispatcher(lib.network.Udp_server):
    '''
    Encapsulation class for using lib.network.Udp_server class
    '''
    def __init__(self, parser, ip, port, plugin_name):
        '''
        Initializes the class

        :param parser: callback function for handling data, called as parser(remoteip, 'tcp:<localip>:<localport>', '<data>')
        :type parser: function
        :param ip: local ip address to bind to
        :type ip: str
        :param port: local port to bind to
        :type port: int
        '''
        self.logger = logging.getLogger(__name__)
        self.parser = parser
        self.dest = f'udp:{ip}:{port}'
        super().__init__(port, ip, 'plugins.' + plugin_name + '_' + self.dest)
        self.set_callbacks(data_received=self.handle_received_data)

    def handle_received_data(self, addr, data):
        '''
        Forward received data to parser callback

        :param addr: address information about the remote client: ('<ip>', <port>)
        :type addr: tuple
        :param data: received data
        :type data: string
        '''
        ip = addr[0]
        addr = f'{addr[0]}:{addr[1]}'
        self.logger.debug(f'{self.name}: incoming connection from {addr} to {self.dest}')
        self.parser(ip, self.dest, data.strip())


class Network(SmartPlugin):
    '''
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    '''
    PLUGIN_VERSION = '1.6.2'

    generic_listeners = {}
    special_listeners = {}
    input_seperator = '|'
    socket_warning = 10
    socket_warning = 2
    _dispatcher_list = []

    def __init__(self, sh):
        '''
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        '''

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.tcp_acl = self.parse_acl(self.get_parameter_value('tcp_acl'))
        self.udp_acl = self.parse_acl(self.get_parameter_value('udp_acl'))
        self.http_acl = self.parse_acl(self.get_parameter_value('http_acl'))

        if self.get_parameter_value('tcp'):
            self.add_listener('tcp', self.get_parameter_value('ip'), self.get_parameter_value('port'), self.tcp_acl,
                              generic=True)
        if self.get_parameter_value('udp'):
            self.add_listener('udp', self.get_parameter_value('ip'), self.get_parameter_value('port'), self.udp_acl,
                              generic=True)
        http_param = self.get_parameter_value('http')
        if str(http_param).isnumeric():
            self.add_listener('http', self.get_parameter_value('ip'), http_param, self.http_acl,
                              generic=True)
        elif str(http_param).lower() in ('yes', 'true'):
            self.logger.warning(f'http parameter must be "no" or <port number>, but it is set to "{http_param}". HTTP listener not enabled.')

    def udp(self, host, port, data):
        '''
        This function writes given data to a host with specified port

        :param host: a host or an ip for destination
        :param port: a port number
        :param data: a string containing data
        '''
        try:
            family, type, proto, canonname, sockaddr = socket.getaddrinfo(host, port)[0]
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.sendto(data.encode(), (sockaddr[0], sockaddr[1]))
            sock.close()
            del (sock)
        except Exception as e:
            self.logger.warning(f'UDP: Problem sending data to {host}:{port}: {e}')
            pass
        else:
            self.logger.debug(f'UDP: Sending data to {host}:{port}: {data}')

    def add_listener(self, proto, ip, port, acl='*', generic=False):
        port = int(port)
        dest = f'{proto}:{ip}:{port}'
        self.logger.debug(f'Adding listener on: {dest}')
        if proto == 'tcp':
            dispatcher = TCPDispatcher(self.parse_input, ip, port, self.get_fullname())
        elif proto == 'udp':
            dispatcher = UDPDispatcher(self.parse_input, ip, port, self.get_fullname())
        elif proto == 'http':
            dispatcher = HTTPDispatcher(self.parse_input, ip, port, self.get_fullname())
        else:
            self.logger.error(f'Cannot add listener as protocol {proto} is not supported')
            return

        self._dispatcher_list.append(dispatcher)

        acl = self.parse_acl(acl)
        if generic:
            self.generic_listeners[dest] = {'items': {}, 'logics': {}, 'acl': acl}
        else:
            self.special_listeners[dest] = {'items': {}, 'logics': {}, 'acl': acl}
        return True

    def parse_acl(self, acl):
        '''
        Parse an acl which can contain either
            '*' which means accept data from all connection requests or
            a list of one or more ip which are allowed to connect
        '''
        self.logger.debug(f'parse_acl called with acl={acl}')
        if acl == ['*']:
            return False
        if isinstance(acl, str):
            return [acl]
        return acl

    def parse_input(self, source, dest, data):
        '''
        :param: source      # '<remoteip>:<port>' or '<remoteip>'
        :param: dest        # '<proto>:<localip>:<port>'
        :param: data either
                        * `item|<item.path>|<value>`
                        * `logic|<logic_name>|<value>`
                        * `log|<loglevel>|message`  # loglevel could be info, warning or error
        '''
        #self.logger.debug(f'parse_input called with source={source}, dest={dest} and data={data}')
        proto = dest.split(':')[0].upper()
        source_ip, __, __ = source.partition(':')
        if dest in self.generic_listeners:
            # decode data
            data_list = data.split(self.input_seperator, 2)  # max 3 elements
            if len(data_list) < 3:
                self.logger.info(f'Ignoring input {data}. Format not recognized.')
                return False
            typ, name, value = data_list
            gacl = self.generic_listeners[dest]['acl']

            if typ == 'item':
                if name not in self.generic_listeners[dest]['items']:
                    self.logger.error(f'Item {name} not available in the generic listener.')
                    return False
                iacl = self.generic_listeners[dest]['items'][name]['acl']
                if iacl:
                    if source_ip not in iacl:
                        self.logger.error(f'Item {name} acl doesn\'t permit updates from {source_ip}.')
                        return False
                elif gacl:
                    if source_ip not in gacl:
                        self.logger.error(f'Generic network acl doesn\'t permit updates from {source_ip}.')
                        return False
                item = self.generic_listeners[dest]['items'][name]['item']
                self.logger.info(f'generic_listeners: Setting {item} to {value} (from {proto}:{source_ip})')
                item(value, proto, source_ip)

            elif typ == 'logic':
                if name not in self.generic_listeners[dest]['logics']:
                    self.logger.error(f'Logic {name} not available in the generic listener.')
                    return False
                lacl = self.generic_listeners[dest]['logics'][name]['acl']
                if lacl:
                    if source_ip not in lacl:
                        self.logger.error(f'Logic {name} acl doesn\'t permit triggering from {source_ip}.')
                        return False
                elif gacl:
                    if source_ip not in gacl:
                        self.logger.error(f'Generic network acl doesn\'t permit triggering from {source_ip}.')
                        return False
                logic = self.generic_listeners[dest]['logics'][name]['logic']
                logic.trigger(proto, source_ip, value)

            elif typ == 'log':
                if gacl:
                    if source_ip not in gacl:
                        self.logger.error(f'Generic network acl doesn\'t permit log entries from {source_ip}')
                        return False
                if name == 'info':
                    self.logger.info(value)
                elif name == 'warning':
                    self.logger.warning(value)
                elif name == 'error':
                    self.logger.error(value)
                else:
                    self.logger.warning(f'Unknown logging priority {name}. Data: {data}')
            else:
                self.logger.error(f'Unsupported key element {typ}. Data: {data}')
                return False

        elif dest in self.special_listeners:
            proto, t1, t2 = dest.partition(':')
            if proto == 'udp':
                gacl = self.udp_acl
            elif proto == 'tcp':
                gacl = self.tcp_acl
            elif proto == 'http':
                gacl = self.http_acl
            else:
                self.logger.warning(f'Protocall {proto} is not supported. Aborting.')
                return
            for entry in self.special_listeners[dest]['logics']:
                lacl = self.special_listeners[dest]['logics'][entry]['acl']
                logic = self.special_listeners[dest]['logics'][entry]['logic']
                if lacl:
                    if source_ip not in lacl:
                        self.logger.error(f'Logic {logic.name} acl doesn\'t permit triggering from {source_ip}.')
                        return False
                elif gacl:
                    if source_ip not in gacl:
                        self.logger.error(f'Generic network acl doesn\'t permit triggering from {source_ip}.')
                        return False
                logic.trigger('network', source_ip, data)
            for entry in self.special_listeners[dest]['items']:
                lacl = self.special_listeners[dest]['items'][entry]['acl']
                item = self.special_listeners[dest]['items'][entry]['item']
                if lacl:
                    if source_ip not in lacl:
                        self.logger.error(f'Item {item.id()} acl doesn\'t permit triggering from {source_ip}.')
                        return False
                elif gacl:
                    if source_ip not in gacl:
                        self.logger.error(f'Generic network acl doesn\'t permit triggering from {source_ip}.')
                        return False
                self.logger.debug(f'special_listeners: Setting {item} to {data} (from {proto}:{source_ip})')
                item(data, 'network', source_ip)
        else:
            self.logger.error(f'Destination {dest}, not in listeners!')
            return False
        return True

    def run(self):
        '''
        Run method for the plugin
        '''
        self.logger.debug('Run method called')
        self.alive = True
        for listener in self._dispatcher_list:
            listener.start()
            if not listener.listening():
                self.logger.error(f'Server {listener.name} did not start properly.')

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.logger.debug('Stop method called')
        for listener in self._dispatcher_list:
            try:  # keep some ugly errors on keyboard interrupt hidden
                listener.close()
            except:
                pass
        self._dispatcher_list = []
        self.alive = False

    def parse_logic(self, logic):
        '''
        Called when the plugin is initialized to parse a logic
        '''
        self.parse_obj(logic, 'logic')

    def parse_item(self, item):
        '''
        This is called when the plugin is initialized and
        a param item is given to decide wether to act on it or not
        '''
        self.parse_obj(item, 'item')

        if self.has_iattr(item.conf, NW_UDP_SEND):
            self.logger.debug(f'parse item: {item}')
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        '''
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        '''
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info(f'Update item: {item.id()}, item has been changed outside this plugin')

            if self.has_iattr(item.conf, NW_UDP_SEND):
                # nw_udp_send: '11.11.11.11:7777=command: itemvalue'    ## sends an UDP packet with 'command: ' and the current item value as payload
                # instead of 'command' any text may be chosen. If somewhere right from equal sign
                # the word ``itemvalue``` appears, it will be replaced by the items value
                addr, __, message = self.get_iattr_value(item.conf, NW_UDP_SEND).partition('=')
                if not message:
                    message = str(item())
                else:
                    message = message.replace('itemvalue', str(item()))
                host, __, port = addr.partition(':')
                self.udp(host, port, message)

    def parse_obj(self, obj, obj_type):
        '''
        parses either an item with item.conf or a logic with logic.conf
        '''
        # NW_ACL, NW_UDP, NW_TCP
        if obj_type in ('item', 'logic'):
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
            self.logger.debug(f'Adding listener {dest} for item {oid}')
            if dest not in self.special_listeners:
                if self.add_listener('udp', ip, port):
                    self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}
                else:
                    self.logger.warning(f'Could not add listener {dest} for {oid}')
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
                    self.logger.warning(f'Could not add listener {dest} for {oid}')
            else:
                self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}

        if NW_HTTP_LISTEN in obj.conf:
            ip, sep, port = obj.conf[NW_HTTP_LISTEN].rpartition(':')
            if not ip:
                ip = '0.0.0.0'
            dest = 'http:' + ip + ':' + port
            if dest not in self.special_listeners:
                if self.add_listener('http', ip, port):
                    self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}
                else:
                    self.logger.warning(f'Could not add listener {dest} for {oid}')
            else:
                self.special_listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}

