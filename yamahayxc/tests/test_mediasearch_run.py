"""run_search: query -> media server -> device, against a fake server and a simulated device."""

from contextlib import nullcontext

import pytest

from plugins.yamahayxc.mediasearch import SearchStatus, YxcListCursor, run_search
from plugins.yamahayxc.mediasearch.cds import CdsClient, CdsSearchFinder, MediaServerError, MediaServerRef
from plugins.yamahayxc.tests.cds_fake import make_library
from plugins.yamahayxc.tests.harness import Entry, FakeBrowse, FakeDevice, FakeNetwork, make_plugin

SERVER = MediaServerRef('NaryaMedia', 'http://media.test:9000/ctl')


def device_entries(server, parent_id):
    """the browse tree the device shows for the server's container, in server order"""
    return [
        Entry(obj.title, device_entries(server, obj.id) if obj.is_container else None)
        for obj in server.children(parent_id)
    ]


def setup(library=None):
    library = library or make_library()
    root = Entry('', [Entry('NaryaMedia', device_entries(library, '0'))])
    device = FakeDevice(browse=FakeBrowse(root))
    network = FakeNetwork({'127.0.0.1': device})
    plugin, _ = make_plugin('items_search.yaml', network)
    finder = CdsSearchFinder(SERVER, CdsClient(SERVER.control_url))
    return library, device, network, plugin, finder


def search(raw_query, library, network, plugin, finder, cancelled=lambda: False):
    with library.active(), network.active():
        return run_search(raw_query, finder, YxcListCursor(plugin, '127.0.0.1'), nullcontext(), cancelled)


def test_album_query_plays_the_album():
    library, device, network, plugin, finder = setup()

    report = search('album: abbey', library, network, plugin, finder)

    assert report.status is SearchStatus.OK
    assert (report.hit.title, report.hit.album) == ('Abbey Road', 'Abbey Road')
    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Abbey Road'))]


def test_track_query_plays_the_track_inside_its_album():
    library, device, network, plugin, finder = setup()

    report = search('title: tiger', library, network, plugin, finder)

    assert report.status is SearchStatus.OK
    assert device.browse.played == [('play', ('NaryaMedia', 'Music', 'Album', 'Greatest Hits', 'Eye of the Tiger'))]


def test_bare_query_prefers_the_exact_title_and_the_album():
    library, device, network, plugin, finder = setup()

    search('help!', library, network, plugin, finder)

    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Help!'))]


def test_nothing_found_plays_nothing():
    library, device, network, plugin, finder = setup()

    report = search('zzzz', library, network, plugin, finder)

    assert report.status is SearchStatus.NO_MATCH
    assert report.hit is None
    assert device.browse.played == []


def test_blank_query_finds_nothing_without_asking_the_server():
    library, device, network, plugin, finder = setup()

    report = search('album:', library, network, plugin, finder)

    assert report.status is SearchStatus.NO_MATCH
    assert library.searches == []


def test_hit_the_device_does_not_list_fails_the_path():
    library, device, network, plugin, finder = setup()
    device.browse.root.children[0].children[0].children.pop(1)  # device lacks the 'Album' view

    report = search('album: abbey', library, network, plugin, finder)

    assert report.status is SearchStatus.PATH_FAILED
    assert report.hit.title == 'Abbey Road'
    assert device.browse.played == []


def test_superseded_search_plays_nothing():
    library, device, network, plugin, finder = setup()

    report = search('album: abbey', library, network, plugin, finder, cancelled=lambda: True)

    assert report.status is SearchStatus.IDLE
    assert device.browse.played == []


def test_unreachable_device_is_an_error():
    library, device, network, plugin, finder = setup()
    device.up = False

    report = search('album: abbey', library, network, plugin, finder)

    assert report.status is SearchStatus.ERROR


def test_unreachable_media_server_raises_for_the_caller_to_rediscover():
    library, device, network, plugin, finder = setup()
    library.control_url = 'http://elsewhere.test/ctl'

    with pytest.raises(MediaServerError):
        search('album: abbey', library, network, plugin, finder)
