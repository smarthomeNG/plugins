# 1!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
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
#  ToDo
#  Fehlermeldung wenn Datei nicht geschrieben werden kann
#  Language Settings
#  Day is out of range for Month...  
#  Replay simulation from beginning when end of file is reached
#
#  Releases:
#  0.1  initial
#  0.2  fixed bug when play is pushed while recording
#       removed rest of state 3 (hold)
#  0.3  changed most logger.info to logger.debug
#       Added release version to init message
#  0.4  Changed logging style
#       corrected serious bug in compare entry with NextDay
#  0.5  Added feature to select which caller is written to the simulation file
#  0.6  Added WebGUI and Clear Data File function
#
##########################################################################

import logging
from datetime import datetime, timedelta
from lib.model.smartplugin import *
from lib.shtime import Shtime
from lib.module import Modules
from lib.item import Items
from lib.scheduler import Scheduler


class Simulation(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.5.0.6"

    def __init__(self, smarthome, data_file, callers=None):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Simulation release 1.5.0.6')
        self._sh = smarthome
        self.shtime = Shtime.get_instance()
        self._datafile = data_file
        self.lastday = ''
        self.items = Items.get_instance()
        self.scheduler = Scheduler.get_instance()
        self._callers = callers
        self._items = []
        self.scheduler_add('midnight', self._midnight, cron='0 0 * *', prio=3)

        if not self.init_webinterface():
            self._init_complete = False

    def run(self):
        self.logger.info('Starting Simulation')
        self.alive = True
        self._start_record()

        # if you want to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        self.logger.info('Exit Simulation')
        try:
            self.file.close()
        except:
            self.logger.error('No file to close')
        self.alive = False

    # --------------------------------- parse_item ----------------------------------
    def parse_item(self, item):
        if 'sim' in item.conf:
            if item.conf['sim'] == 'message':
                self._message_item = item
            if item.conf['sim'] == 'state':
                self.state = item
            if item.conf['sim'] == 'control':
                self.control = item
            if item.conf['sim'] == 'tank':
                self.tank = item
            self._items.append(item)
            return self.update_item
        else:
            return None

    # --------------------------------- parse_logic ---------------------------------
    def parse_logic(self, logic):
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    # --------------------------------- update_item ---------------------------------
    # Callback. Writes the event to the file

    def update_item(self, item, caller=None, source=None, dest=None):
        if (item.conf['sim'] == 'track') and (self.state() == 2) and (self._callers and caller in self._callers):
            now = self.shtime.now()
            day = now.day
            self.file.write(now.strftime('%a;%H:%M:%S'))
            self.file.write(';')
            self.file.write(item.id())
            self.file.write(';')
            self.file.write('{}'.format(item()))
            self.file.write(';')
            self.file.write(caller)
            self.file.write('\n')
            self.file.flush()
            self._message_item(
                'Last event recorded: {}<br>{}   {}'.format(now.strftime('%H:%M:%S'), item.id(), item(), 'Simulation'))
            return None
        if (item.conf['sim'] == 'control') and (caller != 'Simulation'):
            self.state_selector[self.state(), self.control()](self)
            self.control(0, 'Simulation')

    # ----------------------- _start_record ---------------------------
    # Called by run() and by the state machine. Compares times
    # and schedules recording accordingly.

    def _start_record(self):
        tank = self._get_tank()
        self.logger.debug('Tank: {}'.format(tank))
        self.tank(tank)
        now = self.shtime.now()
        last_entry = self._lastentry.replace(year=now.year, month=now.month, day=now.day, tzinfo=now.tzinfo)
        self.logger.debug('last entry: {}'.format(last_entry))
        self.logger.debug('now: {}'.format(now))
        now -= timedelta(minutes=15)
        if now.time() < last_entry.time():
            self._schedule_recording_start(last_entry)
        else:
            start = last_entry
            start += timedelta(days=1)
            self._schedule_recording_start(start)

    # ----------------------- _schedule_recording_start ---------------------------
    def _schedule_recording_start(self, time):
        self.state(1, 'Simulation')
        self.scheduler_remove('startrecord')
        self._message_item('Recording starts {}'.format(time), caller='Simulation')
        self.logger.debug('Scheduling record start {}'.format(time))
        self.scheduler_add('startrecord', self._start_recording, next=time)

    # ----------------------------- _start_recording --------------------------------
    def _start_recording(self):
        self.state(2, 'Simulation')
        self.scheduler_remove('startrecord')
        self._message_item('Recording', caller='Simulation')
        self.logger.debug('starting record')
        self.recording = True
        try:
            self.file = open(self._datafile, 'a')
        except IOError as error:
            self.logger.error('Cannot open file {} for writing: {}'.format(self._datafile, error))
            self._message_item('cannot write to file', 'Simulation')
            self.state(0, 'Simulation')

    # ----------------------------- _stop_recording ---------------------------------
    def _stop_recording(self):
        self.state(0, 'Simulation')
        self.scheduler_remove('startrecord')
        self._message_item('', caller='Simulation')
        self.logger.debug('stop record')
        try:
            self.file.close()
        except:
            self.logger.error('Not running')

    # ----------------------------- _start_playbacl ---------------------------------
    def _start_playback(self):
        self.state(4, 'Simulation')
        self.logger.debug('Starting playback')
        try:
            self.file = open(self._datafile, 'r')
            self._wind_until_now()
            self._set_item()
        except IOError as error:
            self.logger.error('NoFile {}'.format(error))
            self._message_item('No File', 'Simulation')
            self.state(0, 'Simulation')

    # ----------------------------- _stop_playback ---------------------------------
    def _stop_playback(self):
        self.state(0, 'Simulation')
        self.logger.debug('Stopping playback')
        self.scheduler_remove('simulate')
        self._message_item('Playback stopped', 'Simulation')
        try:
            self.file.close()
        except:
            self.logger.error('No fileto close')

    # --------------------------------- _set_item -----------------------------------
    # Is called by the scheduler. Sets the item, reads the next event and
    # schedules it.

    def _set_item(self, **kwargs):
        target = None
        value = None
        if 'target' in kwargs:
            target = kwargs['target']
        if 'value' in kwargs:
            value = kwargs['value']
        if target is not None and value is not None:
            self.logger.debug('Setting {} to {}'.format(target, value))
            item = self.items.return_item(target)
            try:
                item(value, caller='Simulation')
            except:
                self.logger.error('Skipped unknown item: {}'.format(target))
        entry = self.file.readline()
        if entry == 'NextDay\n':
            entry = self.file.readline()
        if entry != '':
            day = entry.split(';')[0]
            time = entry.split(';')[1]
            target = entry.split(';')[2]
            value = entry.split(';')[3]
            hour = int(time.split(':')[0])
            minute = int(time.split(':')[1])
            seconds = int(time.split(':')[2])
            now = self.shtime.now()
            next = now.replace(hour=hour, minute=minute, second=seconds)
            dif = next - now
            if (self.lastday != '') and (self.lastday != day):
                self.logger.debug('Found next day {} {} {} shitfing to tomorrow.'.format(target, value, next))
                next = next + timedelta(1)
            self._message_item('Next event: {}<br>{}   {}'.format(time, target, value, 'Simulation'))
            self.logger.debug('Scheduling {} {} {}'.format(target, value, next))
            self.scheduler_add('simulate', self._set_item, value={'target': target, 'value': value}, next=next)
            self.lastday = day
        else:
            self.logger.info('End of file reached, simulation ended')
            self._message_item('Simulation ended', 'Simulation')
            self.state(0, 'Simulation')

    # ------------------------------ windnuntil_now --------------------------------
    # Reads the events from the file and skips until a time stamp is reached
    # that is past the actual time

    def _wind_until_now(self):
        next = 0
        now = 1
        while next < now:
            pos = self.file.tell()
            entry = self.file.readline()
            if entry == 'NextDay\n':
                entry = self.file.readline()
            if entry != '':
                time = entry.split(';')[1]
                hour = int(time.split(':')[0])
                minute = int(time.split(':')[1])
                seconds = int(time.split(':')[2])
                now = self.shtime.now()
                next = now.replace(hour=hour, minute=minute, second=seconds)
                dif = next - now
            else:
                self.logger.info('End of file reached, simulation ended')
                self._message_item('Simulation ended', 'Simulation')
                self.state(0, 'Simulation')
                return None
        self.file.seek(pos)

    # -------------------------------- do_nothing ----------------------------------
    def _do_nothing(self):
        self.logger.debug('Do nothing state: {} control: {}'.format(self.state(), self.control()))

    # -------------------------------- _midnight ----------------------------------
    # Called by the scheduler at midnight. It writes the NextDas keyword and
    # removes the first day.

    def _midnight(self):
        self.logger.debug('Midnight')
        if self.state() == 2:
            self.file.write('NextDay\n')
            self.file.flush()
            if self.tank() > 13:
                self._remove_first_day()
            else:
                tank = self.tank()
                self.tank(tank + 1)

    # -------------------------------- _get_tank ----------------------------------
    # Returns the number of days in the  event file

    def _get_tank(self):
        self._lastentry = datetime.strptime('0:0:0', '%H:%M:%S')
        try:
            self.file = open(self._datafile, 'r')
        except IOError as error:
            self.logger.error('NoFile {}'.format(error))
            return 0
        entry = 'bla'
        tank = 0;
        while entry != '':
            entry = self.file.readline()
            if entry == 'NextDay\n':
                tank = tank + 1
            else:
                if entry != '':
                    self._lastentry = datetime.strptime(entry.split(';')[1], '%H:%M:%S')
        self.file.close()
        return tank

    # ------------------------------ _remove_first_day ------------------------------
    # Removes the forst day from the event file. It is called when the
    # 15th day is finioshed at midnight.

    def _remove_first_day(self):
        self.logger.debug('Remove Day')
        self.file.close()
        #        try:
        self.file = open(self._datafile, 'r')
        #        except IOError as error:
        #        self.logger.error('NoFile {}'.format(error))
        #        try:
        self.tempfile = open('/tmp/simulation.tmp', 'w')
        #        except IOError as error:
        #        self.logger.error('Canot open tempfile: {}'.format(error))
        entry = 'bla'
        while (entry != 'NextDay\n') and (entry != ''):
            entry = self.file.readline()
        while (entry != ''):
            entry = self.file.readline()
            self.tempfile.write(entry)
        self.file.close()
        self.tempfile.close()
        self.tempfile = open('/tmp/simulation.tmp', 'r')
        self.file = open(self._datafile, 'w')
        entry = 'bla'
        while (entry != ''):
            entry = self.tempfile.readline()
            self.file.write(entry)
        self.file.close()
        self.tempfile.close()
        self.file = open(self._datafile, 'a')

    # state_selector state, control
    #                       (0,1): _remove_first_day,
    state_selector = {(0, 0): _do_nothing,
                      (0, 1): _do_nothing,
                      (0, 2): _start_playback,
                      (0, 3): _start_record,
                      (1, 0): _do_nothing,
                      (1, 1): _stop_recording,
                      (1, 2): _do_nothing,
                      (1, 3): _start_recording,
                      (2, 0): _do_nothing,
                      (2, 1): _stop_recording,
                      (2, 2): _start_playback,
                      (2, 3): _do_nothing,
                      (4, 0): _do_nothing,
                      (4, 1): _stop_playback,
                      (4, 2): _do_nothing,
                      (4, 3): _do_nothing, }

    def _clear_file(self):
        self.logger.debug('Clear File')
        self.file.close()

        self.file = open(self._datafile, 'w')
        self.file.write('')
        self.file.close()
        self.tank(0)

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
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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

    def get_items(self):
        return self._items


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

    @cherrypy.expose
    def index(self, cmd=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        data_file_content = []
        if cmd == 'delete_data_file':
            if len(self.plugin._datafile) > 0:
                self.plugin._clear_file()
        elif cmd == 'show_data_file':
            try:
                file = open(self.plugin._datafile, 'r')

                for line in file:
                    data_file_content.append(line)
                file.close()
            except IOError as error:
                self.logger.error('NoFile {}'.format(error))

        start_record = self.plugin.scheduler_get('startrecord')
        simulate = self.plugin.scheduler_get('simulate')
        start_record_entry = None
        simulate_entry = None
        if start_record is not None:
            start_record_entry = start_record['next']
        if simulate is not None:
            simulate_entry = simulate['next']

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=1, startRecord=start_record_entry,
                           simulate=simulate_entry,
                           cmd=cmd, data_file_content=data_file_content,
                           tab1title="Simulation Items (%s)" % len(self.plugin.get_items()),
                           p=self.plugin)
