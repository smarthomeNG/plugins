#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

# commands for dev LMS/squeezebox


commands = {
    'server': {
        'version': {'read': True, 'write': False, 'read_cmd': 'version ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^version (.*)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'restart': {'read': False, 'write': True, 'write_cmd': 'restartserver', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': r'^restartserver', 'custom_disabled': True, 'item_attrs': {'attributes': {'autotimer': '1s = 0'}}},
        'listenmode': {'read': True, 'write': True, 'write_cmd': 'listen {RAW_VALUE:01}', 'item_type': 'bool', 'dev_datatype': 'LMSonoff', 'reply_pattern': r'^listen (\d)', 'custom_disabled': True},
        'playercount': {'read': True, 'write': False, 'read_cmd': 'player count ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': [r'^player count (\d+)', r'^players 0 100 count:(\d+) '], 'custom_disabled': True},
        'favoritescount': {'read': True, 'write': False, 'read_cmd': 'favorites items', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^favorites items\s+count:(\d+)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'syncgroups': {
            'members': {'read': True, 'write': False, 'read_cmd': 'syncgroups ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^syncgroups sync_members:(.*) sync_member_names:', r'^syncgroups(.*)?$'], 'custom_disabled': True, 'item_attrs': {'initial': True}},
            'names': {'read': True, 'write': False, 'read_cmd': 'syncgroups ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^syncgroups sync_members:.* sync_member_names:(.*)', r'^syncgroups(.*)?$'], 'custom_disabled': True, 'item_attrs': {'initial': False}},
        },
        'playlists': {
            'rename': {'read': False, 'write': True, 'write_cmd': 'playlists rename {VALUE}', 'item_type': 'str', 'dev_datatype': 'LMSPlaylistrename', 'reply_pattern': r'^playlists rename\s+(.*)', 'custom_disabled': True, 'item_attrs': {'attributes': {'remark': 'needed value:<playlist_id> <newname> with a space inbetween'}}},
            'delete': {'read': False, 'write': True, 'write_cmd': 'playlists delete playlist_id:{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^playlists delete playlist_id:(\d+)', 'custom_disabled': True},
        },
    },
    'database': {
        'rescan': {
            'start': {'read': False, 'write': True, 'write_cmd': 'rescan {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'cmd_settings': {'valid_list_re': ['playlists', 'onlinelibrary', 'external', 'full', r'full file://.*']}, 'custom_disabled': True, 'item_attrs': {'attributes': {'remark': 'playlists|onlinelibrary|external|full|full file://some/path'}}},
            'running': {'read': True, 'write': False, 'read_cmd': 'rescan ?', 'item_type': 'bool', 'dev_datatype': 'LMSRescan', 'reply_pattern': [r'^rescanprogress rescan:(.*)', r'^rescan (.*)', r'^scanner notify progress:(.*)'], 'custom_disabled': True, 'item_attrs': {'cycle': '120', 'initial': True}},
            'progress': {'read': True, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^scanner notify progress:(.*)', 'custom_disabled': True, 'item_attrs': {'item_template': 'rescanprogress'}},
            'runningtime': {'read': True, 'read_cmd': 'rescanprogress totaltime', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^(?:rescanprogress totaltime.*)?rescan:(0|[0-9]{2}:[0-9]{2}:[0-9]{2})', 'custom_disabled': True},
            'fail': {'read': True, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^rescanprogress totaltime rescan:0 lastscanfailed:(.*)', 'custom_disabled': True},
            'abortscan': {'read': True, 'write': True, 'write_cmd': 'abortscan', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': r'^abortscan$', 'custom_disabled': True},
            'wipecache': {'read': True, 'write': True, 'write_cmd': 'wipecache', 'item_type': 'bool', 'dev_datatype': 'LMSWipecache', 'reply_pattern': r'^wipecache$', 'custom_disabled': True}
        },
        'totalgenres': {'read': True, 'write': False, 'read_cmd': 'info total genres ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^info total genres (\d+)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'totalduration': {'read': True, 'write': False, 'read_cmd': 'info total duration ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^info total duration ([0-9.]*)', 'custom_disabled': True, 'item_attrs': {'item_template': 'duration', 'initial': True}},
        'totalartists': {'read': True, 'write': False, 'read_cmd': 'info total artists ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^info total artists (\d+)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'totalalbums': {'read': True, 'write': False, 'read_cmd': 'info total albums ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^info total albums (\d+)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'totalsongs': {'read': True, 'write': False, 'read_cmd': 'info total songs ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^info total songs (\d+)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'totalplaylists': {'read': True, 'write': False, 'read_cmd': 'playlists 0 1000 tags:u', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^playlists 0 1000(?: tags:[u,s])? count:(\d+)', 'custom_disabled': True},
        'players': {'read': True, 'write': False, 'read_cmd': 'players 0 100', 'item_type': 'dict', 'dev_datatype': 'LMSPlayers', 'reply_pattern': r'^players 0 100 (.*)', 'custom_disabled': True, 'item_attrs': {'initial': True}},
        'playlists': {'read': True, 'write': False, 'read_cmd': 'playlists 0 1000 tags:u', 'item_type': 'dict', 'dev_datatype': 'LMSPlaylists', 'reply_pattern': r'^playlists 0 1000(?: tags:[u,s])? (.*)', 'item_attrs': {'initial': True}},
    },
    'player': {
        'control': {
            'power': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} power ?', 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} power {RAW_VALUE:01}', 'dev_datatype': 'LMSonoff', 'reply_pattern': [r'^{CUSTOM_PATTERN1} (?:prefset server\s)?power (\d)$', r'^{CUSTOM_PATTERN1} status(?:.*)power:([^\s]+)$'], 'item_attrs': {'initial': True, 'enforce': True}},
            'playmode': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mode ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} mode {VALUE}', 'dev_datatype': 'LMSPlayMode', 'cmd_settings': {'valid_list_ci': ['PLAY', 'PAUSE', 'STOP']}, 'reply_pattern': [r'^{CUSTOM_PATTERN1} mode {VALID_LIST_CI}$', r'^{CUSTOM_PATTERN1} playlist (pause \d|stop)$', r'^{CUSTOM_PATTERN1} status(?:.*)mode:([^\s]+)$'], 'item_attrs': {'enforce': True}},
            'playpause': {'read': True, 'write': True, 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'LMSPlay', 'reply_pattern': [r'^{CUSTOM_PATTERN1} (?:playlist\s)?(play|pause)(?:\s3)?$', r'^{CUSTOM_PATTERN1} pause (0|1)'], 'item_attrs': {'enforce': True}},
            'stop': {'read': True, 'write': True, 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'LMSStop', 'reply_pattern': r'^{CUSTOM_PATTERN1} (?:playlist\s)?(stop)$', 'item_attrs': {'enforce': True}},
            'mute': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mixer muting ?', 'item_type': 'bool', 'write_cmd': '{CUSTOM_ATTR1} mixer muting {RAW_VALUE:01}', 'dev_datatype': 'LMSonoff', 'reply_pattern': [r'^{CUSTOM_PATTERN1} mixer muting$', r'^{CUSTOM_PATTERN1} (?:mixer muting|prefset server mute) (\d)'], 'item_attrs': {'initial': True, 'enforce': True}},
            'volume': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} mixer volume ?', 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} (?:mixer volume |prefset server volume )(\-?\d{1,3})', r'^{CUSTOM_PATTERN1} status(?:.*)mixer volume:([^\s]+)']},
            'volume_fading': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'item_template': 'volume_fading'}},
            'volume_low': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 60}}},
            'volume_high': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume {VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 80}}},
            'volumeup': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume +{VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 1}}},
            'volumedown': {'read': False, 'write': True, 'item_type': 'num', 'write_cmd': '{CUSTOM_ATTR1} mixer volume -{VALUE}', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True, 'enforce_updates': True, 'initial_value': 1}}},
            'set_alarm': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} alarm {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} alarm (.*)', 'item_attrs': {'attributes': {'on_change': '..alarms.query = True'}}},
            'alarms': {'read': True, 'write': False, 'item_type': 'dict', 'read_cmd': '{CUSTOM_ATTR1} alarms 0 100 all', 'dev_datatype': 'LMSAlarms', 'reply_pattern': r'^{CUSTOM_PATTERN1} alarms 0 100 all fade:\d+ count:\d+\s?(.*)?', 'item_attrs': {'initial': True, 'read_groups': [{'name': 'player.control.alarms', 'trigger': 'query'}]}},
            'sync': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} sync ?', 'write_cmd': '{CUSTOM_ATTR1} sync {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} sync (.*)', 'item_attrs': {'initial': True}},
            'unsync': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} sync -', 'item_type': 'bool', 'dev_datatype': 'LMSonoff', 'item_attrs': {'attributes': {'autotimer': '1s = 0'}}},
            'display': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} display ? ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} display {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} display\s?(.*)', 'item_attrs': {'initial': True}},
            'connect': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} connect {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} connect (.*)', 'item_attrs': {'attributes': {'remark': 'ip|www.mysqueezebox.com|www.test.mysqueezebox.com'}}},
            'disconnect': {'read': True, 'write': True, 'item_type': 'str', 'write_cmd': 'disconnect {CUSTOM_ATTR1} {VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'^disconnect {CUSTOM_PATTERN1} (.*)', 'item_attrs': {'attributes': {'remark': 'ip|www.mysqueezebox.com|www.test.mysqueezebox.com'}}},
            'time': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} time ?', 'write_cmd': '{CUSTOM_ATTR1} time {VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} time (\d+(?:\.\d{2})?)', r'^{CUSTOM_PATTERN1} status(?:.*)time:([^\s]+)'], 'item_attrs': {'item_template': 'time', 'enforce': True, 'read_groups': [{'name': 'player.control.time_poll', 'trigger': 'poll'}]}},
            'forward': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} time +{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} time \+(\d+(?:\.\d{2})?)', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 10}}},
            'rewind': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} time -{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} time \-(\d+(?:\.\d{2})?)', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 10}}},
            'playsong': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist play {VALUE}', 'item_type': 'str', 'dev_datatype': 'LMSConvertSpaces', 'item_attrs': {'attributes': {'remark': 'song URL, playlist or directory'}}},
            'sleep': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} sleep ?', 'write_cmd': '{CUSTOM_ATTR1} sleep {VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} sleep (.*[^?])', 'item_attrs': {'initial': True}}
        },
        'playlist': {
            'repeat': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist repeat ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} playlist repeat {VALUE}', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlist repeat {LOOKUP}$', r'^{CUSTOM_PATTERN1} status(?:.*)playlist repeat:{LOOKUP}$'], 'lookup': 'REPEAT', 'item_attrs': {'initial': True, 'attributes': {'remark': '0 = Off, 1 = Song, 2 = Playlist'}, 'lookup_item': True}},
            'rename_current': {'read': False, 'write': True, 'item_type': 'str', 'write_cmd': 'playlists rename playlist_id:{CUSTOM_PARAM1:CURRENT_LIST_ID} newname:{VALUE}', 'dev_datatype': 'str', 'reply_pattern': r'^playlists rename playlist_id:(?:\d+) newname:(.*)', 'custom_disabled': True},
            'delete_current': {'read': False, 'write': True, 'write_cmd': 'playlists delete playlist_id:{CUSTOM_PARAM1:CURRENT_LIST_ID}', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': r'^playlists delete playlist_id:(\d+)', 'custom_disabled': True, 'item_attrs': {'enforce': True, 'attributes': {'autotimer': '1s = 0', 'remark': 'Be careful, instantly deletes the current playlist!'}}},
            'shuffle': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist shuffle ?', 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} playlist shuffle {VALUE}', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlist shuffle {LOOKUP}$', r'^{CUSTOM_PATTERN1} status(?:.*)playlist shuffle:{LOOKUP}$'], 'lookup': 'SHUFFLE', 'item_attrs': {'initial': True, 'attributes': {'remark': '0 = Off, 1 = Song, 2 = Album'}, 'lookup_item': True}},
            'index': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist index ?', 'write_cmd': '{CUSTOM_ATTR1} playlist index {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlist (?:index|newsong .*) (\d+)$', r'^{CUSTOM_PATTERN1} status(?:.*)playlist index:(\d*[^\s]+)', r'^{CUSTOM_PATTERN1} prefset server currentSong (\d+)$', r'^{CUSTOM_PATTERN1} playlist jump (\d+)', r'^{CUSTOM_PATTERN1} play (\d*)'], 'item_attrs': {'initial': True}},
            'name': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist name ?', 'write_cmd': '{CUSTOM_ATTR1} playlist name {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlistcontrol cmd:load playlist_name:(.*) count:(?:\d+)$', r'^{CUSTOM_PATTERN1} playlist name (.*[^?])', r'^{CUSTOM_PATTERN1} playlist playlistsinfo id:(?:\d+) name:(.*) modified:']},
            'url': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} playlist playlistsinfo', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist playlistsinfo id:(?:\d+) name:(?:.*) modified:(?:0|1) url:(.*)'},
            'id': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} playlist playlistsinfo', 'write_cmd': '{CUSTOM_ATTR1} playlistcontrol cmd:load playlist_id:{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} (?:status - 1 .*|playlist playlistsinfo |playlistcontrol cmd:load playlist_)id:(\d+)', r'^{CUSTOM_PATTERN1} playlist loadtracks playlist.id=(\d+)\s'], 'item_attrs': {'initial': True}},
            'save': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist save {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist save (.*)', 'item_attrs': {'enforce': True}},
            'load': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlistcontrol cmd:load playlist_name:{VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlistcontrol cmd:load playlist_name:(.*) count:(?:\d+)', r'^{CUSTOM_PATTERN1} playlist resume (.*)', r'^{CUSTOM_PATTERN1} playlist loadtracks playlist.name:(.*)\s'], 'item_attrs': {'enforce': True}},
            'loadalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist loadalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist loadalbum (.*)', 'item_attrs': {'enforce': True, 'attributes': {'remark': '<Genre> <Artist> <Album>. You can use * for any of the entries. Spaces need to be replaced by %20'}}},
            'loadtracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist loadtracks {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist loadtracks (.*)', 'item_attrs': {'enforce': True}},
            'add': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist add {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist add (.*)', 'item_attrs': {'enforce': True}},
            'addalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist addalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist addalbum (.*)', 'item_attrs': {'enforce': True}},
            'addtracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist addtracks {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist addtracks (.*)', 'item_attrs': {'enforce': True}},
            'insertalbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist insertalbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist insertalbum (.*)', 'item_attrs': {'enforce': True}},
            'inserttracks': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist insert {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist insert (.*)', 'item_attrs': {'enforce': True}},
            'tracks': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} playlist tracks ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlistcontrol cmd:load .* count:(\d+)', r'^{CUSTOM_PATTERN1} playlist_tracks (\d+[^?])', r'^{CUSTOM_PATTERN1} status(?:.*)playlist tracks:(\d*[^\s]+)']},
            'clear': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist clear', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist clear$', 'item_attrs': {'enforce': True, 'attributes': {'autotimer': '1s = 0', 'remark': 'Might go berserk, use with care!'}}},
            'deletesong': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist delete {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist delete (.*)', 'item_attrs': {'enforce': True, 'attributes': {'remark': 'provide songindex that should be deleted'}}},
            'deleteitem': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist deleteitem {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist deleteitem (.*)', 'item_attrs': {'enforce': True}},
            'deletealbum': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist deletealbum {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist deletealbum (.*)', 'item_attrs': {'enforce': True}},
            'preview': {'read': True, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist preview {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} playlist preview (.*)'},
            'next': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist index +{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 1}}},
            'previous': {'read': False, 'write': True, 'write_cmd': '{CUSTOM_ATTR1} playlist index -{VALUE}', 'item_type': 'num', 'dev_datatype': 'str', 'item_attrs': {'enforce': True, 'attributes': {'initial_value': 1}}},
            'modified': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} playlist modified ?', 'item_type': 'bool', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} playlist modified (0|1)', r'^{CUSTOM_PATTERN1} playlist playlistsinfo id:(?:\d+) name:(?:.*) modified:(0|1)']},
            'customskip': {'read': False, 'write': True, 'item_type': 'str', 'write_cmd': '{CUSTOM_ATTR1} customskip setfilter filter{VALUE}.cs.xml', 'dev_datatype': 'str', 'item_attrs': {'attributes': {'cache': True}}}
        },
        'info': {
            'playernames': {'read': True, 'write': False, 'read_cmd': 'players 0 100', 'item_type': 'dict', 'dev_datatype': 'LMSPlayers', 'reply_pattern': r'^players 0 100 (.*)', 'custom_disabled': True, 'item_attrs': {'initial': False, 'item_template': 'players'}},
            'playlists': {'read': True, 'write': False, 'read_cmd': 'playlists 0 1000 tags:u', 'item_type': 'dict', 'dev_datatype': 'LMSPlaylists', 'reply_pattern': r'^playlists 0 1000(?: tags:[u,s])? (.*)', 'item_attrs': {'initial': False, 'item_template': 'playlists'}},
            'status': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} status', 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'^{CUSTOM_PATTERN1} status\s+(.*)', 'item_attrs': {'initial': True}},
            'connected': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} connected ?', 'item_type': 'bool', 'dev_datatype': 'LMSConnection', 'reply_pattern': [r'^{CUSTOM_PATTERN1} (?:connected|client) (\d|disconnect|reconnect)', r'^{CUSTOM_PATTERN1} status(?:.*)player_connected:([^\s]+)']},
            'ip': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} ip ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} ip (.*)', r'^{CUSTOM_PATTERN1} status(?:.*)player_ip:([^:\s]+)']},
            'modelname': {'read': False, 'write': False, 'item_type': 'str', 'dev_datatype': 'str'},
            'firmware': {'read': False, 'write': False, 'item_type': 'str', 'dev_datatype': 'str'},
            'name': {'read': True, 'write': True, 'read_cmd': '{CUSTOM_ATTR1} name ?', 'write_cmd': '{CUSTOM_ATTR1} name {VALUE}', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} name (.*)', r'^{CUSTOM_PATTERN1} status(?:.*)player_name:([^\s]+)']},
            'signalstrength': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} signalstrength ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} signalstrength (\d+)', r'^{CUSTOM_PATTERN1} status(?:.*)signalstrength:([^\s]+)']},
            'genre': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} genre ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} genre (.*)'},
            'artist': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} artist ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} artist (.*)'},
            'album': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} album ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} album (.*)', 'item_attrs': {'initial': True}},
            'title': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} current_title ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} (?:current_title|playlist newsong) (.*?)(?:\s\d+)?$', 'item_attrs': {'initial': True}},
            'path': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} path ?', 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': [r'^{CUSTOM_PATTERN1} path (.*)', r'^{CUSTOM_PATTERN1} playlist open (.*)', r'^{CUSTOM_PATTERN1} playlist play (.*)']},
            'duration': {'read': True, 'write': False, 'read_cmd': '{CUSTOM_ATTR1} duration ?', 'item_type': 'num', 'dev_datatype': 'str', 'reply_pattern': r'^{CUSTOM_PATTERN1} duration (\d+)'},
            'trackstat': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'raw', 'reply_pattern': r'^{CUSTOM_PATTERN1} trackstat changedstatistic (.*)'},
            'albumarturl': {'read': True, 'write': False, 'item_type': 'str', 'dev_datatype': 'str', 'reply_pattern': '^(https?://.*)', 'item_attrs': {'attributes': {'remark': 'This item gets automatically defined and overwritten based on (web_)host and web_port'}}}
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
    'players': {
        'lu_fwd':
            {
                'type': 'dict',
                'eval_trigger': '..',
                'eval': '{value["name"]: key for key, value in sh...().items()}'
            },
        'lu_rev':
            {
                'type': 'dict',
                'eval_trigger': '..',
                'eval': '{key: value["name"] for key, value in sh...().items()}'
            },
        'lu_ci':
            {
                'type': 'dict',
                'eval_trigger': '..',
                'eval': '{value["name"].lower(): key for key, value in sh...().items()}'
            }
    },
    'playlists': {
        'ids':
            {
                'lu_fwd':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{key: value["id"] for key, value in sh....().items()}'
                    },
                'lu_rev':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{value["id"]: key for key, value in sh....().items()}'
                    },
                'lu_ci':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{key.lower(): value["id"] for key, value in sh....().items()}'
                    }
            },
        'urls':
            {
                'lu_fwd':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{key: value["url"] for key, value in sh....().items()}'
                    },
                'lu_rev':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{value["url"]: key for key, value in sh....().items()}'
                    },
                'lu_ci':
                    {
                        'type': 'dict',
                        'eval_trigger': '...',
                        'eval': '{key.lower(): value["url"] for key, value in sh....().items()}'
                    }
            },
    },
    'rescanprogress': {
        'start':
            {
                'type': 'num',
                'eval_trigger': '..',
                'eval': '0 if len(sh...()) == 0 else sh...().split("||")[0]'
            },
        'info':
            {
                'type': 'str',
                'eval_trigger': '..',
                'eval': '0 if len(sh...()) < 3 else sh...().split("||")[2]'
            },
        'step':
            {
                'type': 'num',
                'eval_trigger': '..',
                'eval': '0 if len(sh...()) < 4 else sh...().split("||")[3]'
            },
        'totalsteps':
            {
                'type': 'num',
                'eval_trigger': '..',
                'eval': '0 if len(sh...()) <5 else sh...().split("||")[4]'
            },

    },
    'duration': {
        'duration_format':
            {
                'type': 'str',
                'eval': "'{}d {}h {}i {}s'.format(int(sh...()//86400), int((sh...()%86400)//3600), int((sh...()%3600)//60), round((sh...()%3600)%60))",
                'eval_trigger': '..'
            }
    },
    'time': {
        'poll':
            {
                'type': 'bool',
                'eval': 'True if sh....playmode() == "play" else None',
                'enforce_updates': True,
                'cycle': '10',
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
