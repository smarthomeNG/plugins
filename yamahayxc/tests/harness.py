"""
Shared test harness for the yamahayxc plugin tests.

FakeNetwork stands in for the MusicCast HTTP endpoints behind requests.request()
(the only network boundary of the plugin); everything else runs real plugin code.
"""

import json
import time
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import urlparse

from tests import common
from tests.mock.core import MockScheduler, MockSmartHome

from plugins.yamahayxc import YamahaYXC

ITEMS_DIR = common.BASE + '/plugins/yamahayxc/tests/'


class RecordingScheduler(MockScheduler):
    """MockScheduler that remembers which named jobs are currently scheduled."""

    def __init__(self):
        super().__init__()
        self.jobs = set()

    def add(self, name, *args, **kwargs):
        super().add(name, *args, **kwargs)
        self.jobs.add(name)

    def remove(self, name, from_smartplugin=False):
        super().remove(name, from_smartplugin=from_smartplugin)
        self.jobs.discard(name)


class FakeDevice:
    """One MusicCast device. `responses` maps an endpoint suffix (e.g. 'getStatus') to a body dict."""

    def __init__(self, features=None):
        self.up = True
        self.gate = None  # threading.Event: while set and unset-waiting, getStatus blocks until it is set
        self.calls = []
        self.responses = {}
        self.features = features if features is not None else {'zone': []}

    def handle(self, method, path, data):
        """Return the JSON-serializable body for one request."""
        self.calls.append((method, path, data))
        if self.gate is not None and path.endswith('getStatus'):
            self.gate.wait(5)
        if path.endswith('getFeatures'):
            return {'response_code': 0, **self.features}
        for suffix, body in self.responses.items():
            if path.endswith(suffix):
                return {'response_code': 0, **body}
        return {'response_code': 0}

    def paths(self):
        """All endpoint paths requested so far, in order."""
        return [path for _, path, _ in self.calls]


class FakeNetwork:
    """Routes requests.request() calls to FakeDevices by host."""

    def __init__(self, devices):
        self.devices = devices

    def request(self, method, url, headers=None, data=None, timeout=None):
        parsed = urlparse(url)
        device = self.devices[parsed.hostname]
        if not device.up:
            raise ConnectionError('device unreachable')

        class _Response:
            pass

        response = _Response()
        response.text = json.dumps(device.handle(method, url.split('/YamahaExtendedControl/', 1)[1], data))
        return response

    @contextmanager
    def active(self):
        with patch('plugins.yamahayxc.requests.request', side_effect=self.request):
            yield


def wait_until(condition, timeout=2.0):
    """Poll condition() until it is truthy; return its last value (notifications are processed on worker threads)."""
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)
    return condition()


def make_plugin(items_file, network, initialize=True):
    """Build a running YamahaYXC with items parsed from tests/<items_file>; runs _initialize() against network."""
    sh = MockSmartHome()
    sh.scheduler = RecordingScheduler()
    sh.with_items_from(ITEMS_DIR + items_file)

    YamahaYXC._parameters = {'cycle': 30}
    plugin = YamahaYXC.__new__(YamahaYXC)
    plugin._set_sh(sh)
    plugin.__init__(sh)
    for item in sh.return_items():
        plugin.parse_item(item)

    if initialize:
        with network.active():
            plugin._initialize()
    plugin.alive = True
    return plugin, sh
