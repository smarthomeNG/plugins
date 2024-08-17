#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

# commands for dev pioneer
models = {
    'ALL': ['general.pqls', 'general.settings.speakersystem', 'general.settings.xcurve', 'general.settings.hdmi', 'general.settings.name', 'general.settings.language', 'general.dimmer', 'general.sleep', 'general.display', 'general.error', 'general.multizone', 'tuner', 'zone1', 'zone2.control', 'hdzone'],
    'SC-LX87': ['general.amp', 'general.settings.surroundposition', 'general.settings.xover', 'general.settings.loudness', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.tone_control', 'zone3'],
    'SC-LX77': ['general.amp', 'general.settings.surroundposition', 'general.settings.xover', 'general.settings.loudness', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.tone_control', 'zone3'],
    'SC-LX57': ['general.amp', 'general.settings.surroundposition', 'general.settings.xover', 'general.settings.loudness', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.tone_control', 'zone3'],
    'SC-2023': ['general.settings.surroundposition', 'general.settings.xover', 'zone2.settings.sound.channel_level', 'zone2.settings.sound.tone_control', 'zone3'],
    'SC-1223': ['zone2.settings.sound.channel_level', 'zone2.settings.sound.tone_control'],
    'VSX-1123': [],
    'VSX-923': []
}

commands = {
    'general': {
        'error': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'E0{LOOKUP}', 'lookup': 'ERROR'},
        'display': {'read': True, 'write': False, 'read_cmd': '?FL', 'item_type': 'str', 'dev_datatype': 'PioDisplay', 'reply_pattern': 'FL(.{28}).*'},
        'pqls': {'read': True, 'write': True, 'read_cmd': '?PQ', 'write_cmd': '{RAW_VALUE:01}PQ', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': r'PQ(\d)'},
        'dimmer': {'read': True, 'write': True, 'write_cmd': '{RAW_VALUE}SAA', 'cmd_settings': {'force_min': 0, 'force_max': 3}, 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'SAA(\d)', 'item_attrs': {'attributes': {'remark': '0 = very bright, 1 = bright, 2 = dark, 3 = off'}}},
        'sleep': {'read': True, 'write': True, 'read_cmd': '?SAB', 'write_cmd': '{VALUE}SAB', 'item_type': 'num', 'dev_datatype': 'PioSleep', 'reply_pattern': r'SAB(\d{3})', 'item_attrs': {'attributes': {'remark': '0 = off, 30 = 30 minutes, 60 = 60 minutes, 90 = 90 minutes'}}},
        'amp': {'read': True, 'write': True, 'read_cmd': '?SAC', 'write_cmd': '{VALUE}SAC', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'SAC{LOOKUP}', 'lookup': 'AMP', 'item_attrs': {'attributes': {'remark': '0 = AMP, 1 = THR'}, 'lookup_item': True}},
        'multizone': {'read': True, 'write': True, 'write_cmd': 'ZZ', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'(?:APR|BPR|ZEP)(\d{1})'},
        'settings': {
            'language': {'read': True, 'write': True, 'read_cmd': '?SSE', 'write_cmd': '{VALUE}SSE', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'SSE{LOOKUP}', 'lookup': 'LANGUAGE', 'item_attrs': {'initial': True}},
            'name': {'read': True, 'write': True, 'read_cmd': '?SSO', 'write_cmd': '{VALUE}SSO', 'item_type': 'str', 'dev_datatype': 'PioName', 'reply_pattern': r'SSO(?:\d{2})(.*)', 'item_attrs': {'initial': True}},
            'speakersystem': {'read': True, 'write': True, 'read_cmd': '?SSF', 'write_cmd': '{VALUE}SSF', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'SSF{LOOKUP}', 'lookup': 'SPEAKERSYSTEM', 'item_attrs': {'lookup_item': True, 'initial': True}},
            'surroundposition': {'read': True, 'write': True, 'read_cmd': '?SSP', 'write_cmd': '{VALUE}SSP', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'SSP{LOOKUP}', 'lookup': 'SURROUNDPOSITION', 'item_attrs': {'lookup_item': True, 'initial': True}},
            'xover': {'read': True, 'write': True, 'read_cmd': '?SSQ', 'write_cmd': '{VALUE}SSQ', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'SSQ{LOOKUP}', 'lookup': 'XOVER', 'item_attrs': {'initial': True}},
            'xcurve': {'read': True, 'write': True, 'read_cmd': '?SST', 'write_cmd': '{VALUE}SST', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'SST{LOOKUP}', 'lookup': 'XCURVE', 'item_attrs': {'initial': True}},
            'loudness': {'read': True, 'write': True, 'read_cmd': '?SSU', 'write_cmd': '{RAW_VALUE:01}SSU', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': r'SSU(\d{1})', 'item_attrs': {'initial': True}},
            'initialvolume': {'read': True, 'write': True, 'read_cmd': '?SUC', 'write_cmd': '{VALUE}SUC', 'item_type': 'num', 'dev_datatype': 'PioInitVol', 'reply_pattern': r'SUC(\d{3})', 'item_attrs': {'initial': True}},
            'mutelevel': {'read': True, 'write': True, 'read_cmd': '?SUE', 'write_cmd': '{VALUE}SUE', 'item_type': 'num', 'dev_datatype': 'raw', 'reply_pattern': r'SUE{LOOKUP}', 'lookup': 'MUTELEVEL', 'item_attrs': {'initial': True}},
            'hdmi': {
                'control': {'read': True, 'write': True, 'read_cmd': '?STQ', 'write_cmd': '{RAW_VALUE:01}STQ', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': r'STQ(\d{1})', 'item_attrs': {'initial': True}},
                'controlmode': {'read': True, 'write': True, 'read_cmd': '?STR', 'write_cmd': '{RAW_VALUE:01}STR', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': r'STR(\d{1})', 'item_attrs': {'initial': True}},
                'arc': {'read': True, 'write': True, 'read_cmd': '?STT', 'write_cmd': '{RAW_VALUE:01}STT', 'item_type': 'bool', 'dev_datatype': 'raw', 'reply_pattern': r'STT(\d{1})', 'item_attrs': {'initial': True}},
                'standbythrough': {'read': True, 'write': True, 'read_cmd': '?STU', 'write_cmd': '{VALUE}STU', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'STU{LOOKUP}', 'lookup': 'STANDBYTHROUGH', 'item_attrs': {'lookup_item': True, 'initial': True}}
            }

    }
    },
    'tuner': {
        'tunerpreset': {'read': True, 'write': True, 'read_cmd': '?PR', 'item_type': 'num', 'write_cmd': '{RAW_VALUE}PR', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'PR([A-Ga-g]\d{2})'},
        'tunerpresetup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPI', 'dev_datatype': 'raw'},
        'tunerpresetdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TPD', 'dev_datatype': 'raw'},
        'title': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': ['GEH01020']},
        'genre': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': ['GEH05024']},
        'station': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': ['GEH04022']}
    },
    'zone1': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '?P', 'write_cmd': 'P{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'PWR(\d{1})', 'item_attrs': {'item_template': 'power'}},
            'mute': {'read': True, 'write': True, 'read_cmd': '?M', 'write_cmd': 'M{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'MUT(\d{1})'},
            'volume': {'read': True, 'write': True, 'read_cmd': '?V', 'write_cmd': '{RAW_VALUE:03}VL', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'VOL(\d{3})', 'cmd_settings': {'force_min': 0, 'valid_max': 185}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'VU', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'VD', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'input': {'read': True, 'write': True, 'read_cmd': '?F', 'write_cmd': '{VALUE}FN', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'FN{LOOKUP}', 'lookup': 'INPUT', 'item_attrs': {'lookup_item': True}},
            'inputup': {'read': False, 'write': True, 'write_cmd': 'FU', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'inputdown': {'read': False, 'write': True, 'write_cmd': 'FD', 'item_type': 'bool', 'dev_datatype': 'raw'}
        },
        'settings': {
            'standby': {'read': True, 'write': True, 'read_cmd': '?STY', 'write_cmd': '{VALUE}STY', 'item_type': 'num', 'dev_datatype': 'PioStandby', 'reply_pattern': r'STY(\d{4})', 'item_attrs': {'attributes': {'remark': '0 = OFF, 15 = 15 minutes, 30 = 30 minutes, 60 = 60 minutes'}, 'initial': True}},
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'read_cmd': '?L__CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'L__{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVL__(\d{2})'},
                    'front_right': {'read': True, 'write': True, 'read_cmd': '?R__CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'R__{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVR__(\d{2})'},
                    'front_center': {'read': True, 'write': True, 'read_cmd': '?C__CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'C__{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVC__(\d{2})'},
                    'surround_left': {'read': True, 'write': True, 'read_cmd': '?SL_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'SL_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVSL_(\d{2})'},
                    'surround_right': {'read': True, 'write': True, 'read_cmd': '?SR_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'SR_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVSR_(\d{2})'},
                    'front_height_left': {'read': True, 'write': True, 'read_cmd': '?LH_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'LH_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVLH_(\d{2})'},
                    'front_height_right': {'read': True, 'write': True, 'read_cmd': '?RH_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'RH_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVRH_(\d{2})'},
                    'front_wide_left': {'read': True, 'write': True, 'read_cmd': '?LW_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'LW_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'LWVSW_(\d{2})'},
                    'front_wide_right': {'read': True, 'write': True, 'read_cmd': '?RW_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'RW_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'RWVSW_(\d{2})'},
                    'subwoofer': {'read': True, 'write': True, 'read_cmd': '?SW_CLV', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'SW_{VALUE}CLV', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'CLVSW_(\d{2})'}
                },
                'tone_control': {
                    'tone': {'read': True, 'write': True, 'read_cmd': '?TO', 'item_type': 'bool', 'write_cmd': '{RAW_VALUE:01}TO', 'dev_datatype': 'str', 'reply_pattern': r'TO(\d)', 'item_attrs': {'item_template': 'tone'}},
                    'treble': {'read': True, 'write': True, 'read_cmd': '?TR', 'item_type': 'num', 'write_cmd': '{VALUE}TR', 'dev_datatype': 'str', 'reply_pattern': r'TR{LOOKUP}', 'lookup': 'TONE'},
                    'trebleup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TI', 'dev_datatype': 'raw'},
                    'trebledown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'TD', 'dev_datatype': 'raw'},
                    'bass': {'read': True, 'write': True, 'read_cmd': '?BA', 'item_type': 'num', 'write_cmd': '{VALUE}BA', 'dev_datatype': 'str', 'reply_pattern': r'BA{LOOKUP}', 'lookup': 'TONE'},
                    'bassup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'BI', 'dev_datatype': 'raw'},
                    'bassdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'BD', 'dev_datatype': 'raw'}
                },
                'general': {
                    'hdmiout': {'read': True, 'write': True, 'read_cmd': '?HO', 'write_cmd': '{VALUE}HO', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'HO{LOOKUP}', 'lookup': 'HDMIOUT', 'item_attrs': {'lookup_item': True}},
                    'hdmiaudio': {'read': True, 'write': True, 'read_cmd': '?HA', 'write_cmd': '{VALUE}HA', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'HA{LOOKUP}', 'lookup': 'HDMIAUDIO', 'item_attrs': {'lookup_item': True}},
                    'dialog': {'read': True, 'write': True, 'read_cmd': '?ATH', 'write_cmd': '{VALUE}ATH', 'cmd_settings': {'force_min': 0, 'force_max': 5}, 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'ATH(\d)'},
                    'dialogup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': '9ATH', 'dev_datatype': 'str'},
                    'dialogdown': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': '8ATH', 'dev_datatype': 'str'},
                    'listeningmode': {'read': True, 'write': True, 'read_cmd': '?S', 'write_cmd': '{VALUE}SR', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'SR{LOOKUP}', 'lookup': 'LISTENINGMODE', 'item_attrs': {'lookup_item': True}},
                    'playingmode': {'read': True, 'write': False, 'read_cmd': '?L', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'LM{LOOKUP}', 'lookup': 'PLAYINGMODE', 'item_attrs': {'lookup_item': True}},
                    'speakers': {'read': True, 'write': True, 'read_cmd': '?SPK', 'item_type': 'num', 'dev_datatype': 'str', 'cmd_settings': {'valid_list': [0, 1, 2, 3, 9]}, 'write_cmd': '{RAW_VALUE:01}SPK', 'reply_pattern': r'SPK(\d)', 'item_attrs': {'item_template': 'speakers'}}
                }
            }
        }
    },
    'zone2': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '?AP', 'write_cmd': 'AP{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'APR(\d{1})', 'item_attrs': {'item_template': 'power'}},
            'mute': {'read': True, 'write': True, 'read_cmd': '?Z2M', 'item_type': 'bool', 'write_cmd': 'Z2M{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'Z2MUT(\d{1})'},
            'volume': {'read': True, 'write': True, 'read_cmd': '?ZV', 'write_cmd': '{RAW_VALUE:02}ZV', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'ZV(\d{2})', 'cmd_settings': {'force_min': 0, 'valid_max': 81}, },
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'ZU', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'ZD', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'input': {'read': True, 'write': True, 'read_cmd': '?ZS', 'write_cmd': '{VALUE}ZS', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'Z2F{LOOKUP}', 'lookup': 'INPUT2', 'item_attrs': {'lookup_item': True}},
            'inputup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'ZSFU', 'dev_datatype': 'raw'},
            'inputdown': {'read': False, 'write': True, 'write_cmd': 'ZSFD', 'item_type': 'bool', 'dev_datatype': 'raw'}
        },
        'settings': {
            'standby': {'read': True, 'write': True, 'read_cmd': '?STZ', 'write_cmd': '{VALUE}STZ', 'item_type': 'num', 'dev_datatype': 'PioStandby2', 'reply_pattern': r'STZ(\d{4})', 'item_attrs': {'attributes': {'remark': '0 = OFF, 0.5 = 30 minutes, 1 = 1 hour, 3 = 3 hours, 6 = 6 hours, 9 = 9 hours'}, 'initial': True}},
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'read_cmd': '?ZGEL___', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'L__{VALUE}ZGE', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'ZGEL__(\d{2})'},
                    'front_right': {'read': True, 'write': True, 'read_cmd': '?ZGER___', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'R__{VALUE}ZGE', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'ZGER__(\d{2})'}
                },
                'tone_control': {
                    'tone': {'read': True, 'write': True, 'read_cmd': '?ZGA', 'item_type': 'bool', 'write_cmd': '{RAW_VALUE:01}ZGA', 'dev_datatype': 'str', 'reply_pattern': r'ZGA(\d)', 'item_attrs': {'item_template': 'tone'}},
                    'treble': {'read': True, 'write': True, 'read_cmd': '?ZGC', 'item_type': 'num', 'write_cmd': '{VALUE}ZGC', 'dev_datatype': 'str', 'reply_pattern': r'ZGC{LOOKUP}', 'lookup': 'TONE'},
                    'bass': {'read': True, 'write': True, 'read_cmd': '?ZGB', 'item_type': 'num', 'write_cmd': '{VALUE}ZGB', 'dev_datatype': 'str', 'reply_pattern': r'ZGB{LOOKUP}', 'lookup': 'TONE'}
                }
            }
        }
    },
    'zone3': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '?BP', 'write_cmd': 'BP{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'BPR(\d{1})', 'item_attrs': {'item_template': 'power'}},
            'mute': {'read': True, 'write': True, 'read_cmd': '?Z3M', 'item_type': 'bool', 'write_cmd': 'Z3M{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'Z3MUT(\d{1})'},
            'volume': {'read': True, 'write': True, 'read_cmd': '?YV', 'write_cmd': '{RAW_VALUE:02}YV', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'YV(\d{2})', 'cmd_settings': {'force_min': 0, 'valid_max': 81}, },
            'volumeup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'YU', 'dev_datatype': 'raw'},
            'volumedown': {'read': False, 'write': True, 'write_cmd': 'YD', 'item_type': 'bool', 'dev_datatype': 'raw'},
            'input': {'read': True, 'write': True, 'read_cmd': '?ZT', 'write_cmd': '{VALUE}ZT', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'Z3F{LOOKUP}', 'lookup': 'INPUT3', 'item_attrs': {'lookup_item': True}},
            'inputup': {'read': False, 'write': True, 'item_type': 'bool', 'write_cmd': 'ZTFU', 'dev_datatype': 'raw'},
            'inputdown': {'read': False, 'write': True, 'write_cmd': 'ZTFD', 'item_type': 'bool', 'dev_datatype': 'raw'}
        },
        'settings': {
            'standby': {'read': True, 'write': True, 'read_cmd': '?SUA', 'write_cmd': '{VALUE}SUA', 'item_type': 'num', 'dev_datatype': 'PioStandby2', 'reply_pattern': r'SUA(\d{4})', 'item_attrs': {'attributes': {'remark': '0 = OFF, 0.5 = 30 minutes, 1 = 1 hour, 3 = 3 hours, 6 = 6 hours, 9 = 9 hours'}, 'initial': True}},
            'sound': {
                'channel_level': {
                    'front_left': {'read': True, 'write': True, 'read_cmd': '?ZHEL___', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'L__{VALUE}ZHE', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'ZHEL__(\d{2})'},
                    'front_right': {'read': True, 'write': True, 'read_cmd': '?ZHER___', 'item_type': 'num', 'cmd_settings': {'force_min': -12.0, 'valid_max': 12.0}, 'write_cmd': 'R__{VALUE}ZHE', 'dev_datatype': 'PioChannelVol', 'reply_pattern': r'ZHER__(\d{2})'}
                }
            }
        }
    },
    'hdzone': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '?ZEP', 'write_cmd': 'ZE{VALUE}', 'item_type': 'bool', 'dev_datatype': 'onoff', 'reply_pattern': r'ZEP(\d{1})'},
            'input': {'read': True, 'write': True, 'read_cmd': '?ZEA', 'write_cmd': '{VALUE}ZEA', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'ZEA{LOOKUP}', 'lookup': 'INPUTHD', 'item_attrs': {'lookup_item': True}}
        },
        'settings': {
            'standby': {'read': True, 'write': True, 'read_cmd': '?SUB', 'write_cmd': '{VALUE}SUB', 'item_type': 'num', 'dev_datatype': 'PioStandby2', 'reply_pattern': r'SUB(\d{4})', 'item_attrs': {'attributes': {'remark': '0 = OFF, 0.5 = 30 minutes, 1 = 1 hour, 3 = 3 hours, 6 = 6 hours, 9 = 9 hours'}, 'initial': True}},
        }
    }
}

lookups = {
    'ALL': {
        'ERROR': {
            '2': 'not available now',
            '3': 'invalid command',
            '4': 'command error',
            '6': 'parameter error'
        },
        'HDMIOUT': {
            '0': 'HDMI OUT 1+2 ON',
            '1': 'HDMI OUT 1 ON',
            '2': 'HDMI OUT 2 ON',
            '3': 'HDMI OUT 1/2 OFF',
            '9': 'HDMI OUT 1/2 (cyclic)'
        },
        'HDMIAUDIO': {
            '0': 'AMP',
            '1': 'THRU',
            '9': 'HDMI AUDIO (cyclic)'
        },
        'MUTELEVEL': {
            '0': 'Full',
            '1': '-40db',
            '2': '-20db'
        },
        'XOVER': {
            '0': '50Hz',
            '1': '80Hz',
            '2': '100Hz',
            '3': '150Hz',
            '4': '200Hz'
        },
        'XCURVE': {
            '0': 'OFF',
            '1': '-0.5db',
            '2': '-1.0db',
            '3': '-1,5db',
            '4': '-2.0db',
            '5': '-2.5db',
            '6': '-3.0db'
        },
        'STANDBYTHROUGH': {
            '00': 'OFF',
            '01': 'LAST',
            '02': 'BD',
            '03': 'HDMI 1',
            '04': 'HDMI 2',
            '05': 'HDMI 3',
            '06': 'HDMI 4',
            '07': 'HDMI 5',
            '08': 'HDMI 6',
            '09': 'HDMI 7',
            '10': 'HDMI 8'
        },
        'LANGUAGE': {
            '00': 'English',
            '01': 'French',
            '03': 'German',
            '04': 'Italian',
            '05': 'Spanish',
            '06': 'Dutch',
            '07': 'Russian',
            '08': 'Chinese1',
            '09': 'Chinese2',
            '10': 'Japanese'
        },
        'AMP': {
            '00': 'AMP ON',
            '01': 'AMP Front OFF',
            '02': 'AMP Front & Center OFF',
            '03': 'AMP OFF',
            '98': 'DOWN (cyclic)',
            '99': 'UP (cyclic)'
        },
        'SPEAKERSYSTEM': {
            '00': 'Normal(SB/FH)',
            '01': 'Normal(SB/FW)',
            '02': 'Speaker B',
            '03': 'Front Bi-Amp',
            '04': 'Zone2'
        },
        'SURROUNDPOSITION': {
            '0': 'ON SIDE',
            '1': 'IN REAR'
        },
        'TONE': {
            '00': 6,
            '01': 5,
            '02': 4,
            '03': 3,
            '04': 2,
            '05': 1,
            '06': 0,
            '07': -1,
            '08': -2,
            '09': -3,
            '10': -4,
            '11': -5,
            '12': -6
        },
        'INPUT': {
            '25': 'BD',
            '04': 'DVD',
            '06': 'SAT/CBL',
            '15': 'DVR/BDR',
            '19': 'HDMI 1',
            '20': 'HDMI 2',
            '21': 'HDMI 3',
            '22': 'HDMI 4',
            '23': 'HDMI 5',
            '24': 'HDMI 6',
            '34': 'HDMI 7',
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB',
            '05': 'TV',
            '01': 'CD',
            '02': 'TUNER',
            '33': 'ADAPTER PORT',
            '48': 'MHL',
            '31': 'HDMI (cyclic)',
            '99': 'Multi-ZONE Music'
        },
        'INPUT2': {
            '04': 'DVD',
            '06': 'SAT/CBL',
            '15': 'DVR/BDR',
            '05': 'TV',
            '01': 'CD',
            '02': 'TUNER',
            '33': 'ADAPTER PORT',
            '99': 'Multi-ZONE Music'
        },
        'INPUT3': {
            '10': 'VIDEO 1 (VIDEO)',
            '04': 'DVD',
            '06': 'SAT/CBL',
            '15': 'DVR/BDR',
            '05': 'TV',
            '01': 'CD',
            '02': 'TUNER',
            '33': 'ADAPTER PORT',
            '99': 'Multi-ZONE Music'
        },
        'INPUTHD': {
            '25': 'BD',
            '04': 'DVD',
            '06': 'SAT/CBL',
            '15': 'DVR/BDR',
            '19': 'HDMI 1',
            '20': 'HDMI 2',
            '21': 'HDMI 3',
            '22': 'HDMI 4',
            '23': 'HDMI 5',
            '24': 'HDMI 6',
            '34': 'HDMI 7',
            '48': 'MHL',
            '31': 'HDMI (cyclic)'
        },
        'LISTENINGMODE': {
            '0001': 'STEREO (cyclic)',
            '0010': 'STANDARD (cyclic)',
            '0009': 'STEREO (direct set)',
            '0013': 'PRO LOGIC2 MOVIE',
            '0018': 'PRO LOGIC2x MOVIE',
            '0014': 'PRO LOGIC2 MUSIC',
            '0019': 'PRO LOGIC2x MUSIC',
            '0015': 'PRO LOGIC2 GAME',
            '0020': 'PRO LOGIC2x GAME',
            '0031': 'PRO LOGIC2z HEIGHT',
            '0032': 'WIDE SURROUND MOVIE',
            '0033': 'WIDE SURROUND MUSIC',
            '0012': 'PRO LOGIC',
            '0037': 'Neo:X CINEMA',
            '0038': 'Neo:X MUSIC',
            '0039': 'Neo:X GAME',
            '0021': '(Multi ch source)',
            '0022': '(Multi ch source)+DOLBY EX',
            '0023': '(Multi ch source)+PRO LOGIC2x MOVIE',
            '0024': '(Multi ch source)+PRO LOGIC2x MUSIC',
            '0034': '(Multi-ch Source)+PRO LOGIC2z HEIGHT',
            '0035': '(Multi-ch Source)+WIDE SURROUND MOVIE',
            '0036': '(Multi-ch Source)+WIDE SURROUND MUSIC',
            '0026': '(Multi ch source)DTS-ES matrix',
            '0027': '(Multi ch source)DTS-ES discrete',
            '0030': '(Multi ch source)DTS-ES 8ch discrete',
            '0043': '(Multi ch source)+Neo:X CINEMA',
            '0044': '(Multi ch source)+Neo:X MUSIC',
            '0045': '(Multi ch source)+Neo:X GAME',
            '0100': 'ADVANCED SURROUND (cyclic)',
            '0101': 'ACTION',
            '0103': 'DRAMA',
            '0118': 'ADVANCED GAME',
            '0117': 'SPORTS',
            '0107': 'CLASSICAL',
            '0110': 'ROCK/POP',
            '0112': 'EXTENDED STEREO',
            '0003': 'Front Stage Surround Advance',
            '0200': 'ECO MODE (cyclic)',
            '0212': 'ECO MODE 1',
            '0213': 'ECO MODE 2',
            '0153': 'RETRIEVER AIR',
            '0113': 'PHONES SURROUND',
            '0005': 'AUTO SURR/STREAM DIRECT (cyclic)',
            '0006': 'AUTO SURROUND',
            '0151': 'Auto Level Control (A.L.C.)',
            '0007': 'DIRECT',
            '0008': 'PURE DIRECT'
        },
        'PLAYINGMODE': {
            '0101': 'PLIIx MOVIE',
            '0102': 'PLII MOVIE',
            '0103': 'PLIIx MUSIC',
            '0104': 'PLII MUSIC',
            '0105': 'PLIIx GAME',
            '0106': 'PLII GAME',
            '0107': 'PROLOGIC',
            '0108': 'Neo:6 CINEMA',
            '0109': 'Neo:6 MUSIC',
            '010c': '2ch Straight Decode',
            '010d': 'PLIIz HEIGHT',
            '010e': 'WIDE SURR MOVIE',
            '010f': 'WIDE SURR MUSIC',
            '0110': 'STEREO',
            '0111': 'Neo:X CINEMA',
            '0112': 'Neo:X MUSIC',
            '0113': 'Neo:X GAME',
            '1101': 'PLIIx MOVIE',
            '1102': 'PLIIx MUSIC',
            '1103': 'DIGITAL EX',
            '1104': 'DTS Neo:6',
            '1105': 'ES MATRIX',
            '1106': 'ES DISCRETE',
            '1107': 'DTS-ES 8ch',
            '1108': 'multi ch Straight Decode',
            '1109': 'PLIIz HEIGHT',
            '110a': 'WIDE SURR MOVIE',
            '110b': 'WIDE SURR MUSIC',
            '110c': 'Neo:X CINEMA',
            '110d': 'Neo:X MUSIC',
            '110e': 'Neo:X GAME',
            '0201': 'ACTION',
            '0202': 'DRAMA',
            '0208': 'ADVANCEDGAME',
            '0209': 'SPORTS',
            '020a': 'CLASSICAL',
            '020b': 'ROCK/POP',
            '020d': 'EXT.STEREO',
            '020e': 'PHONES SURR.',
            '020f': 'FRONT STAGE SURROUND ADVANCE',
            '0211': 'SOUND RETRIEVER AIR',
            '0212': 'ECO MODE 1',
            '0213': 'ECO MODE 2',
            '0301': 'PLIIx MOVIE +THX',
            '0302': 'PLII MOVIE +THX',
            '0303': 'PL +THX CINEMA',
            '0305': 'THX CINEMA',
            '0306': 'PLIIx MUSIC +THX',
            '0307': 'PLII MUSIC +THX',
            '0308': 'PL +THX MUSIC',
            '030a': 'THX MUSIC',
            '030b': 'PLIIx GAME +THX',
            '030c': 'PLII GAME +THX',
            '030d': 'PL +THX GAMES',
            '0310': 'THX GAMES',
            '0311': 'PLIIz +THX CINEMA',
            '0312': 'PLIIz +THX MUSIC',
            '0313': 'PLIIz +THX GAMES',
            '0314': 'Neo:X CINEMA + THX CINEMA',
            '0315': 'Neo:X MUSIC + THX MUSIC',
            '0316': 'Neo:X GAMES + THX GAMES',
            '1301': 'THX Surr EX',
            '1303': 'ES MTRX +THX CINEMA',
            '1304': 'ES DISC +THX CINEMA',
            '1305': 'ES 8ch +THX CINEMA',
            '1306': 'PLIIx MOVIE +THX',
            '1309': 'THX CINEMA',
            '130b': 'ES MTRX +THX MUSIC',
            '130c': 'ES DISC +THX MUSIC',
            '130d': 'ES 8ch +THX MUSIC',
            '130e': 'PLIIx MUSIC +THX',
            '1311': 'THX MUSIC',
            '1313': 'ES MTRX +THX GAMES',
            '1314': 'ES DISC +THX GAMES',
            '1315': 'ES 8ch +THX GAMES',
            '1319': 'THX GAMES',
            '131a': 'PLIIz +THX CINEMA',
            '131b': 'PLIIz +THX MUSIC',
            '131c': 'PLIIz +THX GAMES',
            '131d': 'Neo:X CINEMA + THX CINEMA',
            '131e': 'Neo:X MUSIC + THX MUSIC',
            '131f': 'Neo:X GAME + THX GAMES',
            '0401': 'STEREO',
            '0402': 'PLII MOVIE',
            '0403': 'PLIIx MOVIE',
            '0405': 'AUTO SURROUND Straight Decode',
            '0406': 'DIGITAL EX',
            '0407': 'PLIIx MOVIE',
            '0408': 'DTS +Neo:6',
            '0409': 'ES MATRIX',
            '040a': 'ES DISCRETE',
            '040b': 'DTS-ES 8ch',
            '040e': 'RETRIEVER AIR',
            '040f': 'Neo:X CINEMA',
            '0501': 'STEREO',
            '0502': 'PLII MOVIE',
            '0503': 'PLIIx MOVIE',
            '0504': 'DTS/DTS-HD',
            '0505': 'ALC Straight Decode',
            '0506': 'DIGITAL EX',
            '0507': 'PLIIx MOVIE',
            '0508': 'DTS +Neo:6',
            '0509': 'ES MATRIX',
            '050a': 'ES DISCRETE',
            '050b': 'DTS-ES 8ch',
            '050e': 'RETRIEVER AIR',
            '050f': 'Neo:X CINEMA',
            '0601': 'STEREO',
            '0602': 'PLII MOVIE',
            '0603': 'PLIIx MOVIE',
            '0605': 'STREAM DIRECT NORMAL Straight Decode',
            '0606': 'DIGITAL EX',
            '0607': 'PLIIx MOVIE',
            '0609': 'ES MATRIX',
            '060a': 'ES DISCRETE',
            '060b': 'DTS-ES 8ch',
            '060c': 'Neo:X CINEMA',
            '0701': 'STREAM DIRECT PURE 2ch',
            '0702': 'PLII MOVIE',
            '0703': 'PLIIx MOVIE',
            '0704': 'Neo:6 CINEMA',
            '0705': 'STREAM DIRECT PURE Straight Decode',
            '0706': 'DIGITAL EX',
            '0707': 'PLIIx MOVIE',
            '0708': '(nothing)',
            '0709': 'ES MATRIX',
            '070a': 'ES DISCRETE',
            '070b': 'DTS-ES 8ch',
            '070c': 'Neo:X CINEMA',
            '0881': 'OPTIMUM',
            '0e01': 'HDMI THROUGH',
            '0f01': 'MULTI CH IN'
        }
    },
    'SC-LX87': {
        'INPUT': {
            '10': 'VIDEO 1(VIDEO)',
            '35': 'HDMI 8',
            '41': 'PANDORA',
            '13': 'USB-DAC',
            '00': 'PHONO',
            '12': 'MULTI CH IN'
        },
        'INPUT2': {
            '10': 'VIDEO 1 (VIDEO)',
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '13': 'USB-DAC',
            '17': 'iPod/USB'
        },
        'INPUT3': {
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '13': 'USB-DAC',
            '17': 'iPod/USB'
        },
        'INPUTHD': {
            '10': 'VIDEO 1 (VIDEO)',
            '35': 'HDMI 8'
        },
        'SPEAKERSYSTEM': {
            '10': '9.1ch FH/FW',
            '11': '7.1ch + Speaker B',
            '12': '7.1ch Front Bi-Amp',
            '13': '7.1ch + Zone2',
            '14': '7.1ch FH/FW + Zone2',
            '15': '5.1ch Bi-Amp + Zone2',
            '16': '5.1ch + Zone 2+3',
            '17': '5.1ch + SP-B Bi-Amp',
            '18': '5.1ch F+Surr Bi-Amp',
            '19': '5.1ch F+C Bi-Amp',
            '20': '5.1ch C+Surr Bi-Amp',
            '21': 'Multi-ZONE Music'
        },
        'LISTENINGMODE': {
            '0050': 'THX (cyclic)',
            '0051': 'PROLOGIC + THX CINEMA',
            '0052': 'PL2 MOVIE + THX CINEMA',
            '0054': 'PL2x MOVIE + THX CINEMA',
            '0092': 'PL2z HEIGHT + THX CINEMA',
            '0068': 'THX CINEMA (for 2ch)',
            '0069': 'THX MUSIC (for 2ch)',
            '0070': 'THX GAMES (for 2ch)',
            '0071': 'PL2 MUSIC + THX MUSIC',
            '0072': 'PL2x MUSIC + THX MUSIC',
            '0093': 'PL2z HEIGHT + THX MUSIC',
            '0074': 'PL2 GAME + THX GAMES',
            '0075': 'PL2x GAME + THX GAMES',
            '0094': 'PL2z HEIGHT + THX GAMES',
            '0201': 'Neo:X CINEMA + THX CINEMA',
            '0202': 'Neo:X MUSIC + THX MUSIC',
            '0203': 'Neo:X GAME + THX GAMES',
            '0056': 'THX CINEMA (for multi ch)',
            '0057': 'THX SURROUND EX (for multi ch)',
            '0058': 'PL2x MOVIE + THX CINEMA (for multi ch)',
            '0095': 'PL2z HEIGHT + THX CINEMA (for multi ch)',
            '0060': 'ES MATRIX + THX CINEMA (for multi ch)',
            '0061': 'ES DISCRETE + THX CINEMA (for multi ch)',
            '0067': 'ES 8ch DISCRETE + THX CINEMA (for multi ch)',
            '0080': 'THX MUSIC (for multi ch)',
            '0081': 'THX GAMES (for multi ch)',
            '0082': 'PL2x MUSIC + THX MUSIC (for multi ch)',
            '0096': 'PL2z HEIGHT + THX MUSIC (for multi ch)',
            '0097': 'PL2z HEIGHT + THX GAMES (for multi ch)',
            '0086': 'ES MATRIX + THX MUSIC (for multi ch)',
            '0087': 'ES MATRIX + THX GAMES (for multi ch)',
            '0088': 'ES DISCRETE + THX MUSIC (for multi ch)',
            '0089': 'ES DISCRETE + THX GAMES (for multi ch)',
            '0090': 'ES 8CH DISCRETE + THX MUSIC (for multi ch)',
            '0091': 'ES 8CH DISCRETE + THX GAMES (for multi ch)',
            '0204': 'Neo:X CINEMA + THX CINEMA (for multi ch)',
            '0205': 'Neo:X MUSIC + THX MUSIC (for multi ch)',
            '0206': 'Neo:X GAME + THX GAMES (for multi ch)',
            '0152': 'OPTIMUM SURROUND'
        }
    },
    'SC-LX77': {
        'INPUT': {
            '10': 'VIDEO 1(VIDEO)',
            '35': 'HDMI 8',
            '00': 'PHONO'
        },
        'INPUT2': {
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB'
        },
        'INPUT3': {
            '10': 'VIDEO 1 (VIDEO)',
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB'
        },
        'INPUTHD': {
            '10': 'VIDEO 1 (VIDEO)',
            '35': 'HDMI 8'
        },
        'SPEAKERSYSTEM': {
            '10': '9.1ch FH/FW',
            '11': '7.1ch + Speaker B',
            '12': '7.1ch Front Bi-Amp',
            '13': '7.1ch + Zone2',
            '14': '7.1ch FH/FW + Zone2',
            '15': '5.1ch Bi-Amp + Zone2',
            '16': '5.1ch + Zone 2+3',
            '17': '5.1ch + SP-B Bi-Amp',
            '18': '5.1ch F+Surr Bi-Amp',
            '19': '5.1ch F+C Bi-Amp',
            '20': '5.1ch C+Surr Bi-Amp',
            '21': 'Multi-ZONE Music'
        },
        'LISTENINGMODE': {
            '0050': 'THX (cyclic)',
            '0051': 'PROLOGIC + THX CINEMA',
            '0052': 'PL2 MOVIE + THX CINEMA',
            '0054': 'PL2x MOVIE + THX CINEMA',
            '0092': 'PL2z HEIGHT + THX CINEMA',
            '0068': 'THX CINEMA (for 2ch)',
            '0069': 'THX MUSIC (for 2ch)',
            '0070': 'THX GAMES (for 2ch)',
            '0071': 'PL2 MUSIC + THX MUSIC',
            '0072': 'PL2x MUSIC + THX MUSIC',
            '0093': 'PL2z HEIGHT + THX MUSIC',
            '0074': 'PL2 GAME + THX GAMES',
            '0075': 'PL2x GAME + THX GAMES',
            '0094': 'PL2z HEIGHT + THX GAMES',
            '0201': 'Neo:X CINEMA + THX CINEMA',
            '0202': 'Neo:X MUSIC + THX MUSIC',
            '0203': 'Neo:X GAME + THX GAMES',
            '0056': 'THX CINEMA (for multi ch)',
            '0057': 'THX SURROUND EX (for multi ch)',
            '0058': 'PL2x MOVIE + THX CINEMA (for multi ch)',
            '0095': 'PL2z HEIGHT + THX CINEMA (for multi ch)',
            '0060': 'ES MATRIX + THX CINEMA (for multi ch)',
            '0061': 'ES DISCRETE + THX CINEMA (for multi ch)',
            '0067': 'ES 8ch DISCRETE + THX CINEMA (for multi ch)',
            '0080': 'THX MUSIC (for multi ch)',
            '0081': 'THX GAMES (for multi ch)',
            '0082': 'PL2x MUSIC + THX MUSIC (for multi ch)',
            '0096': 'PL2z HEIGHT + THX MUSIC (for multi ch)',
            '0097': 'PL2z HEIGHT + THX GAMES (for multi ch)',
            '0086': 'ES MATRIX + THX MUSIC (for multi ch)',
            '0087': 'ES MATRIX + THX GAMES (for multi ch)',
            '0088': 'ES DISCRETE + THX MUSIC (for multi ch)',
            '0089': 'ES DISCRETE + THX GAMES (for multi ch)',
            '0090': 'ES 8CH DISCRETE + THX MUSIC (for multi ch)',
            '0091': 'ES 8CH DISCRETE + THX GAMES (for multi ch)',
            '0204': 'Neo:X CINEMA + THX CINEMA (for multi ch)',
            '0205': 'Neo:X MUSIC + THX MUSIC (for multi ch)',
            '0206': 'Neo:X GAME + THX GAMES (for multi ch)',
            '0152': 'OPTIMUM SURROUND'
        }
    },
    'SC-LX57': {
        'INPUT': {
            '10': 'VIDEO 1(VIDEO)',
            '35': 'HDMI 8'
        },
        'INPUT2': {
            '10': 'VIDEO 1 (VIDEO)',
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB'
        },
        'INPUTHD': {
            '10': 'VIDEO 1 (VIDEO)',
            '35': 'HDMI 8'
        },
        'SPEAKERSYSTEM': {
            '10': '9.1ch FH/FW',
            '11': '7.1ch + Speaker B',
            '12': '7.1ch Front Bi-Amp',
            '13': '7.1ch + Zone2',
            '14': '7.1ch FH/FW + Zone2',
            '15': '5.1ch Bi-Amp + Zone2',
            '16': '5.1ch + Zone 2+3',
            '17': '5.1ch + SP-B Bi-Amp',
            '18': '5.1ch F+Surr Bi-Amp',
            '19': '5.1ch F+C Bi-Amp',
            '20': '5.1ch C+Surr Bi-Amp',
            '21': 'Multi-ZONE Music'
        },
        'LISTENINGMODE': {
            '0050': 'THX (cyclic)',
            '0051': 'PROLOGIC + THX CINEMA',
            '0052': 'PL2 MOVIE + THX CINEMA',
            '0054': 'PL2x MOVIE + THX CINEMA',
            '0092': 'PL2z HEIGHT + THX CINEMA',
            '0068': 'THX CINEMA (for 2ch)',
            '0069': 'THX MUSIC (for 2ch)',
            '0070': 'THX GAMES (for 2ch)',
            '0071': 'PL2 MUSIC + THX MUSIC',
            '0072': 'PL2x MUSIC + THX MUSIC',
            '0093': 'PL2z HEIGHT + THX MUSIC',
            '0074': 'PL2 GAME + THX GAMES',
            '0075': 'PL2x GAME + THX GAMES',
            '0094': 'PL2z HEIGHT + THX GAMES',
            '0201': 'Neo:X CINEMA + THX CINEMA',
            '0202': 'Neo:X MUSIC + THX MUSIC',
            '0203': 'Neo:X GAME + THX GAMES',
            '0056': 'THX CINEMA (for multi ch)',
            '0057': 'THX SURROUND EX (for multi ch)',
            '0058': 'PL2x MOVIE + THX CINEMA (for multi ch)',
            '0095': 'PL2z HEIGHT + THX CINEMA (for multi ch)',
            '0060': 'ES MATRIX + THX CINEMA (for multi ch)',
            '0061': 'ES DISCRETE + THX CINEMA (for multi ch)',
            '0067': 'ES 8ch DISCRETE + THX CINEMA (for multi ch)',
            '0080': 'THX MUSIC (for multi ch)',
            '0081': 'THX GAMES (for multi ch)',
            '0082': 'PL2x MUSIC + THX MUSIC (for multi ch)',
            '0096': 'PL2z HEIGHT + THX MUSIC (for multi ch)',
            '0097': 'PL2z HEIGHT + THX GAMES (for multi ch)',
            '0086': 'ES MATRIX + THX MUSIC (for multi ch)',
            '0087': 'ES MATRIX + THX GAMES (for multi ch)',
            '0088': 'ES DISCRETE + THX MUSIC (for multi ch)',
            '0089': 'ES DISCRETE + THX GAMES (for multi ch)',
            '0090': 'ES 8CH DISCRETE + THX MUSIC (for multi ch)',
            '0091': 'ES 8CH DISCRETE + THX GAMES (for multi ch)',
            '0204': 'Neo:X CINEMA + THX CINEMA (for multi ch)',
            '0205': 'Neo:X MUSIC + THX MUSIC (for multi ch)',
            '0206': 'Neo:X GAME + THX GAMES (for multi ch)',
            '0152': 'OPTIMUM SURROUND'
        }
    },
    'SC-2023': {
        'INPUT': {
            '10': 'VIDEO 1(VIDEO)',
            '41': 'PANDORA'
        },
        'INPUT2': {
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '41': 'PANDORA',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB'
        },
        'INPUTHD': {
            '10': 'VIDEO 1 (VIDEO)'
        }
    },
    'SC-1223': {
        'INPUT2': {
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '17': 'iPod/USB'
        }
    },
    'SC-1123': {
        'INPUT2': {
            '41': 'PANDORA',
            '44': 'MEDIA SERVER',
            '45': 'FAVORITES',
            '26': 'NETWORK (cyclic)',
            '38': 'INTERNET RADIO',
            '17': 'iPod/USB'
        }
    },
    'UNKNOWN': {
        'LISTENINGMODE': {
            '0011': '(2ch source)',
            '0016': 'Neo:6 CINEMA',
            '0017': 'Neo:6 MUSIC',
            '0025': '(Multi ch source)DTS-ES Neo:6',
            '0053': 'Neo:6 CINEMA + THX CINEMA',
            '0055': 'THX SELECT2 GAMES',
            '0073': 'Neo:6 MUSIC + THX MUSIC',
            '0076': 'THX ULTRA2 GAMES',
            '0077': 'PROLOGIC + THX MUSIC',
            '0078': 'PROLOGIC + THX GAMES',
            '0059': 'ES Neo:6 + THX CINEMA (for multi ch)',
            '0083': 'EX + THX GAMES (for multi ch)',
            '0084': 'Neo:6 + THX MUSIC (for multi ch)',
            '0085': 'Neo:6 + THX GAMES (for multi ch)',
            '0086': 'ES MATRIX + THX MUSIC (for multi ch)'
        },
        'INPUT': {
            '40': 'SiriusXM'
        }
    }
}

item_templates = {
    'speakers': {
        'on_change': ['.speakera = True if value in [1, 3] else False', '.speakerb = True if value in [2, 3] else False'],
        'speakera': {
            'type': 'bool',
            'on_change': '...speakers = None if sh..self.changed_by().startswith("On_Change") else sh....speakers() - 1 if value is False else sh....speakers() + 1'
            },
        'speakerb': {
            'type': 'bool',
            'on_change': '...speakers = None if sh..self.changed_by().startswith("On_Change") else sh....speakers() - 2 if value is False else sh....speakers() + 2'
            }
    },
    'power': {
        'pioneer_read_initial': True,
        'on_change': 'sh....read.timer(sh..readdelay(), True) if value else None',
        'readdelay': {
            'type': 'num',
            'initial_value': 1,
            'remark': 'After turning on a zone, the most likely needs some time to react to read commands. If not, set this value to 0'
        }
    },
    'tone': {
        'pioneer_read_initial': True,
        'on_change': 'sh...read(True) if value else None'
    }
}
