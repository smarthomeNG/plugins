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

class BackendSchedulers:


    # -----------------------------------------------------------------------------------
    #    SCHEDULERS
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def schedules_html(self):
        """
        display a list of all known schedules
        """
        
        schedule_list = []
        for entry in self._sh.scheduler._scheduler:
            schedule = dict()
            s = self._sh.scheduler._scheduler[entry]
            if s['next'] != None and s['cycle'] != '' and s['cron'] != '':
                schedule['fullname'] = entry
                schedule['name'] = entry
                schedule['group'] = ''
                schedule['next'] = s['next'].strftime('%Y-%m-%d %H:%M:%S%z')
                schedule['cycle'] = s['cycle']
                schedule['cron'] = s['cron']
                
                if schedule['cycle'] == None:
                    schedule['cycle'] = ''
                if schedule['cron'] == None:
                    schedule['cron'] = ''
                
                nl = entry.split('.')
                if nl[0].lower() in ['items','logics','plugins']:
                    schedule['group'] = nl[0].lower()
                    del nl[0]
                    schedule['name'] = '.'.join(nl)
                    
                schedule_list.append(schedule)
                    
        schedule_list_sorted = sorted(schedule_list, key=lambda k: k['fullname'].lower())
        return self.render_template('schedules.html', schedule_list=schedule_list_sorted)



