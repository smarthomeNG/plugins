import datetime
import unittest
from types import SimpleNamespace

from plugins.sma import SMA

CET = datetime.timezone(datetime.timedelta(hours=1))
UTC_MINUS_5 = datetime.timezone(datetime.timedelta(hours=-5))


class TestSetTime(unittest.TestCase):
    """_inv_set_time() sends the configured local UTC offset to the inverter."""

    def _sent_offset(self, tzinfo):
        plugin = SMA.__new__(SMA)
        plugin._own_bt_addr_le = bytes(6)
        plugin._inv_bt_addr_le = bytes(6)
        plugin._send_count = 0
        plugin.shtime = SimpleNamespace(
            now=lambda: datetime.datetime(2026, 1, 15, 12, 0, tzinfo=tzinfo),
            utcnow=lambda: datetime.datetime(2026, 1, 15, 11, 0, tzinfo=datetime.timezone.utc),
        )
        sent = []
        plugin._send_msg = sent.append

        plugin._inv_set_time()

        return int.from_bytes(sent[0][-12:-8], byteorder='little', signed=True)

    def test_positive_offset(self):
        self.assertEqual(3600, self._sent_offset(CET))

    def test_negative_offset(self):
        self.assertEqual(-5 * 3600, self._sent_offset(UTC_MINUS_5))
