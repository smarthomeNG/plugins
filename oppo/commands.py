#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
""" commands for dev oppo

Most commands send a string (fixed for reading, attached data for writing)
while parsing the response works by extracting the needed string part by
regex. Some commands translate the device data into readable values via
lookups.
"""

models = {
    'ALL': ['info', 'general', 'control', 'menu'],
    'UDP-203': []
}

commands = {
    'info': {
        'time': {
            'totalelapsed': {'read': True, 'write': False, 'read_cmd': '#QEL', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QEL OK (.*)'},
            'totalremaining': {'read': True, 'write': False, 'read_cmd': '#QRE', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QRE OK (.*)'},
            'chapterelapsed': {'read': True, 'write': False, 'read_cmd': '#QCE', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QCE OK (.*)'},
            'chapterremaining': {'read': True, 'write': False, 'read_cmd': '#QCR', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QCE OK (.*)'},
            'titleelapsed': {'read': True, 'write': False, 'read_cmd': '#QTE', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QTE OK (.*)'},
            'titleremaining': {'read': True, 'write': False, 'read_cmd': '#QTR', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QTR OK (.*)'}
        },
        'audio': {
            'current': {'read': True, 'write': False, 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': [r'@QAT OK (?:[A-Z]*) (\d{1,2})/(?:\d{1,2}) (?:[A-Za-z]*)', r'@UAT (?:[A-Z]{2}) (\d{2})/(?:\d{2}) (?:[A-Z]{3}) (?:[0-7.]*)']},
            'available': {'read': True, 'write': False, 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': [r'@QAT OK (?:[A-Z]*) (?:\d{1,2})/(\d{1,2}) (?:[A-Za-z]*)', r'@UAT (?:[A-Z]{2}) (?:\d{2})/(\d{2}) (?:[A-Z]{3}) (?:[0-7.]*)']},
            'language': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': [r'@QAT OK (?:[A-Z]*) (?:\d{1,2})/(?:\d{1,2}) ([A-Za-z]*)', r'@UAT (?:[A-Z]{2}) (?:\d{2})/(?:\d{2}) ([A-Z]{3}) (?:[0-7.]*)']},
        },
        'subtitle': {
            'current': {'read': True, 'write': False, 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'@UST (\d{2})/(?:\d{2}) ([A-Z]{3})'},
            'available': {'read': True, 'write': False, 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'@UST (?:\d{2})/(\d{2}) (?:[A-Z]{3})'},
            'language': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'@UST (?:\d{2})/(?:\d{2}) ([A-Z]{3})'},
        },
        'firmware': {'read': True, 'write': False, 'read_cmd': '#QVR', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@QVR OK (.*)', 'item_attrs': {'initial': True}},
        'status': {'read': True, 'write': False, 'read_cmd': '#QPL', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': ['@QPL OK {LOOKUP}$', '@UPL {LOOKUP}$', '@OK {LOOKUP}$'], 'item_attrs': {'initial': True}, 'lookup': 'STATUS'},
        'disctype': {'read': True, 'write': False, 'read_cmd': '#QDT', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': ['@QDT (?:OK\s)?{LOOKUP}$', '@UDT {LOOKUP}$', '@OK {LOOKUP}$'], 'item_attrs': {'initial': True}, 'lookup': 'DISCTYPE'},
        'totaltracks': {'read': True, 'write': False, 'read_cmd': '#QTK', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': [r'@QTK OK (?:\d{2})/(\d{2})', r'@OK (?:\d{2})/(\d{2})', r'@UAT (?:[A-Z]{2}) (?:\d{2})/(\d{2}) (?:[A-Z]{3}) (?:[0-7.]*)'], 'item_attrs': {'initial': True}},
        'displaytype': {'read': True, 'write': True, 'write_cmd': '#STC {RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@STC OK (.*)'},
        'audiotype': {'read': True, 'write': False, 'read_cmd': '#QAT', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': ['@QAT OK {LOOKUP}', r'@UAT {LOOKUP} (?:\d{2})/(?:\d{2}) (?:[A-Z]{3}) (?:[0-7.]*)'], 'item_attrs': {'initial': True}, 'lookup': 'AUDIOTYPE'},
        'channels': {'read': True, 'write': False, 'read_cmd': '#QAT', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'@UAT (?:[A-Z]{2}) (?:\d{2})/(?:\d{2}) (?:[A-Z]{3}) ([0-7.]{3})'},
        'trackinfo': {'read': True, 'write': False, 'read_cmd': '#QTK', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': '@UTC (.*)'},
        'inputresolution': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@UVO (?:_?)([a-zA-Z0-9]*)(?:_?)(?:\s_?)(?:[a-zA-Z0-9]*)(?:_?)'},
        'outputresolution': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@UVO (?:_?)(?:[a-zA-Z0-9]*)(?:_?)(?:\s_?)([a-zA-Z0-9]*)(?:_?)'},
        'aspectratio': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@UAR {LOOKUP}$', 'lookup': 'ASPECT'},
        'U3D': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': '@U3D (2D|3D)'},
    },
    'general': {
        'verbose': {'read': True, 'write': True, 'read_cmd': '#QVM', 'write_cmd': '#SVM {VALUE}', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': ['@QVM OK (0|1|2|3)', '@SVM OK (0|1|2|3)'], 'cmd_settings': {'force_min': 1, 'force_max': 3}, 'item_attrs': {'attributes': {'cache': True, 'initial_value': 2}}},
        'hdmiresolution': {'read': True, 'write': True, 'read_cmd': '#QHD', 'write_cmd': '#SHD {RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': ['@SHD OK (.*)', '@QHD OK (.*)'], 'cmd_settings': {'valid_list': ['480I', '480P', '576I', '576P', '720P50', '720P60', '1080I50', '1080I60', '1080P24', '1080P50', '1080P60', '1080PAUTO', 'UHD24', 'UHD50', 'UHD60', 'UHD_AUTO', 'AUTO', 'Source Direct']}, 'item_attrs': {'initial': True}},
    },
    'control': {
        'power': {'read': True, 'write': True, 'read_cmd': '#QPW', 'write_cmd': '#P{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': ['@POFF OK (OFF)', '@PON OK (ON)', '@QPW OK (ON|OFF)', '@UPW (0|1)'], 'item_attrs': {'initial': True}},
        'pureaudio': {'read': True, 'write': True, 'write_cmd': '#PUR', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': '@PUR OK (ON|OFF)'},
        'playpause': {'read': True, 'write': True, 'read_cmd': '#QPL', 'write_cmd': '{VALUE}', 'item_type': 'bool', 'dev_datatype': 'playpause', 'reply_pattern': ['@PLA OK {LOOKUP}$', '@PAU OK {LOOKUP}$'], 'lookup': 'PLAY'},
        'stop': {'read': True, 'write': True, 'read_cmd': '#QPL', 'write_cmd': '#STP', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': ['@STP OK (?:(FULL\s)?){LOOKUP}$'], 'lookup': 'STOP'},
        'eject': {'read': True, 'write': True, 'write_cmd': '#EJT', 'item_type': 'bool', 'dev_datatype': 'openclose', 'reply_pattern': ['@UPL (OPEN|CLOS)', '@EJT OK (OPEN|CLOSE)'], 'item_attrs': {'enforce': True}},
        'chapter': {'read': True, 'write': True, 'read_cmd': '#QCH', 'write_cmd': '#SRH C{RAW_VALUE:03}', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': ['@SRH (OK|ER INVALID)', r'@QCH OK (\d{2})/(?:\d{2})']},
        'title': {'read': True, 'write': True, 'read_cmd': '#QTK', 'write_cmd': '#SRH T{RAW_VALUE:03}', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': [r'@QTK OK (\d{2})/(?:\d{2})', '@SRH (OK|ER INVALID)', r'@UAT (?:[A-Z]{2}) (\d{2})/(?:\d{2}) (?:[A-Z]{3}) (?:[0-7.]{3})']},
        'next': {'read': True, 'write': True, 'write_cmd': '#NXT', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@NXT (.*)'], 'item_attrs': {'enforce': True}},
        'previous': {'read': True, 'write': True, 'write_cmd': '#PRE', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@PRE (.*)'], 'item_attrs': {'enforce': True}},
        'forward': {'read': True, 'write': True, 'write_cmd': '#FWD', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@FWD (.*) 1x'], 'item_attrs': {'enforce': True}},
        'reverse': {'read': True, 'write': True, 'write_cmd': '#REV', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@REV (.*) 1x'], 'item_attrs': {'enforce': True}},
        'audio': {'read': True, 'write': True, 'write_cmd': '#AUD', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': '@AUD (.*)', 'item_attrs': {'enforce': True}},
        'subtitle': {'read': True, 'write': True, 'write_cmd': '#SUB', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': '@SUB (.*)', 'item_attrs': {'enforce': True}},
        'repeat': {'read': True, 'write': True, 'write_cmd': '#RPT', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': ['@RPT OK {LOOKUP}$'], 'lookup': 'REPEAT'},
        'input': {'read': True, 'write': True, 'write_cmd': '#SRC\r#NU{VALUE}', 'item_type': 'num', 'dev_datatype': 'ok', 'reply_pattern': ['@SRC (.*)']},
    },
    'menu': {
        'home': {'read': True, 'write': True, 'write_cmd': '#HOM', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': '@HOM (.*)', 'item_attrs': {'enforce': True}},
        'setup': {'read': True, 'write': True, 'write_cmd': '#SET', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@SET (.*)'], 'item_attrs': {'enforce': True}},
        'option': {'read': True, 'write': True, 'write_cmd': '#OPT', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@OPT (.*)'], 'item_attrs': {'enforce': True}},
        'info': {'read': True, 'write': True, 'write_cmd': '#INH', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@INH (.*)'], 'item_attrs': {'enforce': True}},
        'popup': {'read': True, 'write': True, 'write_cmd': '#MNU', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@MNU (.*)'], 'item_attrs': {'enforce': True}},
        'top': {'read': True, 'write': True, 'write_cmd': '#TTL', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@TTL (.*)'], 'item_attrs': {'enforce': True}},
        'osd': {'read': True, 'write': True, 'write_cmd': '#OSD', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@OSD (.*)'], 'item_attrs': {'enforce': True}},
        'pageup': {'read': True, 'write': True, 'write_cmd': '#PUP', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@PUP (.*)'], 'item_attrs': {'enforce': True}},
        'pagedown': {'read': True, 'write': True, 'write_cmd': '#PDN', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@PDN (.*)'], 'item_attrs': {'enforce': True}},
        'up': {'read': True, 'write': True, 'write_cmd': '#NUP', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@NUP (.*)'], 'item_attrs': {'enforce': True}},
        'down': {'read': True, 'write': True, 'write_cmd': '#NDN', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@NDN (.*)'], 'item_attrs': {'enforce': True}},
        'left': {'read': True, 'write': True, 'write_cmd': '#NLT', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@NLT (.*)'], 'item_attrs': {'enforce': True}},
        'right': {'read': True, 'write': True, 'write_cmd': '#NRT', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@NRT (.*)'], 'item_attrs': {'enforce': True}},
        'select': {'read': True, 'write': True, 'write_cmd': '#SEL', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@SEL (.*)'], 'item_attrs': {'enforce': True}},
        'back': {'read': True, 'write': True, 'write_cmd': '#RET', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@RET (.*)'], 'item_attrs': {'enforce': True}},
        'red': {'read': True, 'write': True, 'write_cmd': '#RED', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@RED (.*)'], 'item_attrs': {'enforce': True}},
        'green': {'read': True, 'write': True, 'write_cmd': '#GRN', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@GRN (.*)'], 'item_attrs': {'enforce': True}},
        'blue': {'read': True, 'write': True, 'write_cmd': '#BLU', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@BLU (.*)'], 'item_attrs': {'enforce': True}},
        'yellow': {'read': True, 'write': True, 'write_cmd': '#YLW', 'item_type': 'bool', 'dev_datatype': 'ok', 'reply_pattern': ['@YLW (.*)'], 'item_attrs': {'enforce': True}},
    }
}

lookups = {
    'ALL': {
        'STATUS': {
            'PLAY': 'PLAY',
            'PAUS': 'PAUSE',
            'PAUSE': 'PAUSE',
            'STOP': 'STOP',
            'DISC': 'No Disc',
            'LOAD': 'Loading Disc',
            'OPEN': 'Tray Open',
            'CLOS': 'Tray Close',
            'STPF': 'Forward Frame-by-Frame',
            'STPR': 'Reverse Frame-by-Frame',
            'HOME': 'Home Menu',
            'MCTR': 'Media Center',
            'MEDIA CENTER': 'Media Center',
            'SCSV': 'Screen Saver',
            'SCREEN SAVER': 'Screen Saver',
            'DISC MENU': 'Disc Menu',
            'MENU': 'Disc Menu'
        },
        'PLAY': {
            'PLAY': True,
            'PAUS': False,
            'PAUSE': False,
            'STOP': False
        },
        'STOP': {
            'PLAY': False,
            'PAUS': False,
            'PAUSE': False,
            'STOP': True
        },
        'REPEAT': {
            '0': 'OFF',
            '1': 'Repeat Chapter',
            '2': 'Repeat Title'
        },
        'ASPECT': {
            '16WW': '16:9 Wide',
            '16AW': '16:9 Auto Wide',
            '16A4': '16:9 Auto Wide, currently 4:3',
            '21M0': '21:9 Movable, currently full screen mode',
            '21M1': '21:9 Movable, currently playing 16:9 or 4:3 content',
            '21M2': '21:9 Movable, currently playing 21:9 content',
            '21F0': '21:9 Fixed, currently full screen mode',
            '21F1': '21:9 Fixed, currently playing 16:9 or 4:3 content',
            '21F2': '21:9 Fixed, currently playing 21:9 content',
            '21C0': '21:9 Cropped, currently full screen mode',
            '21C1': '21:9 Cropped, currently playing 16:9 or 4:3 content',
            '21C2': '21:9 Cropped, currently playing 21:9 content'
        },
        'AUDIOTYPE': {
            'PCM 44.1/16': 'PCM 44.1/16',
            'PCM': 'PCM',
            'DD': 'Dolby Digital',
            'DP': 'Dolby Digital Plus',
            'DT': 'Dolby TrueHD',
            'TS': 'DTS',
            'TH': 'DTS-HD High Resolution',
            'TM': 'DTS-HD Master Audio',
            'PC': 'LPCM',
            'MP': 'MPEG Audio',
            'CD': 'CD Audio',
            'UN': 'Unknown',
        },
        'DISCTYPE': {
            'UHBD': 'Ultra HD Blu-ray Disc',
            'BDMV': 'Blu-ray Disc',
            'BD-MV': 'Blu-ray Disc',
            'DVDV': 'DVD-Video',
            'DVDA': 'DVD-Audio',
            'SACD': 'SACD',
            'CDDA': 'Audio-CD',
            'DATA': 'Data Disc',
            'VCD2': 'VCD 2.0',
            'SVCD': 'SVCD',
            'NO-DISC': 'No Disc',
            'UNKW': 'Unknown',
        },
    }
}
