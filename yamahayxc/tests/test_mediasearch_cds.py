"""CDS client and finder against a fake UPnP ContentDirectory server."""

import socket
import threading

import pytest

from plugins.yamahayxc.mediasearch.cds import (
    CdsClient,
    CdsSearchFinder,
    MediaServerError,
    MediaServerRef,
    resolve_server,
    ssdp_locations,
)
from plugins.yamahayxc.mediasearch.query import HitKind, parse_query
from plugins.yamahayxc.tests.cds_fake import make_library

SERVER = MediaServerRef('NaryaMedia', 'http://media.test:9000/ctl')


def make_finder():
    return CdsSearchFinder(SERVER, CdsClient(SERVER.control_url))


def test_track_search_returns_ranked_tracks_with_their_album():
    library = make_library()

    with library.active():
        found = make_finder().find(parse_query('title: love'))

    assert [(c.kind, c.title, c.album) for c in found] == [
        (HitKind.TRACK, 'Love of My Life', 'Greatest Hits'),
        (HitKind.TRACK, 'Love Is All', 'Greatest Hits'),
    ]


def test_bare_query_searches_albums_and_tracks_separately():
    library = make_library()

    with library.active():
        found = make_finder().find(parse_query('help'))

    assert [(c.kind, c.title) for c in found] == [(HitKind.ALBUM, 'Help!'), (HitKind.TRACK, 'Help!')]
    assert len(library.searches) == 2


def test_album_target_searches_albums_only_with_exact_class():
    library = make_library()

    with library.active():
        make_finder().find(parse_query('album: hits'))

    assert library.searches == ['upnp:class = "object.container.album.musicAlbum" and dc:title contains "hits"']


def test_every_term_becomes_a_title_clause_and_specials_are_escaped():
    library = make_library()

    with library.active():
        make_finder().find(parse_query('title: 5" a\\b'))

    assert library.searches == [
        'upnp:class derivedfrom "object.item.audioItem" and dc:title contains "5\\"" and dc:title contains "a\\\\b"'
    ]


def resolve_first(raw_query):
    library = make_library()
    with library.active():
        finder = make_finder()
        return finder.resolve(finder.find(parse_query(raw_query))[0])


def test_album_resolves_to_its_path_through_the_albums_view():
    hit = resolve_first('album: abbey')

    assert (hit.kind, hit.title, hit.album) == (HitKind.ALBUM, 'Abbey Road', 'Abbey Road')
    assert hit.path == (('NaryaMedia', None), ('Music', 0), ('Album', 1), ('Abbey Road', 0))


def test_track_resolves_through_its_album_not_the_flat_track_list():
    hit = resolve_first('title: something')

    assert (hit.kind, hit.title, hit.album) == (HitKind.TRACK, 'Something', 'Abbey Road')
    assert hit.path == (('NaryaMedia', None), ('Music', 0), ('Album', 1), ('Abbey Road', 0), ('Something', 1))


def test_track_picks_the_duplicate_titled_album_that_contains_it():
    hit = resolve_first('title: tiger')

    assert hit.path[-2:] == (('Greatest Hits', 2), ('Eye of the Tiger', 0))


def test_track_without_a_matching_album_container_is_unresolvable():
    library = make_library()
    library.add('0$1$8$orphan', '0$1$8', 'Lonely Song', 'object.item.audioItem.musicTrack', 'No Such Album')

    with library.active():
        finder = make_finder()
        hit = finder.resolve(finder.find(parse_query('lonely'))[0])

    assert hit is None


def test_description_url_resolves_to_name_and_absolute_control_url():
    library = make_library()

    with library.active():
        server = resolve_server(library.desc_url)

    assert server == SERVER


def test_friendly_name_is_found_among_the_discovered_servers_ignoring_case():
    library = make_library()
    other = 'http://other.test/desc.xml'

    with library.active():
        server = resolve_server('naryaMEDIA', locations=lambda: [other, library.desc_url])

    assert server == SERVER


def test_unknown_friendly_name_is_an_error():
    library = make_library()

    with library.active(), pytest.raises(MediaServerError):
        resolve_server('Nobody', locations=lambda: [library.desc_url])


def test_ssdp_collects_the_locations_of_answering_media_servers():
    responder = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    responder.bind(('127.0.0.1', 0))
    responder.settimeout(2)

    def answer():
        data, sender = responder.recvfrom(2048)
        assert b'urn:schemas-upnp-org:device:MediaServer:1' in data
        for location in ('http://a.test/desc.xml', 'http://a.test/desc.xml', 'http://b.test/desc.xml'):
            responder.sendto(f'HTTP/1.1 200 OK\r\nLOCATION: {location}\r\nST: x\r\n\r\n'.encode(), sender)

    thread = threading.Thread(target=answer)
    thread.start()
    try:
        found = ssdp_locations(timeout=0.5, target=responder.getsockname())
    finally:
        thread.join()
        responder.close()

    assert found == ['http://a.test/desc.xml', 'http://b.test/desc.xml']


def test_characters_xml_forbids_are_dropped_from_titles():
    library = make_library()
    library.add(
        '0$1$12$9', '0$1$12', 'ignored', 'object.container.album.musicAlbum', raw_title='A Beautiful Mind [OST&#29;]'
    )

    with library.active():
        titles = [obj.title for obj in CdsClient(SERVER.control_url).children('0$1$12').objects]

    assert titles[-1] == 'A Beautiful Mind [OST]'
