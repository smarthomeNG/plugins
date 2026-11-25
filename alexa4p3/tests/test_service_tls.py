import logging
import os
import shutil
import ssl
import subprocess
import tempfile
import unittest

from plugins.alexa4p3.service import AlexaService


@unittest.skipIf(shutil.which('openssl') is None, 'openssl command not available')
class TestAlexaServiceTls(unittest.TestCase):
    """AlexaService serves HTTPS when a certificate is configured."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix='alexa4p3_tls.')
        self.addCleanup(self._tmp.cleanup)
        self.cert = os.path.join(self._tmp.name, 'cert.pem')
        self.key = os.path.join(self._tmp.name, 'key.pem')
        subprocess.run(
            [
                'openssl',
                'req',
                '-x509',
                '-newkey',
                'rsa:2048',
                '-nodes',
                '-days',
                '1',
                '-subj',
                '/CN=localhost',
                '-keyout',
                self.key,
                '-out',
                self.cert,
            ],
            check=True,
            capture_output=True,
        )

    def test_server_socket_is_tls_wrapped(self):
        service = AlexaService(
            None,
            logging.getLogger(__name__),
            '3',
            {},
            {},
            '127.0.0.1',
            0,
            https_certfile=self.cert,
            https_keyfile=self.key,
        )
        self.addCleanup(service.server.server_close)

        self.assertIsInstance(service.server.socket, ssl.SSLSocket)
