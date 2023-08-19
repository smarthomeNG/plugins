#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
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
import logging
import datetime
import os
from . import StateEngineDefaults


class SeLogger:

    @property
    def default_log_level(self):
        return SeLogger.__default_log_level.get()

    @default_log_level.setter
    def default_log_level(self, value):
        SeLogger.__default_log_level = value

    @property
    def startup_log_level(self):
        return SeLogger.__startup_log_level.get()

    @startup_log_level.setter
    def startup_log_level(self, value):
        SeLogger.__startup_log_level = value

    @property
    def log_maxage(self):
        return SeLogger.__log_maxage.get()

    @log_maxage.setter
    def log_maxage(self, value):
        try:
            SeLogger.__log_maxage = int(value)
        except ValueError:
            SeLogger.__log_maxage = 0
            logger = StateEngineDefaults.logger
            logger.error("The maximum age of the log files has to be an int number.")

    @property
    def using_default(self):
        return self.__using_default

    @using_default.setter
    def using_default(self, value):
        self.__using_default = value

    @property
    def name(self):
        return self.__name

    # Set global log level
    # loglevel: current loglevel
    @property
    def log_level(self):
        return self.__log_level.get()

    @log_level.setter
    def log_level(self, value):
        try:
            self.__log_level = int(value)
        except ValueError:
            self.__log_level = 0
            logger = StateEngineDefaults.logger
            logger.error("Loglevel has to be an int number!")

    @property
    def log_directory(self):
        return SeLogger.__log_directory

    @log_directory.setter
    def log_directory(self, value):
        SeLogger.__log_directory = value

    @staticmethod
    def init(sh):
        SeLogger.__sh = sh

    # Create log directory
    # logdirectory: Target directory for StateEngine log files
    @staticmethod
    def manage_logdirectory(base, log_directory, create=True):
        if log_directory[0] != "/":
            if base[-1] != "/":
                base += "/"
            log_directory = base + log_directory
        if create is True and not os.path.isdir(log_directory):
            os.makedirs(log_directory)
        return log_directory


    # Remove old log files (by scheduler)
    @staticmethod
    def remove_old_logfiles():
        if SeLogger.log_maxage.get() == 0 or not os.path.isdir(str(SeLogger.log_directory)):
            return
        logger = StateEngineDefaults.logger
        logger.info("Removing logfiles older than {0} days".format(SeLogger.log_maxage))
        count_success = 0
        count_error = 0
        now = datetime.datetime.now()
        for file in os.listdir(str(SeLogger.log_directory)):
            if file.endswith(".log"):
                try:
                    abs_file = os.path.join(str(SeLogger.log_directory), file)
                    stat = os.stat(abs_file)
                    mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                    age_in_days = (now - mtime).total_seconds() / 86400.0
                    if age_in_days > SeLogger.log_maxage.get():
                        os.unlink(abs_file)
                        count_success += 1
                except Exception as ex:
                    logger.error("Problem removing old logfiles: {}".format(ex))
                    logger.error(ex)
                    count_error += 1
        logger.info("{0} files removed, {1} errors occured".format(count_success, count_error))

    # Return SeLogger instance for given item
    # item: item for which the detailed log is
    @staticmethod
    def create(item):
        return SeLogger(item)

    # Constructor
    # item: item for which the detailed log is (used as part of file name)
    def __init__(self, item):
        self.logger = logging.getLogger('stateengine.{}'.format(item.property.path))
        self.__name = 'stateengine.{}'.format(item.property.path)
        self.__section = item.property.path.replace(".", "_").replace("/", "")
        self.__indentlevel = 0
        self.__default_log_level = None
        self.__startup_log_level = None
        self.__log_level = None
        self.__using_default = False
        self.__logmaxage = None
        self.__date = None
        self.__logerror = False
        self.__filename = ""
        self.update_logfile()

    # get current log level of abitem
    def get_loglevel(self):
        return self.log_level.get()

    # Update name logfile if required
    def update_logfile(self):
        if self.__date == datetime.datetime.today() and self.__filename is not None:
            return
        self.__date = str(datetime.date.today())
        self.__filename = f"{SeLogger.log_directory}{self.__date}-{self.__section}.log"

    # Increase indentation level
    # by: number of levels to increase
    def increase_indent(self, by=1):
        self.__indentlevel += by

    # Decrease indentation level
    # by: number of levels to decrease
    def decrease_indent(self, by=1):
        if self.__indentlevel > by:
            self.__indentlevel -= by
        else:
            self.__indentlevel = 0

    # log text something
    # level: required loglevel
    # text: text to log
    def log(self, level, text, *args):
        # Section given: Check level
        _log_level = self.get_loglevel()
        if _log_level == -1:
            self.using_default = True
            _log_level = SeLogger.default_log_level.get()
        else:
            self.using_default = False
        if level <= _log_level:
            indent = "\t" * self.__indentlevel
            text = text.format(*args)
            logtext = "{0}{1} {2}\r\n".format(datetime.datetime.now(), indent, text)
            try:
                with open(self.__filename, mode="a", encoding="utf-8") as f:
                    f.write(logtext)
            except Exception as e:
                if self.__logerror is False:
                    self.__logerror = True
                    self.logger.error("There is a problem with "
                                      "the logfile {}: {}".format(self.__filename, e))

    # log header line (as info)
    # text: header text
    def header(self, text):
        self.__indentlevel = 0
        text += " "
        self.log(1, text.ljust(80, "="))
        self.logger.info(text.ljust(80, "="))

    # log with level=info
    # @param text text to log
    # @param *args parameters for text
    def info(self, text, *args):
        self.log(1, text, *args)
        indent = "\t" * self.__indentlevel
        text = '{}{}'.format(indent, text)
        self.logger.info(text.format(*args))

    # log with level=debug
    # text: text to log
    # *args: parameters for text
    def debug(self, text, *args):
        self.log(2, text, *args)
        indent = "\t" * self.__indentlevel
        text = '{}{}'.format(indent, text)
        self.logger.debug(text.format(*args))

    # log with level=develop
    # text: text to log
    # *args: parameters for text
    def develop(self, text, *args):
        self.log(3, "DEV: " + text, *args)
        indent = "\t" * self.__indentlevel
        text = '{}{}'.format(indent, text)
        self.logger.log(StateEngineDefaults.VERBOSE, text.format(*args))

    # log warning (always to main smarthome.py log)
    # text: text to log
    # *args: parameters for text
    # noinspection PyMethodMayBeStatic
    def warning(self, text, *args):
        self.log(1, "WARNING: " + text, *args)
        indent = "\t" * self.__indentlevel
        text = '{}{}'.format(indent, text)
        self.logger.warning(text.format(*args))

    # log error (always to main smarthome.py log)
    # text: text to log
    # *args: parameters for text
    # noinspection PyMethodMayBeStatic
    def error(self, text, *args):
        self.log(1, "ERROR: " + text, *args)
        indent = "\t" * self.__indentlevel
        text = '{}{}'.format(indent, text)
        self.logger.error(text.format(*args))

    # log exception (always to main smarthome.py log'
    # msg: message to log
    # *args: arguments for message
    # **kwargs: known arguments for message
    # noinspection PyMethodMayBeStatic
    def exception(self, msg, *args, **kwargs):
        self.log(1, "EXCEPTION: " + str(msg), *args)
        self.logger.exception(msg, *args, **kwargs)


