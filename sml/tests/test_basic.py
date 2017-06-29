import common
import unittest

from plugins.sml import Sml
from plugins.sml.tests.base import TestSmlBase, SmlPacket

class TestSmlBasic(TestSmlBase):

    DEFAULT_PACKET1 = SmlPacket(
            # Data from: EHZ363Z5 / EHZ363W5
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:2.8.1*255', 'valTime': None, 'objName': b'\x01\x00\x02\x08\x01\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 27445183.5, 'value': 274451835}
            # Entry {'signature': None, 'unit': 30, 'status': 130, 'obis': '1-0:1.8.0*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x00\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 7071245.300000001, 'value': 70712453}
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:1.8.2*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x02\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 1000.0, 'value': 10000}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '129-129:199.130.5*255', 'valTime': None, 'objName': b'\x81\x81\xc7\x82\x05\xff', 'unitName': None, 'scaler': None, 'valueReal': b'\x00..\x00', 'value': b'\x00..\x00'}
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:1.8.1*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x01\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 7070245.300000001, 'value': 70702453}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '129-129:199.130.3*255', 'valTime': None, 'objName': b'\x81\x81\xc7\x82\x03\xff', 'unitName': None, 'scaler': None, 'valueReal': b'HAG', 'value': b'HAG'}
            # Entry {'signature': None, 'unit': 30, 'status': 130, 'obis': '1-0:2.8.0*255', 'valTime': None, 'objName': b'\x01\x00\x02\x08\x00\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 27446183.5, 'value': 274461835}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '1-0:0.0.9*255', 'valTime': None, 'objName': b'\x01\x00\x00\x00\t\xff', 'unitName': None, 'scaler': None, 'valueReal': b'\x06HAG\x00..\x00', 'value': b'\x06HAG\x00..\x00'}
            # Entry {'signature': None, 'unit': 27, 'status': None, 'obis': '1-0:16.7.0*255', 'valTime': None, 'objName': b'\x01\x00\x10\x07\x00\xff', 'unitName': 'W', 'scaler': 0, 'valueReal': 391, 'value': 391}
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:2.8.2*255', 'valTime': None, 'objName': b'\x01\x00\x02\x08\x02\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 1000.0, 'value': 10000}
            '1b 1b 1b 1b 01 01 01 01 76 09 00 00 00 00 0f 40 0f a9 62 01 62 00 72 63 01 01 '
            '76 01 01 09 00 00 00 00 05 15 5a 90 0b 00 48 41 47 00 00 00 00 00 00>01 01 63 '
            '23 14 00 76 09 00 00 00 00 0f 40 0f aa 62 01 62 00 72 63 07 01 77 01 0b 06 48 '
            '41 47 01 07 19 43 8c d4 07 01 00 62 0a ff ff 72 62 01 65 07 80 49 b9 7a 77 07 '
            '81 81 c7 82 03 ff 01 01 01 01 04 48 41 47 01 77 07 01 00 00 00 09 ff 01 01 01 '
            '01 0b 06 48 41 47 01 07 19 43 8c d4 01 77 07 01 00 01 08 00 ff 62 82 01 62 1e '
            '52 ff 55 04 36 fc 85 01 77 07 01 00 01 08 01 ff 01 01 62 1e 52 ff 55 04 36 d5 '
            '75 01 77 07 01 00 01 08 02 ff 01 01 62 1e 52 ff 53 27 10 01 77 07 01 00 02 08 '
            '00 ff 62 82 01 62 1e 52 ff 55 10 5b f4 8b 01 77 07 01 00 02 08 01 ff 01 01 62 '
            '1e 52 ff 55 10 5b cd 7b 01 77 07 01 00 02 08 02 ff 01 01 62 1e 52 ff 53 27 10 '
            '01 77 07 01 00 10 07 00 ff 01 01 62 1b 52 00 53 01 87 01 77 07 81 81 c7 82 05 '
            'ff 01 01 01 01 83 02<00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
            '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
            '00 00 00 00>01 01 63 4e ab 00 76 09 00 00 00 00 0f 40 0f ab 62 01 62 00 72 63 '
            '02 01 71 01 63 4e 4c 00 1b 1b 1b 1b 1a 00 18 6e',
            'hex'
        )
    DEFAULT_PACKET2 = SmlPacket(
            # Data from: EHZ363Z5 / EHZ363W5
            # Entry {'signature': None, 'unit': 30, 'status': 128, 'obis': '1-0:1.8.0*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x00\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 18121741.400000002, 'value': 181217414}
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:1.8.2*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x02\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 1000.0, 'value': 10000}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '129-129:199.130.5*255', 'valTime': None, 'objName': b'\x81\x81\xc7\x82\x05\xff', 'unitName': None, 'scaler': None, 'valueReal': b"\x00..\x00", 'value': b"\x00..\x00"}
            # Entry {'signature': None, 'unit': 30, 'status': None, 'obis': '1-0:1.8.1*255', 'valTime': None, 'objName': b'\x01\x00\x01\x08\x01\xff', 'unitName': 'Wh', 'scaler': -1, 'valueReal': 18120741.400000002, 'value': 181207414}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '129-129:199.130.3*255', 'valTime': None, 'objName': b'\x81\x81\xc7\x82\x03\xff', 'unitName': None, 'scaler': None, 'valueReal': b'HAG', 'value': b'HAG'}
            # Entry {'signature': None, 'unit': None, 'status': None, 'obis': '1-0:0.0.9*255', 'valTime': None, 'objName': b'\x01\x00\x00\x00\t\xff', 'unitName': None, 'scaler': None, 'valueReal': b'\x06HAG\x00..\x00', 'value': b'\x06HAG\x00..\x00'}
            # Entry {'signature': None, 'unit': 27, 'status': None, 'obis': '1-0:16.7.0*255', 'valTime': None, 'objName': b'\x01\x00\x10\x07\x00\xff', 'unitName': 'W', 'scaler': 0, 'valueReal': 8, 'value': 8}
            '1b 1b 1b 1b 01 01 01 01 76 09 00 00 00 00 0d f2 9d b2 62 01 62 00 72 63 01 01 '
            '76 01 01 09 00 00 00 00 04 a6 34 92 0b 06 48 41 47<01 00 00 00 00>32 01 01 63 '
            'f6 3c 00 76 09 00 00 00 00 0d f2 9d b3 62 01 62 00 72 63 07 01 77 01 0b 06 48 '
            '41 47 01 04 c5 37 5a 32 07 01 00 62 0a ff ff 72 62 01 65 08 f4 54 a4 77 77 07 '
            '81 81 c7 82 03 ff 01 01 01 01 04 48 41 47 01 77 07 01 00 00 00 09 ff 01 01 01 '
            '01 0b 06 48 41 47 01 04 c5 37 5a 32 01 77 07 01 00 01 08 00 ff 62 80 01 62 1e '
            '52 ff 55 0a cd 28 86 01 77 07 01 00 01 08 01 ff 01 01 62 1e 52 ff 55 0a cd 01 '
            '76 01 77 07 01 00 01 08 02 ff 01 01 62 1e 52 ff 53 27 10 01 77 07 01 00 10 07 '
            '00 ff 01 01 62 1b 52 00 53 00 08 01 77 07 81 81 c7 82 05 ff 01 01 01 01 83 02 '
            '<00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 '
            '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00>01 01 63 '
            'a1 b8 00 76 09 00 00 00 00 0d f2 9d b4 62 01 62 00 72 63 02 01 71 01 63 b8 47 '
            '00 00 00 00 1b 1b 1b 1b 1a 03 74 cd',
            'hex'
        )
    DEFAULT_PACKET_MISSING_END = SmlPacket(
            # Entity {'scaler': -4, 'unitName': 'Wh', 'objName': b'\x01\x00\x02\x08\x00\xff', 'status': None, 'obis': '1-0:2.8.0*255', 'value': 29803232821505, 'valTime': None, 'unit': 30, 'signature': None, 'valueReal': 2980323282.1505003}
            # Entity {'scaler': -4, 'unitName': 'Wh', 'objName': b'\x01\x00\x01\x08\x00\xff', 'status': None, 'obis': '1-0:1.8.0*255', 'value': 64963419, 'valTime': None, 'unit': 30, 'signature': None, 'valueReal': 6496.3419}
            # Entity {'scaler': None, 'unitName': None, 'objName': b'\x81\x81\xc7\x82\x03\xff', 'status': None, 'obis': '129-129:199.130.3*255', 'value': b'ESY', 'valTime': None, 'unit': None, 'signature': None, 'valueReal': b'ESY'}}
            '1b 1b 1b 1b 01 01 01 01 76 05 08 ca 78 f7 62 00 62 00 72 65 00 00 01 01 76 01 '
            '01 07 45 53 59 51 33 42 0b 06 45 53 59 01 04 c6 a1 f6 db 01 01 63 bf 6e 00 76 '
            '05 08 ca 78 f8 62 00 62 00 72 65 00 00 07 01 77 01 0b 06 45 53 59 01 04 c6 a1 '
            'f6 db 01 72 62 01 65 06 5a fc 21 79 77 07 81 81 c7 82 03 ff 01 01 01 01 04 45 '
            '53 59 01 77 07 01 00 01 08 00 ff 01 01 62 1e 52 fc 69 00 00 00 00 03 df 43 5b '
            '01 77 07 01 00 02 08 00 ff 01 01 62 1e 52 fc 69 00 00',
            'hex'
        )

    def test_read_packet(self):
        """ Test reading one complete package without data before or after.
        """
        plugin = self.plugin()
        plugin.data.add(TestSmlBasic.DEFAULT_PACKET1)
        values = plugin._refresh()
        self.assertEqual(10, len(values))
        self.assertEntry(values, '1-0:2.8.1*255', unit=30, unitname='Wh', value=274451835)
        self.assertEntry(values, '1-0:1.8.0*255', unit=30, unitname='Wh', value=70712453)
        self.assertEntry(values, '1-0:1.8.1*255', unit=30, unitname='Wh', value=70702453)
        self.assertEntry(values, '1-0:1.8.2*255', unit=30, unitname='Wh', value=10000)
        self.assertEntry(values, '129-129:199.130.3*255', value=b'HAG')
        self.assertEntry(values, '1-0:16.7.0*255', unit=27, unitname='W', value=391)
        self.assertEntry(values, '1-0:2.8.2*255', unit=30, unitname='Wh', value=10000)

    def test_read_packet_within_returns_last_values(self):
        """ Test reading package including data before and after (both only a part
            of a packet). In this case everything is tried to parse and in case a OBIS
            value occurs multiple times in the stream, only the last one will be returned
        """
        plugin = self.plugin()
        plugin.data.add(SmlPacket(TestSmlBasic.DEFAULT_PACKET1.get_data(start=200), 'byte'))
        plugin.data.add(TestSmlBasic.DEFAULT_PACKET1)
        plugin.data.add(SmlPacket(TestSmlBasic.DEFAULT_PACKET2.get_data(length=200), 'byte'))
        values = plugin._refresh()
        self.assertEqual(10, len(values))
        self.assertEntry(values, '1-0:1.8.0*255', unit=30, unitname='Wh', value=181217414)
        self.assertEntry(values, '1-0:1.8.1*255', unit=30, unitname='Wh', value=181207414)
        self.assertEntry(values, '1-0:1.8.2*255', unit=30, unitname='Wh', value=10000)
        self.assertEntry(values, '129-129:199.130.3*255', value=b'HAG')
        self.assertEntry(values, '1-0:16.7.0*255', unit=27, unitname='W', value=391)

    def test_read_packet_missing_end(self):
        plugin = self.plugin()
        plugin.data.add(TestSmlBasic.DEFAULT_PACKET_MISSING_END)
        values = plugin._refresh()
        self.assertEqual(3, len(values))
        self.assertEntry(values, '1-0:2.8.0*255', unit=30, unitname='Wh', value=29803232821505, scaler=-4)
        self.assertEntry(values, '1-0:1.8.0*255', unit=30, unitname='Wh', value=64963419, scaler=-4)
        self.assertEntry(values, '129-129:199.130.3*255', value=b'ESY')

