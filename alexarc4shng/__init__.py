#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 AndreK                    andre.kohler01@googlemail.com
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5.2 and
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
from lib.shtime import Shtime


from datetime import datetime
from io import BytesIO

from subprocess import Popen, PIPE
import json
import sys
import os
import re
import urllib3
import time
import base64
import requests
from urllib.parse import urlencode




ImportPyOTPError = False
try:
    import pyotp
except Exception as err:
    ImportPyOTPError = True

class shngObjects(object):
    def __init__(self):
        self.Devices = {}

    def exists(self, id):
        return id in self.Devices

    def get(self, id):
        return self.Devices[id]

    def put(self, newID):
        self.Devices[newID] = Device()

    def all(self):
        return list( self.Devices.values() )

class Device(object):
    def __init__(self):
        self.Commands=[]

class Cmd(object):
    def __init__(self, id):
        self.id = id
        self.command = ''
        self.ItemValue = ''
        self.EndPoint = ''
        self.Action = ''
        self.Value = ''


##############################################################################
class EchoDevices(object):
    def __init__(self):
        self.devices = {}

    def exists(self, id):
        return id in self.devices

    def get(self, id):
        return self.devices[id]

    def put(self, device):
        self.devices[device.id] = device

    def all(self):
        return list( self.devices.values() )

    def get_Device_by_Serial(self, serialNo):
        for device in self.devices:
            if (serialNo == self.devices[device].serialNumber):
                return self.devices[device].id
class Echo(object):
    def __init__(self, id):
        self.id = id
        self.name = ""
        self.serialNumber = ""
        self.family = ""
        self.deviceType = ""
        self.deviceOwnerCustomerId = ""
        self.playerinfo = {}
        self.queueinfo = {}

##############################################################################

