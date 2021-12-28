#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013-2016 Axel Otterstätter        panzaeron @ knx-user-forum
# Copyright 2019 Bernd Meiners                      Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
#  upwards.
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

from lib.module import Modules
from lib.model.smartplugin import *
from lib.network import Tcp_server

from speech import varParse, dictError

import logging
import sys
import os
import re
import urllib.request
import urllib.parse
import urllib.error
import cherrypy

logger = logging.getLogger(__name__)


class HTTPDispatcher(Tcp_server):
    '''
    Encapsulation class for using lib.network.Tcp_server class with HTTP GET support
    '''
    def __init__(self, parser, ip, port):
        '''
        Initializes the class

        :param parser: callback function for handling data, called as parser(remoteip, 'tcp:<localip>:<localport>', '<data>')
        :type parser: function
        :param ip: local ip address to bind to
        :type ip: str
        :param port: local port to bind to
        :type port: int
        '''
        super().__init__(port, ip, 1, b'\n')
        self.parser = parser
        self.dest = f'http:{ip}:{port}'
        self.terminator = b"\r\n\r\n"
        self.set_callbacks(data_received=self.handle_received_data, incoming_connection=self.handle_connection)
        self.start()

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
        self.logger.debug(f'Received packet from {client.ip}:{client.port} to {self.dest} via HTTP with content "{data}"')

        # find lines starting with GET and return remaining lines "HTTP-like" and return status
        for line in data.splitlines():
            if line.startswith('GET'):
                request = line.split(' ')[1].strip('/')
                request = urllib.parse.unquote_plus(request)
                if self.parser(self.source, self.dest, request) is not False:
                    parsedText = ParseText(self._sh, request)
                    parse_result = parsedText.parse_message()
                    if parse_result[1]:
                        answer = parse_result[1][2]
                    else:
                        answer = parse_result[0]
                else:
                    answer = dictError['error']
                answer_length = len(answer.encode('utf-8'))
                logger.debug("SP: Sende Antwort: %s (%s Bytes)" % (answer, answer_length))
                self.send(bytes("HTTP/1.1 200 OK\r\nContent-type: text/plain; charset=UTF-8\r\nContent-Length: %s\r\n\r\n%s" % (answer_length, answer), encoding="utf-8"), close=True)
            else:
                logger.debug("SP: Sende Antwort: 400 Bad Request")
                self.send(b'HTTP/1.1 400 Bad Request\r\n\r\n', close=True)
            break


