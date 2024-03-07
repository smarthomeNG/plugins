#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2020 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
#  upwards.
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

from lib.module import Modules
from lib.model.smartplugin import *
from lib.item import Items

import datetime
import functools
import os

try:
    import rrdtool
    REQUIRED_PACKAGE_IMPORTED = True
except:
    REQUIRED_PACKAGE_IMPORTED = False



class RRD(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    The Module **rrdtool** from Pypi.org is used to access rrd.
    Documentation can be found at `<https://pythonhosted.org/rrdtool/>`_
    """

    PLUGIN_VERSION = '1.6.2'

    def __init__(self, sh):
        """
        Initalizes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        rrd_dir = self.get_parameter_value('rrd_dir')
        if not rrd_dir:
            rrd_dir = os.path.join(self.get_sh().base_dir, 'var', 'rrd')
        if not rrd_dir.endswith(os.sep):
            rrd_dir += os.sep
        self._rrd_dir = rrd_dir
        if not os.path.exists(self._rrd_dir):
            try:
                os.makedirs(self._rrd_dir)
            except:
                self.logger.error("Unable to create directory '{}'".format(self._rrd_dir))

        self._rrds = {}
        self.step = self.get_parameter_value('step')

        # Initialization code goes here
        if not REQUIRED_PACKAGE_IMPORTED:
            self._init_complete = False
            self.logger.error("{}: Unable to import Python package 'rrdtool'".format(self.get_fullname()))
            return

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        # create rrds
        for itempath in self._rrds:
            rrd = self._rrds[itempath]
            if not os.path.isfile(rrd['rrdb']):
                self._create(rrd)
        offset = 100  # wait 100 seconds for 1-Wire to update values
        self.scheduler_add('RRDtool', self._update_cycle, cycle=self.step, offset=offset, prio=5)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('RRDtool')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin stores a list of items with ``rrd`` attribute
        :param item:    The item to process.
        """
        if not self.has_iattr(item.conf, 'rrd'):
            return

        # set database filename
        dbname = ''
        self.logger.debug("parse item: {}".format(item))
        if self.has_iattr(item.conf,'rrd_ds_name'):
            dbname = self.get_iattr_value(item.conf, 'rrd_ds_name')
        if not dbname:
            dbname = item.property.path
        rrdb = self._rrd_dir + dbname + '.rrd'

        rrd_min = False
        rrd_max = False
        rrd_type = 'GAUGE'
        rrd_step = self.step
        if self.has_iattr(item.conf,'rrd_min'):
            rrd_min = self.get_iattr_value(item.conf,'rrd_min')
        if self.has_iattr(item.conf,'rrd_max'):
            rrd_max = self.get_iattr_value(item.conf,'rrd_max')
        if self.has_iattr(item.conf,'rrd_type'):
            if self.get_iattr_value(item.conf,'rrd_type').lower() == 'counter':
                rrd_type = 'COUNTER'
        if self.has_iattr(item.conf,'rrd_step'):
            rrd_step = self.get_iattr_value(item.conf,'rrd_step')


        no_series = False
        if self.has_iattr(item.conf,'rrd_no_series'):
            no_series = self.get_iattr_value(item.conf,'rrd_no_series')

        if no_series:
            self.logger.warning("Attribute rrd_no_series is set to True, no data series will be provided for item {}".format(item.property.path))
        else:
            item.series = functools.partial(self._series, item=item.property.path)
            item.db = functools.partial(self._single, item=item.property.path)

        self._rrds[item.property.path] = {'item': item, 'id': item.property.path, 'rrdb': rrdb, 'max': rrd_max, 'min': rrd_min, 'step': rrd_step, 'type': rrd_type}

        if self.get_iattr_value(item.conf, 'rrd') == 'init':
            last = self._single('last', '5d', item=item.property.path)
            if last is not None:
                item.set(last, 'RRDtool')

    def _update_cycle(self):
        for itempath in self._rrds:
            rrd = self._rrds[itempath]
            if rrd['type'] == 'GAUGE':
                value = 'N:' + str(float(rrd['item']()))
            else:  # 'COUNTER'
                value = 'N:' + str(int(rrd['step'] * rrd['item']()))
            try:
                rrdtool.update(
                    rrd['rrdb'],
                    value
                )
            except Exception as e:
                self.logger.warning("RRD: error updating {}: {}".format(itempath, e))
                continue


    def parse_logic(self, logic):
        # no logics are supported
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        # no updates of items are processed
        pass

    def _series(self, func, start='1d', end='now', count=100, ratio=1, update=False, step=None, sid=None, item=None):
        """
        Prepare a series of data that can be passed to the websocket and thus to a visu
        """
        if item in self._rrds:
            rrd = self._rrds[item]
        else:
            self.logger.warning("RRDtool: not enabled for {}".format(item))
            return
        query = ["{}".format(rrd['rrdb'])]
        # prepare consolidation function
        if func == 'avg':
            query.append('AVERAGE')
        elif func == 'max':
            if not rrd['max']:
                self.logger.warning("RRDtool: unsupported consolidation function {} for {}".format(func, item))
                return
            query.append('MAX')
        elif func == 'min':
            if not rrd['min']:
                self.logger.warning("RRDtool: unsupported consolidation function {} for {}".format(func, item))
                return
            query.append('MIN')
        elif func == 'raw':
            query.append('AVERAGE')
            self.logger.warning("RRDtool: unsupported consolidation function {} for {}. Using average instead".format(func, item))
        else:
            self.logger.warning("RRDtool: unsupported consolidation function {} for {}".format(func, item))
            return
        # set time frame for query
        if start.isdigit():
            query.extend(['--start', "{}".format(start)])
        else:
            query.extend(['--start', "now-{}".format(start)])
        if end != 'now':
            if end.isdigit():
                query.extend(['--end', "{}".format(end)])
            else:
                query.extend(['--end', "now-{}".format(end)])
        if step is not None:
            query.extend(['--resolution', step])
        # run query
        try:
            meta, name, data = rrdtool.fetch(*query)
        except Exception as e:
            self.logger.warning("error reading {0} data: {1}".format(item, e))
            return None

        # postprocess values
        if sid is None:
            sid = "{}|{}|{}|{}|{}".format(item,func,start,end,count)
        reply = {'cmd': 'series', 'series': None, 'sid': sid}
        istart, iend, istep = meta
        mstart = istart * 1000
        mstep = istep * 1000
        # old way could have null values which need to be suppressed as visu could not handle null properly
        # tuples = [(mstart + i * mstep, v) for i, v in enumerate(data)]
        tuples = []
        for i, v in enumerate(data):
            if v[0] is not None:
                tuples.append((mstart + i * mstep, v[0]))
        reply['series'] = sorted(tuples)
        reply['params'] = {'update': True, 'item': item, 'func': func, 'start': str(iend), 'end': str(iend + istep), 'step': str(istep), 'sid': sid}
        reply['update'] = self.get_sh().now() + datetime.timedelta(seconds=istep)
        self.logger.warning("Returning series for {} from {} to {} with {} values".format(sid, iend, iend+istep, len(tuples) ))
        return reply

    def _single(self, func, start='1d', end='now', item=None):
        """
        Reads a single value from rrd.

        :param func: String with consolidating function 'avg', 'min', 'max', 'last' to use
        :param start: String containing a start time
        :param end: String containing a start time
        """
        if item in self._rrds:
            rrd = self._rrds[item]
        else:
            self.logger.warning("RRDtool: not enabled for {}".format(item))
            return

        # prepare consolidation function
        query = ["{}".format(rrd['rrdb'])]
        if func == 'avg':
            query.append('AVERAGE')
        elif func == 'max':
            if rrd['max']:
                query.append('MAX')
            else:
                query.append('AVERAGE')
        elif func == 'min':
            if rrd['min']:
                query.append('MIN')
            else:
                query.append('AVERAGE')
        elif func == 'last':
            query.append('AVERAGE')
        elif func == 'raw':
            self.logger.warning("RRDtool: unsupported consolidation function {} for {}. Using average instead".format(func, item))
            query.append('AVERAGE')
        else:
            self.logger.warning("RRDtool: unsupported consolidation function {} for {}".format(func, item))
            return

        # set time frame for query
        if start.isdigit():
            query.extend(['--start', "{}".format(start)])
        else:
            query.extend(['--start', "now-{}".format(start)])
        if end != 'now':
            if end.isdigit():
                query.extend(['--end', "{}".format(end)])
            else:
                query.extend(['--end', "now-{}".format(end)])

        # execute query
        try:
            meta, name, data = rrdtool.fetch(*query)
        except Exception as e:
            self.logger.warning("error reading {0} data: {1}".format(item, e))
            return None

        # unpack returned values
        values = [v[0] for v in data if v[0] is not None]

        # postprocess for consolidation
        if func == 'avg':
            if len(values) > 0:
                return sum(values) / len(values)
        elif func == 'min':
            if len(values) > 0:
                return min(values)
        elif func == 'max':
            if len(values) > 0:
                return max(values)
        elif func == 'last':
            if len(values) > 0:
                return values[-1]
        elif func == 'raw':
            self.logger.warning("Unsupported consolidation function {0} for {1}. Using last instead".format(func, item))
            if len(values) > 0:
                return values[-1]

    def _create(self, rrd):
        """
        Creates a rrd according to the given rrd param
        Called by run method to ensure that the database will be present to accept values
        """
        args = [rrd['rrdb']]
        item_id = rrd['id'].rpartition('.')[2][:19]

        args.append("DS:{}:{}:{}:U:U".format(item_id, rrd['type'], str(2 * rrd['step'])))
        if rrd['min']:
            args.append('RRA:MIN:0.5:{}:1825'.format(int(86400 / rrd['step'])))  # 24h/5y
        if rrd['max']:
            args.append('RRA:MAX:0.5:{}:1825'.format(int(86400 / rrd['step'])))  # 24h/5y
        args.extend(['--step', str(rrd['step'])])

        if rrd['type'] == 'GAUGE':
            args.append('RRA:AVERAGE:0.5:1:{}'.format(int(86400 / rrd['step']) * 7 + 8))  # 7 days
            args.append('RRA:AVERAGE:0.5:{}:1536'.format(int(1800 / rrd['step'])))  # 0.5h/32 days
            args.append('RRA:AVERAGE:0.5:{}:1600'.format(int(21600 / rrd['step'])))  # 6h/400 days
            args.append('RRA:AVERAGE:0.5:{}:1826'.format(int(86400 / rrd['step'])))  # 24h/5y
            args.append('RRA:AVERAGE:0.5:{}:1300'.format(int(604800 / rrd['step'])))  # 7d/25y
        elif rrd['type'] == 'COUNTER':
            args.append('RRA:AVERAGE:0.5:{}:1826'.format(int(86400 / rrd['step'])))  # 24h/5y
            args.append('RRA:AVERAGE:0.5:{}:1300'.format(int(604800 / rrd['step'])))  # 7d/25y
        try:
            rrdtool.create(*args)
            self.logger.debug("Creating rrd ({0}) for {1}.".format(rrd['rrdb'], rrd['item']))
        except Exception as e:
            self.logger.warning("Error creating rrd ({0}) for {1}: {2}".format(rrd['rrdb'], rrd['item'], e))
