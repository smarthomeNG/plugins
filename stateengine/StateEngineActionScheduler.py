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
from threading import RLock


class ActionScheduler:

    def __init__(self, smarthome, se_plugin, logger):
        self._queue = Queue()
        self._scheduled = {}
        self._sh = smarthome
        self._se_plugin = se_plugin
        self.logger = logger
        self._lock = RLock()
        self._dirty = False
        self._next_wakeup = None

    # ---------- API für Items ----------
    def add(self, abitem, name, action, value, next_run, overwrite, callback=None):
        self._queue.put((
            'add',
            abitem,
            name,
            {
                'action': action,
                'value': value or {},
                'next': next_run,
                'overwrite': overwrite
            },
            callback
        ))
        self._mark_dirty()

    def remove(self, abitem, name, callback=None):
        self._queue.put(('remove', abitem, name, callback))
        self._mark_dirty()

    def remove_all(self, abitem, callback=None):
        self._queue.put(('remove_all', abitem, callback))
        self._mark_dirty()

    def _mark_dirty(self):
        if not self._dirty:
            self._dirty = True
            self._se_plugin.scheduler_trigger('actionscheduler')

    # ---------- Scheduler Loop ----------
    def run(self):
        self._dirty = False
        self._next_wakeup = None
        now = self._sh.shtime.now()

        while not self._queue.empty():
            cmd = self._queue.get()

            if cmd[0] == 'add':
                _, abitem, name, entry, callback = cmd
                key = (abitem, name)
                with self._lock:
                    if key in self._scheduled and entry.get('overwrite', True) is False:
                        new_next = self._scheduled[key]['next']
                        added = False
                    else:
                        self._scheduled[key] = entry
                        new_next = entry.get('next')
                        added = True

                if callback:
                    try:
                        callback(added, new_next)
                    except Exception as e:
                        self.logger.debug(f"Add callback failed for '{name}': {e}")

            elif cmd[0] == 'remove':
                _, abitem, name, callback = cmd
                with self._lock:
                    removed = self._scheduled.pop((abitem, name), None) is not None
                if callback:
                    try:
                        callback(removed)
                    except Exception as e:
                        self.logger.debug(f"Remove callback failed for '{name}': {e}")

            elif cmd[0] == 'remove_all':
                _, abitem, callback = cmd
                removed = 0
                with self._lock:
                    for key in list(self._scheduled.keys()):
                        if key[0] is abitem:
                            self._scheduled.pop(key, None)
                            removed += 1
                if callback:
                    callback(removed)

        execute = []
        with self._lock:
            for key, entry in self._scheduled.items():
                if now >= entry['next']:
                    execute.append(key)
        for (abitem, name) in execute:
            with self._lock:
                entry = self._scheduled.pop((abitem, name), None)
                if not entry:
                    continue

                action = entry['action']
                vals = entry.get('value', {})
                '''
                try:
                    self.logger.develop(f"Scheduled action '{name}' executing")
                except Exception:
                    self.logger.debug(f"Scheduled action '{name}' executing")
                '''
                action.delayed_execute(**vals)
        next_times = []

        with self._lock:
            for entry in self._scheduled.values():
                next_times.append(entry['next'])

        if next_times:
            next_wakeup = min(next_times)
            self._se_plugin.scheduler_trigger('actionscheduler', dt=next_wakeup)
