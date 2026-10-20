"""Media search through the plugin: search item, status/result items, public method, worker and cursor lock."""

import threading
import time
from contextlib import ExitStack

from plugins.yamahayxc.tests.cds_fake import make_library
from plugins.yamahayxc.tests.harness import Entry, FakeBrowse, FakeDevice, FakeNetwork, make_plugin, wait_until
from plugins.yamahayxc.tests.test_mediasearch_run import device_entries

HOST = '127.0.0.1'


class Setup:
    """A plugin with media search on, a fake media server and a simulated device; use as a context manager"""

    def __init__(self, media_server='library'):
        self.library = make_library()
        root = Entry('', [Entry('NaryaMedia', device_entries(self.library, '0'))])
        self.device = FakeDevice(browse=FakeBrowse(root))
        self.network = FakeNetwork({HOST: self.device})
        setting = {'library': self.library.desc_url}.get(media_server, media_server)
        self.plugin, self.sh = make_plugin(
            'items_search.yaml', self.network, parameters={'media_server': setting}, initialize=False
        )
        self.search_item = self.sh.return_item('yamaha.dev.search')
        self.status = self.sh.return_item('yamaha.dev.search.status')
        self.result = self.sh.return_item('yamaha.dev.search.result')

    def __enter__(self):
        self._stack = ExitStack()
        self._stack.enter_context(self.library.active())
        self._stack.enter_context(self.network.active())
        return self

    def __exit__(self, *exc):
        self.plugin.stop()
        self._stack.close()

    def write(self, query):
        """write query to the search item as a user would and let the plugin handle it"""
        self.search_item(query, 'test')
        self.plugin.update_item(self.search_item, 'test')

    def settle(self, status):
        """wait for the worker to finish with the given status"""
        return wait_until(lambda: self.status() == status)


def test_without_a_media_server_the_search_is_disabled():
    with Setup(media_server='') as setup:
        setup.write('album: abbey')

        assert setup.status() == 'disabled'
        assert setup.device.browse.played == []


def test_search_item_plays_the_best_match_and_reports_it():
    with Setup() as setup:
        setup.write('album: abbey')

        assert setup.settle('ok')
        assert setup.device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Abbey Road'))]
        assert setup.result() == {
            'type': 'album',
            'title': 'Abbey Road',
            'album': 'Abbey Road',
            'path': ['NaryaMedia', 'Music', 'Album', 'Abbey Road'],
        }


def test_search_without_a_match_reports_it_and_clears_the_result():
    with Setup() as setup:
        setup.result({'type': 'album'}, 'test')

        setup.write('zzzz')

        assert setup.settle('no_match')
        assert setup.result() == {}


def test_friendly_name_setting_is_discovered_via_ssdp():
    with Setup(media_server='naryamedia') as setup:
        setup.plugin._media_locations = lambda: [setup.library.desc_url]

        setup.write('title: tiger')

        assert setup.settle('ok')
        assert setup.device.browse.played == [
            ('play', ('NaryaMedia', 'Music', 'Album', 'Greatest Hits', 'Eye of the Tiger'))
        ]


def test_logics_can_call_search_play():
    with Setup() as setup:
        assert setup.plugin.search_play(HOST, 'album: abbey')

        assert setup.settle('ok')


def test_search_play_for_an_unknown_host_is_refused():
    with Setup() as setup:
        assert setup.plugin.search_play('127.0.0.9', 'album: abbey') is False


def test_busy_is_reported_while_the_search_runs():
    with Setup() as setup:
        setup.library.gate = threading.Event()

        setup.write('album: abbey')

        assert setup.status() == 'busy'
        setup.library.gate.set()
        assert setup.settle('ok')


def test_newer_search_supersedes_a_running_one():
    with Setup() as setup:
        setup.library.gate = threading.Event()
        setup.write('album: abbey')
        setup.write('album: help')

        setup.library.gate.set()

        assert setup.settle('ok')
        assert wait_until(lambda: setup.result().get('title') == 'Help!')
        assert setup.device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Help!'))]


def test_media_server_is_rediscovered_after_it_moved():
    with Setup() as setup:
        setup.write('album: abbey')
        assert setup.settle('ok')

        setup.library.control_url = 'http://media.test:9000/moved'
        setup.write('album: help')

        assert wait_until(lambda: setup.result().get('title') == 'Help!')
        assert setup.status() == 'ok'


def test_unreachable_media_server_is_an_error():
    with Setup(media_server='http://nowhere.test/desc.xml') as setup:
        setup.write('album: abbey')

        assert setup.settle('error')


def test_browse_writes_wait_for_a_running_replay():
    with Setup() as setup:
        setup.device.gate = threading.Event()
        browse_return = setup.sh.return_item('yamaha.dev.browse_return')
        setup.write('album: abbey')
        assert wait_until(lambda: 'v1/main/getStatus' in setup.device.paths())
        browse_return(True, 'test')

        writer = threading.Thread(target=setup.plugin.update_item, args=(browse_return, 'test'))
        writer.start()
        time.sleep(0.3)
        blocked = not any('setListControl' in path for path in setup.device.paths())
        setup.device.gate.set()
        writer.join(5)

        assert blocked
        assert not writer.is_alive()
        assert any('type=return' in path for path in setup.device.paths())


def test_status_is_idle_after_startup():
    with Setup() as setup:
        setup.plugin._initialize()

        assert setup.status() == 'idle'


def test_status_is_disabled_after_startup_without_a_server():
    with Setup(media_server='') as setup:
        setup.plugin._initialize()

        assert setup.status() == 'disabled'
