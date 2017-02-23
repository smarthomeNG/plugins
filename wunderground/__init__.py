#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016-2017   Martin Sinn                         m.sinn@gmx.de
# -This plugin is inspired by a logic published by henfri
#  on the wiki of smarthome.py in 2015
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


import logging

import xml.etree.ElementTree as ET
from urllib.request import urlopen

from lib.model.smartplugin import SmartPlugin



class Wunderground(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION='1.2.1'


    ## The constructor: Initialize plugin
    #
    # Store config parameters of plugin. Smarthome.py reads these parameters from plugin.conf
    # and hands them to the __init__ method of the plugin.
    #
    #  @param self      The object pointer.
    #  @param smarthome Defined by smarthome.py.
    #  @param apikey    api key for wunderground.
    #  @param language  language for the forcast messages.
    #  @param location  location to display the weather for.
    #
    def __init__(self, smarthome, apikey='', language='de', location='', cycle='600', item_subtree='', log_start='False'):
        self.logger = logging.getLogger(__name__)
        self.__sh = smarthome

        if self.to_bool(log_start):
            self.logger.info("--------------------   Init Plugin: {0} {1}   --------------------".format(self.__class__.__name__, self.PLUGIN_VERSION))

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

        self.url = 'https://api.wunderground.com/api/' + self.apikey + '/conditions/forecast/lang:' + self.language + '/q/' + self.location + '.xml'
#        self.logger.warning("Wunderground: url={0}".format(self.url))

        if self.is_int(cycle):
            self._cycle = int(cycle)
        else:
            self._cycle = 600
            self.logger.error("Wunderground: Invalid value '"+str(cycle)+"' configured for attribute cycle in plugin.conf, using '"+str(self._cycle)+"' instead")

        self.item_subtree = str(item_subtree)
        if self.item_subtree == '':
            self.logger.warning("Wunderground: item_subtree is not configured, searching complete item-tree instead. Please configure item_subtree to reduce processing overhead" )   


    def run(self):
        """
        Run method for the plugin
        """
        if (self.apikey != '') and (self.language != ''):
            self.alive = True
            self.__sh.scheduler.add(__name__, self._update_items, prio=5, cycle=self._cycle, offset=2)
            self._update_items()


    def stop(self):
        self.alive = False


    def parse_item(self, item):
        if 'wug_xmlstring' in item.conf:
            return self.update_item
        else:
            return None


    def parse_logic(self, logic):
        pass


    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Wunderground':
#            self.logger.warning("update_item: caller={0}, item={1}".format(caller, item))
            pass


    def clean(self, v):
        if v == 'N/A':
            return -1
        try:
            import re 
            non_decimal = re.compile(r'[^-?\d*\.{0,1}\d+$]')
            w=float(non_decimal.sub('', v))
            if v.find('%')>0:
                w=w/100
            return w
        except:
            return -99999


    def _get_item_fromxml(self, item):
        """
        Parse the xml String 
        """
        try:
            s=item.conf['wug_xmlstring']
            if len(s)>0:
                self.logger.debug('_update_items: Behandle jetzt Item "{0}" mit wug_xmlstring "{1}"'.format(item,s))
                val=self.tree.findall('*/'+s)
                if len(val)==0:
                    val=self.tree.findall(s)
                if len(val)>0:
                    val=val[0].text
                    self.logger.debug('_update_items: Wert "{0}" in xml gefunden'.format(val))
                    if not isinstance(item(), str):
                        val_uncleaned = val
                        val=self.clean(val)
                    if val!=-99999:
                        if isinstance(item(), str): # ms
                            if val == None:
                                val = ''  # /ms
                        item(val)
                        self.logger.debug('_update_items: Wert "{0}" ins item geschrieben'.format(val))
                    else:
                        self.logger.debug('_update_items: WARNUNG: Wert konnte nicht gecleaned werden. Kein Wert ins item geschrieben - Item: "{0}" mit wug_xmlstring: "{1}", gefunden: "{2}"'.format(item,s,val_uncleaned))  
                else:
                    self.logger.info('_update_items: returned empty value for item "{0}"'.format(item))   
        except KeyError:
            self.logger.debug('_update_items: wug_xmlstring is empty or not existent for item "{0}"'.format(item))
            pass


    def _update_items(self):
        """
        Sheduler started update for all known items.
        """
        weatheritems = self.__sh.return_item(self.item_subtree)
        if (self.item_subtree != '') and (weatheritems == None):
            self.logger.warning("_update_items: configured item_subtree '{0}' not found, searching complete item-tree instead".format(self.item_subtree) )   

        try:
            xml = self.__sh.tools.fetch_url(self.url, timeout=5)
            #xml=minidom.parseString(xml)
        except:
            self.logger.warning('_update_items: sh.tools.fetch_url() timed out' )   
            xml = False

        if xml == False:
            self.logger.warning('_update_items: Could not read data from Wunderground' )   
        else:
            self.tree=ET.fromstring(xml)
            self.logger.info('_update_items: xml heruntergeladen {0}'.format(xml))

            if weatheritems == None:
                self.itemlist = self.__sh.find_items('wug_xmlstring')
            else:
                self.itemlist = self.__sh.find_children(weatheritems, 'wug_xmlstring')
            for item in self.itemlist:
                self._get_item_fromxml(item)

