"""Replaying a hit's path on the device's browse cursor (real adapter, simulated device)."""

from plugins.yamahayxc.mediasearch import YxcListCursor
from plugins.yamahayxc.mediasearch.query import HitKind
from plugins.yamahayxc.mediasearch.replay import Hit, PathStep, ReplayResult, replay
from plugins.yamahayxc.tests.harness import FakeBrowse, FakeDevice, FakeNetwork, container, make_plugin, track

ALBUMS = [f'Album {n:02d}' for n in range(20)]


def make_library():
    """Layer 0: two servers; NaryaMedia -> Music -> Album -> 20 albums, the last with two tracks"""
    albums = [container(title, track(f'{title} song 1'), track(f'{title} song 2')) for title in ALBUMS]
    return container(
        '', container('MinimServer[narya]'), container('NaryaMedia', container('Music', container('Album', *albums)))
    )


def setup(root=None):
    device = FakeDevice(browse=FakeBrowse(root or make_library()))
    network = FakeNetwork({'127.0.0.1': device})
    plugin, _ = make_plugin('items_search.yaml', network)
    return device, network, YxcListCursor(plugin, '127.0.0.1')


def album_hit(index, title=None):
    title = title or ALBUMS[index]
    return Hit(
        HitKind.ALBUM,
        title,
        title,
        (PathStep('NaryaMedia', None), PathStep('Music', 0), PathStep('Album', 0), PathStep(title, index)),
    )


def track_hit(index, number):
    album = ALBUMS[index]
    return Hit(
        HitKind.TRACK,
        f'{album} song {number}',
        album,
        (
            PathStep('NaryaMedia', None),
            PathStep('Music', 0),
            PathStep('Album', 0),
            PathStep(album, index),
            PathStep(f'{album} song {number}', number - 1),
        ),
    )


def never():
    return False


def test_album_hit_is_played_now_from_its_listing():
    device, network, cursor = setup()

    with network.active():
        result = replay(album_hit(17), cursor, never)

    assert result is ReplayResult.OK
    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Album 17'))]


def test_track_hit_is_played_inside_its_album():
    device, network, cursor = setup()

    with network.active():
        result = replay(track_hit(3, 2), cursor, never)

    assert result is ReplayResult.OK
    assert device.browse.played == [('play', ('NaryaMedia', 'Music', 'Album', 'Album 03', 'Album 03 song 2'))]


def test_replay_starts_from_the_top_wherever_the_cursor_was():
    device, network, cursor = setup()
    device.browse.stack += [device.browse.root.children[1], device.browse.root.children[1].children[0]]

    with network.active():
        result = replay(album_hit(1), cursor, never)

    assert result is ReplayResult.OK
    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Album 01'))]


def test_correct_hint_needs_one_page_per_layer():
    device, network, cursor = setup()

    with network.active():
        replay(album_hit(17), cursor, never)

    list_calls = [path for path in device.paths() if 'getListInfo' in path]
    assert len(list_calls) == 4
    assert 'index=16' in list_calls[-1]


def test_wrong_hint_falls_back_to_scanning_the_layer():
    device, network, cursor = setup()
    hit = album_hit(17)
    wrong = hit._replace(path=hit.path[:-1] + (PathStep('Album 17', 3),))

    with network.active():
        result = replay(wrong, cursor, never)

    assert result is ReplayResult.OK
    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', 'Album 17'))]


def test_missing_entry_fails_the_path_without_playing():
    device, network, cursor = setup()

    with network.active():
        result = replay(album_hit(0, title='No Such Album'), cursor, never)

    assert result is ReplayResult.PATH_FAILED
    assert device.browse.played == []


def test_cancellation_is_honoured_at_layer_boundaries():
    device, network, cursor = setup()
    layers_left = iter([False, False, True])

    with network.active():
        result = replay(album_hit(0), cursor, lambda: next(layers_left, True))

    assert result is ReplayResult.CANCELLED
    assert device.browse.played == []


def test_standby_device_is_woken_and_switched_to_the_server_input():
    device, network, cursor = setup()
    device.browse.power = 'standby'
    device.browse.input = 'tuner'

    with network.active():
        result = replay(album_hit(0), cursor, never)

    assert result is ReplayResult.OK
    assert (device.browse.power, device.browse.input) == ('on', 'server')


def test_truncated_container_text_matches_by_prefix():
    long_title = 'A Very Long Album Title That The Device Cuts Off'
    root = container('', container('NaryaMedia', container('Music', container('Album', container(long_title[:32])))))
    device, network, cursor = setup(root)
    hit = album_hit(0, title=long_title)

    with network.active():
        result = replay(hit, cursor, never)

    assert result is ReplayResult.OK
    assert device.browse.played == [('play_now', ('NaryaMedia', 'Music', 'Album', long_title[:32]))]
