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

import cherrypy

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf
# from ..Exception import Exception

ERR_CODE = 500


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

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
            skip = False
            if self.plugin.gh.pulls[pr]['owner'] in reposbyowner:
                if self.plugin.gh.pulls[pr]['branch'] in reposbyowner[self.plugin.gh.pulls[pr]['owner']]:
                    skip = True

            if not skip:
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
                           auth=self.plugin.gh_apikey != '',
                           conn=self.plugin.gh._github is not None,
                           language=self.plugin.get_sh().get_defaultlanguage())

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def getRateLimit(self):
        try:
            rl = self.plugin.gh.get_rate_limit()
            return {"operation": "request", "result": "success", "data": rl}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def updateForks(self):
        try:
            if self.plugin.fetch_github_forks(fetch=True):
                return {"operation": "request", "result": "success", "data": sorted(self.plugin.gh.forks.keys())}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def isRepoClean(self):
        try:
            json = cherrypy.request.json
            name = json.get('name')

            if not name or name not in self.plugin.repos:
                raise Exception(f'repo {name} invalid or not found')

            clean = self.plugin.is_repo_clean(name)
            return {"operation": "request", "result": "success", "data": clean}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def getPull(self):
        try:
            json = cherrypy.request.json
            try:
                pr = int(json.get("pull", 0))
            except Exception:
                raise Exception(f'invalid value for pr in {json}')
            if pr > 0:
                pull = self.plugin.get_github_pulls(number=pr)
                b = pull.get('branch')
                o = pull.get('owner')
                if b and o:
                    return {"operation": "request", "result": "success", "owner": o, "branch": b}
            else:
                raise Exception(f'invalid data on processing PR {pr}')
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def updatePulls(self):
        try:
            if self.plugin.fetch_github_pulls(fetch=True):
                prn = list(self.plugin.get_github_pulls().keys())
                prt = [v['title'] for pr, v in self.plugin.get_github_pulls().items()]
                return {"operation": "request", "result": "success", "prn": prn, "prt": prt}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def updateBranches(self):
        try:
            json = cherrypy.request.json
            owner = json.get("owner")
            force = json.get("force", False)
            if owner is not None and owner != '':
                branches = self.plugin.fetch_github_branches_from(owner=owner, fetch=force)
                if branches != {}:
                    return {"operation": "request", "result": "success", "data": list(branches.keys())}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def updatePlugins(self):
        try:
            json = cherrypy.request.json
            force = json.get("force", False)
            owner = json.get("owner")
            branch = json.get("branch")
            if owner is not None and owner != '' and branch is not None and branch != '':
                plugins = self.plugin.fetch_github_plugins_from(owner=owner, branch=branch, fetch=force)
                if plugins != {}:
                    return {"operation": "request", "result": "success", "data": plugins}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def removePlugin(self):
        try:
            json = cherrypy.request.json
            name = json.get("name")
            if name is None or name == '' or name not in self.plugin.repos:
                raise Exception(f'Repo {name} nicht vorhanden.')

            if self.plugin.remove_plugin(name):
                return {"operation": "request", "result": "success"}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def removeInitPlugin(self):
        try:
            json = cherrypy.request.json
            name = json.get("name")
            if name is None or name == '' or name not in self.plugin.init_repos:
                raise Exception(f'Plugin {name} nicht vorhanden.')

            try:
                del self.plugin.init_repos[name]
            except Exception:
                pass
            return {"operation": "request", "result": "success"}
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def selectPlugin(self):
        try:
            json = cherrypy.request.json
            owner = json.get("owner")
            branch = json.get("branch")
            plugin = json.get("plugin")
            name = json.get("name")
            confirm = json.get("confirm")

            if (owner is None or owner == '' or
                    branch is None or branch == '' or
                    plugin is None or plugin == ''):
                raise Exception(f'Fehlerhafte Daten für Repo {owner}/plugins, Branch {branch} oder Plugin {plugin} übergeben.')

            if confirm:
                res = self.plugin.create_repo(name)
                msg = f'Fehler beim Erstellen des Repos "{owner}/plugins", Branch {branch}, Plugin {plugin}'
            else:
                res = self.plugin.init_repo(name, owner, plugin, branch)
                msg = f'Fehler beim Initialisieren des Repos "{owner}/plugins", Branch {branch}, Plugin {plugin}'

            if res:
                return {"operation": "request", "result": "success"}
            else:
                raise Exception(msg)
        except Exception as e:
            cherrypy.response.status = ERR_CODE
            return {"error": str(e)}
