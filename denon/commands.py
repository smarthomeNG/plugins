#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
""" commands for dev pioneer

Most commands send a string (fixed for reading, attached data for writing)
while parsing the response works by extracting the needed string part by
regex. Some commands translate the device data into readable values via
lookups.
"""

models = {
    'ALL': ['general.custom_inputnames', 'general.power', 'general.setupmenu', 'general.soundmode', 'general.inputsignal', 'general.inputrate', 'general.inputformat', 'general.inputresolution', 'general.outputresolution', 'general.ecomode',
            'tuner.preset', 'tuner.presetup', 'tuner.presetdown', 'tuner.frequency', 'tuner.frequencyup', 'tuner.frequencydown', 'tuner.band', 'tuner.tuningmode',
            'zone1.control',
            'zone1.settings.sound.general.audioinput', 'zone1.settings.sound.general.cinema_eq', 'zone1.settings.sound.general.hdmiaudioout', 'zone1.settings.sound.general.dynamicrange', 'zone1.settings.sound.general.subwoofertoggle', 'zone1.settings.sound.general.subwoofer', 'zone1.settings.sound.general.subwooferup', 'zone1.settings.sound.general.subwooferdown', 'zone1.settings.sound.general.lfe', 'zone1.settings.sound.general.lfeup', 'zone1.settings.sound.general.lfedown', 'zone1.settings.sound.tone_control',
            'zone1.settings.sound.channel_level.front_left', 'zone1.settings.sound.channel_level.front_right', 'zone1.settings.sound.channel_level.front_height_left', 'zone1.settings.sound.channel_level.front_height_right', 'zone1.settings.sound.channel_level.front_center', 'zone1.settings.sound.channel_level.surround_left', 'zone1.settings.sound.channel_level.surround_right', 'zone1.settings.sound.channel_level.surroundback_left', 'zone1.settings.sound.channel_level.surroundback_right', 'zone1.settings.sound.channel_level.rear_height_left', 'zone1.settings.sound.channel_level.rear_height_right', 'zone1.settings.sound.channel_level.subwoofer',
            'zone2.control', 'zone2.settings.sound.general.hdmiout'],
    'AVR-X6300H': ['info', 'tuner.hd', 'zone1.settings.sound.channel_level.subwoofer2', 'zone1.settings.sound.general.speakersetup', 'zone1.settings.sound.general.dialogenhance',
                   'zone1.settings.video',
                   'zone2.settings.sound.tone_control', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.general.HPF',
                   'zone3'],
    'AVR-X4300H': ['zone1.settings.sound.channel_level.subwoofer2', 'zone1.settings.video', 'zone1.settings.sound.general.dialogtoggle', 'zone1.settings.sound.general.dialog', 'zone1.settings.sound.general.dialogup', 'zone1.settings.sound.general.dialogdown', 'zone1.settings.sound.general.speakersetup',
                   'zone2.settings.sound.tone_control', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.general.HPF',
                   'zone3'],
    'AVR-X3300W': ['tuner.title', 'tuner.album', 'tuner.artist', 'general.display',
                   'zone1.settings.sound.channel_level.subwoofer2', 'zone1.settings.video.aspectratio', 'zone1.settings.video.hdmiresolution', 'zone1.settings.video.videoresolution', 'zone1.settings.video.videoinput', 'zone1.settings.video.pictureenhancer', 'zone1.settings.video.videoprocessingmode',
                   'zone1.settings.sound.general.dialogtoggle', 'zone1.settings.sound.general.dialog', 'zone1.settings.sound.general.dialogup', 'zone1.settings.sound.general.dialogdown', 'zone2.settings.sound.tone_control', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.general.HPF'],
    'AVR-X2300W': ['tuner.title', 'tuner.album', 'tuner.artist', 'general.display',
                   'zone1.settings.video', 'zone1.settings.sound.general.dialogtoggle', 'zone1.settings.sound.general.dialog', 'zone1.settings.sound.general.dialogup', 'zone1.settings.sound.general.dialogdown',
                   'zone2.settings.sound.channel_level'],
    'AVR-X1300W': ['tuner.title', 'tuner.album', 'tuner.artist', 'general.display',
                   'zone1.settings.sound.general.dialogtoggle', 'zone1.settings.sound.general.dialog', 'zone1.settings.sound.general.dialogup', 'zone1.settings.sound.general.dialogdown']
}

commands = {
    'info': {
        'fullmodel': {'read': True, 'write': False, 'read_cmd': 'NSFRN ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'NSFRN\s(.*)', 'item_attrs': {'initial': True}},
        'model': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'VIALL(AVR.*)', 'item_attrs': {'initial': True}},
        'serialnumber': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLS/N\.(.*)'},
        'main': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLMAIN:(.*)'},
        'mainfbl': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLMAINFBL:(.*)'},
        'dsp1': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLDSP1:(.*)'},
        'dsp2': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLDSP2:(.*)'},
        'dsp3': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLDSP3:(.*)'},
        'dsp4': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLDSP4:(.*)'},
        'apld': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLAPLD:(.*)'},
        'vpld': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLVPLD:(.*)'},
        'guidat': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLGUIDAT:(.*)'},
        'heosversion': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLHEOSVER:(.*)'},
        'heosbuild': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLHEOSBLD:(.*)'},
        'heosmod': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLHEOSMOD:(.*)'},
        'heoscnf': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLHEOSCNF:(.*)'},
        'heoslanguage': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLHEOSLCL:(.*)'},
        'mac': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLMAC:(.*)'},
        'wifimac': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLWIFIMAC:(.*)'},
        'btmac': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLBTMAC:(.*)'},
        'audyif': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLAUDYIF:(.*)'},
        'productid': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLPRODUCTID:(.*)'},
        'packageid': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'VIALLPACKAGEID:(.*)'},
        'cmp': {'read': True, 'write': False, 'read_cmd': 'VIALL?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'VIALLCMP:(.*)'},
        'region': {'read': True, 'write': False, 'read_cmd': 'SYMODTUN ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'SYMODTUN\s(.*)', 'item_attrs': {'initial': True}},
    },
    'general': {
        'custom_inputnames': {'read': True, 'write': False, 'read_cmd': 'SSFUN ?', 'item_type': 'dict', 'dev_datatype': 'str', 'reply_pattern': 'SSFUN(.*)', 'item_attrs': {'item_template': 'custom_inputnames'}},
        'power': {'read': True, 'write': True, 'read_cmd': 'PW?', 'write_cmd': 'PW{VALUE}', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': 'PW{LOOKUP}', 'lookup': 'POWER'},
        'setupmenu': {'read': True, 'write': True, 'read_cmd': 'MNMEN?', 'write_cmd': 'MNMEN {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'MNMEN (ON|OFF)'},
        'display': {'read': True, 'write': False, 'read_cmd': 'NSE', 'item_type': 'str', 'dev_datatype': 'DenonDisplay', 'reply_pattern': 'NSE(.*)'},
        'soundmode': {'read': True, 'write': False, 'read_cmd': 'SSSMG ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'SSSMG {LOOKUP}', 'lookup': 'SOUNDMODE', 'item_attrs': {'initial': True}},
        'allzonestereo': {'read': True, 'write': False, 'read_cmd': 'MNZST?', 'write_cmd': 'MNZST {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'MNZST {ON|OFF}', 'item_attrs': {'initial': True}},
        'inputsignal': {'read': True, 'write': False, 'read_cmd': 'SSINFAISSIG ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'SSINFAISSIG {LOOKUP}', 'lookup': 'INPUTSIGNAL', 'item_attrs': {'initial': True}},
        'inputrate': {'read': True, 'write': False, 'read_cmd': 'SSINFAISFSV ?', 'item_type': 'num', 'dev_datatype': 'convert0', 'reply_pattern': r'SSINFAISFSV (\d{2,3}|NON)', 'item_attrs': {'initial': True}},
        'inputformat': {'read': True, 'write': False, 'read_cmd': 'SSINFAISFOR ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SSINFAISFOR (.*)', 'item_attrs': {'initial': True}},
        'inputresolution': {'read': True, 'write': False, 'read_cmd': 'SSINFSIGRES ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SSINFSIGRES I(.*)', 'item_attrs': {'initial': True}},
        'outputresolution': {'read': True, 'write': False, 'read_cmd': 'SSINFSIGRES ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SSINFSIGRES O(.*)', 'item_attrs': {'read_group_levels': 0}},
        'ecomode': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['ON', 'OFF', 'AUTO']}, 'read_cmd': 'ECO?', 'write_cmd': 'ECO{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'ECO{VALID_LIST_CI}'},
    },
    'tuner': {
        'title': {'read': True, 'write': False, 'read_cmd': 'NSE', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'NSE1(.*)', 'item_attrs': {'initial': True}},
        'album': {'read': True, 'write': False, 'read_cmd': 'NSE', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'NSE4(.*)', 'item_attrs': {'read_group_levels': 0}},
        'artist': {'read': True, 'write': False, 'read_cmd': 'NSE', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'NSE2(.*)', 'item_attrs': {'read_group_levels': 0}},
        'preset': {'read': True, 'write': True, 'read_cmd': 'TPAN?', 'item_type': 'num', 'write_cmd': 'TPAN{RAW_VALUE:02}', 'dev_datatype': 'convert0', 'reply_pattern': r'TPAN(\d{2}|OFF)', 'item_attrs': {'initial': True}},
        'presetup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPANUP', 'dev_datatype': 'raw'},
        'presetdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPANDOWN', 'dev_datatype': 'raw'},
        'frequency': {'read': True, 'write': True, 'read_cmd': 'TFAN?', 'item_type': 'num', 'write_cmd': 'TFAN{RAW_VALUE:06}', 'dev_datatype': 'num', 'reply_pattern': r'TFAN(\d{6})', 'item_attrs': {'initial': True}},
        'frequencyup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TFANUP', 'dev_datatype': 'raw'},
        'frequencydown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TFANDOWN', 'dev_datatype': 'raw'},
        'band': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['AM', 'FM']}, 'read_cmd': 'TMAN?', 'item_type': 'str', 'write_cmd': 'TMAN{RAW_VALUE_UPPER}', 'dev_datatype': 'raw', 'reply_pattern': r'TMAN{VALID_LIST_CI}', 'item_attrs': {'initial': True}},
        'tuningmode': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['AUTO', 'MANUAL']}, 'read_cmd': 'TMAN?', 'item_type': 'str', 'write_cmd': 'TMAN{RAW_VALUE_UPPER}', 'dev_datatype': 'raw', 'reply_pattern': r'TMAN{VALID_LIST_CI}'},
        'hd': {
            'channel': {'read': True, 'write': True, 'read_cmd': 'TFHD?', 'item_type': 'num', 'write_cmd': 'TFHD{RAW_VALUE:06}', 'dev_datatype': 'num', 'reply_pattern': r'TFHD(\d{6})', 'item_attrs': {'initial': True}},
            'channelup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TFHDUP', 'dev_datatype': 'raw'},
            'channeldown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TFHDDOWN', 'dev_datatype': 'raw'},
            'multicastchannel': {'read': True, 'write': True, 'read_cmd': 'TFHD?', 'item_type': 'num', 'write_cmd': 'TFHDMC{RAW_VALUE:01}', 'dev_datatype': 'num', 'reply_pattern': r'TFHDMC(\d{1})'},
            'presetmemory': {'read': True, 'write': True, 'item_type': 'num', 'write_cmd': 'TPHDMEM{RAW_VALUE:02}', 'dev_datatype': 'convert0', 'reply_pattern': r'TPHDMEM(\d{2}|OFF)'},
            'preset': {'read': True, 'write': True, 'read_cmd': 'TPHD?', 'item_type': 'num', 'write_cmd': 'TPHD{RAW_VALUE:02}', 'dev_datatype': 'convert0', 'reply_pattern': r'TPHD(\d{2}|OFF)'},
            'presetup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPHDUP', 'dev_datatype': 'raw'},
            'presetdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPHDDOWN', 'dev_datatype': 'raw'},
            'band': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['AM', 'FM', 'AUTO', 'MANUAL', 'AUTOHD', 'ANAAUTO', 'ANAMANU']}, 'read_cmd': 'TMHD?', 'item_type': 'str', 'write_cmd': 'TMHD{RAW_VALUE_UPPER}', 'dev_datatype': 'num', 'reply_pattern': r'TMHD{VALID_LIST_CI}', 'item_attrs': {'initial': True}}
        }

    },
    'zone1': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': 'ZM?', 'write_cmd': 'ZM{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'ZM(ON|OFF)', 'item_attrs': {'initial': True}},
            'mute': {'read': True, 'write': True, 'read_cmd': 'MU?', 'write_cmd': 'MU{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'MU(ON|OFF)', 'item_attrs': {'initial': True}},
            'volume': {'read': True, 'write': True, 'read_cmd': 'MV?', 'write_cmd': 'MV{VALUE}', 'item_type': 'num', 'dev_datatype': 'DenonVol', 'reply_pattern': r'MV(\d{2,3})', 'cmd_settings': {'force_min': 0.0, 'valid_max': 98.0}, 'item_attrs': {'initial': True}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'MVUP', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'MVDOWN', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'volumemax': {'opcode': '{VALUE}', 'read': True, 'write': False, 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'MVMAX (\d{2,3})', 'item_attrs': {'initial': True}},
            'input': {'read': True, 'write': True, 'read_cmd': 'SI?', 'write_cmd': 'SI{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SI{LOOKUP}', 'lookup': 'INPUT', 'item_attrs': {'item_template': 'input', 'initial': True}},
            'listeningmode': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['MOVIE', 'MUSIC', 'GAME', 'DIRECT', 'PURE DIRECT', 'STEREO', 'AUTO', 'DOLBY DIGITAL', 'DOLBY SURROUND', 'DTS SURROUND', 'NEURAL:X', 'AURO3D', 'AURO2DSURR', 'MCH STEREO', 'ROCK ARENA', 'JAZZ CLUB', 'MONO MOVIE', 'MATRIX', 'VIDEO GAME', 'VIRTUAL', 'LEFT', 'RIGHT']}, 'read_cmd': 'MS?', 'write_cmd': 'MS{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'\s?MS(.*)', 'item_attrs': {'initial': True}},
            'sleep': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'SLP?', 'write_cmd': 'SLP{VALUE}', 'dev_datatype': 'convert0', 'reply_pattern': r'SLP(\d{3}|OFF)', 'cmd_settings': {'force_min': 0, 'force_max': 120}, 'item_attrs': {'initial': True}},
            'standby': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'STBY?', 'write_cmd': 'STBY{VALUE}', 'dev_datatype': 'DenonStandby1', 'reply_pattern': r'STBY(\d{2}M|OFF)', 'cmd_settings': {'valid_list_ci': [0, 15, 30, 60]}, 'item_attrs': {'initial': True}},
        },
        'settings': {
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVFL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVFL (\d{2,3})'},
                    'front_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVFR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVFR (\d{2,3})'},
                    'front_height_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVFHL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVFHL (\d{2,3})'},
                    'front_height_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVFHR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVFHR (\d{2,3})'},
                    'front_center': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVC {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVC (\d{2,3})'},
                    'surround_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSL (\d{2,3})'},
                    'surround_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSR (\d{2,3})'},
                    'surroundback_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSBL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSBL (\d{2,3})'},
                    'surroundback_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSBR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSBR (\d{2,3})'},
                    'rear_height_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVRHL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVRHL (\d{2,3})'},
                    'rear_height_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVRHR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVRHR (\d{2,3})'},
                    'subwoofer': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSW {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSW (\d{2,3})'},
                    'subwoofer2': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'read_cmd': 'CV?', 'item_type': 'num', 'write_cmd': 'CVSW2 {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'CVSW2 (\d{2,3})'}
                },
                'tone_control': {
                    'tone': {'read': True, 'write': True, 'read_cmd': 'PSTONE CTRL ?', 'write_cmd': 'PSTONE CTRL {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'PSTONE CTRL (ON|OFF)'},
                    'treble': {'read': True, 'write': True, 'read_cmd': 'PSTRE ?', 'item_type': 'num', 'cmd_settings': {'force_min': -6, 'force_max': 6}, 'write_cmd': 'PSTRE {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'PSTRE (\d{2})'},
                    'trebleup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSTRE UP', 'dev_datatype': 'raw'},
                    'trebledown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSTRE DOWN', 'dev_datatype': 'raw'},
                    'bass': {'read': True, 'write': True, 'read_cmd': 'PSBAS ?', 'item_type': 'num', 'cmd_settings': {'force_min': -6, 'force_max': 6}, 'write_cmd': 'PSBAS {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'PSBAS (\d{2})'},
                    'bassup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSBAS UP', 'dev_datatype': 'raw'},
                    'bassdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSBAS DOWN', 'dev_datatype': 'raw'}
                },
                'general': {
                    'cinema_eq': {'read': True, 'write': True, 'read_cmd': 'PSCINEMA EQ. ?', 'write_cmd': 'PSCINEMA EQ.{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'PSCINEMA EQ.(ON|OFF)'},
                    'dynamic_eq': {'read': True, 'write': True, 'read_cmd': 'PSDYNEQ ?', 'write_cmd': 'PSDYNEQ {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'PSDYNEQ (ON|OFF)'},
                    'multeq': {'read': True, 'write': True, 'read_cmd': 'PSMULTEQ: ?', 'write_cmd': 'PSMULTEQ: {RAW_VALUE_UPPER}', 'item_type': 'bool', 'dev_datatype': 'str', 'cmd_settings': {'valid_list_ci': ['AUDYSSEY', 'BYP.LR', 'FLAT', 'OFF']}, 'reply_pattern': 'PSMULTEQ:{VALID_LIST_CI}'},
                    'dynamic_vol': {'read': True, 'write': True, 'read_cmd': 'DYNVOL ?', 'write_cmd': 'DYNVOL {VALUE}', 'item_type': 'bool', 'dev_datatype': 'num', 'reply_pattern': 'DYNVOL {LOOKUP}', 'lookup': 'DYNVOL'},
                    'speakersetup': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['FL', 'HF']}, 'read_cmd': 'PSSP: ?', 'write_cmd': 'PSSP:{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'PSSP:{VALID_LIST_CI}'},
                    'hdmiaudioout': {'read': True, 'write': True, 'item_type': 'str', 'read_cmd': 'VSAUDIO ?', 'write_cmd': 'VSAUDIO {RAW_VALUE_UPPER}', 'dev_datatype': 'str', 'reply_pattern': 'VSAUDIO {VALID_LIST_CI}', 'cmd_settings': {'valid_list_ci': ['TV', 'AMP']}},
                    'dynamicrange': {'read': True, 'write': True, 'read_cmd': 'PSDRC ?', 'item_type': 'num', 'write_cmd': 'PSDRC {VALUE}', 'dev_datatype': 'str', 'reply_pattern': 'PSDRC {LOOKUP}', 'lookup': 'DYNAM'},
                    'dialogtoggle': {'read': True, 'write': True, 'read_cmd': 'PSDIL ?', 'write_cmd': 'PSDIL {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'PSDIL (ON|OFF)'},
                    'dialog': {'read': True, 'write': True, 'read_cmd': 'PSDIL ?', 'item_type': 'num', 'cmd_settings': {'force_min': -12, 'force_max': 12}, 'write_cmd': 'PSDIL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'PSDIL (\d{2})'},
                    'dialogup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSDIL UP', 'dev_datatype': 'raw'},
                    'dialogdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSDIL DOWN', 'dev_datatype': 'raw'},
                    'dialogenhance': {'read': True, 'write': True, 'read_cmd': 'PSDEH ?', 'write_cmd': 'PSDEH {VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': 'PSDEH {LOOKUP}', 'lookup': 'DIALOG'},
                    'subwoofertoggle': {'read': True, 'write': True, 'read_cmd': 'PSSWL ?', 'write_cmd': 'PSSWL {VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'PSSWL (ON|OFF)'},
                    'subwoofer': {'read': True, 'write': True, 'read_cmd': 'PSSWL ?', 'item_type': 'num', 'cmd_settings': {'force_min': -12, 'valid_max': 12}, 'write_cmd': 'PSSWL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'PSSWL (\d{2})'},
                    'subwooferup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSSWL UP', 'dev_datatype': 'raw'},
                    'subwooferdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSSWL DOWN', 'dev_datatype': 'raw'},
                    'lfe': {'read': True, 'write': True, 'read_cmd': 'PSLFE ?', 'item_type': 'num', 'cmd_settings': {'force_min': -10, 'valid_max': 3}, 'write_cmd': 'PSLFE {RAW_VALUE:02}', 'dev_datatype': 'int', 'reply_pattern': r'PSLFE (\d{2})'},
                    'lfeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSLFE UP', 'dev_datatype': 'raw'},
                    'lfedown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'PSLFE DOWN', 'dev_datatype': 'raw'},
                    'digitalinput': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['AUTO', 'PCM', 'DTS']}, 'read_cmd': 'DC?', 'write_cmd': 'DC{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'DC{VALID_LIST_CI}'},
                    'audioinput': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['AUTO', 'HDMI', 'DIGITAL', 'ANALOG']}, 'read_cmd': 'SD?', 'write_cmd': 'SD{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SD{VALID_LIST_CI}'}
                }
            },
            'video': {
                'aspectratio': {'read': True, 'write': True, 'read_cmd': 'VSASP ?', 'write_cmd': 'VSASP{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'VSASP{LOOKUP}', 'lookup': 'ASPECT'},
                'hdmimonitor': {'read': True, 'write': True, 'cmd_settings': {'force_min': 0, 'force_max': 2}, 'read_cmd': 'VSMONI ?', 'write_cmd': 'VSMONI{VALUE}', 'item_type': 'num', 'dev_datatype': 'convertAuto', 'reply_pattern': 'VSMONI(AUTO|1|2)'},
                'hdmiresolution': {'read': True, 'write': True, 'read_cmd': 'VSSCH ?', 'write_cmd': 'VSSCH{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'VSSCH{LOOKUP}', 'lookup': 'RESOLUTION'},
                'videoprocessingmode': {'read': True, 'write': True, 'item_type': 'str', 'read_cmd': 'VSVPM ?', 'write_cmd': 'VSVPM{VALUE}', 'dev_datatype': 'str', 'reply_pattern': 'VSVPM{LOOKUP}', 'lookup': 'VIDEOPROCESS'},
                'videoresolution': {'read': True, 'write': True, 'read_cmd': 'VSSC ?', 'write_cmd': 'VSSC{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'VSSC{LOOKUP}', 'lookup': 'RESOLUTION'},
                'pictureenhancer': {'read': True, 'write': True, 'read_cmd': 'PVENH ?', 'item_type': 'num', 'cmd_settings': {'force_min': 0, 'force_max': 12}, 'write_cmd': 'PVENH {RAW_VALUE:02}', 'dev_datatype': 'int', 'reply_pattern': r'PVENH (\d{2})'},
                'videoinput': {'read': True, 'write': True, 'cmd_settings': {'valid_list_ci': ['DVD', 'BD', 'TV', 'SAT/CBL', 'MPLAY', 'GAME' 'AUX1', 'AUX2', 'CD', 'ON', 'OFF']}, 'read_cmd': 'SV?', 'write_cmd': 'SV{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'SV{VALID_LIST_CI}'}
            }
        }
    },
    'zone2': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': 'Z2?', 'write_cmd': 'Z2{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z2(ON|OFF)'},
            'mute': {'read': True, 'write': True, 'read_cmd': 'Z2MU?', 'write_cmd': 'Z2MU{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z2MU(ON|OFF)'},
            'volume': {'read': True, 'write': True, 'read_cmd': 'Z2?', 'write_cmd': 'Z2{VALUE}', 'item_type': 'num', 'dev_datatype': 'DenonVol', 'reply_pattern': r'Z2(\d{2,3})', 'cmd_settings': {'force_min': 0.0, 'valid_max': 98.0}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z2UP', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'Z2DOWN', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'input': {'read': True, 'write': True, 'read_cmd': 'Z2?', 'write_cmd': 'Z2{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'Z2{LOOKUP}', 'lookup': 'INPUT', 'item_attrs': {'item_template': 'input'}},
            'sleep': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'Z2SLP?', 'write_cmd': 'Z2SLP{VALUE}', 'dev_datatype': 'convert0', 'reply_pattern': r'Z2SLP(\d{3}|OFF)', 'cmd_settings': {'force_min': 0, 'force_max': 120}},
            'standby': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'Z2STBY?', 'write_cmd': 'Z2STBY{VALUE}', 'dev_datatype': 'DenonStandby', 'reply_pattern': r'Z2STBY(\dH|OFF)', 'cmd_settings': {'valid_list_ci': [0, 2, 4, 8]}},
        },
        'settings': {
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12, 'valid_max': 12}, 'read_cmd': 'Z2CV?', 'item_type': 'num', 'write_cmd': 'Z2CVFL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z2CVFL (\d{2})'},
                    'front_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12, 'valid_max': 12}, 'read_cmd': 'Z2CV?', 'item_type': 'num', 'write_cmd': 'Z2CVFR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z2CVFR (\d{2})'}
                },
                'tone_control': {
                    'treble': {'read': True, 'write': True, 'read_cmd': 'Z2PSTRE ?', 'item_type': 'num', 'cmd_settings': {'force_min': -10, 'force_max': 10}, 'write_cmd': 'Z2PSTRE {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z2PSTRE (\d{2})'},
                    'trebleup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z2PSTRE UP', 'dev_datatype': 'raw'},
                    'trebledown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z2PSTRE DOWN', 'dev_datatype': 'raw'},
                    'bass': {'read': True, 'write': True, 'read_cmd': 'Z2PSBAS ?', 'item_type': 'num', 'cmd_settings': {'force_min': -10, 'force_max': 10}, 'write_cmd': 'Z2PSBAS {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z2PSBAS (\d{2})'},
                    'bassup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z2PSBAS UP', 'dev_datatype': 'raw'},
                    'bassdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z2PSBAS DOWN', 'dev_datatype': 'raw'}
                },
                'general': {
                    'hdmiout': {'read': True, 'write': True, 'item_type': 'str', 'read_cmd': 'Z2HDA?', 'write_cmd': 'Z2HDA {RAW_VALUE_UPPER}', 'dev_datatype': 'str', 'reply_pattern': 'Z2HDA {VALID_LIST_CI}', 'cmd_settings': {'valid_list_ci': ['THR', 'PCM']}},
                    'HPF': {'read': True, 'write': True, 'read_cmd': 'Z2HPF?', 'write_cmd': 'Z2HPF{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z2HPF(ON|OFF)'}
                }
            }
        }
    },
    'zone3': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': 'Z3?', 'write_cmd': 'Z3{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z3(ON|OFF)'},
            'mute': {'read': True, 'write': True, 'read_cmd': 'Z3MU?', 'write_cmd': 'Z3MU{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z3MU(ON|OFF)'},
            'volume': {'read': True, 'write': True, 'read_cmd': 'Z3?', 'write_cmd': 'Z3{VALUE}', 'item_type': 'num', 'dev_datatype': 'DenonVol', 'reply_pattern': r'Z3(\d{2,3})', 'cmd_settings': {'force_min': 0.0, 'valid_max': 98.0}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z3UP', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'Z3DOWN', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'sleep': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'Z3SLP?', 'write_cmd': 'Z3SLP{VALUE}', 'dev_datatype': 'convert0', 'reply_pattern': r'Z3SLP(\d{3}|OFF)', 'cmd_settings': {'force_min': 0, 'valid_max': 120}},
            'standby': {'read': True, 'write': True, 'item_type': 'num', 'read_cmd': 'Z3STBY?', 'write_cmd': 'Z3STBY{VALUE}', 'dev_datatype': 'DenonStandby', 'reply_pattern': r'Z3STBY(\dH|OFF)', 'cmd_settings': {'valid_list_ci': [0, 2, 4, 8]}},
            'input': {'read': True, 'write': True, 'read_cmd': 'Z3?', 'write_cmd': 'Z3{RAW_VALUE_UPPER}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'Z3{LOOKUP}', 'lookup': 'INPUT3', 'item_attrs': {'item_template': 'input'}}
        },
        'settings': {
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12, 'valid_max': 12}, 'read_cmd': 'Z3CV?', 'item_type': 'num', 'write_cmd': 'Z3CVFL {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z3CVFL (\d{2})'},
                    'front_right': {'read': True, 'write': True, 'cmd_settings': {'force_min': -12, 'valid_max': 12}, 'read_cmd': 'Z3CV?', 'item_type': 'num', 'write_cmd': 'Z3CVFR {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z3CVFR (\d{2})'}
                },
                'tone_control': {
                    'treble': {'read': True, 'write': True, 'read_cmd': 'Z3PSTRE ?', 'item_type': 'num', 'cmd_settings': {'force_min': -10, 'force_max': 10}, 'write_cmd': 'Z3PSTRE {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z3PSTRE (\d{2})'},
                    'trebleup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z3PSTRE UP', 'dev_datatype': 'raw'},
                    'trebledown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z3PSTRE DOWN', 'dev_datatype': 'raw'},
                    'bass': {'read': True, 'write': True, 'read_cmd': 'Z3PSBAS ?', 'item_type': 'num', 'cmd_settings': {'force_min': -10, 'force_max': 10}, 'write_cmd': 'Z3PSBAS {VALUE}', 'dev_datatype': 'remap50to0', 'reply_pattern': r'Z3PSBAS (\d{2})'},
                    'bassup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z3PSBAS UP', 'dev_datatype': 'raw'},
                    'bassdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'Z3PSBAS DOWN', 'dev_datatype': 'raw'}
                },
                'general': {
                    'HPF': {'read': True, 'write': True, 'read_cmd': 'Z3HPF?', 'write_cmd': 'Z3HPF{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': 'Z3HPF(ON|OFF)'},
                }
            }
        }
    }
}

