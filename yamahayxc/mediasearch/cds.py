"""
UPnP ContentDirectory client and the search strategy built on it.

CdsClient speaks SOAP (Browse/Search) to one server; CdsSearchFinder turns a
SearchQuery into ranked Candidates and resolves a Candidate into a Hit whose
path the device can replay.
"""

import re
import socket
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import NamedTuple
from urllib.parse import urljoin
from xml.sax.saxutils import escape

import requests

from .query import Candidate, HitKind, SearchQuery, SearchTarget, rank
from .replay import Hit, PathStep

CDS_SERVICE = 'urn:schemas-upnp-org:service:ContentDirectory:1'
ALBUM_CLASS = 'object.container.album.musicAlbum'
AUDIO_CLASS = 'object.item.audioItem'
ROOT_ID = '0'
_FILTER = 'dc:title,upnp:class,upnp:album'
_NS = {
    'didl': 'urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'upnp': 'urn:schemas-upnp-org:metadata-1-0/upnp/',
}
_DEVICE_NS = '{urn:schemas-upnp-org:device-1-0}'
SSDP_GROUP = ('239.255.255.250', 1900)
SSDP_SEARCH_TARGET = 'urn:schemas-upnp-org:device:MediaServer:1'
_PAGE_SIZE = 500
# references to, and raw occurrences of, characters XML 1.0 forbids; some servers emit them in titles
_FORBIDDEN_XML = re.compile(r'&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));|[\x00-\x08\x0b\x0c\x0e-\x1f]')
_MAX_RESULTS = 1000


class MediaServerError(Exception):
    """The media server could not be reached or rejected a request"""


class MediaServerRef(NamedTuple):
    """A resolved media server: its friendlyName (the device's layer-0 entry) and ContentDirectory control URL"""

    friendly_name: str
    control_url: str


def ssdp_locations(timeout: float = 2.0, target: tuple[str, int] = SSDP_GROUP) -> list[str]:
    """return the description URLs of the media servers answering an SSDP search within timeout seconds"""
    request = (
        'M-SEARCH * HTTP/1.1\r\n'
        f'HOST: {target[0]}:{target[1]}\r\n'
        'MAN: "ssdp:discover"\r\n'
        f'MX: {max(1, int(timeout))}\r\n'
        f'ST: {SSDP_SEARCH_TARGET}\r\n\r\n'
    )
    locations: list[str] = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(request.encode(), target)
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            sock.settimeout(remaining)
            try:
                data, _ = sock.recvfrom(4096)
            except OSError:
                break
            for line in data.decode(errors='replace').splitlines():
                name, _, value = line.partition(':')
                if name.strip().upper() == 'LOCATION' and value.strip() not in locations:
                    locations.append(value.strip())
    return locations


def describe_server(description_url: str, timeout: float = 5) -> MediaServerRef:
    """read a UPnP device description and return the server's friendlyName and ContentDirectory control URL"""
    try:
        response = requests.get(description_url, timeout=timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except (requests.RequestException, ET.ParseError) as e:
        raise MediaServerError(f'cannot read device description {description_url}: {e}') from e
    name = root.findtext(f'.//{_DEVICE_NS}friendlyName')
    for service in root.iter(f'{_DEVICE_NS}service'):
        if (service.findtext(f'{_DEVICE_NS}serviceType') or '').startswith(
            'urn:schemas-upnp-org:service:ContentDirectory:'
        ):
            control = service.findtext(f'{_DEVICE_NS}controlURL')
            if name and control:
                return MediaServerRef(name, urljoin(description_url, control))
    raise MediaServerError(f'{description_url} offers no ContentDirectory service')


def resolve_server(setting: str, locations: Callable[[], list[str]] = ssdp_locations) -> MediaServerRef:
    """
    return the media server named by setting: a device description URL, or a friendlyName

    A friendlyName (compared case-insensitively) is looked up among the servers
    that answer an SSDP search.
    """
    if setting.lower().startswith(('http://', 'https://')):
        return describe_server(setting)
    for location in locations():
        try:
            server = describe_server(location)
        except MediaServerError:
            continue
        if server.friendly_name.casefold() == setting.casefold():
            return server
    raise MediaServerError(f'no media server named {setting!r} found')


class CdsObject(NamedTuple):
    """One container or item of the server's tree"""

    id: str
    parent_id: str
    title: str
    upnp_class: str
    album: str


class CdsPage(NamedTuple):
    """One page of Browse/Search results and the total number of matches"""

    objects: list[CdsObject]
    total: int


class CdsClient:
    """SOAP access to one server's ContentDirectory service"""

    def __init__(self, control_url: str, timeout: float = 10):
        self.control_url = control_url
        self.timeout = timeout

    def search(self, criteria: str, start: int = 0, count: int = _PAGE_SIZE) -> CdsPage:
        """run a Search below the root container"""
        return self._call(
            'Search',
            [('ContainerID', '0'), ('SearchCriteria', criteria), ('Filter', _FILTER)] + self._window(start, count),
        )

    def children(self, object_id: str, start: int = 0, count: int = _PAGE_SIZE) -> CdsPage:
        """list the direct children of a container in the server's own order"""
        return self._call(
            'Browse',
            [('ObjectID', object_id), ('BrowseFlag', 'BrowseDirectChildren'), ('Filter', _FILTER)]
            + self._window(start, count),
        )

    def metadata(self, object_id: str) -> CdsObject | None:
        """return the object itself, or None if the server does not know it"""
        page = self._call(
            'Browse',
            [('ObjectID', object_id), ('BrowseFlag', 'BrowseMetadata'), ('Filter', _FILTER)] + self._window(0, 1),
        )
        return page.objects[0] if page.objects else None

    @staticmethod
    def _window(start: int, count: int) -> list[tuple[str, str]]:
        return [('StartingIndex', str(start)), ('RequestedCount', str(count)), ('SortCriteria', '')]

    def _call(self, action: str, args: list[tuple[str, str]]) -> CdsPage:
        """send one SOAP action and parse the DIDL-Lite result"""
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
            's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
            f'<u:{action} xmlns:u="{CDS_SERVICE}">'
            + ''.join(f'<{name}>{escape(value)}</{name}>' for name, value in args)
            + f'</u:{action}></s:Body></s:Envelope>'
        )
        headers = {'Content-Type': 'text/xml; charset="utf-8"', 'SOAPACTION': f'"{CDS_SERVICE}#{action}"'}
        try:
            response = requests.post(self.control_url, data=body.encode(), headers=headers, timeout=self.timeout)
            response.raise_for_status()
            fields = {el.tag.rpartition('}')[2]: el.text or '' for el in ET.fromstring(response.text).iter()}
            return CdsPage(self._parse_didl(fields['Result']), int(fields['TotalMatches']))
        except (requests.RequestException, ET.ParseError, KeyError, ValueError) as e:
            raise MediaServerError(f'{action} on {self.control_url} failed: {e}') from e

    @staticmethod
    def _strip_forbidden(match: re.Match) -> str:
        """replacement for _FORBIDDEN_XML matches: character references to allowed characters stay"""
        if match.group(0)[0] != '&':
            return ''
        code = int(match.group(1), 16) if match.group(1) else int(match.group(2))
        allowed = (
            code in (0x9, 0xA, 0xD) or 0x20 <= code <= 0xD7FF or 0xE000 <= code <= 0xFFFD or 0x10000 <= code <= 0x10FFFF
        )
        return match.group(0) if allowed else ''

    @classmethod
    def _parse_didl(cls, didl: str) -> list[CdsObject]:
        didl = _FORBIDDEN_XML.sub(cls._strip_forbidden, didl)
        return [
            CdsObject(
                node.get('id', ''),
                node.get('parentID', ''),
                node.findtext('dc:title', '', _NS),
                node.findtext('upnp:class', '', _NS),
                node.findtext('upnp:album', '', _NS),
            )
            for node in ET.fromstring(didl)
        ]