class AlexaRc4shNG(SmartPlugin):
    PLUGIN_VERSION = '1.0.3'
    ALLOW_MULTIINSTANCE = False
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    def __init__(self, sh, *args, **kwargs):
        # get Instances
        self.logger = logging.getLogger(__name__)
        self.sh = self.get_sh()
        self.items = Items.get_instance()
        self.shngObjects = shngObjects()
        self.shtime = Shtime.get_instance()
        
        # Init values
        self.header = ''
        self.cookie = {}
        self.csrf = 'N/A'
        self.postfields=''
        self.login_state = False
        self.last_update_time = ''
        self.next_update_time = ''
        self.ImportPyOTPError = False
        # get parameters
        self.cookiefile = self.get_parameter_value('cookiefile')
        self.host = self.get_parameter_value('host')
        self.AlexaEnableItem = self.get_parameter_value('item_2_enable_alexa_rc')
        self.credentials = self.get_parameter_value('alexa_credentials')
        if (self.credentials != 'None'):
            self.credentials = self.get_parameter_value('alexa_credentials').encode('utf-8')
            self.credentials = base64.decodebytes(self.credentials).decode('utf-8')
        self.LoginUpdateCycle = self.get_parameter_value('login_update_cycle')
        self.mfa_Secret = self.get_parameter_value('mfa_secret')
        self.update_file=self.sh.get_basedir()+"/plugins/alexarc4shng/lastlogin.txt"
        self.rotating_log = []
        # Check if MFA is possible
        if (ImportPyOTPError == True):
            self.logger.warning("Plugin '{}': problem during import of pyotp, you will not be able to use MFA-Authentication".format(self.get_fullname()))
            self.ImportPyOTPError = True

        if not self.init_webinterface():
            self._init_complete = False
        
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.info("Plugin '{}': start method called".format(self.get_fullname()))
        # get additional parameters from files
        self.csrf = self.parse_cookie_file(self.cookiefile)
        
        # Check login-state - if logged off and credentials are availabel login in
        if os.path.isfile(self.cookiefile):
            self.login_state=self.check_login_state()
            self.check_refresh_login()
        if (self.login_state == False and self.credentials != ''):
            try:
                os.remove(self.update_file)
            except:
                pass
            self.check_refresh_login()
            self.login_state=self.check_login_state()
        
        # Collect all devices    
        if (self.login_state):
            self.Echos = self.get_devices_by_request()
        else:
            self.Echos = None
        # enable scheduler if Login should be updated automatically
        
        if self.credentials != '':
            self.scheduler_add('check_login', self.check_refresh_login,cycle=300)
            #self.scheduler.add('plugins.alexarc4shng.check_login', self.check_refresh_login,cycle=300,from_smartplugin=True)
        
        if self.ImportPyOTPError:
            logline = str(self.shtime.now())[0:19] + ' no pyOTP installed you can not use MFA'
        else:
            logline = str(self.shtime.now())[0:19] + ' pyOTP installed you can use MFA' 
        self._insert_protocoll_entry(logline)
        
        self.alive = True
        
        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
        self.scheduler_remove('check_login')
        self.alive = False

    def parse_item(self, item):
        itemFound=False
        i=1
        
        myValue = 'alexa_cmd_{}'.format( '%0.2d' %(i))
        while myValue in item.conf:
            

            self.logger.debug("Plugin '{}': parse item: {} Command {}".format(self.get_fullname(), item,myValue))
            
            CmdItem_ID = item._name
            try:
                myCommand = item.conf[myValue].split(":")
                 
                
                if not self.shngObjects.exists(CmdItem_ID):
                    self.shngObjects.put(CmdItem_ID)
                
                actDevice = self.shngObjects.get(CmdItem_ID)
                actDevice.Commands.append(Cmd(myValue))
                
                actCommand = len(actDevice.Commands)-1
                
                actDevice.Commands[actCommand].command = item.conf[myValue]
                myCommand = actDevice.Commands[actCommand].command.split(":")
                self.logger.info("Plugin '{}': parse item: {}".format(self.get_fullname(), item.conf[myValue]))
                
                actDevice.Commands[actCommand].ItemValue = myCommand[0]
                actDevice.Commands[actCommand].EndPoint = myCommand[1]
                actDevice.Commands[actCommand].Action = myCommand[2]
                actDevice.Commands[actCommand].Value = myCommand[3]
                itemFound=True
                
            except Exception as err:
                print("Error:" ,err)
            i += 1
            myValue = 'alexa_cmd_{}'.format( '%0.2d' %(i))
            
        # todo
        # if interesting item for sending values:
        #   return update_item
        if itemFound == True:
            return self.update_item
        else:
            return None
    
    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        
        # Item was not changed but double triggered the Upate_Item-Function
        if (self.AlexaEnableItem != ""):
            AlexaEnabledItem = self.items.return_item(self.AlexaEnableItem) 
            if AlexaEnabledItem() != True:
                return
        
        if item._type == "str":
            newValue=str(item())
            oldValue=str(item.prev_value())
        elif item._type =="num":
            newValue=float(item())
            oldValue=float(item.prev_value())
        else:
            newValue=str(item())
            oldValue=str(item.prev_value())
        
        # Nur bei Wertänderung, sonst nix wie raus hier
        if(oldValue == newValue):
            return         
        # End Test
        

        
        CmdItem_ID = item._name
        
    
        if self.shngObjects.exists(CmdItem_ID):
            self.logger.debug("Plugin '{}': update_item ws called with item '{}' from caller '{}', source '{}' and dest '{}'".format(self.get_fullname(), item, caller, source, dest))
            
            actDevice = self.shngObjects.get(CmdItem_ID)
            
            for myCommand in actDevice.Commands:
                
                newValue2Set = myCommand.Value
                myItemBuffer = myCommand.ItemValue
                # Spezialfall auf bigger / smaller
                if myCommand.ItemValue.find("<=") >=0:
                    actValue = "<="
                    myCompValue = myCommand.ItemValue.replace("<="," ")
                    myCompValue = myCompValue.replace(".",",")
                    myCompValue = float(myCompValue)
                    myCommand.ItemValue = actValue                    
                    if  newValue > myCompValue:
                        return
                elif myCommand.ItemValue.find(">=") >=0:
                    actValue = ">="
                    myCompValue = myCommand.ItemValue.replace(">="," ")
                    myCompValue = myCompValue.replace(".",",")
                    myCompValue = float(myCompValue)
                    myCommand.ItemValue = actValue        
                    if newValue < myCompValue:
                        return
                elif myCommand.ItemValue.find("=") >=0 :
                    actValue = "="
                    myCompValue = myCommand.ItemValue.replace("="," ")
                    myCompValue = myCompValue.replace(".",",")
                    myCompValue = float(myCompValue)
                    myCommand.ItemValue = actValue                    
                    if newValue != myCompValue:
                        return
                elif myCommand.ItemValue.find("<") >=0:
                    actValue = "<"
                    myCompValue = myCommand.ItemValue.replace("<"," ")
                    myCompValue = myCompValue.replace(".",",")
                    myCompValue = float(myCompValue)
                    myCommand.ItemValue = actValue
                    if newValue >= myCompValue :
                        return
                elif myCommand.ItemValue.find(">") >=0:
                    actValue = ">"
                    myCompValue = myCommand.ItemValue.replace(">"," ")
                    myCompValue = myCompValue.replace(".",",")
                    myCompValue = float(myCompValue)
                    myCommand.ItemValue = actValue
                    if  newValue <= myCompValue:
                        return
                else:
                    actValue = str(item())
                    
                if ("volume" in myCommand.Action.lower()):
                    httpStatus, myPlayerInfo = self.receive_info_by_request(myCommand.EndPoint,"LoadPlayerInfo","")
                    # Store Player-Infos to Device
                    if httpStatus == 200:
                        try:
                            myActEcho = self.Echos.get(myCommand.EndPoint)
                            myActEcho.playerinfo = myPlayerInfo['playerInfo']
                            actVolume = self.search(myPlayerInfo, "volume")
                            actVolume = self.search(actVolume, "volume")
                        except:
                            actVolume = 50
                    else:
                        try:
                            actVolume = int(item())
                        except:
                            actVolume = 50
                        
                if ("volumeadj" in myCommand.Action.lower()):
                    myDelta = int(myCommand.Value)
                    if actVolume+myDelta < 0:
                        newValue2Set = 0
                    elif actVolume+myDelta > 100:
                        newValue2Set = 100
                    else:
                        newValue2Set =actVolume+myDelta
                
                # neuen Wert speichern in item
                if ("volume" in myCommand.Action.lower()):
                    item._value = newValue2Set
                    

                if (actValue == str(myCommand.ItemValue) and myCommand):
                    myCommand.ItemValue = myItemBuffer
                    self.send_cmd(myCommand.EndPoint,myCommand.Action,newValue2Set)

    
    
    # find Value for Key in Json-structure
    
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
    
    # handle Protocoll Entries
    def _insert_protocoll_entry(self, entry):
        if len(self.rotating_log) > 400:
            del self.rotating_log[400:]
        self.rotating_log.insert (0,entry)
        
    # Check if update of login is needed
    def check_refresh_login(self):
        my_file= self.update_file
        try:
            with open (my_file, 'r') as fp:
                for line in fp:
                    last_update_time = float(line)
            fp.close()
        except:
            last_update_time = 0
        
        mytime = time.time()
        if (last_update_time + self.LoginUpdateCycle < mytime):
            self.log_off()
            self.auto_login_by_request()

            # set actual values for web-interface
            self.last_update_time = datetime.fromtimestamp(mytime).strftime('%Y-%m-%d %H:%M:%S')
            self.next_update_time = datetime.fromtimestamp(mytime+self.LoginUpdateCycle).strftime('%Y-%m-%d %H:%M:%S')
            self.logger.info('refreshed Login/Cookie: %s' % self.last_update_time)
        else:
            self.last_update_time = datetime.fromtimestamp(last_update_time).strftime('%Y-%m-%d %H:%M:%S')
            self.next_update_time = datetime.fromtimestamp(last_update_time+self.LoginUpdateCycle).strftime('%Y-%m-%d %H:%M:%S')
        
        
    
    
    def replace_mutated_vowel(self,mValue):
        search =  ["ä" , "ö" , "ü" , "ß" , "Ä" , "Ö", "Ü",  "&"  , "é", "á", "ó", "ß"]
        replace = ["ae", "oe", "ue", "ss", "Ae", "Oe","Ue", "und", "e", "a", "o", "ss"]

        counter = 0
        myNewValue = mValue
        try:
            for Replacement in search:
                myNewValue = myNewValue.replace(search[counter],replace[counter])
                counter +=1
        except:
            pass
            
        return myNewValue

  

    ##############################################
    # Amazon API - Calls
    ##############################################
    
    
    def check_login_state(self):
        try:
            myHeader={
                        "DNT":"1",
                        "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:60.0) Gecko/20100101 Firefox/60.0",
                        "Connection":"keep-alive"
                      }
            mySession = requests.Session()
            mySession.cookies.update(self.cookie)
            response= mySession.get('https://'+self.host+'/api/bootstrap?version=0',
                                    headers=myHeader,allow_redirects=True)

            myContent= response.content.decode()
            myHeader = response.headers
            myDict=json.loads(myContent)
            mySession.close()
            
            self.logger.info('Status of check_login_state: %d' % response.status_code)
            
            logline = str(self.shtime.now())[0:19] +' Status of check_login_state: %d' % response.status_code
            self._insert_protocoll_entry(logline)
            
            myAuth =myDict['authentication']['authenticated']
            if (myAuth == True):
                self.logger.info('Login-State checked - Result: Logged ON' )
                logline = str(self.shtime.now())[0:19] +' Login-State checked - Result: Logged ON'
                self._insert_protocoll_entry(logline)
                return True
            else:
                self.logger.info('Login-State checked - Result: Logged OFF' )
                logline = str(self.shtime.now())[0:19] +' Login-State checked - Result: Logged OFF' 
                self._insert_protocoll_entry(logline)
                return False
            
        
        
        except Exception as err:
            self.logger.error('Login-State checked - Result: Logged OFF - try to login again')
            return False
    
    
    def get_list(self, type=""):
        if (self.login_state == False):
            return []
        myReturnList = []
        myHeader = { "Host": "alexa.amazon.de",
                   "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                   "Connection": "keep-alive",
                   "Content-Type": "application/json; charset=UTF-8",
                   "Accept-Language": "en-US,en;q=0.5",
                   "Referer": "https://alexa.amazon.de/spa/index.html",
                   "Origin":"https://alexa.amazon.de",
                   "DNT": "1"
                  }
        mySession = requests.Session()
        mySession.cookies.update(self.cookie)
        response= mySession.get('https://'+self.host + '/api/namedLists?_=1',headers=myHeader,allow_redirects=True)
        myContent= response.content.decode()
        self.logger.warning('Lists loaded - content : {}'.format(myContent))
        self._insert_protocoll_entry('Lists loaded - content : {}'.format(myContent))
        
        myLists = json.loads(myContent)
        for mylistItem in myLists['lists']:
            actList = mylistItem['itemId']
            encoded_args = urlencode({'listIds': actList})
            myListUrl = 'https://'+self.host + '/api/namedLists/{0}/items?startTime=&endTime=&completed=&{1}&_=2'.format(actList,encoded_args)
            myListResponse = mySession.get(myListUrl,headers=myHeader,allow_redirects=True)
            myListResponse= myListResponse.content.decode()
            myListResponse = json.loads(myListResponse)
            self.logger.warning('List-Entry loaded : {}'.format(myListResponse))
            self._insert_protocoll_entry('List-Entry loaded : {}'.format(myListResponse))
            for ListEntry in myListResponse['list']:
                if mylistItem['type'] == type:
                     myReturnList.append({'value': ListEntry['value'].capitalize(), 'completed' : ListEntry['completed'], 'version': ListEntry['version'], 'createdDateTime': ListEntry['createdDateTime'], 'updatedDateTime': ListEntry['updatedDateTime']})
        
        return myReturnList
    
    def receive_info_by_request(self,dvName,cmdName,mValue):
        actEcho = self.Echos.get(dvName)
        myUrl='https://'+self.host
        myDescriptions = ''
        myDict = {}
        # replace the placeholders in URL
        myUrl=self.parse_url(myUrl,
                            mValue,
                            actEcho.serialNumber,
                            actEcho.family,
                            actEcho.deviceType,
                            actEcho.deviceOwnerCustomerId)
        
        myDescription,myUrl,myDict = self.load_command_let(cmdName,None)
        
        myHeader = { "Host": "alexa.amazon.de",
                   "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                   "Connection": "keep-alive",
                   "Content-Type": "application/json; charset=UTF-8",
                   "Accept-Language": "en-US,en;q=0.5",
                   "Referer": "https://alexa.amazon.de/spa/index.html",
                   "Origin":"https://alexa.amazon.de",
                   "DNT": "1"
                  }     
        mySession = requests.Session()
        mySession.cookies.update(self.cookie)
        response= mySession.get(myUrl,headers=myHeader,allow_redirects=True)

        myResult = response.status_code
        myContent= response.content.decode()
        myHeader = response.headers
        myDict=json.loads(myContent)
        mySession.close() 

        
        return myResult,myDict
        

    
    def get_last_alexa(self):
        myHeader = { "Host": "alexa.amazon.de",
                   "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                   "Connection": "keep-alive",
                   "Content-Type": "application/json; charset=UTF-8",
                   "Accept-Language": "en-US,en;q=0.5",
                   "Referer": "https://alexa.amazon.de/spa/index.html",
                   "Origin":"https://alexa.amazon.de",
                   "DNT": "1"
                  }     
        mySession = requests.Session()
        mySession.cookies.update(self.cookie)
        response= mySession.get('https://'+self.host+'/api/activities?startTime=&size=10&offset=0',
                                headers=myHeader,allow_redirects=True)

        myContent= response.content.decode()
        myHeader = response.headers
        myDict=json.loads(myContent)
        mySession.close() 
        myDevice = myDict["activities"][0]["sourceDeviceIds"][0]["serialNumber"]
        myLastDevice = self.Echos.get_Device_by_Serial(myDevice)
        return myLastDevice
    
    def send_cmd(self,dvName, cmdName,mValue,path=None):
        # Parse the value field for dynamic content
        if (str(mValue).find("#") >= 0 and str(mValue).find("/#") >0):
            FirstPos = str(mValue).find("#")
            LastPos = str(mValue).find("/#",FirstPos)
            myItemName = str(mValue)[FirstPos+1:LastPos]
            myItem=self.items.return_item(myItemName)
            
            if myItem._type == "num":
                myValue = str(myItem())
                myValue = myValue.replace(".", ",")
            elif myItem._type == "bool":
                myValue = str(myItem())
            else:
                myValue = str(myItem())
            mValue = mValue[0:FirstPos]+myValue+mValue[LastPos:LastPos-2]+mValue[LastPos+2:len(mValue)]

        mValue = self.replace_mutated_vowel(mValue)
                
        
        buffer = BytesIO()
        actEcho = None
        try:
            actEcho = self.Echos.get(dvName)
        except:
            self.logger.warning('found no Echo with Name : {}'.format(dvName))
            self._insert_protocoll_entry('found no Echo with Name : {}'.format(dvName))
            return
        if actEcho == None:
            self.logger.warning('found no Echo with Name : {}'.format(dvName))
            self._insert_protocoll_entry('found no Echo with Name : {}'.format(dvName))
            return
        
        myUrl='https://'+self.host
        
        myDescriptions = ''
        myDict = {}
        
        
        myDescription,myUrl,myDict = self.load_command_let(cmdName,path)
        # complete the URL
        myUrl='https://'+self.host+myUrl

        # replace the placeholders in URL
        myUrl=self.parse_url(myUrl,
                            mValue,
                            actEcho.serialNumber,
                            actEcho.family,
                            actEcho.deviceType,
                            actEcho.deviceOwnerCustomerId)
        
        # replace the placeholders in Payload
        myHeaders=self.create_request_header()

        
        postfields = self.parse_json(myDict,
                                     mValue,
                                     actEcho.serialNumber,
                                     actEcho.family,
                                     actEcho.deviceType,
                                     actEcho.deviceOwnerCustomerId)
        
        try:        
            logline = str(self.shtime.now())[0:19] + ' sending command to "{}" payload {}'.format(dvName, json.dumps(postfields)) 
            self._insert_protocoll_entry(logline)
        except Exception as err:
            pass
        
        myStatus,myRespHeader, myRespCookie, myContent = self.send_post_request(myUrl,myHeaders,self.cookie,postfields)

        
        myResult = myStatus

        logline = str(self.shtime.now())[0:19] + ' Result of sending Command : {}'.format(myResult) 
        self._insert_protocoll_entry(logline)
                    
        if myResult == 200:
            self.logger.info('Status of send_cmd: %d' % myResult)

        else:
            self.logger.warning("itemStatus of send_cmd: {}: {}".format(myResult, myContent))
        
        return myResult 
        
    def get_devices_by_request(self):
        try:
            myHeader={
                        "DNT":"1",
                        "User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:60.0) Gecko/20100101 Firefox/60.0",
                        "Connection":"keep-alive"
                      }
            mySession = requests.Session()
            mySession.cookies.update(self.cookie)
            response= mySession.get('https://alexa.amazon.de/api/devices-v2/device?cached=false',
                                    headers=myHeader,allow_redirects=True)

            myContent= response.content.decode()
            myHeader = response.headers
            myDict=json.loads(myContent)
            mySession.close()
            myDevices = EchoDevices()
            
            self.logger.info('Status of get_devices_by_request: %d' % response.status_code)
            
        
        
        except Exception as err:
            self.logger.error('Error while getting Devices: %s' %err)
            return None
        
        for device in myDict['devices']:
            deviceFamily=device['deviceFamily']
            #if deviceFamily == 'WHA' or deviceFamily == 'VOX' or deviceFamily == 'FIRE_TV' or deviceFamily == 'TABLET':
            #    continue
            try:
                actName = device['accountName']
                myDevices.put(Echo(actName))
        
                actDevice = myDevices.get(actName)
                actDevice.serialNumber=device['serialNumber']
                actDevice.deviceType=device['deviceType']
                actDevice.family=device['deviceFamily']
                actDevice.name=device['accountName']
                actDevice.deviceOwnerCustomerId=device['deviceOwnerCustomerId']
            except Exception as err:
                self.logger.debug('Error while getting Devices: %s' %err)
                myDevices = None
                
        return myDevices
    
    
    
    def read_cookie_file(self,cookiefile):
        CookieFile = ""
        try:
            with open (cookiefile, 'r') as fp:
                for line in fp:
                    CookieFile += line
            fp.close()
        except Exception as err:
            self.logger.debug('Cookiefile could not be opened %s' % cookiefile)
        
        return CookieFile
    
    def parse_cookie_file(self,cookiefile):
        self.cookie = {}
        csrf = 'N/A'
        try:
            with open (cookiefile, 'r') as fp:
                for line in fp:
                    if line.find('amazon.de')<0:
                            continue
                    
                    lineFields = line.strip().split('\t')
                    if len(lineFields) >= 7:
                        # add Line to self.cookie
                        if lineFields[2] == '/':
                            self.cookie[lineFields[5]]=lineFields[6]
                        
                        
                        if lineFields[5] == 'csrf':
                            csrf = lineFields[6]
            fp.close()
        except Exception as err:
            self.logger.debug('Cookiefile could not be opened %s' % cookiefile)
        
        return csrf
    
    
    def parse_url(self,myDummy,mValue,serialNumber,familiy,deviceType,deviceOwnerCustomerId):
        
        myDummy = myDummy.strip()
        myDummy=myDummy.replace(' ','')
        # for String
        try:
            myDummy=myDummy.replace('<mValue>',mValue)
        except Exception as err:
            print("no String")
        # for Numbers
        try:    
            myDummy=myDummy.replace('"<nValue>"',mValue)
        except Exception as err:
            print("no Integer")
            
        # Inject the Device informations
        myDummy=myDummy.replace('<serialNumber>',serialNumber)
        myDummy=myDummy.replace('<familiy>',familiy)
        myDummy=myDummy.replace('<deviceType>',deviceType)
        myDummy=myDummy.replace('<deviceOwnerCustomerId>',deviceOwnerCustomerId)
        
        return myDummy

        
    def parse_json(self,myDict,mValue,serialNumber,familiy,deviceType,deviceOwnerCustomerId):

        myDummy = json.dumps(myDict, sort_keys=True)
       
        count = 0
        for char in myDummy:
          if char == '{':
            count = count + 1
         
        
        if count > 1:
            # Find First Pos for inner Object
            FirstPos = myDummy.find("{",1)
             
            # Find last Pos for inner Object
            LastPos = 0
            pos1 = 1
            while pos1 > 0:
                pos1 = myDummy.find("}",LastPos+1)
                if (pos1 >= 0):
                    correctPos = LastPos
                    LastPos = pos1
            LastPos = correctPos
        
        
            innerJson = myDummy[FirstPos+1:LastPos]
            innerJson = innerJson.replace('"','\\"')
    
            myDummy = myDummy[0:FirstPos]+'"{'+innerJson+'}"'+myDummy[LastPos+1:myDummy.__len__()]
        
            
        myDummy = myDummy.strip()
        myDummy=myDummy.replace(' ','')
        # for String
        try:
            myDummy=myDummy.replace('<mValue>',mValue)
        except Exception as err:
            print("no String")
        # for Numbers
        try:    
            myDummy=myDummy.replace('"<nValue>"',str(mValue))
        except Exception as err:
            print("no Integer")
        
        # Inject the Device informations
        myDummy=myDummy.replace('<serialNumber>',serialNumber)
        myDummy=myDummy.replace('<familiy>',familiy)
        myDummy=myDummy.replace('<deviceType>',deviceType)
        myDummy=myDummy.replace('<deviceOwnerCustomerId>',deviceOwnerCustomerId)
        
        return myDummy
    
    
    def create_request_header(self):
        myheaders= {"Host": "alexa.amazon.de",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:60.0) Gecko/20100101 Firefox/60.0",
                    "Accept": "*/*",
                    "Accept-Encoding": "deflate, gzip",
                    "DNT": "1",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept-Language": "de,nl-BE;q=0.8,en-US;q=0.5,en;q=0.3",
                    "Referer": "https://alexa.amazon.de/spa/index.html",
                    "Origin": "https://alexa.amazon.de",
                    "csrf": self.csrf,
                    "Cache-Control": "no-cache"
                  }
        return myheaders
    
    def load_command_let(self,cmdName,path=None):
        myDescription   = ''
        myUrl           = ''
        myJson          = ''
        retJson         = {}
        
        if path==None:
            path=self.sh.get_basedir()+"/plugins/alexarc4shng/cmd/"
            
        try:
            file=open(path+cmdName+'.cmd','r')
            for line in file:
                line=line.replace("\r\n","")
                line=line.replace("\n","")
                myFields=line.split("|")
                if (myFields[0]=="apiurl"):
                    myUrl=myFields[1]
                    pass
                if (myFields[0]=="description"):
                    myDescription=myFields[1]
                    pass
                if (myFields[0]=="json"):
                    myJson=myFields[1]
                    retJson=json.loads(myJson)
                    pass
            file.close()
        except:
            self.logger.error("Error while loading Commandlet : {}".format(cmdName))
        return myDescription,myUrl,retJson
    

    
    def load_cmd_list(self):
        retValue=[]
        
        files = os.listdir(self.sh.get_basedir()+'/plugins/alexarc4shng/cmd/')
        for line in files:
            try:
                line=line.split(".")
                if line[1] == "cmd":
                    newCmd = {'Name':line[0]}
                    retValue.append(newCmd)
            except:
                pass
        
        return json.dumps(retValue)

    def check_json(self,payload):
        try:
            myDump = json.loads(payload)
            return 'Json OK'
        except Exception as err:
            return 'Json - Not OK - '+ err.args[0]
        
    def delete_cmd_let(self,name):
        result = ""
        try:
            os.remove(self.sh.get_basedir()+"/plugins/alexarc4shng/cmd/"+name+'.cmd')
            result =  "Status:OK\n"
            result += "value1:File deleted\n"
        except Exception as err:
            result =  "Status:failure\n"
            result += "value1:Error - "+err.args[1]+"\n"
        
        ##################
        # prepare Response
        ##################
        myResult = result.splitlines()
        myResponse=[]
        newEntry=dict()
        for line in myResult:
            myFields=line.split(":")
            newEntry[myFields[0]] = myFields[1]

        myResponse.append(newEntry)        
        ##################
        return json.dumps(myResponse,sort_keys=True)
    
    def test_cmd_let(self,selectedDevice,txtValue,txtDescription,txt_payload,txtApiUrl):
        result = ""
        if (txtApiUrl[0:1] != "/"):
            txtApiUrl = "/"+txtApiUrl
            
        JsonResult = self.check_json(txt_payload)
        if (JsonResult != 'Json OK'):
            result =  "Status:failure\n"
            result += "value1:"+JsonResult+"\n"
        else:
            try:
                self.save_cmd_let("test", txtDescription, txt_payload, txtApiUrl, "/tmp/")
                retVal = self.send_cmd(selectedDevice,"test",txtValue,"/tmp/")
                result =  "Status:OK\n"
                result += "value1: HTTP "+str(retVal)+"\n"
            except Exception as err:
                result =  "Status:failure\n"
                result += "value1:"+err.args[0]+"\n"
                
        ##################
        # prepare Response
        ##################
        myResult = result.splitlines()
        myResponse=[]
        newEntry=dict()
        for line in myResult:
            myFields=line.split(":")
            newEntry[myFields[0]] = myFields[1]

        myResponse.append(newEntry)        
        ##################
        return json.dumps(myResponse,sort_keys=True)

    def load_cmd_2_webIf(self,txtCmdName):
        try:
            myDescription,myUrl,myDict = self.load_command_let(txtCmdName,None)
            result =  "Status|OK\n"
            result += "Description|"+myDescription+"\n"
            result += "myUrl|"+myUrl+"\n"
            result += "payload|"+json.dumps(myDict)+"\n"
        except Exception as err:
            result =  "Status|failure\n"
            result += "value1|"+err.args[0]+"\n"
        ##################
        # prepare Response
        ##################
        myResult = result.splitlines()
        myResponse=[]
        newEntry=dict()
        for line in myResult:
            myFields=line.split("|")
            newEntry[myFields[0]] = myFields[1]

        myResponse.append(newEntry)        
        ##################
        return json.dumps(myResponse,sort_keys=True)
        
        
    def save_cmd_let(self,name,description,payload,ApiURL,path=None):
        if path==None:
            path=self.sh.get_basedir()+"/plugins/alexarc4shng/cmd/"
        
        result = ""
        mydummy = ApiURL[0:1]
        if (ApiURL[0:1] != "/"):
            ApiURL = "/"+ApiURL
            
        JsonResult = self.check_json(payload)
        if (JsonResult != 'Json OK'):
            result =  "Status:failure\n"
            result += "value1:"+JsonResult+"\n"
            
        else:
            try:
                myDict = json.loads(payload)
                myDump = json.dumps(myDict)
                description=description.replace("\r"," ")
                description=description.replace("\n"," ")
                file=open(path+name+".cmd","w")
                file.write("apiurl|"+ApiURL+"\r\n")
                file.write("description|"+description+"\r\n")
                file.write("json|"+myDump+"\r\n")
                file.close
    
                result =  "Status:OK\n"
                result += "value1:"+JsonResult + "\n"
                result += "value2:Saved Commandlet\n"
            except Exception as err:
                print (err)
        
        ##################
        # prepare Response
        ##################
        myResult = result.splitlines()
        myResponse=[]
        newEntry=dict()
        for line in myResult:
            myFields=line.split(":")
            newEntry[myFields[0]] = myFields[1]

        myResponse.append(newEntry)        
        ##################
        return json.dumps(myResponse,sort_keys=True)
    
    def send_get_request(self,url="", myHeader="",Cookie=""):
        mySession = requests.Session()
        mySession.cookies.update(Cookie)
        response=mySession.get(url,
                        headers=myHeader,
                        allow_redirects=True)
        return response.status_code, response.headers, response.cookies, response.content.decode(),response.url
    
    def send_post_request(self,url="", myHeader="",Cookie="",postdata=""):
        mySession = requests.Session()
        mySession.cookies.update(Cookie)
        response=mySession.post(url,
                        headers=myHeader,
                        data=postdata,
                        allow_redirects=True)
        mySession.close()
        return response.status_code, response.headers, mySession.cookies, response.content.decode()
    
    def parse_response_cookie_2_txt(self, cookie, CollectingTxtCookie):
        for c in cookie:
            if c.domain != '':
                CollectingTxtCookie += c.domain+"\t"+str(c.domain_specified)+"\t"+ c.path+"\t"+ str(c.secure)+"\t"+ str(c.expires)+"\t"+ c.name+"\t"+ c.value+"\r\n"
        return CollectingTxtCookie
    
    def parse_response_cookie(self, cookie, CollectingCookie):
        for c in cookie:
            CollectingCookie[c.name] = c.value        
        return CollectingCookie
    
    def collect_postdata(self,content):
        content = str(content.replace('hidden', '\r\nhidden'))
        postdata = {}
        myFile = content.splitlines()
        for myLine in myFile:
            if 'hidden' in myLine:
                data = re.findall(r'hidden.*name="([^"]+).*value="([^"]+).*/',myLine)
                if len(data) >0:
                    postdata[data[0][0]]= data[0][1]
        
        
        postdata['showPasswordChecked'] = 'false'
        return postdata
    
    
    def auto_login_by_request(self):
        if self.credentials == '':
            return False
        if self.credentials   != '':
            dummy = self.credentials.split(":")
            user = dummy[0]
            pwd = dummy[1]
        myResults= []
        myCollectionTxtCookie =  ""
        myCollectionCookie = {}
        ####################################################
        # Start Step 1 - get Page without Post-Fields
        ####################################################
        myHeaders={
                    "Accept-Language":"de,en-US;q=0.7,en;q=0.3",
                    "DNT" : "1",
                    "Upgrade-Insecure-Requests" : "1",
                    "Connection":"keep-alive",
                    "Content-Type" : "text/plain;charset=UTF-8",
                    "User-Agent" : "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                    "Connection" : "keep-alive",
                    "Accept-Encoding" : "gzip, deflate, br"
                  }
        myStatus,myRespHeader, myRespCookie, myContent,myLocation = self.send_get_request('https://'+self.host+'/spa/index.html',myHeaders)
        myCollectionTxtCookie = self.parse_response_cookie_2_txt(myRespCookie,myCollectionTxtCookie)
        myCollectionCookie = self.parse_response_cookie(myRespCookie,myCollectionCookie)
        PostData = self.collect_postdata(myContent)
        
        actSessionID = myRespCookie['session-id']
        
        self.logger.info('Status of Auto-Login First Step: %d' % myStatus)
        myResults.append('HTTP : ' + str(myStatus)+'- Step 1 - get Session-ID')
        ####################################################
        # Start Step 2 - login with form
        ####################################################
        myHeaders={
                    "User-Agent" : "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                    "Accept-Language":"de,en-US;q=0.7,en;q=0.3",
                    "Accept" : "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "DNT"  : "1",
                    "Upgrade-Insecure-Requests":"1",
                    "Connection":"keep-alive",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept-Encoding" : "gzip, deflate, br",
                    "Referer": myLocation
                   }
        newUrl = "https://www.amazon.de"+"/ap/signin/"+actSessionID
        postfields = urllib3.request.urlencode(PostData)
        
        myStatus,myRespHeader, myRespCookie, myContent = self.send_post_request(newUrl,myHeaders,myCollectionCookie,PostData)
        myCollectionTxtCookie = self.parse_response_cookie_2_txt(myRespCookie,myCollectionTxtCookie)
        myCollectionCookie = self.parse_response_cookie(myRespCookie,myCollectionCookie)
        PostData = self.collect_postdata(myContent)
        
        #actSessionID = myRespCookie['session-id']
        
        self.logger.info('Status of Auto-Login Second Step: %d' % myStatus)
        myResults.append('HTTP : ' + str(myStatus)+'- Step 2 - login blank to get referer')
        
        ####################################################
        # Start Step 3 - login with form
        ####################################################
        myHeaders   ={
                        "User-Agent" : "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                        "Accept-Language" :"de,en-US;q=0.7,en;q=0.3",
                        "Accept" : "*/*",
                        "DNT" : "1",
                        "Accept-Encoding" : "gzip, deflate, br",
                        "Connection":"keep-alive",
                        "Upgrade-Insecure-Requests":"1",
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Host":"www.amazon.de",
                        "Referer":"https://www.amazon.de/ap/signin/" + actSessionID
                     }

        newUrl = "https://www.amazon.de/ap/signin"

        PostData['email'] =user
        PostData['password'] = pwd
        
        # If MFA Secret is Set - try with MFA
        if (self.mfa_Secret and self.ImportPyOTPError == False):
            self.logger.info("Plugin '{}': Try to login via MFA".format(self.get_fullname()))
            self.mfa_Secret = self.mfa_Secret.replace(" ","")
            totp = pyotp.TOTP(self.mfa_Secret)
            mfaCode = totp.now() 
            PostData['password'] += mfaCode
            myResults.append('MFA  : ' + 'use MFA/OTP - Login OTP : {}'.format(mfaCode))
            
        
        postfields = urllib3.request.urlencode(PostData)
        myStatus,myRespHeader, myRespCookie, myContent = self.send_post_request(newUrl,myHeaders,myCollectionCookie,PostData)
        myCollectionTxtCookie = self.parse_response_cookie_2_txt(myRespCookie,myCollectionTxtCookie)
        myCollectionCookie = self.parse_response_cookie(myRespCookie,myCollectionCookie)
        PostData = self.collect_postdata(myContent)
        
        self.logger.info('Status of Auto-Login third Step: %d' % myStatus)
        
        myResults.append('HTTP : ' + str(myStatus)+'- Step 3 - login with credentials')
        file=open("/tmp/alexa_step2.html","w")
        file.write(myContent)
        file.close
        
        #################################################################
        ## done - third Step - logged in now go an get the goal (csrf)
        #################################################################
        
        myHeaders ={
                    "User-Agent" : "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0",
                    "Accept-Language" : "de,en-US;q=0.7,en;q=0.3",
                    "DNT" : "1",
                    "Connection" : "keep-alive",
                    "Accept-Encoding" : "gzip, deflate",
                    "Referer" : "https://"+self.host+ "/spa/index.html",
                    "Origin":"https://"+self.host
                   }
        Url = 'https://'+self.host+'/templates/oobe/d-device-pick.handlebars'
        #Url = 'https://'+self.host+'/api/language'
        
        myStatus,myRespHeader, myRespCookie, myContent,myLocation = self.send_get_request(Url,myHeaders,myCollectionCookie)
        myCollectionTxtCookie = self.parse_response_cookie_2_txt(myRespCookie,myCollectionTxtCookie)
        myCollectionCookie = self.parse_response_cookie(myRespCookie,myCollectionCookie)

        myResults.append('HTTP : ' + str(myStatus)+'- Step 4 - get csrf')
        self.logger.info('Status of Auto-Login fourth Step: %d' % myStatus)
        
        ####################################################
        # check the csrf
        ####################################################
        myCsrf = self.search(myCollectionCookie, "csrf")
        if myCsrf != None:
            myResults.append('check CSRF- Step 5 - got good csrf')
            self.logger.info('Status of Auto-Login fifth Step - got CSRF: %s' % myCsrf)
            self.csrf = myCsrf
        else:
            myResults.append('check CSRF- Step 5 - got no CSRF')
            self.logger.info('Status of Auto-Login fifth Step - got no CSRF')

        ####################################################
        # store the new Cookie-File
        ####################################################
        try:
            with open (self.cookiefile, 'w') as myFile:
                
                
                myFile.write("# AlexaRc4shNG HTTP Cookie File"+"\r\n")
                myFile.write("# https://www.smarthomeng.de/user/"+"\r\n")
                myFile.write("# This file was generated by alexarc4shng@smarthomeNG! Edit at your own risk."+"\r\n")
                myFile.write("# ---------------------------------------------------------------------------\r\n")
                for line in myCollectionTxtCookie.splitlines():
                    myFile.write(line+"\r\n")
            myFile.close()            
            
            myResults.append('cookieFile- Step 6 - creation done')
            self.cookie = myCollectionCookie
            self.login_state= self.check_login_state()
            mytime = time.time()
            file=open(self.update_file,"w")
            file.write(str(mytime)+"\r\n")
            file.close()
            
            myResults.append('login state : %s' % self.login_state)
        except:
            myResults.append('cookieFile- Step 6 - error while writing new cookie-File')
                        
        for entry in myResults:
                logline = str(self.shtime.now())[0:19] + ' ' + entry 
                self._insert_protocoll_entry(logline)
        if (self.mfa_Secret != "" and self.ImportPyOTPError == False):
            myResults.append('use OTP-Code : '+mfaCode)
        
        return myResults
    
            
        
    
    
    def log_off(self):
        myUrl='https://'+self.host+"/logout"
        myHeaders={"DNT"       :"1",
                   "Connection":"keep-alive",
                   "User-Agent":"Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:65.0) Gecko/20100101 Firefox/65.0"
                  }
        
        myStatus,myRespHeader, myRespCookie, myContent,myLocation = self.send_get_request(myUrl,myHeaders, self.cookie)
        
        self.logger.info('Status of log_off: {}'.format(myStatus))
        
        if myStatus == 200:
            logline = str(self.shtime.now())[0:19] +' successfully logged off'
            self._insert_protocoll_entry(logline)
            return "HTTP - " + str(myStatus)+" successfully logged off"
        else:
            logline = str(self.shtime.now())[0:19] +' Error while logging off'
            return "HTTP - " + str(myStatus)+" Error while logging off"
        

    
    ##############################################
    # Web-Interface
    ##############################################
    
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
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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


    def render_template(self, tmpl_name, **kwargs):
        """

        Render a template and add vars needed gobally (for navigation, etc.)
    
        :param tmpl_name: Name of the template file to be rendered
        :param **kwargs: keyworded arguments to use while rendering
        
        :return: contents of the template after beeing rendered 

        """
        tmpl = self.tplenv.get_template(tmpl_name)
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                   plugin_info=self.plugin.get_info(), p=self.plugin,
                   **kwargs)

    def set_cookie_pic(self,CookieOK=False):
        dstFile = self.plugin.sh.get_basedir()+'/plugins/alexarc4shng/webif/static/img/plugin_logo.png'
        srcGood = self.plugin.sh.get_basedir()+'/plugins/alexarc4shng/webif/static/img/alexa_cookie_good.png'
        srcBad = self.plugin.sh.get_basedir()+'/plugins/alexarc4shng/webif/static/img/alexa_cookie_bad.png'
        if os.path.isfile(dstFile):
                os.remove(dstFile)
        if CookieOK==True:
            if os.path.isfile(srcGood):
                os.popen('cp '+srcGood + ' ' + dstFile)
        else:
            if os.path.isfile(srcBad):
                os.popen('cp '+srcBad + ' ' + dstFile)            

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        
        if (self.plugin.login_state == True):
            self.set_cookie_pic(True)
        else:
            self.set_cookie_pic(False)
            
        log_file = ''
        for line in self.plugin.rotating_log:
            log_file += str(line)+'\n'
        
        myDevices = self.get_device_list()
        alexa_device_count = len(myDevices)
        
        login_info = self.plugin.last_update_time + '<font color="green"><strong> ('+ self.plugin.next_update_time + ')</strong>'
        
        if (self.plugin.cookiefile != ""):
            cookie_txt = self.plugin.read_cookie_file(self.plugin.cookiefile)
        else:
            cookie_txt = "" 
        return self.render_template('index.html',
                                    device_list=myDevices,
                                    csrf_cookie=self.plugin.csrf,
                                    alexa_device_count=alexa_device_count,
                                    time_auto_login=login_info,
                                    log_file=log_file,
                                    cookie_txt=cookie_txt,
                                    pyOTP = self.plugin.ImportPyOTPError)
  
    @cherrypy.expose
    def handle_mfa_html(self, data = None ):
        txt_Result = {}
        myCommand = json.loads(data)
        myOrder = myCommand["Key"]
        if myOrder == "Step1":
            myUser = myCommand["data"]["User"]
            myPwd = myCommand["data"]["Pwd"]
            myResult = self.store_credentials_html('', myPwd, myUser, False, '', False)
            
            txt_Result["Status"] = "OK"
            txt_Result["Step"] = myOrder
            txt_Result["data"] = { "Result" : myResult }
            
        
        elif myOrder =="Step3":
            myMFA = myCommand["data"]["MFA"]
            myMFA = myMFA.replace(" ","")
            if (len(myMFA) != 52):
                txt_Result["Status"] = "ERROR"
                txt_Result["Step"] = myOrder
                txt_Result["data"] = { "Message" : "MFA - code has not correct length (should be 52)<br>Try again" }
            else:
                try:
                    totp = pyotp.TOTP(myMFA)
                    mfaCode = totp.now() 
                    txt_Result["Status"] = "OK"
                    txt_Result["Step"] = myOrder
                    txt_Result["data"] = { "OTPCode" : mfaCode }
                except err as Exception:
                    txt_Result["Status"] = "ERROR"
                    txt_Result["Step"] = myOrder
                    txt_Result["data"] = { "Message" : "OTP could not calculated something seems to be wrong with the MFA<br>Try again" }
        
        elif myOrder =="Step5":
            myMFA = myCommand["data"]["MFA"]
            myMFA = myMFA.replace(" ","")
            myUser = myCommand["data"]["User"]
            myPwd = myCommand["data"]["Pwd"]
            myResult = self.store_credentials_html('', myPwd, myUser, True, myMFA, False)
            if ('stored new config to filesystem' in myResult):
                txt_Result["Status"] = "OK"
                txt_Result["Step"] = myOrder
                txt_Result["data"] = { "Result" : myResult }
            else:
                txt_Result["Status"] = "ERROR"
                txt_Result["Step"] = myOrder
                txt_Result["data"] = { "Message" : 'could not store Credentials + MFA to /etc/plugin.yaml' }
        
        elif myOrder =="Step6":
            if (myCommand["data"]["command"] == 'login'):
                myResult=self.plugin.auto_login_by_request()
                txt_Result["Status"] = "OK"
                txt_Result["Step"] = myOrder
                txt_Result["data"] = { "Result" :{ "LoginState" : self.plugin.login_state} }
        
            
        return json.dumps(txt_Result)
    
    @cherrypy.expose
    def log_off_html(self,txt_Result=None):
        txt_Result=self.plugin.log_off()
        return json.dumps(txt_Result)
    
    @cherrypy.expose
    def log_in_html(self,txt_Result=None):
        txt_Result=self.plugin.auto_login_by_request()
        return json.dumps(txt_Result)
        
                           
    @cherrypy.expose
    def handle_buttons_html(self,txtValue=None, selectedDevice=None,txtButton=None,txt_payload=None,txtCmdName=None,txtApiUrl=None,txtDescription=None):
        if txtButton=="BtnSave":
            result = self.plugin.save_cmd_let(txtCmdName,txtDescription,txt_payload,txtApiUrl)
        elif txtButton =="BtnCheck":
            pass
        elif txtButton =="BtnLoad":
            result = self.plugin.load_cmd_2_webIf(txtCmdName)
            pass
        elif txtButton =="BtnTest":
            result = self.plugin.test_cmd_let(selectedDevice,txtValue,txtDescription,txt_payload,txtApiUrl)
        elif txtButton =="BtnDelete":
            result = self.plugin.delete_cmd_let(txtCmdName)
        else:
            pass
        
        #return self.render_template("index.html",txtresult=result)
        return result
                
    
    @cherrypy.expose
    def build_cmd_list_html(self,reload=None):
        myCommands = self.plugin.load_cmd_list()
        return myCommands
    
    
    def get_device_list(self):
        if (self.plugin.login_state == True):
            self.plugin.Echos = self.plugin.get_devices_by_request()
        
        Device_items = []
        try:
            myDevices = self.plugin.Echos.devices
            for actDevice in myDevices:
                newEntry=dict()
                Echo2Add=self.plugin.Echos.devices.get(actDevice)
                newEntry['name'] = Echo2Add.id
                newEntry['serialNumber'] = Echo2Add.serialNumber
                newEntry['family'] = Echo2Add.family
                newEntry['deviceType'] = Echo2Add.deviceType
                newEntry['deviceOwnerCustomerId'] = Echo2Add.deviceOwnerCustomerId
                Device_items.append(newEntry)
            
        except Exception as err:
            self.logger.debug("No devices found: {}".format(err))
        
        return Device_items

    @cherrypy.expose
    def store_credentials_html(self, encoded='', pwd = '', user= '', store_2_config=None, mfa='',login=False):
        txt_Result = []
        myCredentials = user+':'+pwd
        byte_credentials = base64.b64encode(myCredentials.encode('utf-8'))
        encoded = byte_credentials.decode("utf-8")
        txt_Result.append("encoded:"+encoded) 
        txt_Result.append("Encoding done")
        conf_file=self.plugin.sh.get_basedir()+'/etc/plugin.yaml'
        if (store_2_config == True):
            new_conf = ""
            with open (conf_file, 'r') as myFile:
                for line in myFile:
                    if line.find('alexa_credentials') > 0:
                        line = '    alexa_credentials: '+encoded+ "\r\n"
                    if line.find('mfa_secret') > 0 :
                        line = '    mfa_secret: '+mfa+ "\r\n"
                    new_conf += line 
            myFile.close()         
            txt_Result.append("replaced credentials in temporary file")
            with open (conf_file, 'w') as myFile:
                for line in new_conf.splitlines():
                    myFile.write(line+'\r\n')
            myFile.close()
            txt_Result.append("stored new config to filesystem")
            self.plugin.credentials = myCredentials
        if login == True:
            if (mfa != '' and self.plugin.ImportPyOTPError == False):
                # Try to login asap with MFA
                self.plugin.mfa_Secret = mfa
            else:
                self.plugin.mfa_Secret = ""
                
            txt_Result_Login=self.plugin.auto_login_by_request()
            for entry in txt_Result_Login:
                txt_Result.append(entry)
                
        return json.dumps(txt_Result)
    
    @cherrypy.expose
    def storecookie_html(self, cookie_txt=None,):
        txt_Result={}
        myLines = bytes(cookie_txt, "utf-8").decode("unicode_escape").replace('"','').splitlines()
        #
        # Problem - different Handling of Cookies by Browser

        file=open("/tmp/cookie.txt","w")
        for line in myLines:
            if (line != ""):
                file.write(line+"\r\n")
        file.close()
        value1 = self.plugin.parse_cookie_file("/tmp/cookie.txt")
        self.plugin.login_state = self.plugin.check_login_state()
        
        if (self.plugin.login_state == True):
            self.set_cookie_pic(True)
        else:
            self.set_cookie_pic(False)
        
        
        if (self.plugin.login_state == False) :
            # Cookies not found give back an error
            
            '''
            tmpl = self.tplenv.get_template('index.html')
            return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin,
                           txt_Result='<font color="red"><i class="fas fa-exclamation-triangle"></i> Cookies are not saved missing csrf',
                           cookie_txt=cookie_txt,
                           csrf_cookie=value1)
            '''
            txt_Result["data"] = { "Result" : False }
            return json.dumps(txt_Result)
        
        # Store the Cookie-file for permanent use
        file=open(self.plugin.cookiefile,"w")
        for line in myLines:
            file.write(line+"\r\n")
        file.close()
        
        self.plugin.csrf = value1
        
        
        myDevices = self.get_device_list()
        alexa_device_count = len(myDevices)
        
        '''
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(), p=self.plugin,
                           txt_Result='<font color="green"> <strong><i class="far fa-check-circle"></i> Cookies were saved - everything OK<strong>',
                           cookie_txt=cookie_txt,
                           csrf_cookie=value1,
                           device_list=myDevices,
                           alexa_device_count=alexa_device_count)
        '''
        txt_Result["data"] = { "Result" : True }
        return json.dumps(txt_Result)
                           

        

    
