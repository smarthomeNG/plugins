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

import datetime
import time

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf

from ..constants import *

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
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
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, action=None, item_id=None, item_path=None, day=None, month=None, year=None,
              time_orig=None, changed_orig=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if item_path is not None:
            item = self.plugin.items.return_item(item_path)
        delete_triggered = False
        if action is not None:
            if action == "delete_log" and item_id is not None:
                if time_orig is not None and changed_orig is not None:
                    self.plugin.deleteLog(item_id, time=time_orig, changed=changed_orig)
                    action = "item_details"
                else:
                    self.plugin.deleteLog(item_id)
                delete_triggered = True
            if action == "item_details" and item_id is not None:
                if day is not None and month is not None and year is not None:
                    time_start = time.mktime(datetime.datetime.strptime("%s/%s/%s" % (month, day, year),
                                                                        "%m/%d/%Y").timetuple()) * 1000
                else:
                    now = self.plugin.shtime.now()
                    time_start = time.mktime(datetime.datetime.strptime("%s/%s/%s" % (now.month, now.day, now.year),
                                                                        "%m/%d/%Y").timetuple()) * 1000
                time_end = time_start + 24 * 60 * 60 * 1000
                tmpl = self.tplenv.get_template('item_details.html')

                rows = self.plugin.readLogs(item_id, time_start=time_start, time_end=time_end)
                log_array = []
                for row in rows:
                    value_dict = {}
                    for key in [COL_LOG_TIME, COL_LOG_ITEM_ID, COL_LOG_DURATION, COL_LOG_VAL_STR, COL_LOG_VAL_NUM,
                                COL_LOG_VAL_BOOL, COL_LOG_CHANGED]:
                        if key not in [COL_LOG_TIME, COL_LOG_CHANGED]:
                            value_dict[key] = row[key]
                        else:
                            value_dict[key] = datetime.datetime.fromtimestamp(row[key] / 1000,
                                                                              tz=self.plugin.shtime.tzinfo())
                            value_dict["%s_orig" % key] = row[key]

                    log_array.append(value_dict)
                reversed_arr = log_array[::-1]
                return tmpl.render(p=self.plugin,
                                   items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path']),
                                                reverse=False), item=item,
                                   tabcount=2, action=action, item_id=item_id, item_path=item_path,
                                   language=self.plugin.get_sh().get_defaultlanguage(), now=self.plugin.shtime.now(),
                                   log_array=reversed_arr, day=day, month=month, year=year,
                                   delete_triggered=delete_triggered)

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path']), reverse=False),
                           tabcount=2, action=action, item_id=item_id, delete_triggered=delete_triggered,
                           language=self.plugin.get_sh().get_defaultlanguage())


    @cherrypy.expose
    def item_csv(self, item_id):
        """
        Returns CSV Output for item log data

        :return: item log data as CSV
        """
        if item_id is None:
            return None
        else:
            rows = self.plugin.readLogs(item_id)
            log_array = []
            for row in rows:
                value_dict = {}
                for key in [COL_LOG_TIME, COL_LOG_ITEM_ID, COL_LOG_DURATION, COL_LOG_VAL_STR, COL_LOG_VAL_NUM,
                            COL_LOG_VAL_BOOL, COL_LOG_CHANGED]:
                    value_dict[key] = row[key]
                log_array.append(value_dict)
            reversed_arr = log_array[::-1]
            csv_file_path = '%s/var/db/%s_item_%s.csv' % (
                self.plugin._sh.base_dir, self.plugin.get_instance_name(), item_id)

            with open(csv_file_path, 'w', encoding='utf-8') as f:
                writer = csv.writer(f, dialect="excel")
                writer.writerow(['time', 'item_id', 'duration', 'val_str', 'val_num', 'val_bool', 'changed'])
                for dataset in reversed_arr:
                    writer.writerow(
                        [dataset[0], dataset[1], dataset[2], dataset[3], dataset[4], dataset[5], dataset[6]])

            cherrypy.request.fileName = csv_file_path
            cherrypy.request.hooks.attach('on_end_request', self.download_complete)
            return cherrypy.lib.static.serve_download(csv_file_path)


    def download_complete(self):
        os.unlink(cherrypy.request.fileName)


    @cherrypy.expose
    def db_dump(self):
        """
        returns the smarthomeNG sqlite database as download
        """

        self.plugin.dump(
            '%s/var/db/smarthomedb_%s.dump' % (self.plugin.get_sh().base_dir, self.plugin.get_instance_name()))
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file(
            "%s/var/db/smarthomedb_%s.dump" % (self.plugin.get_sh().base_dir, self.plugin.get_instance_name()),
            mime, "%s/var/db/" % self.plugin.get_sh().base_dir)


    @cherrypy.expose
    def cleanup(self):
        self.plugin.cleanup()


    @cherrypy.expose
    @cherrypy.tools.json_out()
    def countall(self, item_path):
        if item_path is not None:
            item = self.plugin.items.return_item(item_path)
            count = item.db('countall', 0)
            if count is not None:
                return int(count)
            else:
                return 0
