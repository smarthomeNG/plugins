#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016- Martin Sinn                              m.sinn@gmx.de
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.  
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
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

import base64
import datetime
import decimal
import hashlib
import json
import logging
import struct
import ssl
import struct
import threading

import collections

import lib.connection
from lib.model.smartplugin import SmartPlugin


#########################################################################

class WebSocket(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = "1.4.4"


    def __init__(self, sh, *args, **kwargs):
#    def __init__(self, smarthome, ip='0.0.0.0', port=2424, tls='no', acl='ro', wsproto='3' ):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.
        
        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are implemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method `get_parameter_value(parameter_name)` instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling `self.get_parameter_value(parameter_name)`. It
        returns the value in the datatype that is defined in the metadata.
        """
        self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #   self.param1 = self.get_parameter_value('param1')
        self.ip = self.get_parameter_value('ip')
        self.port = self.get_parameter_value('port')
        self.tls = self.get_parameter_value('tls')
        self.acl = self.get_parameter_value('acl')
        self.wsproto = self.get_parameter_value('wsproto')
        self.querydef = self.get_parameter_value('querydef')

        if self.acl in ('true', 'yes'):
            self.acl = 'rw'

        self.websocket = _websocket(self.get_sh(), self.ip, self.port, self.tls, self.wsproto, self.querydef)
        return
        

    def run(self):
        """
        Run method for the plugin - called once to start the plugins processing
        """        
        self.alive = True
        self.scheduler_add('series', self.websocket._update_series, cycle=10, prio=5)
        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.websocket.stop()
        return


    def parse_item(self, item):
        """
        Plugin's parse_item method. Is called for every item when the plugin is initialized.
        
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. 
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments.
        """
        acl = self.acl
        if 'visu_acl' in item.conf:
            if item.conf['visu_acl'].lower() in ('true', 'yes', 'rw'):
                acl = 'rw'
            elif item.conf['visu_acl'].lower() in ('deny', 'no'):
                return
            else:
                acl = 'ro'
        self.websocket.visu_items[item.id()] = {'acl': acl, 'item': item}
        return self.update_item


    def parse_logic(self, logic):
        """
        Plugin's parse_logic method
        """
#        if hasattr(logic, 'visu_acl'):
#            if logic.conf['visu_acl'].lower() in ('true', 'yes', 'rw'):
#                self.websocket.visu_logics[logic.name] = logic
        return


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        self.websocket.update_item(item.id(), item(), source)
        return
        

    def url(self, url, clientip=''):
        """
        Tell the websocket client (visu) to load a specific url
        """
        self.websocket.url(url, clientip)
        return

		
    def return_clients(self):
        """
        Returns connected clients
        
        :return: list of dicts with client information 
        """
        for client in self.websocket.clients:
            infos = {}
            infos['addr'] = client.addr
            infos['sw'] = client.sw
            infos['swversion'] = client.swversion
            infos['hostname'] = client.hostname
            infos['browser'] = client.browser
            infos['browserversion'] = client.browserversion

            yield infos
        return
        

#########################################################################

class _websocket(lib.connection.Server):
    """
    Websocket specific class of the Plugin. Handles the websocket connections
    """

    def __init__(self, sh, ip, port, tls, wsproto, querydef ):
        lib.connection.Server.__init__(self, ip, port)
        self.logger = logging.getLogger(__name__)
        self._sh = sh
        self.tls = tls
        self.proto = wsproto
        self.querydef = querydef
        self._sh.add_event_listener(['log'], self._send_event)
        self.clients = []
        self.visu_items = {}
        self.visu_logics = {}

        self.tls_crt = '/usr/local/smarthome/etc/home.crt'
        self.tls_key = '/usr/local/smarthome/etc/home.key'
        self.tls_ca = '/usr/local/smarthome/etc/ca.crt'
        return


    def return_clients(self):
        """
        Returns connected websocket clients to the plugin
        """
        for client in self.clients:
            yield client.addr


    def handle_connection(self):
        sock, address = self.accept()
        if sock is None:
            return
        if self.tls:
            try:
                # cert_reqs=ssl.CERT_REQUIRED
                sock = ssl.wrap_socket(sock, server_side=True, cert_reqs=ssl.CERT_OPTIONAL, certfile=self.tls_crt, ca_certs=self.tls_ca, keyfile=self.tls_key, ssl_version=ssl.PROTOCOL_TLSv1)
                self.logger.debug('Client cert: {0}'.format(sock.getpeercert()))
                self.logger.debug('Cipher: {0}'.format(sock.cipher()))
#               print ssl.OPENSSL_VERSION
            except Exception as e:
                self.logger.exception(e)
                return
        client = websockethandler(self._sh, self, sock, address, self.visu_items, self.visu_logics, self.proto, self.querydef)
        self.clients.append(client)

    def stop(self):
        for client in self.clients:
            try:
                client.close()
            except:
                pass
        self.close()

    def update_item(self, item_name, item_value, source):
        data = {'cmd': 'item', 'items': [[item_name, item_value]]}
#        self.logger.warning("_websocket: update_item: data {0}".format(data))
        for client in list(self.clients):
            try:
                client.update(item_name, data, source)
            except:
                pass

    def remove_client(self, client):
        self.clients.remove(client)


    def _send_event(self, event, data):
        for client in list(self.clients):
            try:
                client.send_event(event, data)
            except:
                pass

    def _update_series(self):
        for client in list(self.clients):
            try:
                client.update_series()
            except Exception as e:
                self.logger.warning("_websocket / _update_series: cannot update client {0}, error {1}".format(client, e))
                pass

    def dialog(self, header, content):
        for client in list(self.clients):
            try:
                client.json_send({'cmd': 'dialog', 'header': header, 'content': content})
            except:
                pass

    def url(self, url, clientip=''):
        for client in list(self.clients):
            ip, _, port = client.addr.partition(':')
            if (clientip == '') or (clientip == ip):
                self.logger.debug("VISU: Websocket send url to ip={}, port={}".format(str(ip),str(port)))
                try:
                    client.json_send({'cmd': 'url', 'url': url})
                except:
                    pass


#########################################################################

class websockethandler(lib.connection.Stream):
    """
    Websocket handler class of the Plugin. Each instance handles one client connection
    """

    def __init__(self, smarthome, dispatcher, sock, addr, items, visu_logics, proto, querydef):
        lib.connection.Stream.__init__(self, sock, addr)
        self.terminator = b"\r\n\r\n"
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self._dp = dispatcher
        self.found_terminator = self.parse_header
        self.addr = addr
        self.header = {}
        self.monitor = {'item': [], 'rrd': [], 'log': []}
        self.monitor_id = {'item': 'item', 'rrd': 'item', 'log': 'name'}
        self._update_series = {}
        self.items = items
        self.rrd = False
        self.log = False
        self.logs = self._sh.return_logs()
        self._series_lock = threading.Lock()
        self.visu_logics = visu_logics
        self.proto = proto
        self.querydef = querydef
        self.logger.info("VISU: Websocket handler uses protocol version {0}".format(self.proto))
        self.sw = ''
        self.swversion = ''
        self.hostname = ''
        self.browser = ''
        self.browserversion = ''
        
        # get access to the logics api
        from lib.logic import Logics
        self.logics = Logics.get_instance()
        return
        

    def send_event(self, event, data):
        data = data.copy()  # don't filter the orignal data dict
        if event not in self.monitor:
            return
        if data[self.monitor_id[event]] in self.monitor[event]:
            data['cmd'] = event
#            self.logger.warning("VISU: send_event send to {0}: {1}".format(self.addr, data))
            self.json_send(data)

    def json_send(self, data):
        self.logger.debug("Visu: DUMMY send to {0}: {1}".format(self.addr, data))

    def handle_close(self):
        # remove circular references
        self._dp.remove_client(self)
        try:
            del(self.json_send, self.found_terminator)
        except:
            pass

    def update(self, path, data, source):
        if path in self.monitor['item']:
            if self.addr != source:
#                self.logger.warning("VISU: update send to {0}: {1}, path={2}, source={3}".format(self.addr, data, path, source))
                self.json_send(data)

    def update_series(self):
        now = self._sh.now()
        self._series_lock.acquire()
        remove = []
        for sid, series in self._update_series.items():
            if series['update'] < now:
                try:
                    reply = self.items[series['params']['item']]['item'].series(**series['params'])
                except Exception as e:
                    self.logger.exception("Problem updating series for {0}: {1}".format(series['params'], e))
                    remove.append(sid)
                    continue
                self._update_series[reply['sid']] = {'update': reply['update'], 'params': reply['params']}
                del(reply['update'])
                del(reply['params'])
                if reply['series'] is not None:
#                    self.logger.warning("Visu: update send to {0}: {1}".format(self.addr, reply))
                    self.json_send(reply)
        for sid in remove:
            del(self._update_series[sid])
        self._series_lock.release()

    def difference(self, a, b):
        return list(set(b).difference(set(a)))


    def json_parse(self, data):
        """
        Parse the received request
        
        :param data: json data structure with the request
        :type data: json structure
        
        """
        self.logger.debug("{0} sent {1}".format(self.addr, repr(data)))
        try:
            data = json.loads(data)
        except Exception as e:
            self.logger.debug("Problem decoding {0} from {1}: {2}".format(repr(data), self.addr, e))
            return
        command = data['cmd']
        
        if command == 'item':
            path = data['id']
            value = data['val']
            if path in self.items:
                if not self.items[path]['acl'] == 'ro':
                    self.items[path]['item'](value, 'Visu', self.addr)
                else:
                    self.logger.warning("Client {0} want to update read only item: {1}".format(self.addr, path))
            else:
                self.logger.warning("Client {0} want to update invalid item: {1}".format(self.addr, path))
                
        elif command == 'monitor':
            if data['items'] == [None]:
                return
            items = []
            for path in list(data['items']):
                if path in self.items:
                    items.append([path, self.items[path]['item']()])
                else:
                    self.logger.warning("Client {0} requested invalid item: {1}".format(self.addr, path))
            self.logger.debug("json_parse: send to {0}: {1}".format(self.addr, ({'cmd': 'item', 'items': items})))	# MSinn
            self.json_send({'cmd': 'item', 'items': items})
            self.monitor['item'] = data['items']
            
        elif command == 'logic':
            self.request_logic(data)

        elif command == 'series':
            path = data['item']
            series = data['series']
            start = data['start']
            if 'end' in data:
                end = data['end']
            else:
                end = 'now'
            if 'count' in data:
                count = data['count']
            else:
                count = 100
            if path in self.items:
                if hasattr(self.items[path]['item'], 'series'):
                    try:
                        reply = self.items[path]['item'].series(series, start, end, count)
                    except Exception as e:
                        self.logger.error("Problem fetching series for {0}: {1} - Wrong sqlite plugin?".format(path, e))
                    else:
                        if 'update' in reply:
                            self._series_lock.acquire()
                            self._update_series[reply['sid']] = {'update': reply['update'], 'params': reply['params']}
                            self._series_lock.release()
                            del(reply['update'])
                            del(reply['params'])
                        if reply['series'] is not None:
                            self.json_send(reply)
                        else:
                            self.logger.info("WebSocket: no entries for series {} {}".format(path, series))
                else:
                    self.logger.warning("Client {0} requested invalid series: {1}.".format(self.addr, path))
                    
        elif command == 'log':
            self.log = True
            name = data['name']
            num = 10
            if 'max' in data:
                num = int(data['max'])
            if name in self.logs:
                self.json_send({'cmd': 'log', 'name': name, 'log': self.logs[name].export(num), 'init': 'y'})
            else:
                self.logger.warning("Client {0} requested invalid log: {1}".format(self.addr, name))
            if name not in self.monitor['log']:
                self.monitor['log'].append(name)
                
        elif command == 'ping':
            self.logger.debug("json_parse: send to {0}: {1}".format(self.addr, ({'cmd': 'pong'})))
            self.json_send({'cmd': 'pong'})
            
        elif command == 'proto':  # protocol version
            proto = data['ver']
            if proto > self.proto:
                self.logger.warning("WebSocket: protocol mismatch. SmartHomeNG protocol version={0}, visu protocol version={1}".format(self.proto, proto))
            elif proto < self.proto:
                self.logger.warning("WebSocket: protocol mismatch. Update your client: {0}".format(self.addr))
            self.json_send({'cmd': 'proto', 'ver': self.proto, 'time': self._sh.now()})
#            self.logger.warning("VISU json_parse: send to {0}: {1}".format(self.addr, "{'cmd': 'proto', 'ver': " + str(self.proto) + ", 'time': " + str(self._sh.now()) + "}"))

        elif command == 'identity':  # identify client
            self.sw = data.get('sw','')
            self.swversion = data.get('ver','')
            self.hostname = data.get('hostname','')
            self.browser = data.get('browser','')
            self.browserversion = data.get('bver','')
            self.logger.debug("VISU json_parse: received 'identify' from {0}: {1}".format(self.addr, data))

        elif command == 'list_items':
            if self.querydef:
                path = data.get('path', '')
                response = self.request_list_items(path)
                self.json_send(response)

        elif command == 'list_logics':
            if self.querydef:
                enabled = data.get('enabled', 0)
                response = self.request_list_logics((enabled==1))
                self.json_send(response)

        else:
            self.json_send({'cmd': command, 'error': 'Unknown Command'})
        return
        

    def request_list_items(self, path):
        """
        Build the requested list of logics
        """
        self.logger.info("Client {0} requested a list of defined items.".format(self.addr))
        myitems = []
        for i in self._sh.return_items():
            include = False
#            if i.get('visu_acl', '').lower() != 'no': 
            if (path == '') and (not '.' in i._path):
                include = True
            else:
                if i._path.startswith(path+'.'):
                    p = i._path[len(path+'.'):]
                    if not '.' in p:
                        include = True
            if include:
                myitem = collections.OrderedDict()
                myitem['path'] = i._path
                myitem['name'] = i._name
                myitem['type'] = i.type()
                myitems.append(myitem)

        response = collections.OrderedDict([('cmd','list_items'), ('items',myitems)])
        self.logger.info("Requested a list of defined items: {}".format(response))
        return response


    def request_logic(self, data):
        """
        Request logic (trigger, enable, disable)
        """
        if 'name' not in data:
            return
        name = data['name']
        mylogic = self.logics.return_logic(name)
        if mylogic is not None:
            linfo = self.logics.get_logic_info(name)
            if linfo['visu_access']:
                if 'val' in data:
                    value = data['val']
                    self.logger.info("Client {0} triggerd logic {1} with '{2}'".format(self.addr, name, value))
                    mylogic.trigger(by='Visu', value=value, source=self.addr)
                if 'enabled' in data:
                    if data['enabled']:
                        self.logger.info("Client {0} enabled logic {1}".format(self.addr, name))
                        self.logics.enable_logic(name)
                        # non-persistant enable
                        #self.visu_logics[name].enable()
                    else:
                        self.logger.info("Client {0} disabled logic {1}".format(self.addr, name))
                        self.logics.disable_logic(name)
                        # non-persistant disable
                        #self.visu_logics[name].disable()
            else:
                self.logger.warning("Client {0} requested logic without visu-access: {1}".format(self.addr, name))
        else:
            self.logger.warning("Client {0} requested invalid logic: {1}".format(self.addr, name))


    def request_list_logics(self, enabled):
        """
        Build the requested list of logics
        """
        self.logger.info("Client {0} requested a list of defined logics.".format(self.addr))
        logiclist = []
        for l in self.logics.return_loaded_logics():
            linfo = self.logics.get_logic_info(l)
            if linfo['visu_access']:
                if linfo['userlogic']:
                    logic_def = collections.OrderedDict()
                    logic_def['name'] = l
                    logic_def['desc'] = linfo['description']
                    logic_def['enabled'] = 1
                    if not linfo['enabled']:
                        logic_def['enabled'] = 0
                    if (not enabled) or (logic_def['enabled'] == 1):
                        logiclist.append(logic_def)
        
        response = collections.OrderedDict([('cmd','list_logics'), ('logics',logiclist)])
        self.logger.info("Requested a list of defined logics: {}".format(response))
        return response
        

    def parse_header(self, data):
        data = bytes(data)
        for line in data.splitlines():
            key, sep, value = line.partition(b': ')
            self.header[key] = value
        if b'Sec-WebSocket-Version' in self.header:
            if self.header[b'Sec-WebSocket-Version'] == b'13':
                self.rfc6455_handshake()
            else:
                self.handshake_failed()
        elif b'Sec-WebSocket-Key2' in self.header:
            self.found_terminator = self.hixie76_handshake
            self.terminator = 8
        else:
            self.handshake_failed()

    def handshake_failed(self):
        self.logger.debug("Handshake for {0} with the following header failed! {1}".format(self.addr, repr(self.header)))
        self.close()

    def set_bit(self, byte, bit):
        return byte | (1 << bit)

    def bit_set(self, byte, bit):
        return not 0 == (byte & (1 << bit))

    def rfc6455_handshake(self):
        self.logger.debug("rfc6455 Handshake")
        self.terminator = 8
        self.found_terminator = self.rfc6455_parse
        self.json_send = self.rfc6455_send
        key = self.header[b'Sec-WebSocket-Key'] + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        key = base64.b64encode(hashlib.sha1(key).digest()).decode()
        self.send('HTTP/1.1 101 Switching Protocols\r\n'.encode())
        self.send('Upgrade: websocket\r\n'.encode())
        self.send('Connection: Upgrade\r\n'.encode())
        self.send('Sec-WebSocket-Accept: {0}\r\n'.format(key).encode())
        self.send('\r\n'.encode())

    def rfc6455_parse(self, data):
        # fin = bit_set(data[0], 7)
        # rsv1 = bit_set(data[0], 6)
        # rsv2 = bit_set(data[0], 5)
        # rsv1 = bit_set(data[0], 4)
        opcode = data[0] & 0x0f
        if opcode == 8:
            self.logger.debug("WebSocket: closing connection to {0}.".format(self.addr))
            self.close()
            return
        header = 2
        masked = self.bit_set(data[1], 7)
        if masked:
            header += 4
        length = data[1] & 0x7f
        if length == 126:
            header += 2
            length = int.from_bytes(data[2:4], byteorder='big')
        elif length == 127:
            header += 8
            length = int.from_bytes(data[2:10], byteorder='big')
        read = header + length
        if len(data) < read:  # data too short, read more
            self.inbuffer = data + self.inbuffer
            self.terminator = read
            return
        if masked:
            key = data[header - 4:header]
            payload = bytearray(data[header:])
            for i in range(length):
                payload[i] ^= key[i % 4]
        else:
            payload = data[header:]

        try:
            self.json_parse(payload.decode())
        except Exception as e:
            self.logger.exception("_websocket.json_parse exception: {}".format(e))
        self.terminator = 8

    def rfc6455_send(self, data):
        data = json.dumps(data, cls=JSONEncoder, separators=(',', ':'))
        header = bytearray(2)
        header[0] = self.set_bit(header[0], 0)  # opcode text
        header[0] = self.set_bit(header[0], 7)  # final
        length = len(data)
        if length < 126:
            header[1] = length
        elif length < ((1 << 16) - 1):
            header[1] = 126
            header += bytearray(length.to_bytes(2, byteorder='big'))
        elif length < ((1 << 64) - 1):
            header[1] = 127
            header += bytearray(length.to_bytes(8, byteorder='big'))
        else:
            self.logger.warning("data to big: {0}".format(data))
            return
        self.send(header + data.encode())

    def hixie76_send(self, data):
        data = json.dumps(data, cls=JSONEncoder, separators=(',', ':'))
        packet = bytearray()
        packet.append(0x00)
        packet.extend(data.encode())
        packet.append(0xff)
        self.send(packet)

    def hixie76_parse(self, data):
        try:
            self.json_parse(data.decode().lstrip('\x00'))
        except Exception as e:
            self.logger.exception("_websocket.json_parse exception: {}".format(e))

    def hixie76_handshake(self, key3):
        self.logger.debug("Hixie76 Handshake")
        key1 = self.header[b'Sec-WebSocket-Key1'].decode()
        key2 = self.header[b'Sec-WebSocket-Key2'].decode()
        spaces1 = key1.count(" ")
        spaces2 = key2.count(" ")
        num1 = int("".join([c for c in key1 if c.isdigit()])) // spaces1
        num2 = int("".join([c for c in key2 if c.isdigit()])) // spaces2
        key = hashlib.md5()
        key.update(struct.pack('>II', num1, num2))
        key.update(key3)
        # send header
        self.send(b'HTTP/1.1 101 Web Socket Protocol Handshake\r\n')
        self.send(b'Upgrade: WebSocket\r\n')
        self.send(b'Connection: Upgrade\r\n')
        self.send(b"Sec-WebSocket-Origin: " + self.header[b'Origin'] + b"\r\n")
        self.send(b"Sec-WebSocket-Location: ws://" + self.header[b'Host'] + b"/\r\n\r\n")
        self.send(key.digest())
        self.found_terminator = self.hixie76_parse
        self.json_send = self.hixie76_send
        self.terminator = b"\xff"


#########################################################################

class JSONEncoder(json.JSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        elif isinstance(obj, datetime.time):
            return obj.isoformat()
        elif isinstance(obj, datetime.timedelta):
            return int(obj.total_seconds())
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return json.JSONEncoder.default(self, obj)


