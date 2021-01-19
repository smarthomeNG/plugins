#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 - Alexander Schwithal          alex.schwithal(a)web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
from lib.item import Items

import threading
import requests
import json
import time
from websocket import create_connection

class Casambi(SmartPlugin):
    """
    Main class of the Plugin derived from SmartPlugin.
    """

    # Use VERSION = '1.0.0' for your initial plugin Release
    PLUGIN_VERSION = '1.7.2'    # (must match the version specified in plugin.yaml)

    def __init__(self, sh):
        """
        Initalizes the plugin.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.session = requests.Session()
        self.exit_event = threading.Event()
        self._rx_items = {}
        self.sessionID = ''
        self.networkID = ''
        self.numberNetworks = 0
        self.wire = 1                     # Connection ID, incremental value to identify messages of network/connection
        self.websocket = None
        self.casambiBackendStatus = False
        self.thread = None


        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.api_key = self.get_parameter_value('api_key')
        self.email = self.get_parameter_value('email')
        self.password = self.get_parameter_value('password')

        # Check plugin parameters:
        if (len(self.api_key) < 1):
            self.logger.error('No valid api key specified. Aborting.')
            self._init_complete = False
            return

        if (len(self.email) < 1):
            self.logger.error('No valid email address specified. Aborting.')
            self._init_complete = False
            return

        if (len(self.password) < 1):
            self.logger.error('No valid password specified. Aborting.')
            self._init_complete = False
            return

        self.init_webinterface()
        
        return

    def getSessionCredentials(self):
        sessionID = ''
        networkID = ''
        nrNetworks = 0 

        urlCasambi = 'https://door.casambi.com/'
        functionURL = 'v1/networks/session'
        dataBody = {"email": self.email,"password": self.password}
        # convert to JSON string:
        dataBodyJson = json.dumps(dataBody )

        sessionrequest_response = self.session.post(
            urlCasambi + functionURL, data=dataBodyJson,
            headers={'X-Casambi-Key': self.api_key, 
                     'content-type': 'application/json'}, timeout=10, verify=False)
        
        self.logger.debug("Session request response: {0}".format(sessionrequest_response.text))
        statusCode = sessionrequest_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending session request command successful")
        elif statusCode == 401:
            self.logger.error("Sending session request results in: Unauthorized. Invalid API key or credentials given.") 
            return '','',''
        else:
            self.logger.error("Server error: {0}".format(statusCode))
            return '', '', ''

        responseJson = sessionrequest_response.json()
                
        NetworkInfoJson = ''
        for network in responseJson.keys():
            nrNetworks = nrNetworks + 1
            #self.logger.debug("Network {0}: Name: {1}".format(nrNetworks, network))
            NetworkInfoJson = responseJson[network]
        self.logger.info("In total {0} networks found".format(nrNetworks))
        
        if nrNetworks > 1:
            self.logger.warning("Casambi plugin does currently not support more than one network")
        
        if NetworkInfoJson:
            if 'sessionId' in NetworkInfoJson:
                sessionID = str(NetworkInfoJson['sessionId'])
                self.logger.debug("Session ID received: {0}".format(sessionID))
    
        if 'id' in NetworkInfoJson:
            networkID = str(NetworkInfoJson['id'])
            self.logger.debug("Network ID is: {0}".format(networkID))

        return sessionID, networkID, nrNetworks


    def openWebsocket(self, networkID):

        self.logger.debug("start openWebsocket")
        reference = 'REFERENCE-ID'; # Reference handle created by client to link messages to relevant callbacks
        socketType = 1;             # Client type, use value 1 (FRONTEND)

        openMsg = {
            "method": "open",
            "id": networkID,
            "session": self.sessionID,
            "ref": reference,
            "wire": self.wire,
            "type": socketType
	    }
        # convert to JSON string:
        openMsgJson = json.dumps(openMsg)
        #self.logger.debug("Open msg as json: {0}".format(openMsgJson))

        self.websocket = create_connection("wss://door.casambi.com/v1/bridge/", subprotocols=[self.api_key])

        if (not self.websocket) or (not self.websocket.connected):
            self.logger.error("Could not open websocket")   
            return

        self.websocket.send(openMsgJson)
        self.logger.debug("Sent open message via websocket")
        time.sleep(1)

        result =  self.websocket.recv()
        self.logger.debug("Received: {0}".format(result)) 
        resultJson = json.loads(result.decode('utf-8'))
        wireStatus = ''
        if resultJson:
            if 'wireStatus' in resultJson:
                wireStatus = str(resultJson['wireStatus'])
                self.logger.debug("wireStatus: {0}".format(wireStatus))

        if wireStatus == 'openWireSucceed':
            self.logger.debug("Wire opened successfully")
        else:    
            self.logger.error("wireStatus: {0}".format(wireStatus))    

        pass



    def controlDevice(self, item, id, key):
        """
        Control message format for switching/dimming of casambi devices
        """
        dimValue = 0
        if key == 'ON':
            dimValue = int(item() == True)
        elif key == 'DIMMER' or key == 'VERTICAL':
            dimValue = item() / 100.0
        else:
            self.logger.error("Invalid key: {0}".format(key))

        targetControls = ''
        if key == 'ON' or key == 'DIMMER':
            targetControls = {"Dimmer": {"value": dimValue}} # Dimmer value can be anything from 0 to 1
        elif key == 'VERTICAL':
            targetControls = {"Vertical": {"value": dimValue}} # Vertical fader value can be anything from 0 to 1

        controlMsg = {
                "wire": self.wire,
                "method": "controlUnit",
                "id": id,
                "targetControls": targetControls
	}
        # convert to JSON string:
        controlMsgJson = json.dumps(controlMsg)

        if self.websocket and self.websocket.connected:
            self.websocket.send(controlMsgJson)
            if self.casambiBackendStatus == False:
                self.logger.warning("Command sent but backend is not online.")
            else:
                self.logger.debug("Command with value {0} sent out via open websocket".format(dimValue))
        else:
            self.logger.error("Unable to send command. Websocket is not open")



    def decodeEventData(self, receivedData):

        if len(receivedData) < 1:
            return

        dataJson = json.loads(receivedData.decode('utf-8'))

        if 'wireStatus' in dataJson:
            wireStatus = str(dataJson['wireStatus']) 
            if not (wireStatus == 'openWireSucceed'):
                self.logger.warning("Event: Wirestatus {0} received".format(wireStatus))

        method = ''
        if dataJson:
            if 'method' in dataJson :
                method = str(dataJson ['method'])
        else:
            self.logger.debug("decodeEventData: Invalid Json")

        if method == 'peerChanged':
            online = None
            if 'online' in dataJson:
                self.casambiBackendStatus = bool(dataJson ['online'])
            self.logger.debug("Received {0} status with backend online status: {1}.".format(method, self.casambiBackendStatus))

        elif method == 'unitChanged':
            unitID = None
            on = None          # on status represents the status of the BLE module in the device, not the light status.
            status = None
            dimValue = None
            verticalValue = None
            self.logger.debug("Debug Json unitChanged: {0}".format(dataJson))
            if 'id' in dataJson:
                unitID = int(dataJson['id'])
            if 'on' in dataJson:
                on = bool(dataJson['on'])
            if 'status' in dataJson:
                status = str(dataJson['status'])
            if 'controls' in dataJson:
                controls = dataJson['controls']
                self.logger.debug("Debug controls Json: {0}".format(controls))
                for x in controls:
                    #self.logger.debug("Debug x: {0}".format(x))
                    type = None
                    value = None
                    if 'type' in x:
                        type = str(x['type'])
                    if 'value' in x:
                        value = float(x['value'])
                    #self.logger.debug("Type: {0}, value: {1}".format(type, value))
                    if type == 'Dimmer':
                        dimValue = value
                    elif type == 'Vertical':
                        verticalValue = value

            self.logger.debug("Received {0} status from unit {1}, on: {2}, value: {3}, vertical: {4}.".format(method, unitID, on, dimValue, verticalValue))

            #Copy data into casambi item:
            if unitID and (unitID in self._rx_items):
                #self.logger.debug("Casambi ID found in rx item list")
                # iterate over all items having this id 
                for item in self._rx_items[unitID]:
                    if on and (item.conf['casambi_rx_key'].upper() == 'ON'):
                        item(not (dimValue == 0), self.get_shortname())
                    elif item.conf['casambi_rx_key'].upper() == 'DIMMER':
                        item(dimValue * 100, self.get_shortname())
                    elif item.conf['casambi_rx_key'].upper() == 'VERTICAL':
                        item(verticalValue * 100, self.get_shortname())
            elif unitID and not (unitID in self._rx_items):
                self.logger.warning("Received status information for ID {0} which has no equivalent item.".format(unitID))
        else:
            self.logger.warning("Received unknown method {0} which is not supported.".format(method))

        pass



    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        #self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

        self.sessionID, self.networkID, self.numberNetworks = self.getSessionCredentials()

        self.thread = threading.Thread(target=self.eventHandler, name='CasambiEventHandler')
        self.thread.daemon = False
        self.thread.start()


    def eventHandler(self):
        self.logger.debug("EventHandler thread started")
        if self.networkID:
            self.logger.debug("Trying to open websocket once")
            self.openWebsocket(self.networkID)
        else:
            self.logger.warning("Cannot open websocket once. Invalid networkID")

        errorCount = 0
        doReconnect = False
        while self.alive:
            #self.logger.debug("Starting loop")

            if not self.websocket or self.websocket.connected == False:
                self.logger.debug("Websocket no longer connected.")
                doReconnect = True
                errorCount = errorCount  + 1
            else:
                self.logger.debug("Starting data receive")
                try:
                    self.logger.debug("Trying to receive data")
                    receivedData =  self.websocket.recv()
                    self.logger.debug("Received data: {0}".format(receivedData))
                    errorCount = 0
                except timeout:
                    self.logger.debug("Reception timeout")
                except socket.timeout:
                    self.logger.debug("Socket reception timeout")
                except Exception as e:
                    self.logger.info("Error during data reception: {0}".format(e))
                    errorCount = errorCount  + 1
                    doReconnect = True

                if not receivedData: 
                    self.logger.debug("Received empty data")
                else: 
                    self.logger.debug("Received data: {0}".format(receivedData))
                    self.decodeEventData(receivedData)

            # Error handling:
            if errorCount > 2:
                errorCount = 1
                self.logger.debug("Waiting for 60 seconds")
                self.exit_event.wait(timeout=60)
       
            if not self.alive:
                break

            if doReconnect:
                if self.networkID:
                    self.logger.debug("Trying to reopen websocket")
                    self.openWebsocket(self.networkID)
                    doReconnect = False
                else:
                    self.logger.warning("Cannot reconnect due to invalid network ID")
            
            
        if self.websocket:
            self.websocket.close()

        self.logger.debug("EventHandler thread stopped")


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.exit_event.set()
#        if self.thread:
#            self.thread.join(2)
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
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
        if self.get_iattr_value(item.conf, 'casambi_rx_key'):
            # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
            id_item = item
            while not self.has_iattr( id_item.conf, 'casambi_id'):
                id_item = id_item.return_parent()
                if (id_item is self._sh):
                    self.logger.error("Could not find casambi_id for item {}".format(item))
                    return None
            rx_key = item.conf['casambi_rx_key'].upper()
            id = int(id_item.conf['casambi_id'])

            if (not id in self._rx_items):
                self._rx_items[id] = []
            self._rx_items[id].append(item)
            #self.logger.debug("rx-items dict: {0}".format(self._rx_items))

        if self.has_iattr(item.conf, 'casambi_tx_key'):
            # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
            id_item = item
            while not self.has_iattr( id_item.conf, 'casambi_id'):
                id_item = id_item.return_parent()
                if (id_item is self._sh):
                    self.logger.error("Could not find casambi_id for item {}".format(item))
                    return None

            tx_key = item.conf['casambi_tx_key'].upper()
            id = int(id_item.conf['casambi_id'])
            #self.logger.debug("New TX-item: {0} with casambi ID: {1} and tx key: {2}".format(item, id, tx_key))
          
            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        self.logger.debug("Call function << update_item >>")

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
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if self.has_iattr(item.conf, 'casambi_tx_key'):
                # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
                id_item = item
                while not self.has_iattr( id_item.conf, 'casambi_id'):
                    id_item = id_item.return_parent()
                    if (id_item is self._sh):
                        self.logger.error("Could not find casambi_id for item {}".format(item))
                        return None

                tx_key = item.conf['casambi_tx_key'].upper()
                id = int(id_item.conf['casambi_id'])

                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))
                self.logger.debug("Update TX-item: {0} with casambi ID: {1} and tx key: {2}".format(item, id, tx_key))
                self.controlDevice(item, id, tx_key)

        pass

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
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


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
from jinja2 import Environment, FileSystemLoader


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

        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin, items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])))


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
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}

