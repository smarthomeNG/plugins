#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#  Based on ideas of sqlite plugin by Marcus Popp marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample Web Interface for new plugins to run with SmartHomeNG version 1.4
#  and upwards.
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

import os
import json

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, action=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if action == 'rescan':
            self.plugin.read_repos_from_dir()
            raise cherrypy.HTTPRedirect(cherrypy.url())

        # try to get the webif pagelength from the module.yaml configuration
        pagelength = self.plugin.get_parameter_value('webif_pagelength')

        tmpl = self.tplenv.get_template('index.html')

        reposbyowner = {}
        for repo in self.plugin.repos:
            owner = self.plugin.repos[repo]['owner']
            if owner not in reposbyowner:
                reposbyowner[owner] = []
            reposbyowner[owner].append(self.plugin.repos[repo]['branch'])

        # collect only PRs which (branches) are not already installed as a worktree
        pulls = {}
        for pr in self.plugin.gh.pulls:
            if self.plugin.gh.pulls[pr]['owner'] in reposbyowner:
                if self.plugin.gh.pulls[pr]['branch'] not in reposbyowner[self.plugin.gh.pulls[pr]['owner']]:
                    pulls[pr] = {
                        'title': self.plugin.gh.pulls[pr]['title'],
                        'owner': self.plugin.gh.pulls[pr]['owner'],
                        'branch': self.plugin.gh.pulls[pr]['branch']
                    }

        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           repos=self.plugin.repos,
                           init_repos=self.plugin.init_repos,
                           forklist=sorted(self.plugin.gh.forks.keys()),
                           forks=self.plugin.gh.forks,
                           pulls=pulls,
                           language=self.plugin.get_sh().get_defaultlanguage())

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def updateBranches(self):
        json = cherrypy.request.json
        owner = json.get("owner")
        if owner is not None and owner != '':
            branches = self.plugin.fetch_github_branches_from(owner=owner)
            if branches != {}:
                return {"operation": "request", "result": "success", "data": list(branches.keys())}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def updatePlugins(self):
        json = cherrypy.request.json
        owner = json.get("owner")
        branch = json.get("branch")
        if owner is not None and owner != '' and branch is not None and branch != '':
            plugins = self.plugin.fetch_github_plugins_from(owner=owner, branch=branch)
            if plugins != {}:
                return {"operation": "request", "result": "success", "data": plugins}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def removePlugin(self):
        json = cherrypy.request.json
        name = json.get("name")
        if name is None or name == '' or name not in self.plugin.repos:
            msg = f'Repo {name} nicht vorhanden.'
            self.logger.error(msg)
            return {"operation": "request", "result": "error", "data": msg}

        if self.plugin.remove_plugin(name):
            return {"operation": "request", "result": "success"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def selectPlugin(self):
        json = cherrypy.request.json
        owner = json.get("owner")
        branch = json.get("branch")
        plugin = json.get("plugin")
        name = json.get("name")
        confirm = json.get("confirm")

        if (owner is None or owner == '' or
                branch is None or branch == '' or
                plugin is None or plugin == ''):
            msg = f'Fehlerhafte Daten für Repo {owner}/plugins, Branch {branch} oder Plugin {plugin} übergeben.'
            self.logger.error(msg)
            return {"operation": "request", "result": "error", "data": msg}

        if confirm:
            res = self.plugin.create_repo(name)
            msg = f'Fehler beim Erstellen des Repos "{owner}/plugins", Branch {branch}, Plugin {plugin}'
        else:
            res = self.plugin.init_repo(name, owner, plugin, branch)
            msg = f'Fehler beim Initialisieren des Repos "{owner}/plugins", Branch {branch}, Plugin {plugin}'

        if res:
            return {"operation": "request", "result": "success"}
        else:
            self.logger.error(msg)
            return {"operation": "request", "result": "error", "data": msg}


#    @cherrypy.expose
#    @cherrypy.tools.json_out()
#    def countall(self, item_path):
#        if item_path is not None:
#            item = self.plugin.items.return_item(item_path)
#            count = item.db('countall', 0)
#            if count is not None:
#                return int(count)
#            else:
#                return 0

#     @cherrypy.expose
#     def get_data_html(self, dataSet=None, params=None):
#         """
#         Return data to update the webpage
# 
#         For the standard update mechanism of the web interface, the dataSet to return the data for is None
# 
#         :param dataSet: Dataset for which the data should be returned (standard: None)
#         :return: dict with the data needed to update the web page.
#         """
#         if dataSet == 'overview':
#             # get the new data
#             data = self.plugin._webdata
#             try:
#                 data = json.dumps(data)
#                 return data
#             except Exception as e:
#                 self.logger.error(f"get_data_html exception: {e}")
#         if dataSet == "item_details":
#             item_id = params
#             now = self.plugin.shtime.now()
#             time_start = time.mktime(datetime.datetime.strptime("%s/%s/%s" % (now.month, now.day, now.year),
#                                                                 "%m/%d/%Y").timetuple()) * 1000
#             time_end = time_start + 24 * 60 * 60 * 1000
#             if item_id is not None:
#                 rows = self.plugin.readLogs(item_id, time_start=time_start, time_end=time_end)
#             else:
#                 rows = []
#             log_array = []
#             if rows is None:
#                 reversed_arr = []
#             else:
#                 for row in rows:
#                     value_dict = {}
#                     for key in [COL_LOG_TIME, COL_LOG_ITEM_ID, COL_LOG_DURATION, COL_LOG_VAL_STR, COL_LOG_VAL_NUM,
#                                 COL_LOG_VAL_BOOL, COL_LOG_CHANGED]:
#                         if key not in [COL_LOG_TIME, COL_LOG_CHANGED]:
#                             value_dict[key] = row[key]
#                         else:
#                             value_dict[key] = datetime.datetime.fromtimestamp(row[key] / 1000,
#                                                                               tz=self.plugin.shtime.tzinfo()).isoformat()
#                             value_dict["%s_orig" % key] = row[key]
# 
#                     log_array.append(value_dict)
#                 reversed_arr = log_array[::-1]
#             try:
#                 data = json.dumps(reversed_arr)
#                 if data:
#                     return data
#                 else:
#                     return None
#             except Exception as e:
#                 self.logger.error(f"get_data_html exception: {e}")
# 
#         return {}
# 