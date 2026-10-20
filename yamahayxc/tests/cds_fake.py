"""
FakeMediaServer: a small UPnP ContentDirectory:1 server behind requests.post().

Holds an object tree and answers Browse/Search SOAP calls like a real server
(escaped DIDL-Lite in <Result>, paging via StartingIndex/RequestedCount); the
plugin's CDS client runs unmodified against it.
"""

import re
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from dataclasses import dataclass
from unittest.mock import patch
from xml.sax.saxutils import escape

import requests

SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
CDS_NS = 'urn:schemas-upnp-org:service:ContentDirectory:1'
ALBUM_CLASS = 'object.container.album.musicAlbum'
FOLDER_CLASS = 'object.container.storageFolder'
TRACK_CLASS = 'object.item.audioItem.musicTrack'

_CLAUSE = re.compile(r'\s*(\S+)\s+(=|contains|derivedfrom)\s+"((?:[^"\\]|\\.)*)"\s*')


@dataclass
class FakeObject:
    id: str
    parent_id: str
    title: str
    upnp_class: str
    album: str = ''
    searchable: bool = True
    raw_title: str | None = None  # sent unescaped, to reproduce servers emitting invalid XML

    @property
    def is_container(self):
        return self.upnp_class.startswith('object.container')


class FakeMediaServer:
    """Object tree plus the SOAP endpoint; `searches` records every SearchCriteria received."""

    def __init__(self, control_url='http://media.test:9000/ctl', friendly_name='NaryaMedia'):
        self.control_url = control_url
        self.friendly_name = friendly_name
        self.desc_url = 'http://media.test:9000/dev0/desc.xml'
        self.objects = {'0': FakeObject('0', '-1', 'root', FOLDER_CLASS)}
        self.searches = []
        self.browses = []
        self.gate = None  # threading.Event: while set, SOAP calls wait for it

    def add(self, id, parent_id, title, upnp_class, album='', searchable=True, raw_title=None):
        self.objects[id] = FakeObject(id, parent_id, title, upnp_class, album, searchable, raw_title)

    def get(self, url, timeout=None):
        """serve the UPnP device description"""
        if url != self.desc_url:
            raise requests.ConnectionError(f'no server at {url}')
        path = '/' + self.control_url.split('/', 3)[3]
        return _Response(
            '<?xml version="1.0"?><root xmlns="urn:schemas-upnp-org:device-1-0"><device>'
            '<deviceType>urn:schemas-upnp-org:device:MediaServer:1</deviceType>'
            f'<friendlyName>{escape(self.friendly_name)}</friendlyName><serviceList><service>'
            '<serviceType>urn:schemas-upnp-org:service:ConnectionManager:1</serviceType>'
            '<controlURL>/cm</controlURL></service><service>'
            f'<serviceType>{CDS_NS}</serviceType><controlURL>{path}</controlURL></service>'
            '</serviceList></device></root>'
        )

    def children(self, parent_id):
        return [obj for obj in self.objects.values() if obj.parent_id == parent_id]

    def post(self, url, data=None, headers=None, timeout=None):
        if url != self.control_url:
            raise requests.ConnectionError(f'no server at {url}')
        if self.gate is not None:
            self.gate.wait(5)
        action = headers['SOAPACTION'].strip('"').split('#')[1]
        args = {el.tag: el.text or '' for el in ET.fromstring(data).find(f'.//{{{CDS_NS}}}{action}')}
        if action == 'Search':
            self.searches.append(args['SearchCriteria'])
            matching = [
                obj for obj in self.objects.values() if obj.searchable and self._matches(obj, args['SearchCriteria'])
            ]
        elif args['BrowseFlag'] == 'BrowseMetadata':
            self.browses.append(args['ObjectID'])
            matching = [self.objects[args['ObjectID']]]
        else:
            self.browses.append(args['ObjectID'])
            matching = self.children(args['ObjectID'])
        start, count = int(args['StartingIndex']), int(args['RequestedCount'])
        page = matching[start : start + count if count else None]
        return _Response(self._envelope(action, page, len(matching)))

    @staticmethod
    def _matches(obj, criteria):
        for clause in criteria.split(' and '):
            found = _CLAUSE.fullmatch(clause)
            assert found, f'unsupported SearchCriteria clause {clause!r}'
            prop, op, value = found.groups()
            value = re.sub(r'\\(.)', r'\1', value)
            if prop == 'upnp:class':
                ok = obj.upnp_class == value if op == '=' else obj.upnp_class.startswith(value)
            elif prop == 'dc:title':
                ok = obj.title.casefold() == value.casefold() if op == '=' else value.casefold() in obj.title.casefold()
            else:
                raise AssertionError(f'unsupported property {prop}')
            if not ok:
                return False
        return True

    @staticmethod
    def _envelope(action, page, total):
        didl = ''.join(
            '<{tag} id="{id}" parentID="{parent}" restricted="1"><dc:title>{title}</dc:title>'
            '<upnp:class>{cls}</upnp:class>{album}</{tag}>'.format(
                tag='container' if obj.is_container else 'item',
                id=escape(obj.id),
                parent=escape(obj.parent_id),
                title=obj.raw_title if obj.raw_title is not None else escape(obj.title),
                cls=obj.upnp_class,
                album=f'<upnp:album>{escape(obj.album)}</upnp:album>' if obj.album else '',
            )
            for obj in page
        )
        result = (
            '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            f'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">{didl}</DIDL-Lite>'
        )
        return (
            f'<?xml version="1.0"?><s:Envelope xmlns:s="{SOAP_NS}"><s:Body>'
            f'<u:{action}Response xmlns:u="{CDS_NS}"><Result>{escape(result)}</Result>'
            f'<NumberReturned>{len(page)}</NumberReturned><TotalMatches>{total}</TotalMatches>'
            f'<UpdateID>1</UpdateID></u:{action}Response></s:Body></s:Envelope>'
        )

    @contextmanager
    def active(self):
        with (
            patch('plugins.yamahayxc.mediasearch.cds.requests.post', side_effect=self.post),
            patch('plugins.yamahayxc.mediasearch.cds.requests.get', side_effect=self.get),
        ):
            yield


class _Response:
    status_code = 200

    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


def make_library():
    """
    A Twonky-like library: Music -> {All Tracks (flat), Album (flat album view)}.

    Tracks are searchable in the flat 'All Tracks' view only, as on the real server;
    the copies inside the albums are browse-only. Two albums share the title 'Greatest Hits'.
    """
    server = FakeMediaServer()
    server.add('0$1', '0', 'Music', FOLDER_CLASS)
    server.add('0$1$8', '0$1', 'All Tracks', FOLDER_CLASS)
    server.add('0$1$12', '0$1', 'Album', FOLDER_CLASS)
    albums = {
        '0$1$12$1': ('Abbey Road', ['Come Together', 'Something', 'Here Comes The Sun']),
        '0$1$12$2': ('Greatest Hits', ['Bohemian Rhapsody', 'Love of My Life']),
        '0$1$12$3': ('Greatest Hits', ['Eye of the Tiger', 'Love Is All']),
        '0$1$12$4': ('Help!', ['Help!', 'Yesterday']),
    }
    for album_id, (album_title, tracks) in albums.items():
        server.add(album_id, '0$1$12', album_title, ALBUM_CLASS)
        for number, title in enumerate(tracks):
            server.add(f'{album_id}${number}', album_id, title, TRACK_CLASS, album_title, searchable=False)
            server.add(f'0$1$8${album_id[-1]}{number}', '0$1$8', title, TRACK_CLASS, album_title)
    return server
