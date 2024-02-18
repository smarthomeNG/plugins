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

DEFAULT_RANGE_COLOR_TEMP = (1000,10000)

def kelvin_2_percent(kelvin, device_range):
    _minDevice, _maxDevice = device_range
    range2Set = _maxDevice - _minDevice
    percent_kelvin = 100.0/range2Set
    kelvin2Set = kelvin-_minDevice
    value_new = kelvin2Set*percent_kelvin
    if value_new > 100.0:
        value_new = 100.0
    if value_new < 0.0:
        value_new = 0.0

    return value_new

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
    
#======================================================
# Start - A.Kohler
# P3 - Directives
#======================================================



## Alexa-ColorTemperatureController

@alexa('SetColorTemperature', 'SetColorTemperature', 'colorTemperatureInKelvin','Alexa.ColorTemperatureController',[],"3")
def SetColorTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_kelvin = float( directive['payload']['colorTemperatureInKelvin'] )

    for item in items:
        percent_new = kelvin_2_percent(new_kelvin, item.alexa_range)
        item_new = int(percent_new/100.0*255.0)
        self.logger.info("Alexa P3: SetColorTemperature({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )            # in 0-255 
        self.response_Value = None
        self.response_Value = int(new_kelvin)
    
    return self.p3_respond(directive)


@alexa('IncreaseColorTemperature', 'IncreaseColorTemperature', 'colorTemperatureInKelvin','Alexa.ColorTemperatureController',[],"3")
def IncreaseColorTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    for item in items:
        
        item_now = item()
        _min, _max = item.alexa_range
        myPercentage = int(what_percentage(item_now, [0,255]))
        new_kelvin = percent_2_kelvin(myPercentage,item.alexa_range)        
        new_kelvin = new_kelvin + int(item.alexa_color_temp_delta)
        if  (new_kelvin > _max):
            new_kelvin = _max
        percent_new = kelvin_2_percent(new_kelvin, item.alexa_range)
        item_new = int(percent_new/100.0*255.0)
        item( item_new, "alexa4p3" )
        
        self.logger.info("Alexa P3: IncreaseColorTemperature({}, {:.1f})".format(item.property.path, item_new))
        
        self.response_Value = None
        self.response_Value = int(new_kelvin)
    
    return self.p3_respond(directive)


@alexa('DecreaseColorTemperature', 'DecreaseColorTemperature', 'colorTemperatureInKelvin','Alexa.ColorTemperatureController',[],"3")
def DecreaseColorTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    for item in items:
        
        item_now = item()
        _min, _max = item.alexa_range
        myPercentage = int(what_percentage(item_now, [0,255]))
        new_kelvin = percent_2_kelvin(myPercentage,item.alexa_range)        
        new_kelvin = new_kelvin - int(item.alexa_color_temp_delta)
        if  (new_kelvin < _min):
            new_kelvin = _min
        percent_new = kelvin_2_percent(new_kelvin, item.alexa_range)
        item_new = int(percent_new/100.0*255.0)
        item( item_new, "alexa4p3" )
        
        self.logger.info("Alexa P3: DecreaseColorTemperature({}, {:.1f})".format(item.property.path, item_new))
        
        self.response_Value = None
        self.response_Value = int(new_kelvin)
    
    return self.p3_respond(directive)

# Alexa-Range-Controller

@alexa('AdjustRangeValue', 'AdjustRangeValue', 'rangeValue','Alexa.RangeController',[],"3")
def AdjustRangeValue(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    
    percentage_delta = float( directive['payload']['rangeValueDelta'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_now = item()
        percentage_now = what_percentage(item_now, item_range)
        percentage_new = clamp_percentage(percentage_now + percentage_delta, item_range)
        item_new = calc_percentage(percentage_new, item_range)
        self.logger.info("Alexa P3: AdjustRangeValue({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)
    
@alexa('SetRangeValue', 'SetRangeValue', 'rangeValue','Alexa.RangeController',[],"3")
def SetRangeValue(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['rangeValue'] )
    newValue = str(new_percentage)
    for item in items:
        oldValue=str(item())
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self._proto.addEntry('INFO   ','Changed item :{} from {} to {}'.format(item.property.name,oldValue,newValue))
        self.logger.info("Alexa P3: SetRangeValue({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(new_percentage)
    
    return self.p3_respond(directive)




# Alexa ThermostatController

@alexa('SetThermostatMode', 'SetThermostatMode', 'thermostatMode','Alexa.ThermostatController',['SetTargetTemperature'],"3")
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
        self.logger.info("Alexa: SetThermostatMode({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
    
    #new_temp = items[0]() if items else 0
    
    self.response_Value = new_Mode
    myValue = self.p3_respond(directive)
    return myValue

@alexa('AdjustTargetTemperature', 'AdjustTargetTemperature', 'targetSetpoint','Alexa.ThermostatController',['SetThermostatMode'],"3")
def AdjustTargetTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    delta_temp = float( directive['payload']['targetSetpointDelta']['value'] )
    previous_temp = items[0]() if items else 0

    for item in items:
        item_range = self.item_range(item, DEFAULT_TEMP_RANGE)
        item_new = clamp_temp(previous_temp + delta_temp, item_range)
        self.logger.info("Alexa: AdjustTargetTemperature({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )

    new_temp = items[0]() if items else 0
    
    self.response_Value = None
    self.response_Value = {
                           "value": new_temp,
                           "scale": "CELSIUS"
                          }
    myValue = self.p3_respond(directive)
    return myValue
  
@alexa('SetTargetTemperature', 'SetTargetTemperature', 'targetSetpoint','Alexa.ThermostatController',['SetThermostatMode'],"3")
def SetTargetTemperature(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    target_temp = float( directive['payload']['targetSetpoint']['value'] )
    previous_temp = items[0]() if items else 0

    for item in items:
        item_range = self.item_range(item, DEFAULT_TEMP_RANGE)
        item_new = clamp_temp(target_temp, item_range)
        self.logger.info("Alexa: SetTargetTemperature({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )

    new_temp = items[0]() if items else 0
    
    self.response_Value = None
    self.response_Value = {
                           "value": new_temp,
                           "scale": "CELSIUS"
                          }
    myValue = self.p3_respond(directive)
    return myValue
  


# Alexa PowerController

@alexa('TurnOn', 'TurnOn', 'powerState','Alexa.PowerController',[],"3")
def TurnOn(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: turnOn({}, {})".format(item.property.path, on))
        if on != None:
            item( on, "alexa4p3" )
            self.response_Value = 'ON'            
            self._proto.addEntry('INFO   ', 'Changed item :{} to {}'.format(item.property.name,self.response_Value))
    myValue = self.p3_respond(directive)
    return myValue

@alexa('TurnOff', 'TurnOff', 'powerState','Alexa.PowerController',[],"3")
def TurnOff(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: turnOff({}, {})".format(item.property.path, off))
        if off != None:
            item( off, "alexa4p3" )
            self.response_Value = 'OFF'
    return self.p3_respond(directive)


# Alexa-Doorlock Controller

@alexa('Lock', 'Lock', 'lockState','Alexa.LockController',[],"3")
def Lock(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: Lock({}, {})".format(item.property.path, on))
        if on != None:
            item( on, "alexa4p3" )
            self.response_Value = None
            self.response_Value = 'LOCKED'
    
    return self.p3_respond(directive)

@alexa('Unlock', 'Unlock', 'lockState','Alexa.LockController',[],"3")
def Unlock(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        self.logger.info("Alexa: Unlock({}, {})".format(item.property.path, off))
        if off != None:
            item( on, "alexa4p3" )
            self.response_Value = None
            self.response_Value = 'UNLOCKED'
    
    return self.p3_respond(directive)


# Alexa-Brightness-Controller 

@alexa('AdjustBrightness', 'AdjustBrightness', 'brightness','Alexa.BrightnessController',[],"3")
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
        self.logger.info("Alexa P3: AdjustBrightness({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)

@alexa('SetBrightness', 'SetBrightness', 'brightness','Alexa.BrightnessController',[],"3")
def SetBrightness(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['brightness'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetBrightness({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(new_percentage)

    return self.p3_respond(directive)



# Alexa-Percentage-Controller

@alexa('AdjustPercentage', 'AdjustPercentage', 'percentage','Alexa.PercentageController',[],"3")
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
        self.logger.info("Alexa P3: AdjustPercentage({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)
    
@alexa('SetPercentage', 'SetPercentage', 'percentage','Alexa.PercentageController',[],"3")
def SetPercentage(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['percentage'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetPercentage({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(new_percentage)
    
    return self.p3_respond(directive)


# Alexa.PowerLevelController

@alexa('AdjustPowerLevel', 'AdjustPowerLevel', 'powerLevel','Alexa.PowerLevelController',[],"3")
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
        self.logger.info("Alexa P3: AdjustPowerLevel({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(percentage_new)
    
    return self.p3_respond(directive)

@alexa('SetPowerLevel', 'SetPowerLevel', 'powerLevel','Alexa.PowerLevelController',[],"3")
def SetPowerLevel(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    new_percentage = float( directive['payload']['powerLevel'] )

    for item in items:
        item_range = self.item_range(item, DEFAULT_RANGE)
        item_new = calc_percentage(new_percentage, item_range)
        self.logger.info("Alexa P3: SetPowerLevel({}, {:.1f})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = int(new_percentage)
    
    return self.p3_respond(directive)


# Scene Controller

@alexa('Activate', 'Activate', 'ActivationStarted','Alexa.SceneController',[],"3")
def Activate(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)


    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE_LOGIC)
        item_new = on                           # Should be the No. of the Scene
        self.logger.info("Alexa P3: Activate Scene ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

# Playback-Controller

@alexa('Play', 'Play', '','Alexa.PlaybackController',[],"3")
def Play(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Play received ({}, {})".format(item.property.path, item_new))
        item( item_new )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('Stop', 'Stop', '','Alexa.PlaybackController',[],"3")
def Stop(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Stop received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('FastForward', 'FastForward', '','Alexa.PlaybackController',[],"3")
def FastForward(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC FastForward received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('Next', 'Next', '','Alexa.PlaybackController',[],"3")
def Next(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Next received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('Pause', 'Pause', '','Alexa.PlaybackController',[],"3")
def Pause(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Pause received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('Previous', 'Previous', '','Alexa.PlaybackController',[],"3")
def Previous(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Previous received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('Rewind', 'Rewind', '','Alexa.PlaybackController',[],"3")
def Rewind(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC Rewind received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)

@alexa('StartOver', 'StartOver', '','Alexa.PlaybackController',[],"3")
def StartOver(self, directive):
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        item_new = 1                   
        self.logger.info("Alexa P3: PBC StartOver received ({}, {})".format(item.property.path, item_new))
        item( item_new, "alexa4p3" )
        self.response_Value = None
        self.response_Value = item_new
    
    return self.p3_respond(directive)


# CameraStreamController
@alexa('InitializeCameraStreams', 'InitializeCameraStreams', 'cameraStreamConfigurations','Alexa.CameraStreamController',[],"3")
def InitializeCameraStreams(self, directive):
    p3tools.DumpStreamInfo(directive)
    device_id = directive['endpoint']['endpointId']
    items = self.items(device_id)
    for item in items:
        self.logger.info("Alexa P3: CameraStream Init ({})".format(item.property.path))
        response_Value = None
        AlexaItem = self.devices.get(device_id)
        response_Value = p3tools.CreateStreamPayLoad(AlexaItem)
        self.response_Value = None
        self.response_Value = response_Value
    return self.p3_respond(directive)

# Authorization Interface
@alexa('AcceptGrant', 'AcceptGrant', 'AcceptGrant.Response','Alexa.Authorization',[],"3")
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

@alexa('SetColor', 'SetColor', 'color','Alexa.ColorController',[],"3")
def SetColor(self, directive):
    new_hue = float( directive['payload']['color']['hue'] )
    new_saturation = float( directive['payload']['color']['saturation'] )
    new_brightness = float( directive['payload']['color']['brightness'] )
    # Calc to RGB
    try:
        r,g,b = p3tools.hsv_to_rgb(new_hue,new_saturation,new_brightness)
    except Exception as err:
        self.logger.error("Alexa P3: SetColor Calculate to RGB failed ({}, {})".format(item.property.path, err))
    
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
            
        self.logger.info("Alexa P3: SetColor ({}, {})".format(item.property.path, str(retValue)))
        item( retValue, "alexa4p3" )
        self.response_Value = None
        self.response_Value = directive['payload']['color']
    
    return self.p3_respond(directive)


#======================================================
# No directives only Responses for Reportstate
#======================================================
@alexa('ReportTemperature', 'ReportTemperature', 'temperature','Alexa.TemperatureSensor',[],"3")
def ReportTemperature(self, directive):
    print ("")

@alexa('ReportLockState', 'ReportLockState', 'lockState','Alexa.LockController',[],"3")
def ReportLockState(self, directive):
    print ("")

@alexa('ReportContactState', 'ReportContactState', 'detectionState','Alexa.ContactSensor',[],"3")
def ReportContactState(self, directive):
    print ("")
#======================================================
# Ende - A.Kohler
#======================================================

