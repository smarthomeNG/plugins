#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 - Alexander Schwithal          alex.schwithal(a)web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
from .webif import WebInterface

import threading
import requests
import json
import time
import errno
from websocket import create_connection

class Casambi(SmartPlugin):
    """
    Main class of the Plugin derived from SmartPlugin.
    """

    # Use VERSION = '1.0.0' for your initial plugin Release
    PLUGIN_VERSION = '1.7.6'    # (must match the version specified in plugin.yaml)

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

        self.init_webinterface(WebInterface)

        return

    def sessionIDValid(self):
        return self.sessionID != ''

    def networkIDValid(self):
        return self.networkID != ''

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
        
        self.logger.debug(f"Session request response: {sessionrequest_response.text}")
        statusCode = sessionrequest_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending session request command successful")
        elif statusCode == 401:
            self.logger.error("Sending session request results in: Unauthorized. Invalid API key or credentials given.") 
            return '','',''
        else:
            self.logger.error(f"Server error: {statusCode}")
            return '', '', ''

        responseJson = sessionrequest_response.json()
                
        NetworkInfoJson = ''
        for network in responseJson.keys():
            nrNetworks = nrNetworks + 1
            #self.logger.debug(f"Network {nrNetworks}: Name: {network}")
            NetworkInfoJson = responseJson[network]
        self.logger.info(f"In total {nrNetworks} networks found")
        
        if nrNetworks > 1:
            self.logger.warning("Casambi plugin does currently not support more than one network")
        
        if NetworkInfoJson:
            if 'sessionId' in NetworkInfoJson:
                sessionID = str(NetworkInfoJson['sessionId'])
                self.logger.debug(f"Session ID received: {sessionID}")
    
        if 'id' in NetworkInfoJson:
            networkID = str(NetworkInfoJson['id'])
            self.logger.debug(f"Network ID is: {networkID}")

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
        #self.logger.debug(f"Open msg as json: {openMsgJson}")

        self.websocket = create_connection("wss://door.casambi.com/v1/bridge/", subprotocols=[self.api_key])

        if (not self.websocket) or (not self.websocket.connected):
            self.logger.error("Could not open websocket")   
            return

        try:
            self.websocket.send(openMsgJson)
        except Exception as e:
            self.logger.info(f"Exception during sending in openWebsocket(): {e}")
       
        self.logger.debug("Sent open message via websocket")
        time.sleep(1)

        try:
            result = self.websocket.recv()
        except Exception as e:
            self.logger.info(f"Exception during receiving in openWebsocket(): {e}")
            return
        
        self.logger.debug(f"Received: {result}") 
        
        #try:
        self.decodeEventData(result)
        #except Exception as e:
        #    self.logger.error(f"Exception in decodeEventData from openWebsocket: {e}")

        pass