def _quote(term: str) -> str:
    """return term as a quoted SearchCriteria string value"""
    return '"' + term.replace('\\', '\\\\').replace('"', '\\"') + '"'


class CdsSearchFinder:
    """Finds candidates on a media server with Search() and resolves them to replayable hits"""

    def __init__(self, server: MediaServerRef, client: CdsClient):
        self.server = server
        self.client = client

    def find(self, query: SearchQuery) -> list[Candidate]:
        """return the server's matches for query, best first"""
        candidates: list[Candidate] = []
        if query.target in (SearchTarget.ANY, SearchTarget.ALBUM):
            candidates += self._search(HitKind.ALBUM, f'upnp:class = {_quote(ALBUM_CLASS)}', query)
        if query.target in (SearchTarget.ANY, SearchTarget.TRACK):
            candidates += self._search(HitKind.TRACK, f'upnp:class derivedfrom {_quote(AUDIO_CLASS)}', query)
        return rank(query, candidates)

    def _search(self, kind: HitKind, class_clause: str, query: SearchQuery) -> list[Candidate]:
        criteria = ' and '.join([class_clause] + [f'dc:title contains {_quote(term)}' for term in query.terms])
        found: list[Candidate] = []
        while len(found) < _MAX_RESULTS:
            page = self.client.search(criteria, start=len(found))
            if not page.objects:
                break
            found += [Candidate(kind, obj.title, obj.album or obj.title, obj.id) for obj in page.objects]
            if len(found) >= page.total:
                break
        return found

    def resolve(self, candidate: Candidate) -> Hit | None:
        """
        return the replayable hit for candidate, or None if its album container cannot be found

        A track is replayed through its album container: tracks found by Search
        sit in the flat all-tracks view, which is far too long to scan on the
        device. The path steps carry the position the server lists each entry at,
        which the device lists identically.
        """
        track_title = None
        if candidate.kind is HitKind.ALBUM:
            container = self.client.metadata(candidate.ref)
        else:
            container = self._album_container(candidate)
            track_title = candidate.title
        if container is None:
            return None

        chain = []
        node: CdsObject | None = container
        while node is not None and node.id != ROOT_ID:
            chain.insert(0, node)
            node = self.client.metadata(node.parent_id)

        steps = [PathStep(self.server.friendly_name, None)]
        steps += [
            PathStep(obj.title, self._position(obj.parent_id, lambda child, obj=obj: child.id == obj.id))
            for obj in chain
        ]
        if track_title is not None:
            position = self._position(container.id, lambda child: child.title.casefold() == track_title.casefold())
            steps.append(PathStep(track_title, position))
        return Hit(candidate.kind, candidate.title, candidate.album, tuple(steps))

    def _album_container(self, track: Candidate) -> CdsObject | None:
        """return the album container named after track's album that lists the track"""
        for album in self.client.search(
            f'upnp:class = {_quote(ALBUM_CLASS)} and dc:title = {_quote(track.album)}'
        ).objects:
            if self._position(album.id, lambda child: child.title.casefold() == track.title.casefold()) is not None:
                return album
        return None

    def _position(self, parent_id: str, wanted: Callable[[CdsObject], bool]) -> int | None:
        """return the position of the first child of parent_id satisfying wanted, or None"""
        start = 0
        while True:
            page = self.client.children(parent_id, start=start)
            for offset, child in enumerate(page.objects):
                if wanted(child):
                    return start + offset
            start += len(page.objects)
            if not page.objects or start >= page.total:
                return None