class Speech_Parser(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.7.0'
    listeners = {}
    socket_warning = 10
    socket_warning = 2
    errorMessage = False

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.ip = self.get_parameter_value('listen_ip')
        self.port = self.get_parameter_value('listen_port')
        self.acl = self.parse_acl(self.get_parameter_value('acl'))
        self.default_access = self.get_parameter_value('default_access')
        try:
            self.config = os.path.expanduser(self.get_parameter_value('config_file'))
        except:
            pass

        # Initialization code goes here
        dest = "http:{}:{}".format(self.ip, self.port)
        logger.info("SP: Adding listener on: {}".format(dest))
        self.dispatcher = HTTPDispatcher(self.parse_input, self.ip, self.port)
        self.listeners[dest] = {'items': {}, 'logics': {}, 'acl': self.parse(self.acl)}

        speech_plugin_path = os.path.dirname(os.path.realpath(__file__))

        if not os.path.exists(self.config):
            try_other_path = os.path.join(speech_plugin_path, self.config)
            if os.path.exists(try_other_path):
                self.config = try_other_path
            else:
                self.logger.error("Configuration file with base path of plugin '{}' not found".format(try_other_path))
                self._init_complete = False
                return

        config_base = os.path.basename(self.config)

        if config_base == "speech.py":
            sys.path.append(os.path.dirname(self.config))
            global varParse, dictError
            self.logger.info("Configuration file '{}' successfully imported".format(self.config))
        else:
            self.logger.error("Configuration file '{}' error, the filename should be speech.py".format(config_base))
            self._init_complete = False
            return

        # if plugin should start even without web interface
        self.init_webinterface()

    def parse_acl(self, acl):
        if acl == '*':
            return False
        if isinstance(acl, str):
            return [acl]
        return acl

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.logger.info("SP: Server Starts - %s:%s" % (self.ip, self.port))
        self.dispatcher.start()
        if not self.dispatcher.connected:
            self.logger.error(f'Could not start server on {self.ip}:{self.port}. Plugin deactivated')
            return
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False
        self.dispatcher.close()

    def parse_item(self, item):
        self.parse_obj(item, 'item')

    def parse_logic(self, logic):
        self.parse_obj(logic, 'logic')

    def parse_obj(self, obj, obj_type):
        # sp
        if obj_type == 'item':
            oid = obj.id()
        elif obj_type == 'logic':
            oid = obj.id()
        else:
            return

        if 'sp_acl' in obj.conf:
            acl = obj.conf['sp_acl']
        else:
            acl = False
        if 'sp' in obj.conf:  # adding object to listeners
            if obj.conf['sp'] in ['ro', 'rw', 'yes']:
                for dest in self.listeners:
                    self.listeners[dest][obj_type + 's'][oid] = {obj_type: obj, 'acl': acl}

    def parse_input(self, source, dest, data):
        if not self.alive:
            return False
        if dest in self.listeners:
            parse_text = ParseText(self._sh, data)
            result = parse_text.parse_message()
            if not result[0]:
                result = result[1]
            else:
                errorMessage = result[0]
                return [False, errorMessage]
            name, value, answer, typ, varText = result
            self.logger.info('Speech Parse data: ' + str(data) + ' Result: ' + str(result))
            # logger.debug("SP: Result: "+str(result))
            # logger.debug("SP: Item: "+name)
            # logger.debug("SP: Value: "+value)
            # logger.debug("SP: Answer: "+answer)
            # logger.debug("SP: Typ: "+typ)
            source, __, port = source.partition(':')
            gacl = self.listeners[dest]['acl']
            if typ == 'item':
                if name not in self.listeners[dest]['items']:
                    self.logger.error("SP: Item '{}' not available in the listener.".format(name))
                    return False
                iacl = self.listeners[dest]['items'][name]['acl']
                if iacl:
                    if source not in iacl:
                        self.logger.error("SP: Item '{}' acl doesn't permit updates from {}.".format(name, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("SP: Network acl doesn't permit updates from {}.".format(source))
                        return False

                item = self.listeners[dest]['items'][name]['item']
                # Parameter default_access added 141207 (KNXfriend)
                if item.conf['sp'] == 'rw' or self.default_access == 'rw':
                    item(value, source)

            elif typ == 'logic':
                if name not in self.listeners[dest]['logics']:
                    self.logger.error("SP: Logic '{}' not available in the listener.".format(name))
                    return False
                lacl = self.listeners[dest]['logics'][name]['acl']
                if lacl:
                    if source not in lacl:
                        self.logger.error("SP: Logic '{}' acl doesn't permit triggering from {}.".format(name, source))
                        return False
                elif gacl:
                    if source not in gacl:
                        self.logger.error("SP: Network acl doesn't permit triggering from {}.".format(source))
                        return False
                logic = self.listeners[dest]['logics'][name]['logic']
                logic.trigger(varText, source, value)
            else:
                self.logger.error("SP: Unsupporter key element {}. Data: {}".format(typ, data))
                return False
        else:
            self.logger.error("SP: Destination {}, not in listeners!".format(dest))
            return False
        return True

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Not initializing the web interface")
            return False

        if "SmartPluginWebIf" not in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


class ParseText():
    parseText = False
    errorMessage = False

    def __init__(self, smarthome, varText):
        self._sh = smarthome
        self.parseText = varText

    def parse_message(self):
        for parseline in varParse:
            varResult = self.get_expr(parseline)

            if varResult:
                answer = varResult[3]
                name = varResult[0]
                value = varResult[1]
                typ = varResult[4]
                logger.debug("SP: parseText: " + self.parseText)
                logger.debug("SP: Item: " + name)
                logger.debug("SP: Value: " + value)
                logger.debug("SP: List: " + str(varResult[2]))
                logger.debug("SP: Answer: " + answer)
                logger.debug("SP: Typ: " + typ)

                # get status if needed
                if value == '%status%':
                    value_received = str(self.get_item_value(name))
                    value_received = value_received.replace('.', ',')       # Dezimal Zahlen werden mit Punkt getrennt, ersetzen durch Komma
                    answer = answer.replace('%status%', value_received)     # Platzhalter %status% ersetzen

                return(False, [name, value, answer, typ, self.parseText])
            else:
                logger.debug("SP: parseText: Unbekannter Befehl")
                self.errorMessage = dictError['unknown_command']
        return [self.errorMessage, False]

    def get_expr(self, parseline):
        varItem = parseline[0]
        varValue = parseline[1]
        varVars = parseline[2]
        varAnswer = parseline[3]
        varList = []
        varList2 = []
        reg_ex = ".*"
        if len(parseline) == 5:
            varTyp = parseline[4].lower()
        else:
            varTyp = 'item'

        # Build regular expression
        for x in range(0, len(varVars)):
            reg_ex += '('
            if type(varVars[x]) == list:
                for var2 in varVars[x]:
                    for word in var2[1]:
                        reg_ex += str(word) + '|'
                reg_ex = reg_ex[:-1] + ')'
            else:
                reg_ex += str(varVars[x]) + ')'
            reg_ex += '.*'
            if len(varVars) - 1 != x:
                reg_ex += ' '
        logger.debug("Regular Expression:\n>" + reg_ex + "<")
        # test regular Expression on transmitted Text
        mo = re.match(reg_ex, self.parseText, re.IGNORECASE)

        if mo:
            for x in range(0, len(varVars)):
                if type(varVars[x]) == list:
                    for y in range(0, len(varVars[x])):
                        if mo.group(x + 1).lower() in varVars[x][y][1]:
                            varList.append(str(varVars[x][y][0]))
                            varList2.append(str(varVars[x][y][1][0]))
                else:
                    varList.append(str(mo.group(x + 1)))
                    varList2.append(str(mo.group(x + 1)))
            for x in range(0, len(varList)):
                var = '%' + str(x) + '%'
                varItem = varItem.replace(var, str(varList[x]))
                varValue = varValue.replace(var, str(varList[x]))
                if varList[x].lower() == '%status%':
                    varAnswer = varAnswer.replace(var, '%status%')
                else:
                    varAnswer = varAnswer.replace(var, str(varList2[x]))
            return (varItem, varValue, varList, varAnswer, varTyp)
        self.errorMessage = dictError['unknown_command']
        return False

    def get_item_value(self, status_item):
        item = self._sh.return_item(status_item)
        if not item():
            self.errorMessage = dictError['status_error']
        return item()


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------


class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            # self.plugin.beodevices.update_devices_info()

            # return it as json the the web page
            # return json.dumps(self.plugin.beodevices.beodeviceinfo)
            pass
        return
