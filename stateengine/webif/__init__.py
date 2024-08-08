#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-     <AUTHOR>                                   <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
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

import json

from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        super().__init__()
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()
        self.vis_enabled = plugin.vis_enabled

    @cherrypy.expose
    def index(self, action=None, item_id=None, item_path=None, reload=None, abitem=None, page='index'):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        item = self.plugin.get_sh().return_item(item_path)

        tmpl = self.tplenv.get_template('{}.html'.format(page))
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        if action == "get_graph" and abitem is not None:
            if isinstance(abitem, str):
                try:
                    abitem = self.plugin.abitems[abitem]
                except Exception as e:
                    self.logger.warning("Item {} not initialized yet. "
                                        "Try again later. Error: {}".format(abitem, e))
                    return None
            if self.vis_enabled:
                self.plugin.get_graph(abitem, 'graph')
            tmpl = self.tplenv.get_template('visu.html')
            return tmpl.render(p=self.plugin, item=abitem, firstrun=str(abitem.firstrun),
                               language=self.plugin.get_sh().get_defaultlanguage(), now=self.plugin.shtime.now())
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           vis_enabled=self.vis_enabled,
                           webif_pagelength=pagelength,
                           item_count=len(self.plugin._items),
                           language=self.plugin.get_sh().get_defaultlanguage(), now=self.plugin.shtime.now())

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
            for item in self.plugin.get_items():
                laststate = item.laststate_name
                laststate = "-" if laststate in ["", None] else laststate
                conditionset = item.lastconditionset_name
                conditionset = "-" if conditionset in ["", None] else conditionset
                ll = item.logger.log_level_as_num
                if item.laststate_releasedby in [None, []]:
                    lsr = "-"
                else:
                    lsr = [entry.split('.')[-1] for entry in item.laststate_releasedby]
                data.update({item.id: {'laststate': laststate,
                           'lastconditionset': conditionset, 'log_level': ll,
                           'laststate_releasedby': lsr}})
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        elif dataSet and isinstance(dataSet, str):
            try:
                dataSet = self.plugin.abitems[dataSet]
            except Exception as e:
                self.logger.warning("Item {} not initialized yet. "
                                    "Try again later. Error: {}".format(dataSet, e))
                return json.dumps({"success": "error"})
            if self.vis_enabled and dataSet.firstrun is None:
                self.plugin.get_graph(dataSet, 'graph')
                return json.dumps({"success": "true"})
            return json.dumps({"success": "false"})
        else:
            return {}
