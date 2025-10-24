#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

""" commands for dev kodi """

commands = {
    'info': {
        'player':           {'read': True,  'write': False, 'opcode': 'player',                    'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'state':            {'read': True,  'write': False, 'opcode': 'media',                     'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'media':            {'read': True,  'write': False, 'opcode': 'media',                     'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'title':            {'read': True,  'write': False, 'opcode': 'title',                     'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'streams':          {'read': True,  'write': False, 'opcode': 'streams',                   'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'subtitles':        {'read': True,  'write': False, 'opcode': 'subtitles',                 'reply_pattern': '*', 'item_type': 'list', 'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'macro':            {'read': True,  'write': True,  'opcode': 'macro',                     'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
    },
    'status': {
        'update':           {'read': False, 'write': True,  'opcode': 'update',                    'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None},
        'ping':             {'read': True,  'write': False, 'opcode': 'JSONRPC.Ping',              'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None},
        'get_status_au':    {'read': True,  'write': False, 'opcode': 'Application.GetProperties', 'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'properties': ['volume', 'muted']}},
        'get_actplayer':    {'read': True,  'write': False, 'opcode': 'Player.GetActivePlayers',   'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None},
        'get_settings':     {'read': True,  'write': False, 'opcode': 'Settings.GetSettings',      'reply_pattern': '*', 'item_type': 'dict', 'dev_datatype': 'raw', 'params': None},
        'get_status_play':  {'read': True,  'write': False, 'opcode': 'Player.GetProperties',      'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'properties': ['type', 'speed', 'time', 'percentage', 'totaltime', 'position', 'currentaudiostream', 'audiostreams', 'subtitleenabled', 'currentsubtitle', 'subtitles', 'currentvideostream', 'videostreams']}},
        'get_item':         {'read': True,  'write': False, 'opcode': 'Player.GetItem',            'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'properties': ['title', 'artist']}},
        'get_favourites':   {'read': True,  'write': False, 'opcode': 'Favourites.GetFavourites',  'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'properties': ['window', 'path', 'thumbnail', 'windowparameter']}},
    },
    'control': {
        'playpause':        {'read': True,  'write': True,  'opcode': 'Player.PlayPause',          'reply_pattern': r'{\'speed\': (\d)}', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'play': 'toggle'}, 'item_attrs': {'read_group_levels': 0}},
        'seek':             {'read': True,  'write': True,  'opcode': 'Player.Seek',               'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'value': '{VALUE}'}, 'cmd_settings': {'force_min': 0.0, 'force_max': 100.0}, 'item_attrs': {'read_group_levels': 0}},
        'audio':            {'read': True,  'write': True,  'opcode': 'Player.SetAudioStream',     'reply_pattern': '*', 'item_type': 'foo',  'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'stream': '{VALUE}'}, 'item_attrs': {'read_group_levels': 0}},
        'speed':            {'read': True,  'write': True,  'opcode': 'Player.SetSpeed',           'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'speed': '{VALUE}'}, 'cmd_settings': {'valid_list': [-32,-16,-8,-4,-2,-1,1,2,4,8,16,32]}, 'item_attrs': {'read_group_levels': 0}},
        'subtitle':         {'read': True,  'write': True,  'opcode': 'Player.SetSubtitle',        'reply_pattern': '*', 'item_type': 'foo',  'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'subtitle': '{VALUE}', 'enable': ('False if "VAL"=="off" else True',)}, 'item_attrs': {'read_group_levels': 0}},
        'stop':             {'read': True,  'write': True,  'opcode': 'Player.Stop',               'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'playerid': '{ID}'}, 'item_attrs': {'read_group_levels': 0}},
        'goto':             {'read': True,  'write': True,  'opcode': 'Player.GoTo',               'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'raw', 'params': {'playerid': '{ID}', 'to': '{VALUE}'}, 'cmd_settings': {'valid_list': ['previous','next']}, 'item_attrs': {'read_group_levels': 0}},
        'power':            {'read': True,  'write': True,  'opcode': 'System.Shutdown',           'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'quit':             {'read': True,  'write': True,  'opcode': 'Application.Quit',          'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': None, 'item_attrs': {'read_group_levels': 0}},
        'mute':             {'read': True,  'write': True,  'opcode': 'Application.SetMute',       'reply_pattern': '*', 'item_type': 'bool', 'dev_datatype': 'raw', 'params': {'mute': '{VALUE}'}, 'item_attrs': {'read_group_levels': 0}},
        'volume':           {'read': True,  'write': True,  'opcode': 'Application.SetVolume',     'reply_pattern': '*', 'item_type': 'num',  'dev_datatype': 'raw', 'params': {'volume': '{VALUE}'}, 'cmd_settings': {'force_min': 0, 'force_max': 100}, 'item_attrs': {'read_group_levels': 0}},
        'action':           {'read': True,  'write': True,  'opcode': 'Input.ExecuteAction',       'reply_pattern': '*', 'item_type': 'str',  'dev_datatype': 'raw', 'params': {'action': '{VALUE}'}, 'cmd_settings': {'valid_list': ['left','right','up','down','select','back','menu','info','pause','stop','skipnext','skipprevious','fullscreen','aspectratio','stepforward','stepback','osd','showsubtitles','nextsubtitle','cyclesubtitle','audionextlanguage','number1','number2','number3','number4','number5','number6','number7','number8','number9','fastforward','rewind','play','playpause','volumeup','volumedown','mute','enter']}, 'item_attrs': {'read_group_levels': 0}}
    }

}
