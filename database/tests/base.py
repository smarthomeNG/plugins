import common
import datetime
import unittest

from plugins.database import Database
from tests.mock.core import MockSmartHome

class TestDatabaseBase(unittest.TestCase):

    TIME_FACTOR = 1000

    def plugin(self):
        self.sh = MockSmartHome()
        self.sh.with_dbapi('sqlite', 'sqlite3')
        self.sh.with_items_from(common.BASE + '/plugins/database/tests/test_items.conf')
        plugin = Database(self.sh, 'sqlite', {'database' : ':memory:'})
        for item in self.sh.return_items():
            plugin.parse_item(item)
        return plugin

    def t(self, s):
        return s * TestDatabaseBase.TIME_FACTOR;

    def create_item(self, plugin, name):
        return plugin.id(self.sh.return_item(name), True)

    def create_log(self, plugin, name, tuples):
        """ Create log in database (pass list of tuples: start, end, value)
        """
        id = self.create_item(plugin, name)
        for t in tuples:
            if t[1] is None:
                duration = None
            else:
                duration = self.t(t[1]-t[0])
            plugin.insertLog(id, time=self.t(t[0]), duration=duration, val=t[2], it='num')

    def dump_log(self, plugin, name):
        values = [(value[0], value[2], value[4]) for value in plugin.readLogs(plugin.id(self.sh.return_item(name), False))]
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
        n = 0
        value = func(n=n)
        while value <= end:
            values.append(value)
            n = n + 1
            value = func(n)
        return values

    def log_dump(self, values):
        func = [
           lambda v, nv: "{0:5} - {1: >5} ({2: >3})".format(v, (nv if nv != None else 0), (nv if nv != None else 0)-v),
           lambda v, nv: v,
           lambda v, nv: v
        ]
        align = [
           ">26", ">10", ">10"
        ]
        for (j, value) in enumerate(values):
           for (i, column) in enumerate(value):
               fmt = "{0: " + align[i] + "}"
               v = column
               nv = None if j == len(values)-1 else values[j+1][i]
               res = func[i](v, nv)
               print(fmt.format(res if res is not None else "(none)"), end='')
           print("");

    def assertSingle(self, expected, actual):
        self.assertEquals(expected, actual)

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
        for (i, e) in enumerate(expected):
            result.append((self.t(e[0]), e[1]))
        self.assertEquals(result, actual['series'])

    def assertSeriesCount(self, expected, actual):
        self.assertEquals(expected, len(actual['series']))

