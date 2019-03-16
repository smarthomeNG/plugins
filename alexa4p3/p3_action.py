'''
Created on 23.06.2018

@author: andreK
'''
import os
import sys
import uuid
import colorsys

from datetime import datetime



from . import p3_tools as p3tools
from .action import alexa

DEFAULT_RANGE = (0, 100)
DEFAULT_RANGE_LOGIC = (True, False)

def what_percentage(value, range):
    _min, _max = range
    return ( (value - _min) / (_max - _min) ) * 100

def calc_percentage(percent, range):
    _min, _max = range
    return (_max - _min) * (percent / 100) + _min

def clamp_percentage(percent, range):
    _min, _max = range
    return min(_max, max(_min, percent))

DEFAULT_TEMP_RANGE = (16, 26)

def clamp_temp(temp, range):
    _min, _max = range
    return min(_max, max(_min, temp))


#======================================================
# Start - A.Kohler
# P3 - Directives
#======================================================
# Alexa ThermostatController

@alexa('SetThermostatMode', 'SetThermostatMode', 'thermostatMode','Alexa.ThermostatController',['SetTargetTemperature'])
def SetThermostatMode(self, directive):
    # define Mode-Lists
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    AlexaItem = self.devices.get(device_id)
    myModes = AlexaItem.thermo_config
    myValueList = self.GenerateThermoList(myModes,1)
    myModeList = self.GenerateThermoList(myModes,2)
    
    # End of Modes-List
    
    
    new_Mode = directive['payload']['thermostatMode']['value'] 
    
    
    
    item_new = myModeList[new_Mode]
    for item in items:
        self.logger.info("Alexa: SetThermostatMode({}, {})".format(item.id(), item_new))
        item( item_new )
    
    #new_temp = items[0]() if items else 0
    
    self.response_Value = new_Mode
    myValue = self.p3_respond(directive)
    return myValue

@alexa('AdjustTargetTemperature', 'AdjustTargetTemperature', 'targetSetpoint','Alexa.ThermostatController',['SetThermostatMode'])
def AdjustTargetTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    delta_temp = float( directive['payload']['targetSetpointDelta']['value'] )
    previous_temp = items[0]() if items else 0

    for item in items:
        item_range = self.item_range(item, DEFAULT_TEMP_RANGE)
        item_new = clamp_temp(previous_temp + delta_temp, item_range)
        self.logger.info("Alexa: AdjustTargetTemperature({}, {:.1f})".format(item.id(), item_new))
        item( item_new )

    new_temp = items[0]() if items else 0
    
    self.response_Value = None
    self.response_Value = {
                           "value": new_temp,
                           "scale": "CELSIUS"
                          }
    myValue = self.p3_respond(directive)
    return myValue
  
@alexa('SetTargetTemperature', 'SetTargetTemperature', 'targetSetpoint','Alexa.ThermostatController',['SetThermostatMode'])
def SetTargetTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    target_temp = float( directive['payload']['targetSetpoint']['value'] )
    previous_temp = items[0]() if items else 0

    for item in items:
        item_range = self.item_range(item, DEFAULT_TEMP_RANGE)
        item_new = clamp_temp(target_temp, item_range)
        self.logger.info("Alexa: SetTargetTemperature({}, {:.1f})".format(item.id(), item_new))
        item( item_new )

    new_temp = items[0]() if items else 0
    
    self.response_Value = None
    self.response_Value = {
                           "value": new_temp,
                           "scale": "CELSIUS"
                          }
    myValue = self.p3_respond(directive)
    return myValue
  


# Alexa PowerController

