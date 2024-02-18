
#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 Kai Meder <kai@meder.info>
#  fork 2018 Andre Kohler <andre.kohler01@googlemail.com>
#########################################################################
#  This file is part of SmartHomeNG.
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
import os
import sys
import uuid



from lib.model.smartplugin import *
from lib.item import Items
from lib.shtime import Shtime
import logging
import json
import datetime

from .device import AlexaDevices, AlexaDevice
from .action import AlexaActions
from .service import AlexaService

from . import actions_turn
from . import actions_temperature
from . import actions_percentage
from . import actions_lock
# Tools for Payload V3 

from . import p3_action
import requests




class protocoll(object):
    
    log = []
    
    def __init__(self):
        pass
    
    def addEntry(self,type, _text ):
        myLog = self.log
        if (myLog == None):
            return
        try:
            if len (myLog) >= 500:
                myLog = myLog[0:499]
        except:
            return
        now = str(datetime.datetime.now())[0:22]
        myLog.insert(0,str(now)[0:19]+' Type: ' + str(type) + ' - '+str(_text))
        self.log = myLog



class Alexa4P3(SmartPlugin):
    PLUGIN_VERSION = "1.0.2"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, *args, **kwargs):
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        
        self.sh = self.get_sh()
        self.service_port = self.get_parameter_value('service_port')
        self.service_https_certfile = None
        self.service_https_keyfile = None        
        self.service_host='0.0.0.0'        
        
        self._proto = protocoll()
        
        self.devices = AlexaDevices()
        self.actions = AlexaActions(self.sh, self.logger, self.devices,self._proto)
        
        self.service = AlexaService(self._proto,self.logger, self.PLUGIN_VERSION, self.devices, self.actions,
                                    self.service_host, int(self.service_port), self.service_https_certfile, self.service_https_keyfile)
        self.action_count_v2 = 0
        self.action_count_v3 = 0
        
        self.init_webinterface()

    def run(self):
        self.validate_devices()
        self.create_alias_devices()
        self.alive = True
        #myProto = getattr(self,'_proto.addEntry')
        #self.service._proto = myProto
        self.service.start()
        
        

    def stop(self):
        self.service.stop()
        self.alive = False


    def parse_item(self, item):
        # device/appliance
        #self.logger.debug('Parse-Item')
        device_id = None
        if 'alexa_device' in item.conf:
            device_id = item.conf['alexa_device']
        
        #supported actions/directives
        action_names = None
        if 'alexa_actions' in item.conf:
            action_names = list( map(str.strip, item.conf['alexa_actions'].split(' ')) )
            self.logger.debug("Alexa: {}-actions = {}".format(item.property.path, action_names))
            for action_name in action_names:
                if action_name and self.actions.by_name(action_name) is None:
                    self.logger.error("Alexa: invalid alexa action '{}' specified in item {}, ignoring item".format(action_name, item.property.path))
                    return None
                actAction = self.actions.by_name(action_name)
                if actAction.payload_version == "3":
                    self.action_count_v3 += 1
                else:
                    self.action_count_v2 += 1
                    
        # friendly name
        name = None
        name_is_explicit = None
        if 'alexa_name' in item.conf:
            name = item.conf['alexa_name']
            name_is_explicit = True
        elif action_names and 'name' in item.conf:
            name = item.conf['name']
            name_is_explicit = False
        
            
        # deduce device-id from name
        if name and not device_id:
            device_id = AlexaDevice.create_id_from_name(name)

        # skip this item if no device could be determined
        if device_id:
            self.logger.debug("Alexa: {}-device = {}".format(item.property.path, device_id))
        else:
            return None # skip this item

        # create device if not yet existing
        if not self.devices.exists(device_id):
            self.devices.put( AlexaDevice(device_id) )

        device = self.devices.get(device_id)
              
        # types
        if 'alexa_types' in item.conf:
            device.types = list( map(str.strip, item.conf['alexa_types'].split(' ')) )
            self.logger.debug("Alexa: {}-types = {}".format(item.property.path, device.types))

        # friendly name
        if name and (not device.name or name_is_explicit):
            self.logger.debug("Alexa: {}-name = {}".format(item.property.path, name))
            if device.name and device.name != name:
                self.logger.warning("Alexa: item {} is changing device-name of {} from '{}' to '{}'".format(item.property.path, device_id, device.name, name))
            device.name = name

        # friendly description
        if 'alexa_description' in item.conf:
            descr = item.conf['alexa_description']
            self.logger.debug("Alexa: {}-description = {}".format(item.property.path, descr))
            if device.description and device.description != descr:
                self.logger.warning("Alexa: item {} is changing device-description of {} from '{}' to '{}'".format(item.property.path, device_id, device.description, descr))
            device.description = descr

        # alias names
        if 'alexa_alias' in item.conf:
            alias_names = list( map(str.strip, item.conf['alexa_alias'].split(',')) )
            for alias_name in alias_names:
                self.logger.debug("Alexa: {}-alias = {}".format(item.property.path, alias_name))
                device.alias.append(alias_name)

        # value-range
        if 'alexa_item_range' in item.conf:
            item_min_raw, item_max_raw = item.conf['alexa_item_range'].split('-')
            item_min = float( item_min_raw.strip() )
            item_max = float( item_max_raw.strip() )
            item.alexa_range = (item_min, item_max)
            self.logger.debug("Alexa: {}-range = {}".format(item.property.path, item.alexa_range))

        # special turn on/off values
        if 'alexa_item_turn_on' in item.conf or 'alexa_item_turn_off' in item.conf:
            turn_on  = item.conf['alexa_item_turn_on']  if 'alexa_item_turn_on'  in item.conf else True
            turn_off = item.conf['alexa_item_turn_off'] if 'alexa_item_turn_off' in item.conf else False
            item.alexa_range = (turn_on, turn_off)
            self.logger.debug("Alexa: {}-range = {}".format(item.property.path, item.alexa_range))
        
        # special ColorValue Type for RGB-devices
        if 'alexa_color_value_type' in item.conf:
            alexa_color_value_type = item.conf['alexa_color_value_type']
            device.alexa_color_value_type = alexa_color_value_type
            self.logger.debug("Alexa4P3: {}-ColorValueType = {}".format(item.property.path, device.alexa_color_value_type))
        
        # special Alexa_Instance for RangeController
        if 'alexa_range_delta' in item.conf:
            alexa_range_delta = item.conf['alexa_range_delta']
            device.alexa_range_delta = alexa_range_delta
            self.logger.debug("Alexa4P3: {}-Alexa_Range_Delta = {}".format(item.property.path, device.alexa_range_delta))
        
        # special Alexa_Instance for ColorTemperaturController
        if 'alexa_color_temp_delta' in item.conf:
            alexa_color_temp_delta = item.conf['alexa_color_temp_delta']
            item.alexa_color_temp_delta = alexa_color_temp_delta
            self.logger.debug("Alexa4P3: {}-Alexa_ColorTemp_Delta = {}".format(item.property.path, item.alexa_color_temp_delta))
            
            
        #===============================================
        #P3 - Properties
        #===============================================
        # ---- Start CamerStreamController

            
        
        i=1
        while i <= 3:
            myStream='alexa_stream_{}'.format(i)
            if myStream in item.conf:
                try:
                    camera_uri = item.conf[myStream]
                    camera_uri = json.loads(camera_uri)
                    device.camera_setting[myStream] =  camera_uri
                    self.logger.debug("Alexa4P3: {}-added Camera-Streams = {}".format(item.property.path, camera_uri))
                    if 'alexa_csc_proxy_uri' in item.conf:
                        # Create a proxied URL for this Stream
                        myCam = str(uuid.uuid4().hex)
                        myProxiedurl ="%s%s%s" % (item.conf['alexa_csc_proxy_uri'], '/',myCam)
                        device.proxied_Urls['alexa_proxy_url-{}'.format(i)] = myProxiedurl
                        myNewEntry='alexa_proxy_url-{}'.format(i)
                        item.conf[myNewEntry]=myProxiedurl
                except Exception as e:
                    self.logger.debug("Alexa4P3: {}-wrong Stream Settings = {}".format(item.property.path, camera_uri))
            i +=1    
        
        if 'alexa_proxy_credentials' in item.conf:
            alexa_proxy_credentials = item.conf['alexa_proxy_credentials']
            device.alexa_proxy_credentials = alexa_proxy_credentials
            self.logger.debug("Alexa4P3: {}-Proxy-Credentials = {}".format(item.property.path, device.alexa_proxy_credentials))

        if 'alexa_csc_uri' in item.conf:
            camera_uri = item.conf['alexa_csc_uri']
            device.camera_uri = json.loads(camera_uri)
            self.logger.debug("Alexa4P3: {}-Camera-Uri = {}".format(item.property.path, device.camera_uri))
            
        
        if 'alexa_auth_cred' in item.conf:
            alexa_auth_cred = item.conf['alexa_auth_cred']
            device.alexa_auth_cred = alexa_auth_cred
            self.logger.debug("Alexa4P3: {}-Camera-Auth = {}".format(item.property.path, device.alexa_auth_cred))
            
        if 'alexa_camera_imageUri' in item.conf:
            alexa_camera_imageUri = item.conf['alexa_camera_imageUri']
            device.camera_imageUri = alexa_camera_imageUri
            self.logger.debug("Alexa4P3: {}-Camera-Image-Uri = {}".format(item.property.path, device.camera_imageUri))
        
        if 'alexa_cam_modifiers' in item.conf:
            alexa_cam_modifiers = item.conf['alexa_cam_modifiers']
            device.camera_imageUri = alexa_cam_modifiers
            self.logger.debug("Alexa4P3: {}-Camera-Stream-Modifiers = {}".format(item.property.path, device.alexa_cam_modifiers))
        
        # ---- Ende CamerStreamController    
        
        
        
        if 'alexa_thermo_config' in item.conf:
            thermo_config = item.conf['alexa_thermo_config']
            device.thermo_config =item.conf['alexa_thermo_config']
            self.logger.debug("Alexa4P3: {}-Thermo-Config = {}".format(item.property.path, device.thermo_config))
        # Icon for Alexa-App - default = SWITCH
        if 'alexa_icon' in item.conf:
            icon = item.conf['alexa_icon']
            if not icon in str(device.icon):
                device.icon.append(icon)
                self.logger.debug("Alexa4P3: {}-added alexa_icon = {}".format(item.property.path, device.icon))
        # allows to get status of ITEM, default = false
        if 'alexa_retrievable' in item.conf:
            retrievable = item.conf['alexa_retrievable']
            device.retrievable = retrievable
            self.logger.debug("Alexa4P3: {}-alexa_retrievable = {}".format(item.property.path, device.retrievable))
        
        
        if 'alexa_proactivelyReported' in item.conf:
            proactivelyReported = item.conf['alexa_proactivelyReported']
            device.proactivelyReported = proactivelyReported
            self.logger.debug("Alexa4P3: {}-alexa_proactivelyReported = {}".format(item.property.path, device.proactivelyReported))
        
            
        # register item-actions with the device
        if action_names:
            for action_name in action_names:
                device.register(action_name, item)
            self.logger.info("Alexa: {} supports {} as device {}".format(item.property.path, action_names, device_id, device.supported_actions()))
            self._proto.addEntry('INFO   ', "Alexa: {} supports {} as device {}".format(item.property.path, action_names, device_id, device.supported_actions()))

        return None

    def _update_values(self):
        return None

    def validate_devices(self):
        for device in self.devices.all():
            self.logger.debug("validating device {}".format(device.id))
            self._proto.addEntry('INFO   ', "validating device {}".format(device.id))
            if not device.validate(self.logger, self._proto):
                self.devices.delete(device.id)
                self.logger.warning("invalid device {} - removed Device from Plugin".format(device.id))
                self._proto.addEntry('WARNING', "invalid device {} - removed Device from Plugin".format(device.id))

    def create_alias_devices(self):
        for device in self.devices.all():
            alias_devices = device.create_alias_devices()
            for alias_device in alias_devices:
                self.logger.info("Alexa: device {} aliased '{}' via {}".format(device.id, alias_device.name, alias_device.id))
                self._proto.addEntry('INFO   ', "Alexa: device {} aliased '{}' via {}".format(device.id, alias_device.name, alias_device.id))
                self.devices.put( alias_device )

        self.logger.info("Alexa: providing {} devices".format( len(self.devices.all()) ))


    ################################################
    # Function for Web-Interface to Test directives
    ################################################
    def load_command_let(self,cmdName,path=None):
        myDescription   = ''
        myUrl           = ''
        myJson          = ''
        retJson         = {}
        
        if path==None:
            path=self.sh.get_basedir()+"/plugins/alexa4p3/directives/"
            
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
            self.logger.error("Error while loading Directive : {}".format(cmdName))
        return myDescription,myUrl,retJson
    

    
    def load_cmd_list(self):
        retValue=[]
        
        files = os.listdir(self.sh.get_basedir()+'/plugins/alexa4p3/directives/')
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
            os.remove(self.sh.get_basedir()+"/plugins/alexa4p3/directives/"+name+'.cmd')
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
                    
        JsonResult = self.check_json(txt_payload)
        if (JsonResult != 'Json OK'):
            result =  "Status:failure\n"
            result += "value1:"+JsonResult+"\n"
        else:
            try:
                myDummy=txt_payload.replace('<endpoint id>',selectedDevice)
                myDummy=myDummy.replace('"<nValue>"',str(txtValue))
                myDummy=myDummy.replace('<Instance>',selectedDevice)
                myDummy = json.loads(myDummy)
                myResponse = requests.post("http://127.0.0.1:"+str(self.service_port), data = json.dumps(myDummy))
                result =  "Status:OK\n"
                result += "value1: HTTP "+str(myResponse.status_code)+"\n"
                #result += "payload: HTTP "+str(myResponse.status_code)+"\n"
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
            result += "payload|"+str(myDict)+"\n"
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
            path=self.sh.get_basedir()+"/plugins/alexa4p3/directives/"
        
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
                result += "value2:Saved Directive\n"
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
    
    
    def get_alexa_items(self):
        item_count = 0
        alexa_items = []
        for device in self.plugin.devices.all():
            newEntry = {}
            supported_actions = device.supported_actions()
            newEntry['AlexaName'] = device.name
            newEntry['Alias_for'] = device.alias_for
            newEntry['Actions'] = ""
            for myAction in supported_actions:
                #==================
                actAction = self.plugin.actions.by_name(myAction)
                if actAction.payload_version == "3":
                    newEntry['Actions'] += '<font color="green">'+myAction +'</font>'+ ' / '
                else:
                    newEntry['Actions'] += '<font color="red">'+myAction +'</font>'+ ' / '
                #==================
                
            newEntry['Actions']=newEntry['Actions'][:-2]
            newEntry['Items'] = ""
            for action_items in device.action_items:
                if not str(device.action_items[action_items][0]) in newEntry['Items']:
                    newEntry['Items'] +=str(device.action_items[action_items][0])+ ' / ' 
            newEntry['Items']=newEntry['Items'][:-2]
            newEntry['DeviceID']=device.id
            alexa_items.append(newEntry)
            item_count += 1
        return item_count, alexa_items
    
    @cherrypy.expose
    def get_proto_html(self, proto_Name= None):
        if proto_Name == 'state_log_file':
            return json.dumps(self.plugin._proto.log)

    @cherrypy.expose
    def clear_proto_html(self, proto_Name= None):
        self.plugin._proto.log = []
        return None

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
    
    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered 
        """
        tmpl = self.tplenv.get_template('index.html')
        
        item_count,alexa_items = self.get_alexa_items()
        yaml_result = '\r\n'
        
        try:
            my_state_loglines = self.plugin._proto.log
            state_log_file = ''
            for line in my_state_loglines:
                state_log_file += str(line)+'\n'
        except:
            state_log_file = 'No Data available right now\n'
        
        payload_action = "used Actions Payload V2 = " + str(self.plugin.action_count_v2) + " / " +"<strong>used Actions Payload V3 = " + str(self.plugin.action_count_v3)+'</strong>'
        if (self.plugin.action_count_v2 != 0 and self.plugin.action_count_v3 != 0):
            payload_action = '<font color="red">' + payload_action + '</font>'
        else:
            payload_action = '<font color="green">' + payload_action + '</font>'
         
        
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           items=sorted(alexa_items, key=lambda k: str.lower(k['AlexaName'])),
                           item_count=item_count,
                           yaml_result=yaml_result,
                           payload_action=payload_action,
                           state_log_lines=state_log_file
                           )