#    def debugTest(self, item, id, key, error_count = 0):
#        """
#        Control message format for switching/dimming of casambi devices
#        """
#
#        local_error_cnt = error_count
#    
#        self.logger.warning(f"debugTest executed with error_count {error_count}, local error count {local_error_cnt}")
#
#        local_error_cnt = local_error_cnt + 1
#        time.sleep(3)
#
#        # Retry sending command only one time after a failure:
#        if local_error_cnt == 1:
#            self.logger.warning(f"Retry sending debugTest...(Local error count {local_error_cnt})")
#            #self.debugTest(item, id, key, error_count = 1)
#            self.debugTest(item, id, key, 1)
#
#        else: 
#            self.logger.warning(f"debugTest does not retry sending debugTest: error_count {error_count}, local error count {local_error_cnt}")


    def controlDevice(self, item, id, key, error_count = 0):
        """
        Control message format for switching/dimming of casambi devices
        """
        sendValue = 0
        local_error_cnt = error_count
        
        if key == 'ON':
            sendValue = int(item() == True)
        elif key == 'DIMMER' or key == 'VERTICAL':
            sendValue = item() / 100.0
        elif key == 'CCT':
            sendValue = item()
        else:
            self.logger.error(f"Invalid key: {key}")

        targetControls = ''
        if key == 'ON' or key == 'DIMMER':
            targetControls = {"Dimmer": {"value": sendValue}} # Dimmer value can be anything from 0 to 1
        elif key == 'VERTICAL':
            targetControls = {"Vertical": {"value": sendValue}} # Vertical fader value can be anything from 0 to 1
        elif key == 'CCT':
            targetControls = {"ColorTemperature": {"value" : sendValue}, "Colorsource": {"source": "TW"}} # ColorTemperature value in Kelvins 

        controlMsg = {
                "wire": self.wire,
                "method": "controlUnit",
                "id": id,
                "targetControls": targetControls
	}
        # convert to JSON string:
        controlMsgJson = json.dumps(controlMsg)
        self.logger.debug(f"Send command: {controlMsgJson}")

        if self.websocket and self.websocket.connected:
            try:
                self.websocket.send(controlMsgJson)
            except Exception as e:
                self.logger.error(f"Exception during sending in controlDevice(): {e}")
                if e.errno == errno.EPIPE:
                    if self.websocket:
                        self.websocket.close()
                    self.logger.warning("Closed websocket for reinitialization")
                local_error_cnt = local_error_cnt + 1
            else:
                # Command was sent without exceptions. Now, analyse backend status:
                if self.casambiBackendStatus == False:
                    self.logger.warning("Command sent but backend is not online.")
                else:
                    self.logger.debug(f"Command {key} with value {sendValue} sent out via open websocket")
        else:
            self.logger.warning("Unable to send command. Websocket is not open")

        #Restart thread in case it is no longer active:
        if not self.thread.is_alive():
            self.logger.warning("Event thread is not alive. Restarting...")
            self.run()
            self.logger.warning("Event thread restarted.")
            time.sleep(3)

        # Retry sending command only after exactly one error occured:
        if local_error_cnt == 1:
            self.logger.info(f"Retry sending command with rrror count {local_error_cnt}")
            self.controlDevice(item, id, key, 2)


    def decodeEventData(self, receivedData):

        if len(receivedData) < 1:
            return

        method = ''

        dataJson = json.loads(receivedData.decode('utf-8'))
        
        if dataJson:
            if 'wireStatus' in dataJson:
                wireStatus = str(dataJson['wireStatus']) 

                if wireStatus == 'openWireSucceed':
                    self.logger.debug("Wire opened successfully")
                elif wireStatus == '':
                    self.logger.debug("No wireStatus received")
                else:    
                    self.logger.error(f"wireStatus: {wireStatus}")   
                    self.logger.error(f"Debug: wireStatus response: {receivedData}")    

            if 'method' in dataJson :
                method = str(dataJson ['method'])
        else:
            self.logger.debug("decodeEventData: Invalid Json")

        if method == '':
            # This happens for example if a wireStatus response to an open message is received which does not contain a method attribute.
            self.logger.debug("Event: No method info received.")
        elif method == 'peerChanged':
            online = None
            if 'online' in dataJson:
                self.casambiBackendStatus = bool(dataJson ['online'])
                for id in self._rx_items:
                    for item in self._rx_items[id]:
                        if (item.conf['casambi_rx_key'].upper() == 'BACKEND_ONLINE_STAT'):
                            item( self.casambiBackendStatus, self.get_shortname())

            self.logger.debug(f"Received {method} status with backend online status: {self.casambiBackendStatus}.")

        elif method == 'unitChanged':
            unitID = None
            status = None       # Health status of sensor
            dimValue = None
            verticalValue = None
            cctValue = None

            self.logger.debug("Debug Json unitChanged: {0}".format(dataJson))
            if 'id' in dataJson:
                unitID = int(dataJson['id'])
            if 'status' in dataJson:
                status = str(dataJson['status'])
                if status != 'ok':
                    self.logger.warning(f"Sensor with ID  {unitID} reported status {status}") 

            if 'controls' in dataJson:
                controls = dataJson['controls']
                self.logger.debug(f"Debug controls Json: {controls}")
                for x in controls:
                    #self.logger.debug(f"Debug x: {x}")
                    type = None
                    value = None
                    if 'type' in x:
                        type = str(x['type'])
                    if 'value' in x:
                        value = float(x['value'])
                    #self.logger.debug(f"Type: {type}, value: {value}")
                    if type == 'Dimmer':
                        dimValue = value
                    elif type == 'Vertical':
                        verticalValue = value
                    elif type == 'CCT':
                        cctValue = value

            self.logger.debug(f"Received {method} status from unit {unitID}, value: {dimValue}, vertical: {verticalValue}, cct: {cctValue}.")

            #Copy data into casambi item:
            if unitID and (unitID in self._rx_items):
                #self.logger.debug("Casambi ID found in rx item list")
                # iterate over all items having this id 
                for item in self._rx_items[unitID]:
                    #if on and (item.conf['casambi_rx_key'].upper() == 'ON'):
                    if (item.conf['casambi_rx_key'].upper() == 'ON'):
                        item(not (dimValue == 0), self.get_shortname())
                    elif item.conf['casambi_rx_key'].upper() == 'DIMMER':
                        item(dimValue * 100, self.get_shortname())
                    elif item.conf['casambi_rx_key'].upper() == 'VERTICAL':
                        item(verticalValue * 100, self.get_shortname())
                    elif item.conf['casambi_rx_key'].upper() == 'CCT':
                        item(cctValue, self.get_shortname())

            elif unitID and not (unitID in self._rx_items):
                self.logger.warning(f"Received status information for ID {unitID} which has no equivalent item.")

        elif method == 'networkUpdated':
            self.logger.warning(f"Casambi network has been updated with persistent changes")
            self.logger.warning(f"Debug: decodeData(), receivedData: {receivedData}")

        elif method == 'networkLog':
            self.logger.debug(f"Casambi network sent network logging information")
            self.logger.debug(f"Debug: decodeData(), receivedData: {receivedData}")

        else:
            self.logger.warning(f"Received unknown method {method} which is not supported.")
            self.logger.warning(f"Debug: decodeData(), receivedData: {receivedData}")

        pass



    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        self.alive = True
        try:                    
            self.sessionID, self.networkID, self.numberNetworks = self.getSessionCredentials()
        except Exception as e:
            self.logger.error(f"Exception during getSessionCredectials: {e}")        

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
        noNetworkIDErrorCount = 0
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
                    self.logger.debug(f"Received data: {receivedData}")
                    errorCount = 0
                except timeout:
                    self.logger.debug("Reception timeout")
                except socket.timeout:
                    self.logger.debug("Socket reception timeout")
                except Exception as e:
                    self.logger.info(f"Error during data reception: {e}")
                    errorCount = errorCount  + 1
                    doReconnect = True

                if not receivedData: 
                    self.logger.debug("Received empty data")
                else: 
                    self.logger.debug(f"Received data: {receivedData}")
                    #try:
                    self.decodeEventData(receivedData)
                    #except Exception as e:
                    #    self.logger.error(f"Exception during decodeEventData: {e}")


            # Error handling:
            if errorCount > 2:
                errorCount = 1
                self.logger.debug("Waiting for 60 seconds")
                self.exit_event.wait(timeout=60)
       
            if not self.alive:
                self.logger.debug("Alive check negative. Breaking")
                break

            if doReconnect:
                if self.networkID:
                    self.logger.debug("Trying to reopen websocket")
                    try:                    
                        self.openWebsocket(self.networkID)
                    except Exception as e:
                        self.logger.error(f"Exception during openWebsocket in while loop: {e}")
                    doReconnect = False
                else:
                    self.logger.warning("Cannot reconnect due to invalid network ID")
                    noNetworkIDErrorCount = noNetworkIDErrorCount + 1
            if noNetworkIDErrorCount > 10:
                self.logger.warning("Requesting new network and session ID")
                try:                    
                    self.sessionID, self.networkID, self.numberNetworks = self.getSessionCredentials()
                except Exception as e:
                    self.logger.error(f"Exception during getSessionCredectials: {e}")

                noNetworkIDErrorCount = 0
        
        self.logger.debug(f"Debug Casambi: self.alive: {self.alive}")
        if self.websocket:
            self.websocket.close()

        self.logger.debug("Debug Casambi EventHandler thread stopped")


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.exit_event.set()
        if self.websocket:
            self.websocket.close()

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
                    self.logger.error(f"Could not find casambi_id for item {item}")
                    return None
            rx_key = item.conf['casambi_rx_key'].upper()
            id = int(id_item.conf['casambi_id'])

            if (not id in self._rx_items):
                self._rx_items[id] = []
            self._rx_items[id].append(item)
            #self.logger.debug(f"rx-items dict: {self._rx_items}")

        if self.has_iattr(item.conf, 'casambi_tx_key'):
            # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
            id_item = item
            while not self.has_iattr( id_item.conf, 'casambi_id'):
                id_item = id_item.return_parent()
                if (id_item is self._sh):
                    self.logger.error(f"Could not find casambi_id for item {item}")
                    return None

            tx_key = item.conf['casambi_tx_key'].upper()
            id = int(id_item.conf['casambi_id'])
            #self.logger.debug(f"New TX-item: {item} with casambi ID: {id} and tx key: {tx_key}")
          
            # register item for event handling via smarthomeNG core. Needed for sending control actions:
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        #self.logger.debug("Call function << update_item >>")

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
            self.logger.debug(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'casambi_tx_key'):
                # look from the most specifie info (tx/rx key) up to id info - one id might use multiple tx/rx child elements
                id_item = item
                while not self.has_iattr( id_item.conf, 'casambi_id'):
                    id_item = id_item.return_parent()
                    if (id_item is self._sh):
                        self.logger.error(f"Could not find casambi_id for item {item}")
                        return None

                tx_key = item.conf['casambi_tx_key'].upper()
                id = int(id_item.conf['casambi_id'])

                self.logger.debug(f"update_item was called with item '{item}' from caller '{caller}', source '{source}' and dest '{dest}'")
                self.logger.debug(f"Update TX-item: {item} with casambi ID: {id} and tx key: {tx_key}")
                self.controlDevice(item, id, tx_key)
                #self.debugTest(item, id, tx_key) 

        pass

    def get_rxItemLength(self):
        return len(self._rx_items)

