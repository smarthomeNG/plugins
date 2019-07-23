#
#   https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference
#
import uuid
from datetime import datetime


import sys



action_func_registry = []

# action-func decorator
def alexa(action_name, directive_type, response_type, namespace, properties ):
    def store_metadata(func):
        func.alexa_action_name = action_name
        func.alexa_directive_type = directive_type
        func.alexa_response_type = response_type
        func.alexa_namespace = namespace
        func.alexa_properties = properties

        action_func_registry.append( func )
        return func
    return store_metadata


class AlexaActions(object):
    def __init__(self, sh, logger, devices):
        self.actions = {}
        self.actions_by_directive = {}
        for func in action_func_registry:
            logger.debug("Alexa: initializing action {}".format(func.alexa_action_name))
            action = AlexaAction(sh, logger, devices, func, func.alexa_action_name, func.alexa_directive_type, func.alexa_response_type,func.alexa_namespace, func.alexa_properties)
            self.actions[action.name] = action
            self.actions_by_directive[action.directive_type] = action

    def by_name(self, name):
        return self.actions[name] if name in self.actions else None

    def for_directive(self, directive):
        return self.actions_by_directive[directive] if directive in self.actions_by_directive else None
    
    

class AlexaAction(object):
    def __init__(self, sh, logger, devices, func, action_name, directive_type, response_type, namespace,properties):
        self.sh = sh
        self.logger = logger
        self.devices = devices
        self.func = func
        self.name = action_name
        self.directive_type = directive_type
        self.response_type = response_type
        #P3 Properties
        self.namespace = namespace
        self.response_Value = None
        self.properties = properties

    def __call__(self, payload):
        return self.func(self, payload)

    def items(self, device_id):
        device = self.devices.get(device_id)
        return device.items_for_action(self.name) if device else []

    def item_range(self, item, default=None):
        return item.alexa_range if hasattr(item, 'alexa_range') else default

    def header(self, name=None):
        return {
            'messageId': uuid.uuid4().hex,
            'name': name if name else self.response_type,
            'namespace': 'Alexa.ConnectedHome.Control',
            'payloadVersion': '2'
        }

    def respond(self, payload={}):
        return {
            'header': self.header(),
            'payload': payload
        }
    # find Value for Key in Json-structure
    # needed for Alexa Payload V3
    def search(self,p, strsearch):
        if type(p) is dict:  # im Dictionary nach 'language' suchen
            if strsearch in p:
                tokenvalue = p[strsearch]
                if not tokenvalue is None:
                 return tokenvalue
            else:
                for i in p:
                    tokenvalue = self.search(p[i], strsearch)  # in den anderen Elementen weiter suchen
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
        
    def p3_AddDependencies(self, orgDirective, dependency, myEndPointID):
        now = datetime.now().isoformat()
        myTimeStamp = now[0:22]+'Z'
        
    
        for addDependencies in dependency:
            AlexaItem = self.devices.get(myEndPointID)
            #myItems = AlexaItem.action_items()
            # walk over all Items examp..: Item: OG.Flur.Spots.dimmen / Item: OG.Flur.Spots
            for myAction in AlexaItem.action_items:
                if myAction == addDependencies:        # Action für dieses Device gefunden
                    myitem = AlexaItem.action_items[myAction][0]
                    myAddValue = myitem()
                    myAddName = None
                    if myAction == 'SetThermostatMode':
                        myModes = AlexaItem.thermo_config
                        myValueList = self.GenerateThermoList(myModes,1)
                        myMode = self.search(myValueList, str(int(myAddValue)))
                       
                        myAddName = {
                                      "namespace": "Alexa.ThermostatController",
                                      "name": "thermostatMode",
                                      "value": myMode,
                                      "timeOfSample": myTimeStamp,
                                      "uncertaintyInMilliseconds": 5000
                                    }
                    elif myAction == 'SetTargetTemperature':
                        myAddName = {
                                      "namespace": "Alexa.ThermostatController",
                                      "name": "targetSetpoint",
                                      "value": {
                                        "value": myAddValue,
                                        "scale": "CELSIUS"
                                               },
                                      "timeOfSample": myTimeStamp,
                                      "uncertaintyInMilliseconds": 5000
                                    }
                    if myAddName != None:
                        orgDirective['context']['properties'].append(myAddName)
        
        return orgDirective
    
    def p3_respond(self, Request):
        
        myEndpoint = self.search(Request,'endpoint')
        myScope = self.search(Request,'scope')
        myEndPointID = self.search(Request,'endpointId')
        myHeader = self.search(Request,'header')
        now = datetime.now().isoformat()
        myTimeStamp = now[0:22]+'Z'
        self.replace(myHeader,'messageId',uuid.uuid4().hex)
        self.replace(myHeader,'name','Response')
        self.replace(myHeader,'namespace','Alexa')
        
        
        myReponse = {
          "context": {
            "properties": [ {
              "namespace": self.namespace,
              "name": self.response_type,
              "value": self.response_Value,
              "timeOfSample": myTimeStamp,
              "uncertaintyInMilliseconds": 5000
            } ]
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
        
        # Check for Special Response-Type
        if self.namespace == 'Alexa.SceneController':
            
            self.replace(myReponse,'context',{})
            self.replace(myReponse,'payload',{
                                              "cause" : {
                                                "type" : "VOICE_INTERACTION"
                                              },
                                              "timestamp" : myTimeStamp
                                            })
            self.replace(myReponse,'namespace',self.namespace)
            self.replace(myReponse,'name',self.response_type,)
        
        elif self.namespace == 'Alexa.CameraStreamController':
            myContext = {
                            "properties": [
                                {
                                    "namespace": "Alexa.EndpointHealth",
                                    "name": "connectivity",
                                    "value": {
                                        "value": "OK"
                                    },
                                    "timeOfSample": myTimeStamp,
                                    "uncertaintyInMilliseconds": 200
                                }
                            ]
                    }
            self.replace(myReponse,'namespace',self.namespace)
            self.replace(myReponse,'context',myContext)
            self.replace(myReponse,'payload',self.response_Value)
        
        # Check for special needs of dependencies
        if len(self.properties) != 0:
            myReponse = self.p3_AddDependencies(myReponse, self.properties,myEndPointID)
        
        
        
        
        
        
        
        return myReponse 
   
         
# https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference#error-messages
def error(self, error_type, payload={}):
        return {
            'header': self.header(error_type),
            'payload': payload
        }
