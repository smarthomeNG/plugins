import datetime
import ipaddress
import logging
import ssl

import httpx2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from plugins.mcp.clients import ClientRegistry
from plugins.mcp.logs import LogReader
from plugins.mcp.server import create_mcp_server
from plugins.mcp.transport import McpHttpServer, TransportSettings
from plugins.mcp.types import Entitlement
from tests.mock.core import MockSmartHome

from .support import StaticSource

LOCAL_TOKEN = 'local-token-0123456789'
DESKTOP_TOKEN = 'desktop-token-0123456789'
LOCAL = Entitlement('local', 'none', False, frozenset(), 30)
PING = {'jsonrpc': '2.0', 'id': 1, 'method': 'ping'}
HEADERS = {'Accept': 'application/json, text/event-stream', 'Content-Type': 'application/json'}


def start(items, settings, clients=None):
    registry = ClientRegistry.build(LOCAL_TOKEN, LOCAL, clients or {})
    mcp_server = create_mcp_server(items, registry, StaticSource(), LogReader('/nonexistent'))
    server = McpHttpServer(mcp_server, registry, '127.0.0.1', 0, settings)
    server.start()
    return server


@pytest.fixture
def items():
    """The item tree; built in a fixture of its own because creating the mock reconfigures logging."""
    sh = MockSmartHome()
    assert sh.items is not None
    return sh.items


@pytest.fixture
def started(items):
    servers = []

    def factory(settings=TransportSettings(), clients=None):
        servers.append(start(items, settings, clients))
        return servers[-1]

    yield factory
    for server in servers:
        server.stop()


def request(server, token, headers, scheme='http', verify: bool | ssl.SSLContext = True):
    return httpx2.post(
        f'{scheme}://127.0.0.1:{server.port}/mcp',
        json=PING,
        headers={'Authorization': f'Bearer {token}', **HEADERS, **headers},
        verify=verify,
    )


def ping(server, token=LOCAL_TOKEN, scheme='http', verify: bool | ssl.SSLContext = True, **headers: str):
    return request(server, token, headers, scheme, verify)


class TestHostAndOrigin:
    def test_without_settings_the_loopback_defaults_apply(self, started):
        server = started()
        assert ping(server).status_code == 200
        assert ping(server, Host='shng.example:8765').status_code == 421

    def test_a_configured_host_is_accepted_next_to_loopback(self, started):
        server = started(TransportSettings(allowed_hosts=('shng.example:*',)))
        assert ping(server, Host='shng.example:8765').status_code == 200
        assert ping(server).status_code == 200
        assert ping(server, Host='evil.example:8765').status_code == 421

    def test_a_browser_origin_must_be_configured(self, started):
        server = started(TransportSettings(allowed_hosts=('shng.example:*',), allowed_origins=('https://app.example',)))
        assert ping(server, Origin='https://app.example').status_code == 200
        assert ping(server, Origin='https://evil.example').status_code == 403
        assert ping(server).status_code == 200


def certificate(tmp_path):
    """Write a self-signed certificate for 127.0.0.1 and return the file paths of certificate and key."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, '127.0.0.1')])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / 'cert.pem', tmp_path / 'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
        )
    )
    return str(cert_path), str(key_path)


class TestTls:
    def test_the_server_speaks_https_with_the_configured_certificate(self, started, tmp_path):
        cert, key = certificate(tmp_path)
        server = started(TransportSettings(tls_certfile=cert, tls_keyfile=key))
        assert ping(server, scheme='https', verify=ssl.create_default_context(cafile=cert)).status_code == 200

    def test_plain_http_is_not_served_when_tls_is_on(self, started, tmp_path):
        cert, key = certificate(tmp_path)
        server = started(TransportSettings(tls_certfile=cert, tls_keyfile=key))
        with pytest.raises(httpx2.HTTPError):
            ping(server)

    def test_an_unreadable_certificate_stops_the_server_from_starting(self, items, tmp_path):
        with pytest.raises(RuntimeError):
            start(
                items,
                TransportSettings(tls_certfile=str(tmp_path / 'none.pem'), tls_keyfile=str(tmp_path / 'none.key')),
            )


class TestFailedAuthentication:
    def test_failures_are_throttled_per_address_but_valid_tokens_still_pass(self, started):
        server = started(TransportSettings(auth_failure_limit=3))
        codes = [ping(server, token='wrong').status_code for _ in range(5)]
        assert codes == [401, 401, 401, 429, 429]
        assert ping(server).status_code == 200

    def test_a_throttled_answer_says_when_to_retry(self, started):
        server = started(TransportSettings(auth_failure_limit=1))
        ping(server, token='wrong')
        throttled = ping(server, token='wrong')
        assert 1 <= int(throttled.headers['retry-after']) <= 60

    def test_a_failure_is_logged_with_the_address_but_not_the_token(self, started, caplog):
        server = started()
        with caplog.at_level(logging.WARNING, logger='plugins.mcp.transport'):
            ping(server, token='guessed-token-value')
        text = ' '.join(record.getMessage() for record in caplog.records)
        assert '127.0.0.1' in text
        assert 'guessed-token-value' not in text


class TestAllowedNetworks:
    def test_a_client_outside_its_networks_is_forbidden_with_a_valid_token(self, started, caplog):
        server = started(clients={'desktop': {'token': DESKTOP_TOKEN, 'allowed_networks': ['10.0.0.0/8']}})
        with caplog.at_level(logging.WARNING, logger='plugins.mcp.transport'):
            assert ping(server, token=DESKTOP_TOKEN).status_code == 403
        assert "'desktop'" in ' '.join(record.getMessage() for record in caplog.records)

    def test_a_client_inside_its_networks_is_served(self, started):
        server = started(clients={'desktop': {'token': DESKTOP_TOKEN, 'allowed_networks': ['127.0.0.0/8']}})
        assert ping(server, token=DESKTOP_TOKEN).status_code == 200

    def test_the_forbidden_attempts_are_not_counted_as_guessing(self, started):
        server = started(
            TransportSettings(auth_failure_limit=1),
            {'desktop': {'token': DESKTOP_TOKEN, 'allowed_networks': ['10.0.0.0/8']}},
        )
        assert [ping(server, token=DESKTOP_TOKEN).status_code for _ in range(3)] == [403, 403, 403]

    def test_behind_a_local_proxy_the_forwarded_address_counts(self, started):
        server = started(clients={'desktop': {'token': DESKTOP_TOKEN, 'allowed_networks': ['10.0.0.0/8']}})
        assert request(server, DESKTOP_TOKEN, {'X-Forwarded-For': '10.1.2.3'}).status_code == 200
        assert request(server, DESKTOP_TOKEN, {'X-Forwarded-For': '203.0.113.7'}).status_code == 403
