#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
#########################################################################
#  Finite state machine plugin for SmartHomeNG
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
from queue import Queue


class ActionScheduler:

    def __init__(self, smarthome, logger):
        self._queue = Queue()
        self._scheduled = {}
        self._sh = smarthome
        self.logger = logger

    # ---------- API für Items ----------
    def add(self, abitem, name, action, value, next_run):
        self._queue.put((
            'add',
            abitem,
            name,
            {
                'action': action,
                'value': value or {},
                'next': next_run
            }
        ))

    def remove(self, abitem, name):
        self._queue.put(('remove', abitem, name))

    def remove_all(self, abitem):
        self._queue.put(('remove_all', abitem))

    # ---------- Scheduler Loop ----------
    def run(self):
        now = self._sh.shtime.now()

        while not self._queue.empty():
            cmd = self._queue.get()

            if cmd[0] == 'add':
                _, abitem, name, entry = cmd
                self._scheduled[(abitem, name)] = entry

            elif cmd[0] == 'remove':
                _, abitem, name = cmd
                self._scheduled.pop((abitem, name), None)

            elif cmd[0] == 'remove_all':
                _, abitem = cmd
                for key in list(self._scheduled.keys()):
                    if key[0] is abitem:
                        self._scheduled.pop(key, None)

        execute = []

        for key, entry in self._scheduled.items():
            if now >= entry['next']:
                execute.append(key)
        for (abitem, name) in execute:
            entry = self._scheduled.pop((abitem, name), None)
            if not entry:
                continue

            action = entry['action']
            vals = entry.get('value', {})
            try:
                self.logger.develop(f"Scheduled action '{name}' executing")
            except Exception:
                self.logger.debug(f"Scheduled action '{name}' executing")
            action.delayed_execute(**vals)