lookups = {
    'ALL': {
        'INPUTSIGNAL': {
            '01': 'Analog',
            '02': 'PCM',
            '03': 'Dolby Digital',
            '04': 'Dolby TrueHD',
            '05': 'Dolby Atmos',
            '06': 'DTS',
            '07': '07',
            '08': 'DTS-HD Hi Res',
            '09': 'DTS-HD MSTR',
            '10': '10',
            '11': '11',
            '12': 'Unknown',
            '13': 'PCM Zero',
            '14': '14',
            '15': 'MP3',
            '16': '16',
            '17': 'AAC',
            '18': 'FLAC',
        },
        'RESOLUTION': {
            '48P': '480p/576p',
            '10I': '1080i',
            '72P': '720p',
            '10P': '1080p',
            '10P24': '1080p:24Hz',
            '4K': '4K',
            '4KF': '4K(60/50)',
            'AUTO': 'Auto'
        },
        'ASPECT': {
            'NRM': '4:3',
            'FUL': '16:9'
        },
        'POWER': {
            'ON': True,
            'STANDBY': False
        },
        'SOUNDMODE': {
            'MUS': 'MUSIC',
            'MOV': 'MOVIE',
            'GAM': 'GAME',
            'PUR': 'PURE DIRECT'
        },
        'DYNAM': {
            'OFF': 0,
            'LOW': 1,
            'MID': 2,
            'HI': 3,
            'AUTO': 4
        },
        'DYNVOL': {
            'OFF': 0,
            'LIT': 1,
            'MED': 2,
            'HEV': 3
        },
        'DIALOG': {
            'OFF': 0,
            'LOW': 1,
            'MED': 2,
            'HIGH': 3,
            'AUTO': 4
        },
        'VIDEOPROCESS': {
            'MOVI': 'Movie',
            'BYP': 'Bypass',
            'GAME': 'Game',
            'AUTO': 'Auto'
        },
        'INPUT': {
            'SOURCE': 'SOURCE',
            'TUNER': 'TUNER',
            'DVD': 'DVD',
            'BD': 'BD',
            'TV': 'TV',
            'SAT/CBL': 'SAT/CBL',
            'MPLAY': 'MPLAY',
            'GAME': 'GAME',
            'HDRADIO': 'HDRADIO',
            'NET': 'NET',
            'AUX1': 'AUX1',
            'BT': 'BT'
        },
        'INPUT3': {
            'SOURCE': 'SOURCE',
            'TUNER': 'TUNER',
            'PHONO': 'PHONO',
            'CD': 'CD',
            'DVD': 'DVD',
            'BD': 'BD',
            'TV': 'TV',
            'SAT/CBL': 'SAT/CBL',
            'MPLAY': 'MPLAY',
            'GAME': 'GAME',
            'NET': 'NET',
            'AUX1': 'AUX1',
            'AUX2': 'AUX2',
            'BT': 'BT',
            'QUICK1': 'QUICK1',
            'QUICK2': 'QUICK2',
            'QUICK3': 'QUICK3',
            'QUICK4': 'QUICK4',
            'QUICK5': 'QUICK5',
            'QUICK1 MEMORY': 'QUICK1 MEMORY',
            'QUICK2 MEMORY': 'QUICK2 MEMORY',
            'QUICK3 MEMORY': 'QUICK3 MEMORY',
            'QUICK4 MEMORY': 'QUICK4 MEMORY',
            'QUICK5 MEMORY': 'QUICK5 MEMORY'
        }
    },
    'AVR-X6300H': {
        'INPUT': {
            'PHONO': 'PHONO',
            'CD': 'CD',
            'AUX2': 'AUX2'
        }
    },
    'AVR-X4300H': {
        'INPUT': {
            'PHONO': 'PHONO',
            'CD': 'CD',
            'AUX2': 'AUX2'
        }
    },
    'AVR-X3300W': {
        'INPUT': {
            'CD': 'CD',
            'AUX2': 'AUX2',
            'IRADIO': 'IRADIO',
            'SERVER': 'SERVER',
            'FAVORITES': 'FAVORITES',
            'USB/IPOD': 'USB/IPOD',
            'USB': 'USB',
            'IPD': 'IPD',
            'IRP': 'IRP',
            'FVP': 'FVP'
        }
    },
    'AVR-X2300W': {
        'INPUT': {
            'CD': 'CD',
            'AUX2': 'AUX2',
            'IRADIO': 'IRADIO',
            'SERVER': 'SERVER',
            'FAVORITES': 'FAVORITES',
            'USB/IPOD': 'USB/IPOD',
            'USB': 'USB',
            'IPD': 'IPD',
            'IRP': 'IRP',
            'FVP': 'FVP'
        }
    },
    'AVR-X1300W': {
        'INPUT': {
            'IRADIO': 'IRADIO',
            'SERVER': 'SERVER',
            'FAVORITES': 'FAVORITES',
            'USB/IPOD': 'USB/IPOD',
            'USB': 'USB',
            'IPD': 'IPD',
            'IRP': 'IRP',
            'FVP': 'FVP'
        }
    }
}

item_templates = {
    'custom_inputnames': {
        'cache': True,
        'reverse': {
            'type': 'dict',
            'eval': '{} if sh...() == {} else {v: k for (k, v) in sh...().items()}',
            'update': {
                'type': 'bool',
                'eval': 'sh...timer(2, {})',
                'eval_trigger': '...'
            }
        }
    },
    'input': {
        'on_change': [".custom_name = '' if sh.....general.custom_inputnames() == {} else sh.....general.custom_inputnames()[value]",],
        'custom_name': {
            'type': 'str',
            'on_change': ".. = '' if sh......general.custom_inputnames.reverse() == {} else sh......general.custom_inputnames.reverse()[value]"
        }
    }
}
