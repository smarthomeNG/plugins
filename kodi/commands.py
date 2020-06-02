#   'commandname':  {'method': command for JSON-RPC,        'set': writa,   'get': use retval, param': names of params,                   'values': param values,ID=playerid,VAL=data,tuple="eval"       'bounds': optional bounds, tuple is range, list is valid items}

commands = {
    'update':         {'special': True, 'set': True},  # call-only item to trigger update of all status fields
    'player':         {'special': True, 'set': False},  # stores player_id
    'state':          {'special': True, 'set': False},  # stores kodi state
    'media':          {'special': True, 'set': False},  # stores media type
    'title':          {'special': True, 'set': False},  # stores media title
    'streams':        {'special': True, 'set': False},  # stores available audio streams
    'subtitles':      {'special': True, 'set': False},  # stores available subtitles
    'macro':          {'special': True, 'set': True},  # triggers macro evaluation

    'ping':           {'method': 'JSONRPC.Ping',              'set': False,   'get': True,    'params': None,                               'values': None,                                                'bounds': None},
    'get_status_au':  {'method': 'Application.GetProperties', 'set': False,   'get': True,    'params': ['properties'],                     'values': [['volume', 'muted']],                               'bounds': None},
    'get_players':    {'method': 'Player.GetPlayers',         'set': False,   'get': True,    'params': None,                               'values': None,                                                'bounds': None},
    'get_actplayer':  {'method': 'Player.GetActivePlayers',   'set': False,   'get': True,    'params': None,                               'values': None,                                                'bounds': None},
    'get_status_play':{'method': 'Player.GetProperties',      'set': False,   'get': True,    'params': ['playerid', 'properties'],         'values': ['ID', ['type', 'speed', 'time', 'percentage', 'totaltime', 'position', 'currentaudiostream', 'audiostreams', 'subtitleenabled', 'currentsubtitle', 'subtitles', 'currentvideostream', 'videostreams']], 'bounds': None},
    'get_item':       {'method': 'Player.GetItem',            'set': False,   'get': True,    'params': ['playerid', 'properties'],         'values': ['ID', ['title', 'artist']],                         'bounds': None},
    'get_favourites': {'method': 'Favourites.GetFavourites',  'set': False,   'get': True,    'params': ['properties'],                     'values': [['window', 'path', 'thumbnail', 'windowparameter']],'bounds': None},

    'playpause':      {'method': 'Player.PlayPause',          'set': True,    'get': False,   'params': ['playerid', 'play'],               'values': ['ID', 'toggle'],                                    'bounds': None},
    'seek':           {'method': 'Player.Seek',               'set': True,    'get': False,   'params': ['playerid', 'value'],              'values': ['ID', 'VAL'],                                       'bounds': (0.0, 100.0)},
    'audio':          {'method': 'Player.SetAudioStream',     'set': True,    'get': False,   'params': ['playerid', 'stream'],             'values': ['ID', 'VAL'],                                       'bounds': None},
    'speed':          {'method': 'Player.SetSpeed',           'set': True,    'get': False,   'params': ['playerid', 'speed'],              'values': ['ID', 'VAL'],                                       'bounds': [-32,-16,-8,-4,-2,-1,1,2,4,8,16,32]},
    'subtitle':       {'method': 'Player.SetSubtitle',        'set': True,    'get': False,   'params': ['playerid', 'subtitle', 'enable'], 'values': ['ID', 'VAL', ('False if "VAL"=="off" else True',)],    'bounds': None},
    'stop':           {'method': 'Player.Stop',               'set': True,    'get': False,   'params': ['playerid'],                       'values': ['ID'],                                              'bounds': None},
    'goto':           {'method': 'Player.GoTo',               'set': True,    'get': False,   'params': ['playerid', 'to'],                 'values': ['ID', 'VAL'],                                       'bounds': ['previous','next']},
    'power':          {'method': 'System.Shutdown',           'set': True,    'get': False,   'params': None,                               'values': None,                                                'bounds': None},
    'quit':           {'method': 'Application.Quit',          'set': True,    'get': False,   'params': None,                               'values': None,                                                'bounds': None},
    'mute':           {'method': 'Application.SetMute',       'set': True,    'get': False,   'params': ['mute'],                           'values': ['VAL'],                                             'bounds': None},
    'volume':         {'method': 'Application.SetVolume',     'set': True,    'get': False,   'params': ['volume'],                         'values': ['VAL'],                                             'bounds': (0, 100)},
    'action':         {'method': 'Input.ExecuteAction',       'set': True,    'get': False,   'params': ['action'],                         'values': ['VAL'],                                             'bounds': ['left','right','up','down','select','back','menu','info','pause','stop','skipnext','skipprevious','fullscreen','aspectratio','stepforward','stepback','osd','showsubtitles','nextsubtitle','cyclesubtitle','audionextlanguage','number1','number2','number3','number4','number5','number6','number7','number8','number9','fastforward','rewind','play','playpause','volumeup','volumedown','mute','enter']},
}

# 'macroname': [ [cmd1, val1], [cmd2, val2], [cmd3, val3], ...]. -- cmd can be one of commands.keys() or 'wait' to wait 'val' seconds
macros = {
    'resume': [['action', 'play'], ['wait', 1], ['action', 'select']],
    'beginning': [['action', 'play'], ['wait', 1], ['action', 'down'], ['action', 'select']]
}