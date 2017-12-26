#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       René Frieß                  rene.friess@gmail.com
#                       Martin Sinn                         m.sinn@gmx.de
#                       Bernd Meiners
#                       Christian Strassburg          c.strassburg@gmx.de
#########################################################################
#  Backend plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import cherrypy
import platform
import collections
import datetime
import pwd
import html
import subprocess
import socket
import sys
import threading
import os
import lib.config
from lib.logic import Logics
import lib.logic   # zum Test (für generate bytecode -> durch neues API ersetzen)
from lib.model.smartplugin import SmartPlugin
from .utils import *

import lib.item_conversion

class BackendItems:


    def __init__(self):

        self.logger.debug("BackendItems __init__ {}".format(''))        


    # -----------------------------------------------------------------------------------
    #    ITEMS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def items_html(self):
        """
        display a list of items
        """
        return self.render_template('items.html', item_count=self._sh.item_count, 
                                    items=sorted(self._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False) )


    @cherrypy.expose
    def items_json(self, mode="tree"):
        """
        returns a list of items as json structure

        :param mode:             tree (default) or list structure
        """
        items_sorted = sorted(self._sh.return_items(), key=lambda k: str.lower(k['_path']), reverse=False)

        if mode == 'tree':
            parent_items_sorted = []
            for item in items_sorted:
                if "." not in item._path:
                    parent_items_sorted.append(item)

            item_data = self._build_item_tree(parent_items_sorted)
            return json.dumps(item_data)
        else:
            item_list = []
            for item in items_sorted:
                item_list.append(item._path)
            return json.dumps(item_list)


    @cherrypy.expose
    def cache_check_json_html(self):
        """
        returns a list of items as json structure
        """
        cache_path = "%s/var/cache/" % self._sh_dir
        from os import listdir
        from os.path import isfile, join
        onlyfiles = [f for f in listdir(cache_path) if isfile(join(cache_path, f))]
        unused_cache_files = []
        for file in onlyfiles:
            if not file.find(".") == 0:  # filter .gitignore etc.
                item = self._sh.return_item(file)
                no_cache_file = False;
                if item is None:
                    no_cache_file = True
                elif not item._cache:
                    no_cache_file = True

                if no_cache_file:
                    file_data = {}
                    file_data['last_modified'] = datetime.datetime.fromtimestamp(
                        int(os.path.getmtime(cache_path + file))
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    file_data['created'] = datetime.datetime.fromtimestamp(
                        int(os.path.getctime(cache_path + file))
                    ).strftime('%Y-%m-%d %H:%M:%S')
                    file_data['filename'] = file
                    file_data['filename'] = file
                    unused_cache_files.append(file_data)

        return json.dumps(unused_cache_files)

    @cherrypy.expose
    def cache_file_delete_html(self, filename=''):
        """
        deletes a file from cache
        """
        if len(filename) > 0:
            file_path = "%s/var/cache/%s" % (self._sh_dir, filename)
            os.remove(file_path);

        return

    @cherrypy.expose
    def item_change_value_html(self, item_path, value):
        """
        Is called by items.html when an item value has been changed
        """
        item_data = []
        item = self._sh.return_item(item_path)
        if self.updates_allowed:
            if 'num' in item.type():
                if "." in value or "," in value:
                    value = float(value)
                else:
                    value = int(value)
            item(value, caller='Backend')

        return

    def disp_str(self, val):
        s = str(val)
        if s == 'False':
            s = '-'
        elif s == 'None':
            s = '-'
        return s

    def age_to_string(self, days, hours, minutes, seconds):
        s = ''
        if days > 0:
            s += str(int(days)) + ' '
            if days == 1:
                s += translate('Tag')
            else:
                s += translate('Tage')
            s += ', '
        if (hours > 0) or (s != ''):
            s += str(int(hours)) + ' '
            if hours == 1:
                s += translate('Stunde')
            else:
                s += translate('Stunden')
            s += ', '
        if (minutes > 0) or (s != ''):
            s += str(int(minutes)) + ' '
            if minutes == 1:
                s += translate('Minute')
            else:
                s += translate('Minuten')
            s += ', '
        if days > 0:
            s += str(int(seconds))
        else:
            s += str("%.2f" % seconds)
        s += ' ' + translate('Sekunden')
        return s

    def disp_age(self, age):
        days = 0
        hours = 0
        minutes = 0
        seconds = age
        if seconds >= 60:
            minutes = int(seconds / 60)
            seconds = seconds - 60 * minutes
            if minutes > 59:
                hours = int(minutes / 60)
                minutes = minutes - 60 * hours
                if hours > 23:
                    days = int(hours / 24)
                    hours = hours - 24 * days
        return self.age_to_string(days, hours, minutes, seconds)


    def list_to_displaystring(self, l):
        """
        """
        if type(l) is str:
            return l
        
        edit_string = ''
        for entry in l:
            if edit_string != '':
                edit_string += ' | '
            edit_string += str(entry)
        if edit_string == '':
            edit_string = '-'
#        self.logger.info("list_to_displaystring: >{}<  -->  >{}<".format(l, edit_string))
        return edit_string


    def build_on_list(self, on_dest_list, on_eval_list):
        """
        build on_xxx data
        """
        on_list = []
        if on_dest_list is not None:
            if isinstance(on_dest_list, list):
                for on_dest, on_eval in zip(on_dest_list, on_eval_list):
                    if on_dest != '':
                        on_list.append( on_dest + ' = ' + on_eval )
                    else:
                        on_list.append( on_eval )
            else:
                if on_dest_list != '':
                    on_list.append( on_dest_list + ' = ' + on_eval_list )
                else:
                    on_list.append( on_eval_list )
        return on_list


    @cherrypy.expose
    def item_detail_json_html(self, item_path):
        """
        returns a list of items as json structure
        """
        item_data = []
        item = self._sh.return_item(item_path)
        if item is not None:
            if item.type() is None or item.type() is '':
                prev_value = ''
                value = ''
            else:
                prev_value = item.prev_value()
                value = item._value

            if isinstance(prev_value, datetime.datetime):
                prev_value = str(prev_value)

            if 'str' in item.type():
                value = html.escape(value)
                prev_value = html.escape(prev_value)

            cycle = ''
            crontab = ''
            for entry in self._sh.scheduler._scheduler:
                if entry == item._path:
                    if self._sh.scheduler._scheduler[entry]['cycle']:
                        cycle = self._sh.scheduler._scheduler[entry]['cycle']
                    if self._sh.scheduler._scheduler[entry]['cron']:
                        crontab = html.escape(str(self._sh.scheduler._scheduler[entry]['cron']))
                    break
            if cycle == '':
                cycle = '-'
            if crontab == '':
                crontab = '-'

            changed_by = item.changed_by()
            if changed_by[-5:] == ':None':
                changed_by = changed_by[:-5]

            updated_by = item.updated_by()
            if updated_by[-5:] == ':None':
                updated_by = updated_by[:-5]

            if item.prev_age() < 0:
                prev_age = ''
            else:
                prev_age = self.disp_age(item.prev_update_age())
            if item.prev_update_age() < 0:
                prev_update_age = ''
            else:
                prev_update_age = self.disp_age(item.prev_update_age())

            if str(item._cache) == 'False':
                cache = 'off'
            else:
                cache = 'on'
            if str(item._enforce_updates) == 'False':
                enforce_updates = 'off'
            else:
                enforce_updates = 'on'

            item_conf_sorted = collections.OrderedDict(sorted(item.conf.items(), key=lambda t: str.lower(t[0])))
            if item_conf_sorted.get('sv_widget', '') != '':
                item_conf_sorted['sv_widget'] = html.escape(item_conf_sorted['sv_widget'])

            logics = []
            for trigger in item.get_logic_triggers():
                logics.append(html.escape(format(trigger)))
            triggers = []
            for trigger in item.get_method_triggers():
                trig = format(trigger)
                trig = trig[1:len(trig) - 27]
                triggers.append(html.escape(format(trig.replace("<", ""))))

            try:
                upd_age = item.update_age()
            except:
                # if used lib.items doesn't support update_age() function
                upd_age = item.age()
            
            # build on_update and on_change data
            on_update_list = self.build_on_list(item._on_update_dest_var, item._on_update)
            on_change_list = self.build_on_list(item._on_change_dest_var, item._on_change)
            
            data_dict = {'path': item._path,
                         'name': item._name,
                         'type': item.type(),
                         'value': value,
                         'age': self.disp_age(item.age()),
                         'update_age': self.disp_age(item.update_age()),
                         'last_update': str(item.last_update()),
                         'last_change': str(item.last_change()),
                         'changed_by': changed_by,
                         'updated_by': updated_by,
                         'previous_value': prev_value,
                         'previous_age': prev_age,
                         'previous_update_age': prev_update_age,
                         'previous_update': str(item.prev_update()),
                         'previous_change': str(item.prev_change()),
                         'enforce_updates': enforce_updates,
                         'cache': cache,
                         'eval': html.escape(self.disp_str(item._eval)),
                         'eval_trigger': self.disp_str(item._eval_trigger),
                         'on_update': html.escape(self.list_to_displaystring(on_update_list)),
                         'on_change': html.escape(self.list_to_displaystring(on_change_list)),
                         'cycle': str(cycle),
                         'crontab': str(crontab),
                         'autotimer': self.disp_str(item._autotimer),
                         'threshold': self.disp_str(item._threshold),
                         'config': json.dumps(item_conf_sorted),
                         'logics': json.dumps(logics),
                         'triggers': json.dumps(triggers),
                         'filename': str(item._filename),
                         }

            # cast raw data to a string
            if item.type() in ['foo', 'list', 'dict']:
                data_dict['value'] = str(item._value)
                data_dict['previous_value'] = str(prev_value)

            item_data.append(data_dict)
            return json.dumps(item_data)
        else:
            self.logger.error("Requested item %s is None, check if item really exists." % item_path)
            return

    def _build_item_tree(self, parent_items_sorted):
        item_data = []

        for item in parent_items_sorted:
            nodes = self._build_item_tree(item.return_children())
            tags = []
            tags.append(len(nodes))
            item_data.append({'path': item._path, 'name': item._name, 'tags': tags, 'nodes': nodes})

        return item_data

