# https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/steps-to-create-a-smart-home-skill
# https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference
import os
import sys
from argparse import Namespace




from http.server import BaseHTTPRequestHandler, HTTPServer
import ssl
import json
import uuid
from datetime import datetime
import colorsys

from . import p3_tools as p3tools

 
ALEXA_Range_Controller={}

DEFAULT_RANGE = (0, 100)
DEFAULT_RANGE_LOGIC = (True, False)


## Start - Definitions for global used Utterances from the global catalog
ALEXA_Range_Controller["capabilityResources"] = {"friendlyNames":[{"@type":"asset","value":{"assetId":"Alexa.Setting.Opening"}}]}
ALEXA_Range_Controller["configuration"] = {"supportedRange":{"minimumValue":0,"maximumValue":100,"precision":1},"unitOfMeasure":"Alexa.Unit.Percent"}
ALEXA_Range_Controller["semantics"] =  {"actionMappings":[{"@type":"ActionsToDirective","actions":["Alexa.Actions.Close"],"directive":{"name":"SetRangeValue","payload":{"rangeValue":100}}},{"@type":"ActionsToDirective","actions":["Alexa.Actions.Open"],"directive":{"name":"SetRangeValue","payload":{"rangeValue":0}}},{"@type":"ActionsToDirective","actions":["Alexa.Actions.Lower"],"directive":{"name":"AdjustRangeValue","payload":{"rangeValueDelta":999,"rangeValueDeltaDefault":False}}},{"@type":"ActionsToDirective","actions":["Alexa.Actions.Raise"],"directive":{"name":"AdjustRangeValue","payload":{"rangeValueDelta":-999,"rangeValueDeltaDefault":False}}}],"stateMappings":[{"@type":"StatesToValue","states":["Alexa.States.Closed"],"value":0},{"@type":"StatesToRange","states":["Alexa.States.Open"],"range":{"minimumValue":1,"maximumValue":100}}]}

## End  - Definitions for global used Utterances from the global catalog
                                                                                                                                                                                                                                                                                                                                                                                                                                               


def what_percentage(value, range):
    _min, _max = range
    return ( (value - _min) / (_max - _min) ) * 100

def percent_2_kelvin(value, device_range):
    _minDevice, _maxDevice = device_range
    range2Set = _maxDevice - _minDevice
    
    kelvin2Add = (value/100.0*range2Set)
    
    value_new = round((kelvin2Add+_minDevice)/10)*10
    if value_new > _maxDevice:
        value_new = _maxDevice
    if value_new < _minDevice:
        value_new = _minDevice
    
    
    return value_new

class AlexaService(object):
    def __init__(self, Proto, logger, version, devices, actions, host, port, auth=None, https_certfile=None, https_keyfile=None):
        self.logger = logger
        self.version = version
        self.devices = devices
        self.actions = actions
        self._proto = Proto
        self._protocol = Proto
        self.logger.info("Alexa: service setup at {}:{}".format(host, port))

        handler_factory = lambda *args: AlexaRequestHandler(self._proto,logger, version, devices, actions, *args)
        self.server = HTTPServer((host, port), handler_factory)

        if https_certfile: # https://www.piware.de/2011/01/creating-an-https-server-in-python/
            self.logger.info("Alexa: enabling SSL/TLS support with cert-file {} & key-file {}".format(https_certfile, https_keyfile))
            # TODO: client-certificates can be handled here as well: https://docs.python.org/2/library/ssl.html
            self.server.socket = ssl.wrap_socket(self.server.socket, server_side=True, certfile=https_certfile, keyfile=https_keyfile)

    def start(self):
        self.logger.info("Alexa: service starting")
        self._proto.addEntry('INFO   ', "Alexa - service starting")
        self.server.serve_forever()
        

    def stop(self):
        self.logger.info("Alexa: service stopping")
        self.server.shutdown()
    
    

