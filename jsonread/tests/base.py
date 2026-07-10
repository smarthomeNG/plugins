import os

from plugins.jsonread import JSONREAD
from tests.mock.core import MockSmartHome


class JsonreadTestBase:
    """
    Shared plugin-instantiation helper for jsonread tests.

    SmartPlugin parameter loading isn't available in test environments, so
    get_parameter_value() would return None for everything — inject the
    plugin.yaml defaults directly as a class-level parameter dict instead,
    same pattern as plugins/database/tests/base.py.
    """

    FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

    def plugin(self, url=None, cycle=30):
        self.sh = MockSmartHome()
        JSONREAD._parameters = {'url': url or f'file://{self.FIXTURES_DIR}/fronius.json', 'cycle': cycle}
        return JSONREAD(self.sh)

    def fixture_path(self, name):
        return os.path.join(self.FIXTURES_DIR, name)
