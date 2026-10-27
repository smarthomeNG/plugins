import asyncio
import logging
import threading
import time
import unittest

try:
    import slixmpp
except ImportError:
    slixmpp = None

if slixmpp is not None:
    from plugins.xmpp import XMPP


def make_plugin(server=('127.0.0.1', 1)):
    """An XMPP plugin with a real slixmpp client that connects to *server* (port 1: connection refused)."""
    plugin = XMPP.__new__(XMPP)
    plugin.logger = logging.getLogger('plugins.xmpp.test')
    plugin.set_asyncio_executor_names = lambda loop: None
    plugin._setup('shng@example.invalid', 'secret', server, [], [])
    return plugin


@unittest.skipIf(slixmpp is None, 'slixmpp not installed')
class TestEventLoop(unittest.TestCase):
    def test_setup_does_not_touch_the_event_loop_of_the_calling_thread(self):
        asyncio.set_event_loop(None)
        plugin = make_plugin()
        self.addCleanup(plugin._loop.close)

        self.assertIs(plugin._loop, plugin.xmpp.loop)
        with self.assertRaises(RuntimeError):
            asyncio.get_event_loop()

    def test_run_connects_and_stop_ends_the_thread(self):
        plugin = make_plugin()
        thread = threading.Thread(target=plugin.run)
        thread.start()
        deadline = time.time() + 5
        while not plugin._loop.is_running() and time.time() < deadline:
            time.sleep(0.05)
        self.assertTrue(plugin._loop.is_running())

        plugin.stop()
        thread.join(10)

        self.assertFalse(thread.is_alive())
        self.assertFalse(plugin.is_connected())

    def test_send_is_handed_to_the_plugin_loop(self):
        plugin = make_plugin()
        self.addCleanup(plugin._loop.close)
        sent = []
        plugin.xmpp.send_message = lambda **kwargs: sent.append(kwargs)

        plugin.send('a@example.invalid', 'hello')
        plugin._loop.run_until_complete(asyncio.sleep(0))

        self.assertEqual([{'mto': 'a@example.invalid', 'mbody': 'hello', 'mtype': 'chat'}], sent)


if __name__ == '__main__':
    unittest.main()