class AlexaRequestHandler(BaseHTTPRequestHandler):
    def __init__(self,Proto, logger, version, devices, actions, *args):
        self.logger = logger
        self.version = version
        self.devices = devices
        self.actions = actions
        self._proto = Proto
        BaseHTTPRequestHandler.__init__(self, *args)
    
    

        
        
    
    # find Value for Key in Json-structure
    # needed for Alexa Payload V3
    
    def search(self,p, strsearch):
        if type(p) is dict:  
            if strsearch in p:
                tokenvalue = p[strsearch]
                if not tokenvalue is None:
                 return tokenvalue
            else:
                for i in p:
                    tokenvalue = self.search(p[i], strsearch)  
                    if not tokenvalue is None:
                        return tokenvalue    
    def replace(self,p, strsearch, newValue):
        if type(p) is dict:  
            if strsearch in p:
                tokenvalue = p[strsearch]
                p[strsearch] = newValue
                if not tokenvalue is None:
                 return tokenvalue
            else:
                for i in p:
                    tokenvalue = self.replace(p[i], strsearch,newValue)  
                    if not tokenvalue is None:
                        return tokenvalue
    
    def GenerateThermoList(self, myModes, listType):
            mylist = myModes.split(' ')
            myValueList = {}
            myModeList = {}
            for i in mylist:
                key=i.split(':')
                myValueList[key[0]]=key[1]
                myModeList[key[1]] = key[0]
            if listType == 1:
                return myValueList
            elif listType == 2:
                return myModeList                    
    def do_POST(self):
        self.logger.debug("{} {} {}".format(self.request_version, self.command, self.path))
        try:
            length = int(self.headers.get('Content-Length'))
            data = self.rfile.read(length).decode('utf-8')
            req = json.loads(data)
            #======================================
            # Test Payloadversion
            #======================================
            payloadVersion = self.search( req,'payloadVersion')
            #======================================
            # PayloadVersion = 2 -> Standard Handling
            #======================================
            
            if payloadVersion == '2':
                
                self.logger.debug("Alexa: received Request with payload : 2")                
                header = req['header']
                payload = req['payload']
    
                if header['namespace'] == 'Alexa.ConnectedHome.System':
                    return self.handle_system(header, payload)
    
                elif header['namespace'] == 'Alexa.ConnectedHome.Discovery':
                    return self.handle_discovery(header, payload)
    
                elif header['namespace'] == 'Alexa.ConnectedHome.Control':
                    return self.handle_control(header, payload)
    
                else:
                    msg = "unknown `header.namespace` '{}'".format(header['namespace'])
                    self.logger.error(msg)
                    self.send_error(400, explain=msg)
            #======================================
            # PayloadVersion = 3 -> new Handling
            #======================================
            elif payloadVersion == '3':
                self.logger.debug("Alexa: received Request with payload : 3")
                mydirective = self.search( req,'directive')
                header = self.search( req,'header')
                payload =  self.search( req,'payload')
                if header['namespace'] == 'Alexa.Discovery':
                    return self.p3_handle_discovery(header, payload)
                elif header['namespace'] == 'Alexa':
                    return self.p3_handle_control(header, payload,mydirective)
                
                elif mydirective != None:
                    return self.p3_handle_control(header, payload,mydirective)
                else:
                    msg = "unknown `header.namespace` '{}'".format(header['namespace'])
                    self.logger.error(msg)
                    self.send_error(400, explain=msg)
            else:
                self.send_error(500,"Request with unknown Payload '{}'".format(payloadVersion))
        except Exception as e:
            self.send_error(500, explain=str(e))
            
    def respond(self, response):
        data = json.dumps(response).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(data))
        self.end_headers()
        self.wfile.write(data)
    #========================================================
    # A.Kohler 22.06.2018
    #========================================================
    
    def handle_system(self, header, payload):
        directive = header['name']
        self.logger.debug("Alexa: system-directive '{}' received".format(directive))

        if directive == 'HealthCheckRequest':
            self.respond(self.confirm_health(payload))
        else:
            msg = "unknown `header.name` '{}'".format(directive)
            self.logger.error(msg)
            self.send_error(400, explain=msg)

    def confirm_health(self, payload):
        requested_on = payload['initiationTimestamp']
        self.logger.debug("Alexa: confirming health as requested on {}".format(requested_on))
        return {
            'header': self.header('HealthCheckResponse', 'Alexa.ConnectedHome.System'),
            'payload': {
                'description': 'The system is currently healthy',
                'isHealthy': True
                        }}
                
    def handle_discovery(self, header, payload):
        directive = header['name']
        self.logger.debug("AlexaP3: discovery-directive '{}' received".format(directive))

        if directive == 'DiscoverAppliancesRequest':
            #myResponse = self.discover_appliances()
            self.respond(self.discover_appliances())
        else:
            msg = "unknown `header.name` '{}'".format(directive)
            self.logger.error(msg)
            self.send_error(400, explain=msg)
    
            
    # Handling für Payload V3 Discovery
    
    def p3_handle_discovery(self, header, payload):
        directive = header['name']
        self.logger.debug("AlexaP3: discovery-directive '{}' received".format(directive))
        self._proto.addEntry('INFO   ', "AlexaP3: discovery-directive '{}' received".format(directive))

        if directive == 'Discover':
            self.respond(self.p3_discover_appliances())
        else:
            msg = "unknown `header.name` '{}'".format(directive)
            self.logger.error(msg)
            self._proto.addEntry('ERROR  ', msg)
            self.send_error(400, explain=msg)

    def p3_discover_appliances(self):
        discovered = []
        for device in self.devices.all():
            mycapabilities = []

            newcapa = {"type": "AlexaInterface",
                       "interface": "Alexa",
                       "version": "3"
                      }
            mycapabilities.append(newcapa)
            
            # Standard capability for Connectivity
            newcapa = {"type": "AlexaInterface",
                       "interface": "Alexa.EndpointHealth",
                       "version": "3",
                       "properties" : {
                           "supported": [
                               {
                                   "name": "connectivity"
                               }
                        ],
                       "proactivelyReported": False,
                       "retrievable": True
                       }
                       }
            mycapabilities.append(newcapa)
            
            # Start - Check Namespaces for Actions
            myNameSpace = {}
            myItems = device.backed_items()
            for Item in myItems:
                # Get all  Actions for this item
                action_names = list( map(str.strip, Item.conf['alexa_actions'].split(' ')) )
                # über alle Actions für dieses item
                for myActionName in action_names:
                    myAction = self.actions.by_name(myActionName)
                    if myAction.namespace not in str(myNameSpace):
                        myNameSpace[myAction.namespace] = myAction.response_type
                         
                for NameSpace in myNameSpace:
                    print (NameSpace, 'correspondend to ', myNameSpace[NameSpace])
                # End - Check Namespaces
            
            
            
            if len(myNameSpace) != 0:          
                for NameSpace in myNameSpace:

                    newcapa = {}
                    newcapa = {
                        "type": "AlexaInterface",
                        "interface": NameSpace,
                        "version": "3",
                        "properties": {
                            "supported": [
                                {
                                    "name": myNameSpace[NameSpace]
                                    }
                                ],
                            "proactivelyReported": device.proactivelyReported,
                            "retrievable": device.retrievable
                            }
                        }
                    # Check of special NameSpace
                    
                    if NameSpace == 'Alexa.ThermostatController':
                        AlexaItem = self.devices.get(device.id)
                        myModeList = self.GenerateThermoList(AlexaItem.thermo_config, 2)
                        myModes = []
                        for mode in myModeList:
                            myModes.append(mode)
                        mysupported = {
                                      "supportsScheduling": False,
                                      "supportedModes":
                                      myModes
                                      }
                        newcapa['properties']['configuration'] = mysupported
                        mysupported=[
                                     {"name" : 'thermostatMode'},
                                     {"name" : 'targetSetpoint'}
                                    ]
                        newcapa['properties']['supported'] = mysupported
                    

                        
                    if NameSpace == 'Alexa.SceneController':
                        newcapa={"type": "AlexaInterface",
                                 "interface": NameSpace,
                                 "version": "3",
                                 "supportsDeactivation" : False
                                }                              
                    if NameSpace == 'Alexa.CameraStreamController':
                        AlexaItem = self.devices.get(device.id)

                        myStreams = p3tools.CreateStreamSettings(AlexaItem)
                        newcapa={"type": "AlexaInterface",
                                 "interface": NameSpace,
                                 "version": "3",
                                 "cameraStreamConfigurations" : myStreams
                                }                                                         
                    if NameSpace == 'Alexa.PlaybackController':
                        AlexaItem = self.devices.get(device.id)
                        myModeList= AlexaItem.supported_actions()
                        myModes = []
                        for mode in myModeList:
                            if mode in "Play Stop FastForward Next Pause Previous Rewind StartOver":
                                myModes.append(mode)
                        newcapa={"type": "AlexaInterface",
                                  "interface": "Alexa.PlaybackController",
                                  "version": "3",
                                  "supportedOperations" : myModes
                                }
                    
                    
                    if NameSpace == 'Alexa.RangeController':
                        try:
                            if hasattr(device, "alexa_range_delta"):
                                alexa_range_delta = device.alexa_range_delta
                            else:
                                alexa_range_delta = 20      # default
                                
                            myConfig = json.dumps(ALEXA_Range_Controller["semantics"])
                            myConfig = myConfig.replace("-999",str(int(alexa_range_delta)*-1))
                            myConfig = myConfig.replace("999",str(int(alexa_range_delta)))
                            myConfig = json.loads(myConfig)
                            
                            if ("EXTERIOR_BLIND" in device.icon  or "INTERIOR_BLIND" in device.icon):
                                newcapa["instance"] = device.id
                                newcapa["capabilityResources"]  = ALEXA_Range_Controller["capabilityResources"]
                                newcapa["configuration"] = ALEXA_Range_Controller["configuration"]
                                newcapa["semantics"] = myConfig
   
                        except Exception as e:
                            pass

                            
                    # End Check special Namespace
                    mycapabilities.append(newcapa)
                if device.icon == None:
                    device.icon = ["SWITCH"]
                    
                    
                
                appliance = {
                    "endpointId": device.id,
                    "friendlyName": device.name,
                    "description": device.description + " by SmartHomeNG",
                    "manufacturerName": "SmarthomeNG",
                    "displayCategories": 
                        device.icon,
                    "cookie": {
                        'extraDetail{}'.format(idx+1) : item.property.path for idx, item in enumerate(device.backed_items())
                        },
                    "capabilities" : 
                        mycapabilities
                    }
                discovered.append(appliance)
        
        
        return {
            "event": {
            "header": {
            "namespace": "Alexa.Discovery",
            "name": "Discover.Response",
            "payloadVersion": "3",
            "messageId": uuid.uuid4().hex
            },
            "payload": {
                "endpoints": 
                discovered
                }
            }
            }
        

    # https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference#discovery-messages
    
    def discover_appliances(self):
        discovered = []
        for device in self.devices.all():
            appliance = {
                'actions': device.supported_actions(),
                'additionalApplianceDetails': {
                    'item{}'.format(idx+1) : item.property.path for idx, item in enumerate(device.backed_items())
                },
                'applianceId': device.id,
                'friendlyDescription': device.description,
                'friendlyName': device.name,
                'isReachable': True,
                'manufacturerName': 'SmartHomeNG',
                'modelName': 'SmartHomeNG',
                'version': self.version
            }
            if device.types:
                appliance['applianceTypes'] = device.types
            discovered.append(appliance)

        return {
            'header': self.header('DiscoverAppliancesResponse', 'Alexa.ConnectedHome.Discovery'),
            'payload': {
                'discoveredAppliances': discovered
            }
        }
    # ================================================
    # Resportstate for all devices
    # ================================================
    
    def p3_ReportState(self, directive):
        now = datetime.now().isoformat()
        myTimeStamp = now[0:22]+'Z'
        device_id = directive['endpoint']['endpointId']
        
        AlexaItem = self.devices.get(device_id)
        myItems = AlexaItem.backed_items()
        self._proto.addEntry('INFO   ', "received ReportState for '{}' ".format(device_id))
        Properties = []
        differentNameSpace = ''
        myValue = None  
        alreadyReportedControllers = []
        # walk over all Items examp..: Item: OG.Flur.Spots.dimmen / Item: OG.Flur.Spots
        for Item in myItems:
            msg = ""
            # Get all  Actions for this item
            action_names = list( map(str.strip, Item.conf['alexa_actions'].split(' ')) )
            # über alle Actions für dieses item
            for myActionName in action_names:
                try:
                    myAction = self.actions.by_name(myActionName)
                    differentNameSpace = ''
                    # all informations colletec (Namespace, ResponseTyp, .....
                    # check if capabilitie is alredy in
                    self.logger.debug("Alexa: ReportState for {}".format(Item._name))
                    if myAction.response_type not in str(alreadyReportedControllers):
                    #if myAction.namespace not in str(alreadyReportedControllers):
                    #if myAction.response_type not in str(Properties):
                        Propertyname = myAction.response_type
                        if myAction.namespace == "Alexa.PowerController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            myValue=Item()
                            if myValue == 0:
                                myValue = 'OFF'
                            elif myValue == 1:
                                myValue = 'ON'
                        
                        elif myAction.namespace == "Alexa.RangeController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_range = Item.alexa_range
                            item_now = Item()
                            myValue = int(what_percentage(item_now, item_range))
                        
                        elif myAction.namespace == "Alexa.ColorTemperatureController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_now = Item()
                            myPercentage = int(what_percentage(item_now, [0,255]))
                            myValue = percent_2_kelvin(myPercentage,Item.alexa_range)
                            
                        elif myAction.namespace == "Alexa.BrightnessController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_range = Item.alexa_range
                            item_now = Item()
                            myValue = int(what_percentage(item_now, item_range))
                        
                        elif myAction.namespace == "Alexa.PowerLevelController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_range = Item.alexa_range
                            item_now = Item()
                            myValue = int(what_percentage(item_now, item_range))
                            
                        elif myAction.namespace == "Alexa.LockController" and myAction.name != 'ReportLockState':
                                continue
    
                        elif myAction.namespace == "Alexa.LockController" and myAction.name == 'ReportLockState':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_new = Item()
                            if item_new == 0:
                                myValue = 'UNLOCKED'
                            elif item_new == 1:
                                myValue = 'LOCKED'
                            elif item_new == 254:
                                myValue = 'JAMMED'
                            else:
                                myValue = 'JAMMED'      # no known value -> blocked
                                 
                        
                        elif myAction.namespace == "Alexa.PercentageController":
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_range = Item.alexa_range
                            item_now = Item()
                            myValue = int(what_percentage(item_now, item_range))
                        
                        elif myAction.namespace == "Alexa.ThermostatController" and myAction.response_type == 'targetSetpoint':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_now = Item()
                            myValue = {
                                        "value": item_now,
                                        "scale": "CELSIUS"
                                      }
                        elif myAction.namespace == "Alexa.ThermostatController" and myAction.response_type == 'thermostatMode':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_now = Item()
                            myModes = AlexaItem.thermo_config
                            myValueList = self.GenerateThermoList(myModes,1)
                            myIntMode = int(item_now)
                            myMode = self.search(myValueList, str(myIntMode))
                            
                            myValue = myMode
                            
                        elif myAction.namespace == 'Alexa.TemperatureSensor':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            item_now = Item()
                            myValue = {
                                        "value": item_now,
                                        "scale": "CELSIUS"
                                      }
                        
                        elif myAction.namespace == 'Alexa.ContactSensor':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            myValue=Item()
                            if myValue == 0:
                                myValue = 'DETECTED'            # means Contact is open
                            elif myValue == 1:
                                myValue = 'NOT_DETECTED'        # means Contact is closed
                        
                        elif myAction.namespace == 'Alexa.ColorController':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            myValue=Item()
                            if len(myValue) == 0:
                                myValue.append(0)
                                myValue.append(0)
                                myValue.append(0)
                            try:
                                myColorTyp = Item.conf['alexa_color_value_type']
                            except Exception as err:
                                # default = RGB
                                myColorTyp = 'RGB'
                            if myColorTyp == 'HSB':
                                myHSB = myValue
                            else:
                                try:
                                    myHSB = p3tools.rgb_to_hsv(myValue[0], myValue[1], myValue[2])
                                except Exception as err:
                                    print(err)
    
                            myValue ={
                                        "hue": myHSB[0],
                                        "saturation": myHSB[1],
                                        "brightness": myHSB[2]
                                     }
                        elif myAction.namespace == 'Alexa.PlaybackController':
                            msg="calculating Value for Controller'{}' - Item : {} ".format(Item.property.name,myAction.namespace)
                            differentNameSpace = 'Alexa.PlaybackStateReporter'
                            myValue ={
                                     "state": "PLAYING"
                                     }                        
                        if differentNameSpace == '':
                            differentNameSpace = myAction.namespace        
                        
                        #====================================================
                        # Add default values if nothing is reported
                        #====================================================
                        if myAction.namespace not in alreadyReportedControllers:
                            if myAction.namespace == 'Alexa.LockController' and myValue == None:
                                myValue = 'LOCKED'
                        
                        MyNewProperty = {
                                        "namespace":differentNameSpace,
                                        "name":Propertyname,
                                        "value":myValue,
                                        "timeOfSample":myTimeStamp,
                                        "uncertaintyInMilliseconds":5000
                                        }
                        
                        # Take care for Controllers with instances
                        if differentNameSpace == 'Alexa.RangeController':
                            MyNewProperty["instance"] = device_id
                        
                            
                        Properties.append(MyNewProperty)
                        alreadyReportedControllers.append(myAction.response_type)
                    
                    #alreadyReportedControllers.append(myAction.namespace)
                except:
                    self._proto.addEntry('ERROR  ', msg)
        # Add the EndpointHealth Property
        MyNewProperty ={
                        "namespace": "Alexa.EndpointHealth",
                        "name": "connectivity",
                        "value": {
                          "value": "OK"
                         },
                          "timeOfSample": myTimeStamp,
                          "uncertaintyInMilliseconds": 5000
                       }
        
        
        Properties.append(MyNewProperty)
            
        myEndpoint = self.search(directive,'endpoint')
        myScope = self.search(directive,'scope')
        myEndPointID = self.search(directive,'endpointId')
        myHeader = self.search(directive,'header')
        now = datetime.now().isoformat()
        myTimeStamp = now[0:22]+'Z'
        self.replace(myHeader,'messageId',uuid.uuid4().hex)
        self.replace(myHeader,'name','StateReport')
        self.replace(myHeader,'namespace','Alexa')
        
        # Special things for special Controller
        #if myAction.namespace == 'Alexa.PlaybackController':
        #    Properties = []
        
        myResponse = {
          "context": {
            "properties":  Properties 
          },
          "event": {
              "header": myHeader
                   ,
          "endpoint" : {
                        "scope": myScope,
                        "endpointId": myEndPointID 
                       },
          "payload": {}
                    }
          }
     
        
        self._proto.addEntry('INFO   ', "respondig ReportState for '{}' ".format(myEndPointID))
        return myResponse
    
    def p3_handle_control(self, header, payload,mydirective):
        directive = header['name']
        try:
            device_id = mydirective["endpoint"]["endpointId"]
        except :
            device_id = 'unknown'
        self.logger.debug("Alexa: control-directive '{}' received".format(directive))
        
        if header['name'] == 'ReportState':
            directive =  header['namespace']+header['name']
            try:
                self.respond( self.p3_ReportState(mydirective))
                return
            except Exception as e:
                self.logger.error("Alexa P3: execution of control-directive '{}' failed: {}".format(directive, e))
                self._proto.addEntry('ERROR  ', "Alexa P3: execution of control-directive '{}' failed: {}".format(directive, e))
                self.respond({
                    'header': self.header('DriverInternalError', 'Alexa.ConnectedHome.Control'),
                    'payload': {}
                })
                return
        self._proto.addEntry('INFO   ', "received Directive {} for '{}' Payload : {}".format(directive, device_id, json.dumps(mydirective)))
        action = self.actions.for_directive(directive)
        if action:
            try:
                self._proto.addEntry('INFO   ', "response Payload : {}".format(json.dumps(mydirective)))
                self.respond( action(mydirective) )
            except Exception as e:
                self.logger.error("Alexa P3: execution of control-directive '{}' failed: {}".format(directive, e))
                self._proto.addEntry('ERROR  ', "Alexa P3: execution of control-directive '{}' failed: {}".format(directive, e))
                self.respond({
                    'header': self.header('DriverInternalError', 'Alexa.ConnectedHome.Control'),
                    'payload': {}
                })
        else:
            self.logger.error("Alexa P3: no action implemented for directive '{}'".format(directive))
            self._proto.addEntry('ERROR  ', "Alexa P3: no action implemented for directive '{}'".format(directive))
            self.respond({
                'header': self.header('UnexpectedInformationReceivedError', 'Alexa.ConnectedHome.Control'),
                'payload': {}
            })
        

    def handle_control(self, header, payload):
        directive = header['name']
        self.logger.debug("Alexa: control-directive '{}' received".format(directive))

        action = self.actions.for_directive(directive)
        if action:
            try:
                self.respond( action(payload) )
            except Exception as e:
                self.logger.error("Alexa: execution of control-directive '{}' failed: {}".format(directive, e))
                self.respond({
                    'header': self.header('DriverInternalError', 'Alexa.ConnectedHome.Control'),
                    'payload': {}
                })
        else:
            self.logger.error("Alexa: no action implemented for directive '{}'".format(directive))
            self.respond({
                'header': self.header('UnexpectedInformationReceivedError', 'Alexa.ConnectedHome.Control'),
                'payload': {}
            })

    def header(self, name, namespace):
        return {
            'messageId': uuid.uuid4().hex,
            'name': name,
            'namespace': namespace,
            'payloadVersion': '2'
        }
    
