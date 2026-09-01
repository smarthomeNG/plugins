import unittest

from lib.metadata import Metadata
from plugins.viessmann import viessmann
from tests.mock.core import MockSmartHome


class TestReadTempAddr(unittest.TestCase):
    def plugin(self):
        sh = MockSmartHome()
        viessmann._parameters = {
            'model': 'VScotHO1_200_11',
            'viess_proto': 'KW',
            'serialport': '/dev/null',
            'cycle': 300,
            'plugin_path': 'plugins.viessmann',
            'command_class': 'SDPCommandViessmann',
        }
        plugin = viessmann.__new__(viessmann)
        plugin._set_sh(sh)
        plugin.metadata = Metadata(sh, 'viessmann', 'plugin', classpath='plugins.viessmann')
        plugin.__init__(sh)
        return plugin

    def test_read_temp_addr_accepts_new_address(self):
        plugin = self.plugin()
        plugin.read_temp_addr('abcd', length=1, mult=0, signed=False)
        self.assertNotIn('temp_cmd', plugin._commands._commands)
