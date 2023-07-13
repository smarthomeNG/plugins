#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
""" commands for dev epson

Most commands send a string (fixed for reading, attached data for writing)
while parsing the response works by extracting the needed string part by
regex. Some commands translate the device data into readable values via
lookups.
"""

models = {
    'ALL': ['power', 'source']
}

commands = {
    'power': {'read': True, 'write': True, 'read_cmd': 'PWR?', 'write_cmd': 'PWR {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': ['^(?:\:+)?\s?PWR=0(0|1)', '^:+WR=0(0|1)'], 'item_attrs': {'cycle': '60', 'initial': True}},
    'source': {'read': True, 'write': True, 'write_cmd': 'SOURCE {RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': 'SOURCE {LOOKUP}', 'lookup': 'SOURCE'}
}

lookups = {
    'ALL': {
        'SOURCE': {
            '11': 'Analog',
            '12': 'Digital',
            '13': 'Video',
            '14': 'YCbCr (4 Component)',
            '15': 'YPbPr (4 Component)',
            '1F': 'Auto',
            '21': 'Analog',
            '22': 'Video',
            '23': 'YCbCr',
            '24': 'YPbPr (5 Component)',
            '25': 'YPbPr',
            '2F': 'Auto',
            'A0': 'HDMI',
            '41': 'Video',
            '42': 'S-Video',
            '43': 'YCbCr',
            '44': 'YPbPr'
            }
    }
}