@alexa('TurnOn', 'TurnOn', 'powerState','Alexa.PowerController',[])
def TurnOn(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: turnOn({}, {})".format(item.id(), on))
        if on != None:
            item( on )
            self.response_Value = 'ON'
    myValue = self.p3_respond(directive)
    return myValue

@alexa('TurnOff', 'TurnOff', 'powerState','Alexa.PowerController',[])
def TurnOff(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: turnOff({}, {})".format(item.id(), off))
        if off != None:
            item( off )
            self.response_Value = 'OFF'
    return self.p3_respond(directive)


# Alexa-Doorlock Controller

@alexa('Lock', 'Lock', 'lockState','Alexa.LockController',[])
def Lock(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: Lock({}, {})".format(item.id(), on))
        if on != None:
            item( on )
            self.response_Value = None
            self.response_Value = 'LOCKED'
    
    return self.p3_respond(directive)

@alexa('Unlock', 'Unlock', 'lockState','Alexa.LockController',[])
def Unlock(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: Unlock({}, {})".format(item.id(), off))
        if off != None:
            item( on )
            self.response_Value = None
            self.response_Value = 'UNLOCKED'
    
    return self.p3_respond(directive)


# Alexa-Brightness-Controller 

@alexa('AdjustBrightness', 'AdjustBrightness', 'brightness','Alexa.BrightnessController',[])
def AdjustBrightness(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    percentage_delta = float( directive['payload']['brightnessDelta'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_now = item()
        percentage_now = what_percentage(item_now, item_range)
        percentage_new = clamp_percentage(percentage_now + percentage_delta, item_range)
        item_new = calc_percentage(percentage_new, item_range)
        self.logger.info("Alexa P3: AdjustBrightness({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)

@alexa('SetBrightness', 'SetBrightness', 'brightness','Alexa.BrightnessController',[])
def SetBrightness(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['brightness'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetBrightness({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(new_percentage)

    return self.p3_respond(directive)



# Alexa-Percentage-Controller

@alexa('AdjustPercentage', 'AdjustPercentage', 'percentage','Alexa.PercentageController',[])
def AdjustPercentage(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    percentage_delta = float( directive['payload']['percentageDelta'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_now = item()
        percentage_now = what_percentage(item_now, item_range)
        percentage_new = clamp_percentage(percentage_now + percentage_delta, item_range)
        item_new = calc_percentage(percentage_new, item_range)
        self.logger.info("Alexa P3: AdjustPercentage({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)
    
@alexa('SetPercentage', 'SetPercentage', 'percentage','Alexa.PercentageController',[])
def SetPercentage(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['percentage'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetPercentage({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(new_percentage)
    
    return self.p3_respond(directive)


# Alexa.PowerLevelController

@alexa('AdjustPowerLevel', 'AdjustPowerLevel', 'powerLevel','Alexa.PowerLevelController',[])
def AdjustPowerLevel(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    percentage_delta = float( directive['payload']['powerLevelDelta'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_now = item()
        percentage_now = what_percentage(item_now, item_range)
        percentage_new = clamp_percentage(percentage_now + percentage_delta, item_range)
        item_new = calc_percentage(percentage_new, item_range)
        self.logger.info("Alexa P3: AdjustPowerLevel({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)

@alexa('SetPowerLevel', 'SetPowerLevel', 'powerLevel','Alexa.PowerLevelController',[])
def SetPowerLevel(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['powerLevel'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetPowerLevel({}, {:.1f})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = int(new_percentage)
    
    return self.p3_respond(directive)


# Scene Controller

@alexa('Activate', 'Activate', 'ActivationStarted','Alexa.SceneController',[])
def Activate(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)


    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        item_new = on                           # Should be the No. of the Scene
        self.logger.info("Alexa P3: Activate Scene ({}, {})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)


@alexa('Play', 'Play', '','Alexa.PlaybackController',[])
def Play(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

@alexa('Stop', 'Stop', '','Alexa.PlaybackController',[])
def Stop(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)


    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Stop received ({}, {})".format(item.id(), item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)


# CameraStreamController
@alexa('InitializeCameraStreams', 'InitializeCameraStreams', 'cameraStreamConfigurations','Alexa.CameraStreamController',[])
def InitializeCameraStreams(self, directive):
    
    p3tools.DumpStreamInfo(directive)
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        self.logger.info("Alexa P3: CameraStream Init ({})".format(item.id()))
        response_Value = None
        AlexaItem = self.devices.get(device_id)
        response_Value = p3tools.CreateStreamPayLoad(AlexaItem)
        self.response_Value = None
        self.response_Value = response_Value
    return self.p3_respond(directive)

# Authorization Interface
@alexa('AcceptGrant', 'AcceptGrant', 'AcceptGrant.Response','Alexa.Authorization',[])
def AcceptGrant(self, directive):
    self.logger.info("Alexa P3: AcceptGrant received ({})")
    myResponse = {
                  "event": {
                    "header": {
                      "messageId": "",
                      "namespace": "Alexa.Authorization",
                      "name": "AcceptGrant.Response",
                      "payloadVersion": "3"
                    },
                    "payload": {
                    }
                  }
                }
    self.replace(myResponse,'messageId',uuid.uuid4().hex)
    return myResponse

# Scene Controller

@alexa('SetColor', 'SetColor', 'color','Alexa.ColorController',[])
def SetColor(self, directive):
    new_hue = float( directive['payload']['color']['hue'] )
    new_saturation = float( directive['payload']['color']['saturation'] )
    new_brightness = float( directive['payload']['color']['brightness'] )
    # Calc to RGB
    try:
        r,g,b = p3tools.hsv_to_rgb(new_hue,new_saturation,new_brightness)
    except Exception as err:
        self.logger.error("Alexa P3: SetColor Calculate to RGB failed ({}, {})".format(item.id(), err))
    
    retValue=[]
    retValue.append(r)
    retValue.append(g)
    retValue.append(b)
    
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    

    for item in items:
        
        if 'alexa_color_value_type' in item.conf:
            colortype = item.conf['alexa_color_value_type']
            if colortype == 'HSB':
                old_Values = item()
                retValue=[]
                retValue.append(new_hue)
                retValue.append(new_saturation)
                if len(old_Values) > 0:
                    if int(old_Values[2])>0:
                        retValue.append(old_Values[2])
                    else:
                        retValue.append(1.0)
                else:
                    retValue.append(new_brightness)
            
        self.logger.info("Alexa P3: SetColor ({}, {})".format(item.id(), str(retValue)))
        item( retValue )
        self.response_Value = None
        self.response_Value = directive['payload']['color']
    
    return self.p3_respond(directive)


#======================================================
# No directives only Responses for Reportstate
#======================================================
@alexa('ReportTemperature', 'ReportTemperature', 'temperature','Alexa.TemperatureSensor',[])
def ReportTemperature(self, directive):
    print ("")

@alexa('ReportLockState', 'ReportLockState', 'lockState','Alexa.LockController',[])
def ReportLockState(self, directive):
    print ("")

@alexa('ReportContactState', 'ReportContactState', 'detectionState','Alexa.ContactSensor',[])
def ReportContactState(self, directive):
    print ("")
#======================================================
# Ende - A.Kohler
#======================================================