class SeLoggerDummy:
    # Constructor
    # item: item for which the detailed log is (used as part of file name)
    # noinspection PyUnusedLocal
    def __init__(self, item=None):
        self.logger = StateEngineDefaults.logger

    # Update name logfile if required
    def update_logfile(self):
        pass

    # Increase indentation level
    # by: number of levels to increase
    def increase_indent(self, by=1):
        pass

    # Decrease indentation level
    # by: number of levels to decrease
    def decrease_indent(self, by=1):
        pass

    # log text something
    # level: required loglevel
    # text: text to log
    def develop(self, text, *args):
        pass

    # log text something
    # level: required loglevel
    # text: text to log
    def log(self, level, text, *args):
        pass

    # log header line (always to main smarthomeNG log as info)
    # text: header text
    def header(self, text):
        self.logger.info(text)

    # log with level=info (always to main smarthomeNG log)
    # @param text text to log
    # @param *args parameters for text
    def info(self, text, *args):
        self.logger.info(text.format(*args))

    # log with level=debug (always to main smarthomeNG log)
    # text: text to log
    # *args: parameters for text
    def debug(self, text, *args):
        self.logger.debug(text.format(*args))

    # log warning (always to main smarthomeNG log)
    # text: text to log
    # *args: parameters for text
    # noinspection PyMethodMayBeStatic
    def warning(self, text, *args):
        self.logger.warning(text.format(*args))

    # log error (always to main smarthomeNG log)
    # text: text to log
    # *args: parameters for text
    # noinspection PyMethodMayBeStatic
    def error(self, text, *args):
        self.logger.error(text.format(*args))

    # log exception (always to main smarthomeNG log)
    # msg: message to log
    # *args: arguments for message
    # **kwargs: known arguments for message
    # noinspection PyMethodMayBeStatic
    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)
