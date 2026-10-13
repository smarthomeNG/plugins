"""End-to-end test of the knx_cache start-up read against a fake knxd speaking the eibd wire protocol."""

import logging
import socket
import struct
import threading
import time
import unittest

import lib.translation
from tests import common
from tests.mock.core import MockSmartHome

from plugins.knx import KNX
from plugins.knx.knxd import KNXD

SRC_PA = bytes([0x11, 0x05])  # 1.1.5
OTHER_PA = bytes([0x11, 0x09])  # 1.1.9
GA_LAMP = bytes([0x09, 0x01])  # 1/1/1
GA_SENSOR = bytes([0x09, 0x02])  # 1/1/2
RESPONSE_OFF = bytes([0x00, 0x40])
WRITE_OFF = bytes([0x00, 0x80])
RESPONSE_ON = bytes([0x00, 0x41])  # group response, value 1


class RecordCollector(logging.Handler):
    def __init__(self, records):
        super().__init__(logging.WARNING)
        self.records = records

    def emit(self, record):
        self.records.append(record)


class FakeKnxd:
    """Minimal eibd server: answers the first cache read per GA with 'no value' and every
    later one with the cached value. Without a configured group cache it rejects every request."""

    def __init__(self, cache_configured=True):
        self.cache_configured = cache_configured
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.cache_reads = 0
        self.conn = None
        self.frames = []
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _read_exactly(self, size):
        data = b''
        while len(data) < size:
            try:
                chunk = self.conn.recv(size - len(data))
            except OSError:
                return None
            if not chunk:
                return None
            data += chunk
        return data

    def _read_frame(self):
        head = self._read_exactly(2)
        if head is None:
            return None
        return self._read_exactly(struct.unpack('>H', head)[0])

    def push_telegram(self, src, dst, apci):
        """Deliver a group monitor telegram: src/dst as 2 bytes each, apci as 2 bytes"""
        self._send_frame(struct.pack('>H', KNXD.GROUP_PACKET) + src + dst + apci)

    def push_invalid_request(self):
        """Deliver an unattributed INVALID_REQUEST reject"""
        self._send_frame(struct.pack('>H', KNXD.INVALID_REQUEST))

    def _send_frame(self, body):
        self.conn.sendall(struct.pack('>H', len(body)) + body)

    def _serve(self):
        self.conn, _ = self.server.accept()
        while (frame := self._read_frame()) is not None:
            self.frames.append(frame)
            if not self.cache_configured:
                self._send_frame(struct.pack('>H', KNXD.INVALID_REQUEST))
            elif struct.unpack('>H', frame[:2])[0] == KNXD.CACHE_READ:
                self.cache_reads += 1
                reply = struct.pack('>H', KNXD.CACHE_READ) + SRC_PA + frame[2:4]
                if self.cache_reads > 1:
                    reply += RESPONSE_ON
                self._send_frame(reply)

    def close(self):
        self.server.close()
        if self.conn:
            self.conn.close()


