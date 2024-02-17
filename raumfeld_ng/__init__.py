#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019  Matthias Lemke                                 <EMAIL>
#  Copyright 2020  Bernd Meiners                    Bernd.Meiners@mail.de
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

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory
import httplib2
import json
import time


class Raumfeld_ng(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.5.2'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get parameter used throughout the plugin from metadata:

        self._Host = self.get_parameter_value('host')
        self._Port = self.get_parameter_value('port')
        self._baseURL = 'http://{}:{}/raumserver'.format(self._Host, self._Port)
        self.logger.warning('self._baseURL= {}'.format(self._baseURL))

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = self.get_parameter_value('cycle')

        # Initialization code goes here
        self.Zones = []
        self.Rooms = []

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface()
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        # setup scheduler for device poll loop
        self.scheduler_add(__name__, self.poll_device, cycle=self._cycle)
        # self.get_sh().scheduler.add(__name__, self.poll_device, cycle=self._cycle)   # for shNG before v1.4

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)
        # initial Run to collect Zone Information
        self.ZoneConfig = self.getZoneConfig()

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
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
        # retrieves all Zones present in any "power state" item - from previous attempts, not used currently
        if self.has_iattr(item.conf, 'rf_renderer_name') and self.get_iattr_value(item.conf,
                    'rf_attr') == "power_state" and self.get_iattr_value(item.conf, 'rf_scope') == "zone":
            ZoneObject = {"Name": item.conf["rf_renderer_name"]}
            self.logger.info("Zonenitem found :{}".format(ZoneObject["Name"]))
            self.Zones.append(ZoneObject)

        # check for raumfeld related items and updates 'em .
        if self.has_iattr(item.conf, 'rf_attr'):
            return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        self.logger.info("item has been updated and sent to raumfeld: {}".format(item.property.path))
        if self.alive and caller != self.get_shortname():
            # code to execute, only if the item has not been changed by this this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))
            urlaction = []
            # all items which interact with this plugin have to have the "rf_attr"
            if self.has_iattr(item.conf, 'rf_attr'):
                self.logger.debug(
                    "Plugin '{}': update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(
                        self.get_fullname(), item, caller, source, dest))
                # get info of item
                renderer = self.get_iattr_value(item.conf, 'rf_renderer_name')
                value = item()

                # Power_state item is bool. If it is set to true,power has to be switched on. If not -> switched off.
                if self.get_iattr_value(item.conf, 'rf_attr') == "power_state":
                    scope = self.get_iattr_value(item.conf, 'rf_scope')
                    if value:
                        action = "leaveStandby"
                    else:
                        action = "enterManualStandby"
                    urlaction = [self._baseURL + "/controller/" + action + "?id=" + renderer + "&scope=" + scope]

                # all case-insensitive parameter-less actions can be done here:
                if self.get_iattr_value(item.conf, 'rf_attr') == 'play_state':
                    if value.lower() in ("stop", "play", "pause", "next", "prev"):
                        action = value.lower()
                        # play state actionsalways act on zone level
                        urlaction = [self._baseURL + "/controller/" + action + "?id=" + renderer + "&scope=zone"]
                    else:
                        self.logger.debug("Status nicht erkannt:" + value)

                # mute-related actions are case sensitive and scope dependend, therefore own check:
                if self.get_iattr_value(item.conf, 'rf_attr') == 'set_mute':
                    if value.lower() in ("mute", "unmute", "togglemute"):
                        if value.lower() in ("mute"):
                            action = "mute"
                        elif value.lower() in ("unmute"):
                            action = "unMute"
                        elif value.lower() in ("togglemute"):
                            action = "toggleMute"
                        else:
                            self.logger.debug("mute action nicht erkannt")

                        scope = self.get_iattr_value(item.conf, 'rf_scope')
                        urlaction = [self._baseURL + "/controller/" + action + "?id=" + renderer + "&scope=" + scope]
                    else:
                        self.logger.debug("Status nicht erkannt:" + value)

                # loads the playlist, jumps to a tracknumber and starts. playlist name is always a string, track number an integer.
                # Both can be packed in a list: ["plname",4]. Without track number always 1st track is played.
                # For call w/o tracknumber playlist name can be a single element list or simple string : ["plname"] or "plname"
                if self.get_iattr_value(item.conf, 'rf_attr') == 'load_playlist':
                    action = "loadPlaylist"
                    if type(value) == list:
                        pl = self.urlencode(value[0])
                        self.logger.info("Playlist item gefunden: {}".format(pl))
                        urlaction = [self._baseURL + "/controller/" + action + "?id=" + renderer + "&value=" + pl]
                        if len(value) == 2:
                            tracknum = str(value[1])
                            self.logger.info("Track im Playlist item gefunden: {}".format(tracknum))
                            urlaction.append(
                                self._baseURL + "/controller/seekToTrack?id=" + renderer + "&TrackNumber=" + tracknum)
                    else:
                        pl = self.urlencode(value)
                        urlaction = [self._baseURL + "/controller/" + action + "?id=" + renderer + "&value=" + pl]

                # change track item...
                if self.get_iattr_value(item.conf, 'rf_attr') == 'load_track':
                    tracknum = str(value)
                    action = "seekToTrack"
                    urlaction = [
                        self._baseURL + "/controller/" + action + "?id=" + renderer + "&TrackNumber=" + tracknum]

                # Volume...rf_mode can be used to make volume change relative.
                if self.get_iattr_value(item.conf, 'rf_attr') == 'set_volume':
                    scope = self.get_iattr_value(item.conf, 'rf_scope')
                    action = "setVolume"
                    url = self._baseURL + "/controller/" + action + "?value=" + str(
                        value) + "&id=" + renderer + "&scope=" + scope
                    if self.has_iattr(item.conf, 'rf_mode'):
                        setmode = self.get_iattr_value(item.conf, 'rf_mode')
                        if setmode == 'relative':
                            url += "&relative=1"
                    urlaction = [url]

                # here the action is performed.
                # this loop can be used if items are created which need multiple calls of the server (example: load playlist,set volume,...)
                # was used before to combine load playlist and seek to track -> no combined within one item.
                for taskindex, task in enumerate(urlaction):
                    if task != '':
                        urlobj = httplib2.Http(".cache")
                        (resp_headers, content) = urlobj.request(task, "GET")
                        response = json.loads(content.decode('utf-8'))
                        self.logger.info(json.dumps(response, sort_keys=True, indent=3, ensure_ascii=False))
                        if response["error"]:
                            self.logger.error(response["data"]["errorMessage"])
                        # if multiple calls need some delay inbetween to give raumserver some time to perform action.
                        # would make sense to make delay configurable. only happens if more than 1 task is defined.
                        if taskindex + 1 < len(urlaction):
                            time.sleep(5)

                # finally: update Zone Config Information after action.
                self.ZoneConfig = self.getZoneConfig()


    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler.
        """

        self.ZoneConfig = self.getZoneConfig()

        # now we update a couple of rf items
        items = self.get_sh().find_items('rf_attr')  # all raumfeld related items
        try:
            for i in items:     # check each item...
                renderer = i.conf["rf_renderer_name"]  # which somehow has a renderer-relation
                for Zone in self.ZoneConfig["Zones"]:
                    if renderer in Zone["Name"]:
                        if i.conf["rf_attr"] == "power_state":
                            scope = i.conf["rf_scope"]
                            # for room scope
                            if scope == "room":
                                for room in Zone["Rooms"]:
                                    if renderer in room["Name"]:
                                        ps = room["PowerState"] == "ACTIVE"
                                        i(ps, self.get_shortname())
                            # for zone scope - if speaker of a zone are "off" or "on" it is filled,
                            # if some speakers are "on" and some "off" -> set to "None"
                            if scope == "zone":
                                ps = Zone["PowerState"]
                                if ps == "Off":
                                    i(False, self.get_shortname())
                                elif ps == "On":
                                    i(True, self.get_shortname())
                                else:
                                    i(None, self.get_shortname())
                        # use a little translation between raumfeld states and plugin states to make it readable...
                        if i.conf["rf_attr"] == "play_state":
                            ps = Zone["PlayState"]
                            if ps == "STOPPED":
                                i("Stop", self.get_shortname())
                            elif ps == "PAUSED_PLAYBACK":
                                i("Pause", self.get_shortname())
                            elif ps == "PLAYING":
                                i("Play", self.get_shortname())
                            else:
                                i(None, self.get_shortname())

                        if i.conf["rf_attr"] == "set_volume":
                            for room in Zone["Rooms"]:
                                if renderer in room["Name"]:
                                    ps = room["Volume"]
                                    i(ps, self.get_shortname())

                        if i.conf["rf_attr"] == "get_mediainfo":
                            if "CurrentTrack" in Zone["PlayMedia"].keys():
                                TrackNum = int(Zone["PlayMedia"]["CurrentTrack"])
                            else:
                                TrackNum = None
                            ps = [Zone["PlayMedia"]["Album"], Zone["PlayMedia"]["Artist"], Zone["PlayMedia"]["Title"],
                                  TrackNum]
                            self.logger.info("Current Media Info: {}".format(ps))
                            i(ps, self.get_shortname())

                        if i.conf["rf_attr"] == "load_track":
                            if "CurrentTrack" in Zone["PlayMedia"].keys():
                                ps = int(Zone["PlayMedia"]["CurrentTrack"])
                                self.logger.info("Current Track Info: {}".format(ps))
                                i(ps, self.get_shortname())
                            else:
                                i(None, self.get_shortname())
                                self.logger.info("No Track Info found in Zone {}".format(Zone["Name"]))

        except Exception as err:
            self.logger.error("Beim Powerraumupdate geht was schief")
            self.logger.error(err.args)

    def urlencode(self, plain):  #if playlist names are not URL-encoded this hand-made translation. maybe not needed?
        urltext = plain.replace(' ', '%20').replace('ä', '%C3%A4').replace('ö', '%C3%B6').replace('ü',
                                                                                                  '%C3%BC').replace('Ä',
                                                                                                                    '%C3%84').replace(
            'Ö',
            '%C3%96').replace('Ü', '%C3%9C')
        # %C3%A4=ä
        # %C3%B6=ö
        # %C3%BC=ü
        # %C3%84=Ä
        # %C3%96=Ö
        # %C3%9C=Ü

        return urltext

    def getZoneConfig(self):
        # build central Config Object
        urlobj = httplib2.Http(".cache")
        (resp_headers, content) = urlobj.request(self._baseURL + "/data/getZoneConfig", "GET")
        response = json.loads(content.decode('utf-8'))
        try:
            info = response['data']['zoneConfig']['zones']
        except:
            self.logger.error(response["errorMsg"])
            return None
        ZoneCheckList = []
        Config = {"NumOfZones": 0, "Zones": []}
        for zoneListNum, zoneList in enumerate(info):
            # Seems to be always an one-element list...but to be save
            for ZoneNum, zone in enumerate(zoneList['zone']):
                if zone not in ZoneCheckList:
                    ZoneCheckList.append(zone['$']['udn'])
                    Config["NumOfZones"] += 1
                    ZoneObject = {"Name": zone['$']['udn'], "PowerState": "Off", "PlayState": "unknown",
                                  "PlayMedia": {"Title": "", "Artist": "", "Album": ""}, "Rooms": []}
                    RoomObjectList = []
                    PowerState = []
                    for roomNum, room in enumerate(zone['room']):
                        if room['$']['name'] not in RoomObjectList:
                            RoomObject = {"Name": room['$']['name'], "PowerState": room['$']['powerState'], "Mute": 0,
                                          "Volume": 0}
                            RoomObjectList.append(room['$']['name'])
                            ZoneObject["Rooms"].append(RoomObject)
                            PowerState.append(room['$']['powerState'] in "ACTIVE")
                    if all(PowerState):
                        ZoneObject["PowerState"] = "On"
                    elif any(PowerState):
                        ZoneObject["PowerState"] = "Any"
                    else:
                        ZoneObject["PowerState"] = "Off"
                    ZoneObject["Name"] = ".".join(RoomObjectList)
                    self.updateRendererState(ZoneObject)
                    Config["Zones"].append(ZoneObject)
        return Config

    def updateRendererState(self, zone):
        # fill in information about current play state and tracks infos of zone
        urlobj = httplib2.Http(".cache")
        # asking for one room yields data for whole zone-> take first room
        (resp_headers, content) = urlobj.request(
            self._baseURL + "/data/getRendererState?id=" + zone["Rooms"][0]["Name"] + "&scope=zone&onlyVirtual=true",
            "GET")
        response = json.loads(content.decode('utf-8'))
        try:
            zs = response["data"][0]
        except:
            self.logger.error("No Data for Zone " + zone["Name"] + " found")
            return

        zone["PlayState"] = zs["TransportState"]
        if zs["TransportState"] not in "NO_MEDIA_PRESENT":
            try:
                if zs["mediaItem"]["title"] is not None:
                    zone["PlayMedia"]["Title"] = zs["mediaItem"]["title"]
                else:
                    zone["PlayMedia"]["Title"] = "No title found"

                if zs["mediaItem"]["album"] is not None:
                    zone["PlayMedia"]["Album"] = zs["mediaItem"]["album"]
                else:
                    zone["PlayMedia"]["Album"] = zs["mediaItem"]["section"]

                if zs["mediaItem"]["artist"] is not None:
                    zone["PlayMedia"]["Artist"] = zs["mediaItem"]["artist"]
                else:
                    zone["PlayMedia"]["Artist"] = zs["mediaItem"]["name"]
                zone["PlayMedia"]["Section"] = zs["mediaItem"]["section"]
                zone["PlayMedia"]["CurrentTrack"] = zs["CurrentTrack"]

                zone["PlayMedia"]["PlayState"] = zs["TransportState"]
            except:
                print(json.dumps(zs, sort_keys=True, indent=3, ensure_ascii=False))
                print("Media Meta Data incomplete")

        for zroom in zone["Rooms"]:
            for room in zs["rooms"]:
                if "name" in room.keys():
                    if zroom["Name"] == room["name"]:
                        zroom["PowerState"] = room["powerState"]
                        zroom["Volume"] = room["Volume"]
                        zroom["Mute"] = room["Mute"]

    def getZonebyroom(self, room):
        pass

    def __call__(self):
        print(json.dumps(self.ZoneConfig, sort_keys=True, indent=3, ensure_ascii=False))
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

