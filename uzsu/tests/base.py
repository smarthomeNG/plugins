import os
import unittest

from tests import common
from tests.mock.core import MockSmartHome

from lib.orb import Orb
from plugins.uzsu import UZSU

BERLIN_LON = 13.4050
BERLIN_LAT = 52.5200
BERLIN_ELEV = 34


class TestUZSUBase(unittest.TestCase):
    """Base class for UZSU plugin tests.

    Mirrors plugins/database/tests/base.py: builds a MockSmartHome with a
    fixed set of test items, injects plugin.yaml defaults directly (since
    the full parameter-loading infrastructure isn't available in test
    environments), and constructs the plugin.
    """

    def plugin(self, parameters=None, tz='Europe/Berlin'):
        self.sh = MockSmartHome()
        self.sh.shtime.set_tz(tz)
        # UZSU relies on sh.sun/sh.moon (set up by bin/smarthome.py in a real
        # instance) for sunrise/sunset-bound entries; MockSmartHome doesn't
        # provide these, so build them the same way lib/smarthome.py does.
        self.sh.sun = Orb('sun', BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.sh.moon = Orb('moon', BERLIN_LON, BERLIN_LAT, BERLIN_ELEV)
        self.sh.with_items_from(os.path.join(os.path.dirname(__file__), 'test_items.yaml'))

        UZSU._parameters = {
            'remove_duplicates': True,
            'ignore_once_entries': False,
            'suncalculation_cron': '0 0 * *',
            'interpolation_interval': 5,
            'interpolation_type': 'none',
            'backintime': 0,
            'interpolation_precision': 2,
        }
        if parameters:
            UZSU._parameters.update(parameters)

        plugin = UZSU(self.sh)
        for item in self.sh.return_items():
            callback = plugin.parse_item(item)
            if callback is not None:
                plugin._items_callback = callback
        # run() does the real startup bookkeeping (self._series[item] = {},
        # self._lastvalues[item] = None, initial scheduling) that
        # bin/smarthome.py normally triggers once all plugins are loaded.
        plugin.run()
        return plugin

    def plugin_with_entry(self, item_path, entry, active=True, rrule='FREQ=DAILY', **plugin_kwargs):
        """Build a plugin and seed one uzsu list entry directly on
        plugin._items[item]. Bypasses item()'s value-change callback (not
        wired up in this mock setup) and writes the internal state the
        scheduling methods (_get_time, _schedule, ...) actually consume."""
        plugin = self.plugin(**plugin_kwargs)
        item = self.sh.return_item(item_path)
        full_entry = {'active': True, 'rrule': rrule, **entry}
        plugin._items[item]['active'] = active
        plugin._items[item]['list'] = [full_entry]
        return plugin
