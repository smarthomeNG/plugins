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

import logging
import os
import html

class BackendLogging:

    # -----------------------------------------------------------------------------------
    #    LOGGING
    # -----------------------------------------------------------------------------------

    @cherrypy.expose
    def logging_html(self):
        """
        display a list of all loggers
        """
        loggerDict = {}
        # Filter to get only active loggers
        for l in logging.Logger.manager.loggerDict:
            if (logging.getLogger(l).level > 0) or (logging.getLogger(l).handlers != []):
                loggerDict[l] = logging.Logger.manager.loggerDict[l]
        

        # get information about active loggers
        loggerList_sorted = sorted(loggerDict)
        loggerList_sorted.insert(0, "root")      # Insert information about root logger at the beginning of the list
        loggers = []
        for ln in loggerList_sorted:
            if ln == 'root':
                logger = logging.root
            else:
                logger = logging.getLogger(ln)
            l = dict()
            l['name'] = logger.name
            l['disabled'] = logger.disabled
            
            # get information about loglevels
            if logger.level == 0:
                l['level'] = ''
            elif logger.level in logging._levelToName:
                l['level'] = logging._levelToName[logger.level]
            else:
                l['level'] = logger.level

            l['filters'] = logger.filters

            # get information about handlers and filenames
            l['handlers'] = list()
            l['filenames'] = list()
            for h in logger.handlers:
                l['handlers'].append(h.__class__.__name__)
                try:
                    fn = str(h.baseFilename)
                except:
                    fn = ''
                l['filenames'].append(fn)
                
            if l['handlers'] == ['NullHandler']:
                self.logger.warning("logging_html: Filtered out logger {}: l['handlers'] = {}".format(l['name'], l['handlers']))
            else:
                loggers.append(l)

        return self.render_template('logging.html', loggers=loggers)


    @cherrypy.expose
    def log_view_html(self, text_filter='', log_level_filter='ALL', page=1, logfile='smarthome.log'):
        """
        returns the smarthomeNG logfile as view
        """
        log = '/var/log/' + os.path.basename(logfile)
        log_name = self._sh_dir + log
        fobj = open(log_name)
        log_lines = []
        start = (int(page) - 1) * 1000
        end = start + 1000
        counter = 0
        log_level_hit = False
        total_counter = 0
        for line in fobj:
            line_text = html.escape(line)
            if log_level_filter != "ALL" and not self.validate_date(line_text[0:10]) and log_level_hit:
                if start <= counter < end:
                    log_lines.append(line_text)
                counter += 1
            else:
                log_level_hit = False
            if (log_level_filter == "ALL" or line_text.find(log_level_filter) in [19, 20, 21, 22,
                                                                                  23]) and text_filter in line_text:
                if start <= counter < end:
                    log_lines.append(line_text)
                    log_level_hit = True
                counter += 1
        fobj.close()
        num_pages = -(-counter // 1000)
        if num_pages == 0:
            num_pages = 1
        return self.render_template('log_view.html', 
                                    current_page=int(page), pages=num_pages, log_level_filter=log_level_filter,
                                    logfile=os.path.basename(log_name), log_lines=log_lines, text_filter=text_filter)


    @cherrypy.expose
    def log_dump_html(self, logfile='smarthome.log'):
        """
        returns the smarthomeNG logfile as download
        """
        log = '/var/log/' + os.path.basename(logfile)
        log_name = self._sh_dir + log
        mime = 'application/octet-stream'
        return cherrypy.lib.static.serve_file(log_name, mime, log_name)


