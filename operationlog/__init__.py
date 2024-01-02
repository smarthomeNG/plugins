#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2016- Jan Troelsen                            jan@troelsen.de
# Copyright 2017- Oliver Hinckel                       github@ollisnet.de
# Copyright 2020- Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  OperationLog
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
#########################################################################

import logging
import threading
import datetime
import lib.log
import os
import pickle
import ast

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items
from lib.shtime import Shtime

from .AutoBlindLoggerOLog import AbLogger

class OperationLog(SmartPlugin, AbLogger):
    _log = None
    _items = {}

    PLUGIN_VERSION = "1.3.6"

    def __init__(self, sh):
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.shtime = Shtime.get_instance()
        self.name = self.get_parameter_value('name')
        self._filepattern = self.get_parameter_value('filepattern')
        self._maxlen = self.get_parameter_value('maxlen')
        self.mapping = self.get_parameter_value('mapping')
        self._items = self.get_parameter_value('items')
        self._cache = self.get_parameter_value('cache')
        self.additional_logger_name = self.get_parameter_value('logger')
        self._logtofile = self.get_parameter_value('logtofile')
        log_directory = self.get_parameter_value('logdirectory')

        # Todo: make windows compatible path settings
        try:
            if log_directory[0] != "/":
                base = self.get_sh().base_dir
                if base[-1] != "/":
                    base += "/"
                self.log_directory = base + log_directory
            else:
                self.log_directory = log_directory

            if not os.path.exists(self.log_directory):
                os.makedirs(self.log_directory)
        except Exception as e:
            self.logger.error("Error '{}' while establishing a log_directory '{}'".format(e,log_directory))
            return

        # Autoblindlogger
        AbLogger.set_logdirectory(self.log_directory)
        AbLogger.set_loglevel(2)
        AbLogger.set_logmaxage(0)
        AbLogger.__init__(self, self.name)

        self._log = lib.log.Log(self.get_sh(), self.name, self.mapping, self._maxlen)
        self._path = self.name
        self._cachefile = None
        self.__myLogger = None
        self._logcache = None

        self._item_conf = {}
        self._logic_conf = {}
        self.__date = None
        self.__fname = None

        #
        info_txt_cache = ", caching active" if self._cache else ""

        # additional logger given from plugin.yaml section "logger"
        if self.additional_logger_name:
            self.additional_logger = logging.getLogger(self.additional_logger_name)
        else:
            self.additional_logger = None

        if self.additional_logger:
            info_additional_logger_log = ", logging to {}".format(self.additional_logger_name)
        else:
            info_additional_logger_log = ""

        info_txt_log = "OperationLog {}: logging to file {}{}, keeping {} entries in memory".format(self.name, self.log_directory,
                                                                                                    self._filepattern, int(self._maxlen))

        self.logger.info(info_txt_log + info_txt_cache + info_additional_logger_log)

        #############################################################
        # Cache
        #############################################################
        if self._cache is True:
            cache_directory = os.path.join(self.get_sh().get_vardir(), 'log'+os.path.sep, 'cache'+os.path.sep)
            old_cache_file = os.path.join(self.get_sh().get_vardir(), 'cache'+os.path.sep, self._path)

            self._cachefile = os.path.join(cache_directory, self._path)
            if not os.path.isdir(cache_directory):
                os.makedirs(cache_directory)
            if os.path.isfile(old_cache_file):
                os.rename(old_cache_file, self._cachefile)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("OperationLog {}: moved cache from {} to {}".format(self.name, old_cache_file, self._cachefile))
            try:
                self.__last_change, self._logcache = _cache_read(self._cachefile, self.shtime.tzinfo())
                self.load(self._logcache)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("OperationLog {}: read cache: {}".format(self.name, self._logcache))
            except Exception:
                try:
                    _cache_write(self.logger, self._cachefile, self._log.export(int(self._maxlen)))
                    _cache_read(self._cachefile, self.shtime.tzinfo())
                    self.logger.info("OperationLog {}: generated cache file".format(self.name))
                except Exception as e:
                    self.logger.warning("OperationLog {}: problem reading cache: {}".format(self._path, e))

        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug("init {} done".format(__name__))
        self._init_complete = True

    def update_logfilename(self):
        if self.__date == datetime.datetime.today() and self.__fname is not None:
            return
        now = self.shtime.now()
        self.__fname = self._filepattern.format(**{'name': self.name, 'year': now.year, 'month': now.month, 'day': now.day})
        self.__myLogger.update_logfile(self.__fname)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        if self._logtofile is True:
            self.__myLogger = self.create(self.name)
        sh = self.get_sh()
        shtime = Shtime.get_instance()
        for item_id in self._item_conf:
            if 'olog_eval' in self._item_conf[item_id]:
                for (ind, eval_str) in enumerate(self._item_conf[item_id]['olog_eval']):
                    try:
                        eval(eval_str)
                    except Exception as e:
                        self.logger.warning('olog: could not evaluate {} for item: {}, {}'.format(eval_str, item_id, e))
                        self._item_conf[item_id]['olog_eval'][ind] = "'--'"
        for logic_name in self._logic_conf:
            if 'olog_eval' in self._logic_conf[logic_name]:
                for (ind, eval_str) in enumerate(self._logic_conf[logic_name]['olog_eval']):
                    try:
                        eval(eval_str)
                    except Exception as e:
                        self.logger.warning('olog: could not evaluate {} for logic: {}, {}'.format(eval_str, logic_name, e))
                        self._logic_conf[logic_name]['olog_eval'][ind] = "'--'"

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if 'olog' in item.conf and item.conf['olog'] == self.name:
            id = item.property.path
            self._item_conf[id] = {}

            # set these as default in any case. default is to log
            self._item_conf[id]['olog_rules'] = {}
            self._item_conf[id]['olog_rules']['lowlim'] = None
            self._item_conf[id]['olog_rules']['highlim'] = None
            self._item_conf[id]['olog_rules']['lowlimit'] = None
            self._item_conf[id]['olog_rules']['highlimit'] = None
            self._item_conf[id]['olog_rules']['*'] = 'value'

            if 'olog_txt' in item.conf:
                olog_txt = item.conf['olog_txt']
                self._item_conf[id]['olog_eval'] = []
                eval_parse = self.parse_eval("item.conf, item {}".format(id), olog_txt)
                self._item_conf[id]['olog_txt'] = eval_parse['olog_txt']
                self._item_conf[id]['olog_eval'] = eval_parse['olog_eval']
                if len(self._item_conf[id]['olog_eval']) != 0:
                    self.logger.info('Item: {}, olog evaluating: {}'.format(id, self._item_conf[id]['olog_eval']))

            if 'olog_rules' in item.conf:
                # we have explicit rules, remove default 'all'
                self._item_conf[id]['olog_rules']['*'] = None
                olog_rules = item.conf['olog_rules']
                if isinstance(olog_rules, str):
                    try:
                        temp = ast.literal_eval(olog_rules)
                    except:
                        temp = None
                    if isinstance(temp, list):
                        olog_rules = temp
                    else:
                        olog_rules = [olog_rules, ]
                for txt in olog_rules:
                    key_txt, value = txt.split(':')
                    if key_txt == 'True':
                        key = True
                    elif key_txt == 'False':
                        key = False
                    else:
                        try:
                            if float(key_txt) == int(key_txt):
                                key = int(key_txt)
                            else:
                                key = float(key_txt)
                        except:
                            key = key_txt
                            if key_txt in ['lowlim', 'highlim', 'lowlimit', 'highlimit']:
                                self._item_conf[id]['olog_rules']["*"] = 'value'
                    self._item_conf[id]['olog_rules'][key] = value

            self.logger.info('Item: {}, olog rules: {}'.format(id, self._item_conf[id]['olog_rules']))
            return self.update_item
        else:
            return None

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'olog' in logic.conf and logic.conf['olog'] == self.name:
            self._logic_conf[logic.name] = {}
            if 'olog_txt' in logic.conf:
                eval_parse = self.parse_eval("logic {}".format(logic.name), logic.conf['olog_txt'])
                olog_txt = eval_parse['olog_txt']
                olog_eval = eval_parse['olog_eval']
            else:
                olog_txt = "Logic {logic.name} triggered"
                olog_eval = []
            self._logic_conf[logic.name]['olog_txt'] = olog_txt
            self._logic_conf[logic.name]['olog_eval'] = olog_eval
            return self.trigger_logic

    def parse_eval(self, info, olog_txt):
        olog_eval = []
        pos = -1
        while True:
            pos = olog_txt.find('{eval=', pos + 1)
            if pos == -1:
                 break
            start = pos + 5
            pos = olog_txt.find('}', pos + 1)
            if pos == -1:
                self.logger.warning('olog: did not find ending } for eval in '.format(info))
                break
            eval_str = olog_txt[start + 1:pos]
            olog_eval.append(eval_str)
            olog_txt = olog_txt[:start - 4] + olog_txt[pos:]
            pos = start
        return {'olog_txt' : olog_txt, 'olog_eval' : olog_eval}

    def __call__(self, param1=None, param2=None):
        if isinstance(param1, list) and isinstance(param2, type(None)):
            self.log(param1)
        elif isinstance(param1, str) and isinstance(param2, type(None)):
            self.log([param1])
        elif isinstance(param1, str) and isinstance(param2, str):
            self.log([param2], param1)
        elif isinstance(param1, type(None)) and isinstance(param2, type(None)):
            return self._log

    def load(self, logentries):
        """
        Loads logentries (which were just read from cache) into the log object (see lib.log.Log())
        """
        if len(logentries) != 0:
            for logentry in reversed(logentries):
                log = []
                for name in self._log.mapping:
                    if name == 'time':
                        log.append(logentry['time'])
                    elif name == 'thread':
                        log.append(logentry['thread'])
                    elif name == 'level':
                        log.append(logentry['level'])
                    elif name == 'message':
                        log.append(logentry['message'])
                self._log.add(log)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to a log

        :param item: item that was updated before
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        sh = self.get_sh()
        shtime = Shtime.get_instance()
        if self.alive and caller != self.get_shortname():
            # this plugin does not change any item thus the check for caller is not really necessary
            if item.conf['olog'] == self.name:
                if len(self._items) == 0:
                    id = item.property.path
                    if id in self._item_conf and 'olog_txt' in self._item_conf[id]:
                        mvalue = item.property.value
                        if 'olog_rules' in self._item_conf[id]:
                            if item.type() == 'num':
                                lowlimit = self._item_conf[id]['olog_rules']['lowlimit']
                                lowlim = self._item_conf[id]['olog_rules']['lowlim']
                                highlimit = self._item_conf[id]['olog_rules']['highlimit']
                                highlim = self._item_conf[id]['olog_rules']['highlim']
                                if lowlimit is not None and item() < float(lowlimit):
                                    return
                                elif lowlim is not None and item() < float(lowlim):
                                    return
                                if highlimit is not None and item() >= float(highlimit):
                                    return
                                elif highlim is not None and item() >= float(highlim):
                                    return
                            elif item.type() == 'str':
                                if lowlimit is not None and item() < str(lowlimit):
                                    return
                                elif lowlim is not None and item() < str(lowlim):
                                    return
                                if highlimit is not None and item() >= str(highlimit):
                                    return
                                elif highlim is not None and item() >= str(highlim):
                                    return
                            try:
                                mvalue = self._item_conf[id]['olog_rules'][item()]
                            except KeyError:
                                mvalue = item()
                                if self._item_conf[id]['olog_rules']["*"] is None:
                                    return
                        self._item_conf[id]['olog_eval_res'] = []
                        for expr in self._item_conf[id]['olog_eval']:
                            self._item_conf[id]['olog_eval_res'].append(eval(expr))
                        try:
                            pname = str(item.return_parent())
                            pid = item.return_parent().property.path
                        except Exception:
                            pname = ''
                            pid = ''
                        time = shtime.now().strftime("%H:%M:%S")
                        date = shtime.now().strftime("%d.%m.%Y")
                        stamp = shtime.now().timestamp()
                        now = str(shtime.now())

                        logtxt = self._item_conf[id]['olog_txt'].format(*self._item_conf[id]['olog_eval_res'],
                                                                               **{'value': item(),
                                                                                  'mvalue': mvalue,
                                                                                  'name': str(item),
                                                                                  'age': round(item.prev_age(), 2),
                                                                                  'pname': pname,
                                                                                  'id': id,
                                                                                  'item': id,
                                                                                  'time': time,
                                                                                  'date': date,
                                                                                  'stamp': stamp,
                                                                                  'now': now,
                                                                                  'pid': pid,
                                                                                  'lowlimit': self._item_conf[id]['olog_rules']['lowlimit'],
                                                                                  'highlimit': self._item_conf[id]['olog_rules']['highlimit'],
                                                                                  'lowlim': self._item_conf[id]['olog_rules']['lowlim'],
                                                                                  'highlim': self._item_conf[id]['olog_rules']['highlim']})
                        logvalues = [logtxt]
                    else:
                        logvalues = [id, '=', item()]
                else:
                    logvalues = []
                    for it in self._items:
                        logvalues.append('{} = {} '.format(str(it), self.get_sh().return_item(it)()))
                self.log(logvalues, 'INFO' if 'olog_level' not in item.conf else item.conf['olog_level'])

    def trigger_logic(self, logic, by=None, source=None, dest=None):
        if self.name == logic.conf['olog'] and logic.name in self._logic_conf:
            olog_txt = self._logic_conf[logic.name]['olog_txt']
            olog_eval = self._logic_conf[logic.name]['olog_eval']
            eval_res = [eval(expr) for expr in olog_eval]
            logvalues = [olog_txt.format(*eval_res, **{'plugin' : self, 'logic' : logic, 'by' : by, 'source' : source, 'dest' : dest})]
            self.log(logvalues, 'INFO' if 'olog_level' not in logic.conf else logic.conf['olog_level'])

    def log(self, logvalues, level='INFO'):
        """
        Creates a log entry with logvalues of given level
        """
        if len(logvalues):
            log = []
            for name in self._log.mapping:
                if name == 'time':
                    log.append(self.shtime.now())
                elif name == 'thread':
                    log.append(threading.current_thread().name)
                elif name == 'level':
                    log.append("INFO" if level == "NONE" else level)
                else:
                    values_txt = map(str, logvalues)
                    log.append(' '.join(values_txt))
            self._log.add(log)
            # consider to write the log entry to
            if self._logtofile:
                self.update_logfilename()
                if level == "NONE":
                    self.__myLogger.none('{}', ''.join(log[3:]))
                else:
                    self.__myLogger.info('{}: {}', log[2], ''.join(log[3:]))

            if self._cache is True:
                try:
                    _cache_write(self.logger, self._cachefile, self._log.export(int(self._maxlen)))
                except Exception as e:
                    self.logger.warning("OperationLog {}: could not update cache {}".format(self._path, e))

            if self.additional_logger:
                if level == "NONE":
                    level = "INFO"
                self.additional_logger.log(logging.getLevelName(level), ' '.join(map(str, logvalues)))



#####################################################################
# Cache Methods
#####################################################################
def _cache_read(filename, tz):
    """
    This loads the cache from a file

    :param filename: file to load from
    :param tz: timezone
    :return: [description]
    :rtype: a tuple with datetime and values from file
    """
    ts = os.path.getmtime(filename)
    dt = datetime.datetime.fromtimestamp(ts, tz)
    value = None
    with open(filename, 'rb') as f:
        value = pickle.load(f)
    return (dt, value)


def _cache_write(logger, filename, value):
    try:
        with open(filename, 'wb') as f:
            pickle.dump(value, f)
    except IOError:
        logger.warning("Could not write to {}".format(filename))