def wait_for(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


class TestKnxCacheRetry(unittest.TestCase):
    def start_plugin(self, cache_configured=True):
        self.knxd = FakeKnxd(cache_configured)
        self.addCleanup(self.knxd.close)

        self.sh = MockSmartHome()
        self.sh.with_items_from(common.BASE + '/plugins/knx/tests/test_items.yaml')

        KNX._parameters = {
            'provider': 'knxd',
            'host': '127.0.0.1',
            'port': self.knxd.port,
            'loglevel_knxd_cache_problems': 'WARNING',
            'time_ga': '',
            'date_ga': '',
            'send_time': 0,
            'enable_stats': False,
            'log_own_packets': False,
            'busmonitor': 'off',
            'readonly': False,
            'project_file_password': '',
            'use_project_file': False,
            'projectpath': '',
        }
        self.plugin = KNX.__new__(KNX)
        self.plugin._set_sh(self.sh)
        self.plugin._set_shortname('knx')
        self.plugin._set_plugin_dir(common.BASE + '/plugins/knx')
        lib.translation.initialize_translations(common.BASE, 'en', 'de')
        lib.translation.load_translations('plugin', 'plugins/knx', 'plugin/knx')
        self.plugin.__init__(self.sh)
        self.records = []
        self.plugin.logger.setLevel(logging.WARNING)
        self.plugin.logger.addHandler(RecordCollector(self.records))
        for item in self.sh.return_items():
            self.plugin.parse_item(item)
        self.plugin.run()
        self.addCleanup(self._shutdown_plugin)

    def _shutdown_plugin(self):
        # plugin.stop() needs Scheduler.get(), which MockScheduler lacks
        self.plugin.alive = False
        self.plugin._client.close()

    def test_unanswered_cache_read_is_repeated_and_sets_item(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))
        self.assertTrue(wait_for(lambda: self.plugin.get_unsatisfied_cache_read_ga() == ['1/1/1']))
        self.assertFalse(self.sh.lamp())

        self.plugin._cacheread_retry()

        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 2))
        self.assertTrue(wait_for(lambda: self.sh.lamp()))
        self.assertEqual(self.plugin.get_unsatisfied_cache_read_ga(), [])

    def test_rejected_cache_request_warns_about_missing_group_cache(self):
        self.start_plugin(cache_configured=False)

        self.assertTrue(wait_for(lambda: any('group cache' in r.getMessage() for r in self.records)))
        time.sleep(0.3)
        self.assertEqual(sum('group cache' in r.getMessage() for r in self.records), 1)

    def test_reject_after_cache_replies_does_not_blame_missing_group_cache(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))
        self.assertTrue(wait_for(lambda: self.plugin.get_unsatisfied_cache_read_ga() == ['1/1/1']))

        self.knxd.push_invalid_request()
        time.sleep(0.3)

        self.assertFalse(any('group cache' in r.getMessage() for r in self.records))

    def test_empty_cache_answer_is_logged_as_cache_miss(self):
        self.start_plugin()

        self.assertTrue(
            wait_for(lambda: any('cache miss' in r.getMessage() and '1/1/1' in r.getMessage() for r in self.records))
        )
        self.assertFalse(any('not enough data' in r.getMessage() for r in self.records))

    def test_truncated_group_packet_is_not_reported_as_cache_miss(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))

        self.knxd.push_telegram(SRC_PA, GA_LAMP, b'')

        self.assertTrue(wait_for(lambda: any('truncated' in r.getMessage() for r in self.records)))
        self.assertEqual(sum('cache miss' in r.getMessage() for r in self.records), 1)

    def test_cache_value_source_is_marked_initial(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))
        self.plugin._cacheread_retry()
        self.assertTrue(wait_for(lambda: self.sh.lamp()))

        self.assertEqual(self.sh.lamp.property.last_update_by, 'knx:1.1.5:ga=1/1/1:init')

    def test_live_write_after_initial_value_is_not_marked(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))
        self.plugin._cacheread_retry()
        self.assertTrue(wait_for(lambda: self.sh.lamp()))

        self.knxd.push_telegram(OTHER_PA, GA_LAMP, WRITE_OFF)

        self.assertTrue(wait_for(lambda: not self.sh.lamp()))
        self.assertEqual(self.sh.lamp.property.last_update_by, 'knx:1.1.9:ga=1/1/1')

    def test_late_bus_response_for_unanswered_cache_read_is_marked_initial(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))

        self.knxd.push_telegram(SRC_PA, GA_LAMP, RESPONSE_ON)

        self.assertTrue(wait_for(lambda: self.sh.lamp()))
        self.assertEqual(self.sh.lamp.property.last_update_by, 'knx:1.1.5:ga=1/1/1:init')

    def test_write_for_unanswered_cache_read_is_not_marked_initial(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: self.knxd.cache_reads == 1))

        self.knxd.push_telegram(OTHER_PA, GA_LAMP, bytes([0x00, 0x81]))

        self.assertTrue(wait_for(lambda: self.sh.lamp()))
        self.assertEqual(self.sh.lamp.property.last_update_by, 'knx:1.1.9:ga=1/1/1')

    def test_knx_init_response_is_marked_initial_once(self):
        self.start_plugin()
        self.assertTrue(wait_for(lambda: len(self.knxd.frames) >= 4))

        self.knxd.push_telegram(SRC_PA, GA_SENSOR, bytes([0x00, 0x41]))
        self.assertTrue(wait_for(lambda: self.sh.sensor()))
        self.assertEqual(self.sh.sensor.property.last_update_by, 'knx:1.1.5:ga=1/1/2:init')

        self.knxd.push_telegram(SRC_PA, GA_SENSOR, RESPONSE_OFF)
        self.assertTrue(wait_for(lambda: not self.sh.sensor()))
        self.assertEqual(self.sh.sensor.property.last_update_by, 'knx:1.1.5:ga=1/1/2')
