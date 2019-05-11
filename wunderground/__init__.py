#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-2017   Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  Free for non-commercial use
#
#  Plugin for the software SmartHomeNG, which allows to get weather
#  information from wunderground.com.
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


# TO DO:
#
# - Windrichtung: Wunderground liefert
#   - Nordwest statt NW
#   - Nord-Nordost statt NNO
#   - Nord-Nordwest statt NNW

import logging

import json
from urllib.request import urlopen

from lib.item import Items
from lib.model.smartplugin import *



class Wunderground(SmartPlugin):
    """
    Main class of the Wunderground-Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION='1.4.8'


    def __init__(self, sh, apikey='', language='de', location='', cycle='600', item_subtree=''):
        """
        Initalizes the plugin. The parameters described for this method are pulled from the entry in plugin.yaml.

        :param sh:                 The instance of the smarthome object, save it for later references
        :param apikey:             api key needed to access wunderground
        :param language:           language for the forcast messages
        :param location:           location to display the weather for
        :param cycle:              number of seconds between updates
        :param item_subtree:       subtree of items in which the plugin looks for items to update
        :param log_start:          x
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.',2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.__sh = sh

        self.items = Items.get_instance()

        languagedict = {"de": "DL", "en": "EN", 'fr': "FR"}
        self.apikey = str(apikey)
        if self.apikey == '':
            self.logger.error("Wunderground: No api key specified, plugin is not starting")

        self.language = ''
        self.language = languagedict.get( str(language).lower() )
        if self.language == None:
            self.language = str(language).upper()

        self.location = str(location)
        if self.location == '':
            self.logger.error("Wunderground: No location specified, plugin is not starting")

        self.url = 'https://api.wunderground.com/api/' + self.apikey + '/conditions/forecast/lang:' + self.language + '/q/' + self.location + '.json'

        self.logger.info("Wunderground: url={}".format(str(self.url)))

        if self.is_int(cycle):
            self._cycle = int(cycle)
        else:
            self._cycle = 600
            self.logger.error("Wunderground: Invalid value '"+str(cycle)+"' configured for attribute cycle in plugin.conf, using '"+str(self._cycle)+"' instead")

        self.item_subtree = str(item_subtree)
        if self.item_subtree == '':
            self.logger.warning("Wunderground: item_subtree is not configured, searching complete item-tree instead. Please configure item_subtree to reduce processing overhead" )   

        # if plugin should start even without web interface
        self.init_webinterface()

        return
        

    def run(self):
        """
        Run method for the plugin
        """
        if (self.apikey != '') and (self.language != ''):
            self.alive = True
            self.__sh.scheduler.add(__name__, self._update_items, prio=5, cycle=self._cycle, offset=2)
            self._update_items()


    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False


    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:  The item to process
        :return:      If the plugin needs to be informed of an items change you should return a call back function
                      like the function update_item down below. An example when this is needed is the knx plugin
                      where parse_item returns the update_item function when the attribute knx_send is found.
                      This means that when the items value is about to be updated, the call back function is called
                      with the item, caller, source and dest as arguments and in case of the knx plugin the value
                      can be sent to the knx with a knx write function within the knx plugin.

        """
        if 'wug_matchstring' in item.conf:
            return self.update_item
        elif 'wug_xmlstring' in item.conf:
            # if config is still stored in wug_xmlstring, copy it to wug_matchstring
            item.conf['wug_matchstring'] = item.conf['wug_xmlstring']
            return self.update_item
        else:
            return None


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method

        :param logic:  The logic to process
        """
        pass


    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values

        This function is called by the core when a value changed, 
        so the plugin can update it's peripherals

        :param item:   item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest:   if given it represents the dest
        """
        if caller != 'Wunderground':
#            self.logger.warning("update_item: caller={0}, item={1}".format(caller, item))
            pass


    def _check_result_value(self, item, val):
        """
        Check if value returned by wunderground is plausible, if the itemtype is 'num'
        
        :param item:   item to be updated with the value
        :param val:    value to be checked
        :return:       checked/cleaned value
        """
        if item.type() != 'num':
            return val

        if val in ['N/A', 'NA', '-1']:
            return -1

        dt=item.conf.get('wug_datatype', '').lower()
        oval = val
        # number has to be a percentage value
        if dt == 'percent':
            try:
                if val[-1:] == '%':
                    val = val[:-1]
            except:
                pass
                
            if self.is_float(val):
                fval = float(val)
                if (fval <0) or (fval>100):
                    val=-9999
                else:
                    val = fval
            else:
                val=-99999
            self.logger.debug("_check_result_value: wug_matchstring '{}', percent val '{}' -> '{}'".format( str(item.conf['wug_matchstring']), str(oval), str(val) ))

        # number has to be positive
        if dt == 'positive':
            if val == '--':
                val = 0
            if self.is_float(val):
                fval = float(val)
                if (fval <0):
                    val=-99999
            else:
                val=-99999

        if val==-99999:
            self.logger.warning("_check_result_value: Handling Item '{}' invalid data from wunderground for wug_datatype '{}' -> '{}'".format(item,dt, str(oval)))

        return val


    def _get_item_fromwugdata(self, item):
        """
        Parse the self.wugdata structure from wunderground json string
        
        This routine is called for every item that has a configuration parameter wug_matchstring
        
        :param item:   item to be updated
        """
        s=item.conf['wug_matchstring']
        if s == '':
            return
            
        sp = s.split('/')
        
        # parse dict structure with wunderground data to get value for item
        wrk = self.wugdata
        while True:
            if (len(sp) == 0) or (wrk == None):
                break
            if type(wrk) is list:
                if self.is_int(sp[0]):
                    if int(sp[0]) < len(wrk):
                        wrk = wrk[int(sp[0])]
                    else:
                        self.logger.error("_get_item_fromwugdata: invalid wug_matchstring '{}'; integer too large in matchstring".format(s))
                        break
                else:
                    self.logger.error("_get_item_fromwugdata: invalid wug_matchstring '{}'; integer expected in matchstring".format(s))
                    break
            else:
                wrk = wrk.get( sp[0] )
            if len(sp) == 1:
                spl = s.split('/')
                self.logger.debug("_get_item_fromwugdata: wug_matchstring split len={}, content={} -> '{}'".format( str(len(spl)), str(spl), str(wrk) ))
            sp.pop(0)

        # if a value was found, store it to item
        if wrk != None:
            cwrk = self._check_result_value(item, wrk)    
            if cwrk != -99999:
                item(cwrk, 'Wunderground')
                self.logger.debug('_get_item_fromwugdata: Value "{0}" written to item'.format(cwrk))
            else:
                self.logger.debug('_get_item_fromwugdata: WARNING: Value could not be cleaned. No value was written to item - Item: "{}"; wug_matchstring: "{}", found: "{}"'.format(item,s,wrk))  


    def _update_items(self):
        """
        Get new data from wunderground.com and update all known items
        
        This routine is started by the scheduler
        """
#        weatheritems = self.__sh.return_item(self.item_subtree)
        weatheritems = self.items.return_item(self.item_subtree)
        if (self.item_subtree != '') and (weatheritems == None):
            self.logger.warning("_update_items: configured item_subtree '{}' not found, searching complete item-tree instead".format(self.item_subtree) )   

        try:
            wugjson = self.__sh.tools.fetch_url(self.url, timeout=5)
        except:
            self.logger.warning('_update_items: sh.tools.fetch_url() timed out' )   
            wugjson = False

        if wugjson == False:
            self.logger.warning('_update_items: Could not read data from Wunderground' )   
        else:
            self.wugdata = json.loads( wugjson.decode('utf-8') )

            teststr = str(self.wugdata)
            if teststr.find("'title': ''") == -1 and teststr.find("'date': ''") == -1:
                self.logger.info('_update_items: Downloaded json {}'.format(str(self.wugdata)))
                # update items with weather information )only if no invalid forecast data is sent
                if weatheritems == None:
                    # search complete item-tree
                    self.itemlist = self.items.find_items('wug_matchstring')
                else:
                    # search subtree
                    self.itemlist = self.items.find_children(weatheritems, 'wug_matchstring')

                for item in self.itemlist:
                    # check every item
                    self._get_item_fromwugdata(item)
            else:
                self.logger.info('_update_items: Ignoring INVALID json {}'.format(str(self.wugdata)))



    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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
        from pprint import pformat
        
        plgitems = []
        for item in self.items.return_items():
            if ('wug_matchstring' in item.conf) and (item._path.startswith(self.plugin.item_subtree)):
                plgitems.append(item)

        pf = pformat(self.plugin.wugdata)
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])),
                           wugdata=self.plugin.wugdata,
                           ppwugdata=pf.replace('\n','<br>').replace(' ','&nbsp;'),
                           ppwugdata2=pf.replace('\n','<br>')
                          )

