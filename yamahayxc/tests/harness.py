"""
Shared test harness for the yamahayxc plugin tests.

FakeNetwork stands in for the MusicCast HTTP endpoints behind requests.request()
(the only network boundary of the plugin); everything else runs real plugin code.
"""

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

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


ATTR_SELECT = 1 << 0
ATTR_PLAY = 1 << 1
ATTR_PLAY_NOW = 1 << 23


@dataclass
class Entry:
    """One line of a browse list; children is None for a playable track, a list for a container"""

    text: str
    children: list['Entry'] | None = None

    @property
    def attribute(self):
        return ATTR_SELECT | ATTR_PLAY_NOW if self.children is not None else ATTR_PLAY | ATTR_PLAY_NOW


def container(text, *children):
    return Entry(text, list(children))


def track(text):
    return Entry(text)


@dataclass
class FakeBrowse:
    """
    netusb browsing of a FakeDevice: a tree of lists and the one device-global position in it.

    Answers getListInfo (8 lines per call, aligned to 8), setListControl select/return/play and
    manageList play_now like the real device; `played` records what it was told to play, as
    (action, texts from layer 0 down to the played entry).
    """

    root: Entry
    power: str = 'on'
    input: str = 'server'
    stack: list[Entry] = field(default_factory=list)
    played: list[tuple[str, tuple[str, ...]]] = field(default_factory=list)

    def __post_init__(self):
        self.stack = [self.root]

    def handle(self, path):
        """Return the response body for a browse/power/input request path, or None if it is not one"""
        endpoint, _, query = path.partition('?')
        args = {key: values[0] for key, values in parse_qs(query).items()}
        current = self.stack[-1]
        if endpoint == 'v1/main/setPower':
            self.power = args['power']
        elif endpoint == 'v1/main/setInput':
            self.input = args['input']
        elif endpoint == 'v1/main/getStatus':
            return {'power': self.power, 'input': self.input}
        elif endpoint == 'v1/netusb/getListInfo':
            index = int(args['index'])
            if index % 8 or self.power != 'on' or args['input'] != self.input:
                return {'response_code': 4 if index % 8 else 5}
            return {
                'menu_layer': len(self.stack) - 1,
                'menu_name': current.text,
                'max_line': len(current.children),
                'index': index,
                'playing_index': 255,
                'list_info': [
                    {'text': entry.text, 'attribute': entry.attribute} for entry in current.children[index : index + 8]
                ],
            }
        elif endpoint in ('v1/netusb/setListControl', 'v1/netusb/manageList'):
            return self._control(args, current)
        else:
            return None
        return {}

    def _control(self, args, current):
        action = args['type']
        if action == 'return':
            if len(self.stack) > 1:
                self.stack.pop()
            return {}
        index = int(args['index'])
        if not 0 <= index < len(current.children):
            return {'response_code': 4}
        entry = current.children[index]
        if action == 'select':
            if entry.children is None:
                return {'response_code': 4}
            self.stack.append(entry)
        else:
            self.played.append((action, tuple(e.text for e in self.stack[1:]) + (entry.text,)))
        return {}


class FakeDevice:
    """One MusicCast device. `responses` maps an endpoint suffix (e.g. 'getStatus') to a body dict."""

    def __init__(self, features=None, browse=None):
        self.browse = browse
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
        if self.browse is not None:
            body = self.browse.handle(path)
            if body is not None:
                return {'response_code': 0, **body}
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


def make_plugin(items_file, network, initialize=True, parameters=None):
    """Build a running YamahaYXC with items parsed from tests/<items_file> and the given plugin parameters; runs _initialize() against network."""
    sh = MockSmartHome()
    sh.scheduler = RecordingScheduler()
    sh.with_items_from(ITEMS_DIR + items_file)

    YamahaYXC._parameters = {'cycle': 30, **(parameters or {})}
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
