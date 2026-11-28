"""Behaviour of ``Bark.notify()``."""

import logging

from .base import DEVICE_KEY, BarkTestBase


class TestNotify(BarkTestBase):
    def test_posts_body_to_push_endpoint(self):
        plugin = self.load_plugin()

        self.assertTrue(plugin.notify('Tor links zu'))

        self.assertEqual([push.path for push in self.server.pushes], ['/push'])
        self.assertEqual(self.payloads(), [{'device_key': DEVICE_KEY, 'body': 'Tor links zu'}])

    def test_sends_title_and_url(self):
        plugin = self.load_plugin()

        plugin.notify('Pumpe blockiert', 'Spülmaschine Fehler', 'http://visu.local/')

        self.assertEqual(
            self.payloads(),
            [
                {
                    'device_key': DEVICE_KEY,
                    'body': 'Pumpe blockiert',
                    'title': 'Spülmaschine Fehler',
                    'url': 'http://visu.local/',
                }
            ],
        )

    def test_server_url_with_trailing_slash(self):
        plugin = self.load_plugin(server_url=self.server.url + '/')

        plugin.notify('text')

        self.assertEqual([push.path for push in self.server.pushes], ['/push'])

    def test_rejected_push_returns_false_and_warns_without_device_key(self):
        plugin = self.load_plugin()
        self.server.status = 400

        with self.assertLogs(plugin.logger.logger, logging.WARNING) as logs:
            self.assertFalse(plugin.notify('text'))

        self.assertIn('400', logs.output[0])
        self.assertNotIn(DEVICE_KEY, ''.join(logs.output))

    def test_unreachable_server_returns_false(self):
        # port 1 on the loopback interface has no listener
        plugin = self.load_plugin(server_url='http://127.0.0.1:1')

        with self.assertLogs(plugin.logger.logger, logging.WARNING):
            self.assertFalse(plugin.notify('text'))

    def test_server_url_without_scheme_returns_false(self):
        plugin = self.load_plugin(server_url='bark.local')

        with self.assertLogs(plugin.logger.logger, logging.WARNING):
            self.assertFalse(plugin.notify('text'))

    def test_stopped_plugin_sends_nothing(self):
        plugin = self.load_plugin()
        plugin.stop()

        with self.assertLogs(plugin.logger.logger, logging.WARNING):
            self.assertFalse(plugin.notify('text'))

        self.assertEqual(self.payloads(), [])

    def test_empty_body_sends_nothing(self):
        plugin = self.load_plugin()

        with self.assertLogs(plugin.logger.logger, logging.WARNING):
            self.assertFalse(plugin.notify(''))

        self.assertEqual(self.payloads(), [])
