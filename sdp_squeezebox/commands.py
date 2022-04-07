#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

# commands for dev squeezebox


commands = {
    'server': {
        'listenmode': {'read': True, 'write': True, 'write_cmd': 'listen {RAW_VALUE:01}', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': r'listen (\d)', 'item_attrs': {'custom1': ''}},
        'playercount': {'read': True, 'write': False, 'read_cmd': 'player count ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'player count (\d+)', 'item_attrs': {'initial': True, 'custom1': ''}},
        'favoritescount': {'read': True, 'write': False, 'read_cmd': 'favorites items', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'favorites items\s+ count:(\d+)', 'item_attrs': {'initial': True, 'custom1': ''}},
    },
    'database': {
        'rescan': {
            'start': {'read': False, 'write': True, 'write_cmd': 'rescan {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'item_attrs': {'custom1': ''}},
            'running': {'read': True, 'write': False, 'read_cmd': 'rescan ?', 'item_type': 'bool', 'dev_datatype': 'SqueezeRescan', 'reply_pattern': 'rescan (.*)', 'item_attrs': {'initial': True, 'custom1': ''}},
            'progress': {'read': True, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'scanner notify progress:(.*)', 'item_attrs': {'custom1': ''}},
            'runningtime': {'read': True, 'read_cmd': 'rescanprogress totaltime', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'rescanprogress totaltime .* totaltime:([0-9]{2}:[0-9]{2}:[0-9]{2})', 'item_attrs': {'custom1': ''}},
            'fail': {'read': True, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': 'rescanprogress totaltime rescan:0 lastscanfailed:(.*)', 'item_attrs': {'custom1': ''}},
            'abortscan': {'read': True, 'write': True, 'write_cmd': 'abortscan', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': 'abortscan', 'item_attrs': {'custom1': ''}},
            'wipecache': {'read': True, 'write': True, 'write_cmd': 'wipecache', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': 'wipecache', 'item_attrs': {'custom1': ''}}
        },
        'totalgenres': {'read': True, 'write': False, 'read_cmd': 'info total genres ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'info total genres (\d+)', 'item_attrs': {'initial': True, 'custom1': ''}},
        'totalduration': {'read': True, 'write': False, 'read_cmd': 'info total duration ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'info total duration ([0-9.]*)', 'item_attrs': {'initial': True, 'custom1': ''}},
        'totalartists': {'read': True, 'write': False, 'read_cmd': 'info total artists ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'info total artists (\d+)', 'item_attrs': {'initial': True, 'custom1': ''}},
        'totalalbums': {'read': True, 'write': False, 'read_cmd': 'info total albums ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'info total albums (\d+)', 'item_attrs': {'initial': True, 'custom1': ''}},
        'totalsongs': {'read': True, 'write': False, 'read_cmd': 'info total songs ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'info total songs (\d+)', 'item_attrs': {'initial': True, 'custom1': ''}}
    },
    'player': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} power ?', 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} power {RAW_VALUE:01}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:prefset server\s)?power (\d)', 'item_attrs': {'initial': True}},
            'playmode': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mode ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} mode {VALUE}', 'dev_datatype': 'SqueezePlayMode', 'cmd_settings': {'valid_list_ci': ['PLAY', 'PAUSE', 'STOP']}, 'reply_pattern': r'{CUSTOM_PATTERN1} (?:mode|playlist) (play$|pause\s?\d?|stop$)', 'item_attrs': {'initial': True}},
            'playpause': {'read': True, 'write': True, 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'SqueezePlay', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:playlist\s)?(play|pause)(?:\s3)?$'},
            'stop': {'read': True, 'write': True, 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'SqueezeStop', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:playlist\s)?(stop)$'},
            'mute': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mixer muting ?', 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} mixer muting {RAW_VALUE:01}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:mixer muting|prefset server mute) (\d)', 'item_attrs': {'initial': True}},
            'volume': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mixer volume ?', 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:mixer volume |prefset server volume \-?)(\d{1,3})', 'item_attrs': {'initial': True}},
            'volume_fading': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'item_template': 'volume_fading'}},
            'volume_low': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 60}}},
            'volume_high': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 80}}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume +{VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 1}}},
            'volumedown': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume -{VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 1}}},
            'set_alarm': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} alarm {VALUE}', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} alarm (.*)'},
            'alarms': {'read': True, 'write': False, 'item_type': 'dict', 'read_cmd': '{CUSTOM_ATTR1} alarms 0 100 all', 'dev_datatype': 'SqueezeAlarms', 'reply_pattern': r'{CUSTOM_PATTERN1} alarms 0 100 all fade:\d+ count:\d+ (.*)', 'item_attrs': {'initial': True, 'read_groups': [{'name': 'player.control.alarms', 'trigger': 'query'}]}},
            'sync': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} sync ?', 'write_cmd': '{CUSTOM_ATTR1} sync {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} sync (.*)', 'item_attrs': {'initial': True}},
            'unsync': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} sync -', 'item_type': 'bool', 'dev_datatype': 'str'},
            'display': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} display ? ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} display {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} display\s?(.*)', 'item_attrs': {'initial': True}},
            'connect': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} connect {VALUE}', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} connect (.*)'},
            'disconnect': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': 'disconnect {CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'str', 'reply_pattern': 'disconnect {CUSTOM_PATTERN1} (.*)'},
            'time': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} time ?', 'write_cmd': '{CUSTOM_ATTR1} time {VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} time (\d+(?:\.\d{2})?)', 'item_attrs': {'item_template': 'time', 'enforce': True, 'read_groups': [{'name': 'player.control.time_poll', 'trigger': 'poll'}]}},
            'forward': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} time +{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} time \+(\d+(?:\.\d{2})?)', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 10}}},
            'rewind': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} time -{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} time \-(\d+(?:\.\d{2})?)', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 10}}},
            'playsong': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist play {VALUE}', 'item_type': 'str', 'dev_datatype': 'str'},
            'sleep': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} sleep ?', 'write_cmd': '{CUSTOM_ATTR1} sleep {VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} sleep (.*[^?])', 'item_attrs': {'initial': True}}
        },
        'playlist': {
            'repeat': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist repeat ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} playlist repeat {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} playlist repeat {LOOKUP}', 'lookup': 'REPEAT', 'item_attrs': {'initial': True,  'attributes': {'remark': '0 = Off, 1 = Song, 2 = Playlist'}, 'lookup_item': True}},
            'shuffle': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist shuffle ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} playlist shuffle {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} playlist shuffle {LOOKUP}', 'lookup': 'SHUFFLE', 'item_attrs': {'initial': True,  'attributes': {'remark': '0 = Off, 1 = Song, 2 = Album'}, 'lookup_item': True}},
            'index': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist index ?', 'write_cmd': '{CUSTOM_ATTR1} playlist index {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} playlist (?:index|newsong .*) (\d+)$', 'item_attrs': {'initial': True}},
            'name': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist name ?', 'write_cmd': '{CUSTOM_ATTR1} playlist name {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist name (.*[^?])', 'item_attrs': {'initial': True}},
            'id': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} status - 1', 'write_cmd': '{CUSTOM_ATTR1} playlistcontrol cmd:load playlist_id:{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:status - 1 .*|playlist playlistsinfo |playlistcontrol cmd:load playlist_)id:(\d+)'},
            'save': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist save {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist save (.*)'},
            'load': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist resume {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist resume (.*)'},
            'loadalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist loadalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist loadalbum (.*)'},
            'loadtracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist loadtracks {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist loadtracks (.*)'},
            'add': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist add {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist add (.*)'},
            'addalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist addalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist addalbum (.*)'},
            'addtracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist addtracks {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist addtracks (.*)'},
            'insertalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist insertalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist insertalbum (.*)'},
            'inserttracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist insert {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist insert (.*)'},
            'tracks': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} playlist tracks ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist tracks (.*[^?])', 'item_attrs': {'initial': True}},
            'clear': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist clear', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist clear$', 'item_attrs': {'enforce': True, 'attributes': {'eval': 'True if value else None'}}},
            'delete': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist delete {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist delete (.*)'},
            'deleteitem': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist deleteitem {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist deleteitem (.*)'},
            'deletealbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist deletealbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist deletealbum (.*)'},
            'preview': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist preview {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} playlist preview (.*)'},
            'next': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist index +{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 1}}},
            'previous': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist index -{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 1}}},
            'customskip': {'read': False, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} customskip setfilter filter{VALUE}.cs.xml', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True}}}
        },
        'info': {
            'connected': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} connected ?', 'item_type': 'bool', 'dev_datatype': 'SqueezeConnection', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:connected|client) (\d|disconnect|reconnect)', 'item_attrs': {'initial': True}},
            'name': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} name ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} name (.*)', 'item_attrs': {'initial': True}},
            'syncgroups': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} syncgroups ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} syncgroups (\d+)', 'item_attrs': {'initial': True}},
            'signalstrength': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} signalstrength ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} signalstrength (\d+)', 'item_attrs': {'initial': True}},
            'genre': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} genre ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} genre (.*)'},
            'artist': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} artist ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} artist (.*)'},
            'album': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} album ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} album (.*)', 'item_attrs': {'initial': True}},
            'title': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} current_title ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} (?:current_title|playlist newsong) (.*?)(?:\s\d+)?$', 'item_attrs': {'initial': True}},
            'path': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} path ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '{CUSTOM_PATTERN1} path (.*)'},
            'duration': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} duration ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'{CUSTOM_PATTERN1} duration (\d+)'},
            'albumarturl': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '(http://.*)'}
        }
    }
}

lookups = {
    'REPEAT': {
        '0': 'OFF',
        '1': 'SONG',
        '2': 'PLAYLIST'
    },
    'SHUFFLE': {
        '0': 'OFF',
        '1': 'SONG',
        '2': 'ALBUM'
    }
}

item_templates = {
    'time': {
        'poll':
            {
                'type': 'bool',
                'eval': 'True if sh....playmode() == "play" else None',
                'enforce_updates': True,
                'cycle': '10 = True',
                'sqb_read_group_trigger': 'player.control.time_poll'
            }
    },
    'volume_fading': {
        'goal': {
            'type': 'num',
            'visu_acl': 'rw',
            'cache': 'True'
        }
    }
}
