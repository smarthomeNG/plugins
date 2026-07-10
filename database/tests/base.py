import os
import sys

print(sys.path)
from tests import common
import datetime
import tempfile
import unittest

from plugins.database import Database
from tests.mock.core import MockSmartHome


class TestDatabaseBase(unittest.TestCase):
    TIME_FACTOR = 1000

    def plugin(self):
        self.sh = MockSmartHome()
        self.sh.with_items_from(common.BASE + '/plugins/database/tests/test_items.yaml')

        # In test environments the full SmartPlugin parameter loading infrastructure
        # is not available, so get_parameter_value() would return None for everything.
        # Inject the plugin.yaml defaults directly as a class-level parameter dict so
        # the Database constructor can initialise without errors.
        #
        # Use a named temp file rather than ':memory:' because SQLite3 opens a
        # separate, independent in-memory database for every connection.  The plugin
        # creates two connections (_db and _db_maint); with ':memory:' they cannot
        # see each other's data, which breaks build_orphanlist() and any test that
        # uses the maintenance connection.  A shared on-disk file avoids this.
        self._db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self._db_file.close()
        self.addCleanup(os.unlink, self._db_file.name)

        Database._parameters = {
            'driver': 'sqlite3',
            'connect': {'database': self._db_file.name},
            'prefix': '',
            'cycle': 60,
            'removeold_cycle': 91,
            'precision': 2,
            'time_precision': 3,
            'count_logentries': False,
            'max_delete_logentries': 20000,
            'max_reassign_logentries': 20,
            'default_maxage': 0,
            'copy_database': False,
            'copy_database_name': '',
        }

        plugin = Database(self.sh)
        for item in self.sh.return_items():
            plugin.parse_item(item)
        return plugin

    def t(self, s):
        return s * TestDatabaseBase.TIME_FACTOR

    def create_tmpfile(self):
        (fd, name) = tempfile.mkstemp()
        os.close(fd)
        return name

    def read_tmpfile(self, name):
        with open(name, 'r') as f:
            content = f.read(os.path.getsize(name))
        os.unlink(name)
        return content

    def create_item(self, plugin, name):
        return plugin.id(self.sh.return_item(name), True)

    def create_log(self, plugin, name, tuples):
        """Create log in database (pass list of tuples: start, end, value)"""
        id = self.create_item(plugin, name)
        for t in tuples:
            if t[1] is None:
                duration = None
            else:
                duration = self.t(t[1] - t[0])
            plugin.insertLog(id, time=self.t(t[0]), duration=duration, val=t[2], it='num')

    def dump_item(self, plugin, name):
        value = plugin.readItem(plugin.id(self.sh.return_item(name)))
        values = [(value[0], value[2], value[4])]
        self.log_dump(values)

    def dump_log(self, plugin, name):
        values = [
            (value[0], value[2], value[4]) for value in plugin.readLogs(plugin.id(self.sh.return_item(name), False))
        ]
        self.log_dump(values)

    def log_slice(self, start, interval, *tuples_list):
        logs = []
        for tuples in tuples_list:
            for t in tuples:
                logs.append((start, start + interval, t))
                start = start + interval
        return logs

    def log_slice_values_delta(self, start, end, delta):
        values = []
        value = start
        while (delta < 0 or value <= end) and (delta > 0 or value >= end):
            values.append(value)
            value = value + delta
        return values

    def log_slice_values_func(self, start, end, func):
        values = []
        n = 0
        value = func(n=n)
        while value <= end:
            values.append(value)
            n = n + 1
            value = func(n)
        return values

    def log_dump(self, values):
        func = [
            lambda v, nv: '{0:5} - {1: >5} ({2: >3})'.format(
                v, (nv if nv is not None else 0), (nv if nv is not None else 0) - v
            ),
            lambda v, nv: v,
            lambda v, nv: v,
        ]
        align = ['>26', '>10', '>10']
        for j, value in enumerate(values):
            for i, column in enumerate(value):
                fmt = '{0: ' + align[i] + '}'
                v = column
                nv = None if j == len(values) - 1 else values[j + 1][i]
                res = func[i](v, nv)
                print(fmt.format(res if res is not None else '(none)'), end='')
            print('')

    def assertLines(self, expected, actual):
        print(actual.split('\n'))
        for line in actual.split('\n'):
            self.assertIn(line, expected)

    def assertSingle(self, expected, actual):
        self.assertEqual(expected, actual)

    def assertSeries(self, expected, actual):
        # Series result is (in actual):
        # {
        # 'sid': 'main.num|avg|0|now|100',
        # 'params': {
        #   'item': 'main.num',
        #   'step': None,
        #   'update': True,
        #   'func': 'avg',
        #   'start': 1494087165032,
        #   'sid': 'main.num|avg|0|now|100',
        #   'end': 'now'
        # },
        # 'series': [
        #   (1494087165029, 0.0),
        #   (1494087165032, 0.0)
        # ],
        # 'update': datetime.datetime(2017, 10, 26, 16, 27, 16, 33702),
        # 'cmd': 'series'
        # }
        result = []
        for i, e in enumerate(expected):
            result.append((self.t(e[0]), e[1]))
        self.assertEqual(result, actual['series'])

    def assertSeriesCount(self, expected, actual):
        self.assertEqual(expected, len(actual['series']))
