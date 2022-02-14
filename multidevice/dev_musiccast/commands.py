#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

""" commands for dev musiccast """

commands = {
    'info': {'item_attrs': {'read_group_levels': 0},
        'track':      {'read': True,  'write': False, 'reply_pattern': 'track', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'albumart':   {'read': True,  'write': False, 'reply_pattern': 'albumart_url', 'item_type': 'str', 'dev_datatype': 'url', 'item_attrs': {'read_group_levels': 0}},
        'artist':     {'read': True,  'write': False, 'reply_pattern': 'artist', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'album':      {'read': True,  'write': False, 'reply_pattern': 'album', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'curtime':    {'read': True,  'write': False, 'reply_pattern': 'play_time', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'totaltime':  {'read': True,  'write': False, 'reply_pattern': 'total_time', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'model':      {'read': True,  'write': False, 'reply_pattern': 'model_name', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'zones':      {'read': True,  'write': False, 'reply_pattern': 'system.zone_num', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'inputs_raw': {'read': True,  'write': False, 'reply_pattern': 'input_list', 'item_type': 'list', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'inputs_sys': {'read': False, 'write': False, 'item_type': 'list', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'inputs_user':{'read': False, 'write': False, 'item_type': 'list', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
        'error':      {'read': False, 'write': False, 'item_type': 'str', 'dev_datatype': 'mc', 'lookup': 'error', 'item_attrs': {'read_group_levels': 0}},
    },
    'system': {
        'passthru':   {'read': True,  'write': True,  'opcode': '{RAW_VALUE}', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'deviceinfo': {'read': True,  'write': False, 'opcode': 'v1/system/getDeviceInfo', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},  # {"response_code":0,"model_name":"RX-V483","destination":"BG","device_id":"00A0DEFC4C38","system_id":"0CA45EC3","system_version":2.87,"api_version":2.08,"netmodule_generation":1,"netmodule_version":"1923    ","netmodule_checksum":"A7E6476F","operation_mode":"normal","update_error_code":"00000000"}
        'features':   {'read': True,  'write': False, 'opcode': 'v1/system/getFeatures', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},    # {"response_code":0,"system":{"func_list":["wired_lan","wireless_lan","wireless_direct","network_standby","network_standby_auto","bluetooth_standby","bluetooth_tx_setting","zone_b_volume_sync","hdmi_out_1","airplay","disklavier_settings","remote_info","network_reboot"],"zone_num":2,"input_list":[{"id":"spotify","distribution_enable":true,"rename_enable":false,"account_enable":false,"play_info_type":"netusb"},{"id":"juke","distribution_enable":true,"rename_enable":false,"account_enable":true,"play_info_type":"netusb"},{"id":"qobuz","distribution_enable":true,"rename_enable":false,"account_enable":true,"play_info_type":"netusb"},{"id":"tidal","distribution_enable":true,"rename_enable":false,"account_enable":true,"play_info_type":"netusb"},{"id":"deezer","distribution_enable":true,"rename_enable":false,"account_enable":true,"play_info_type":"netusb"},{"id":"airplay","distribution_enable":false,"rename_enable":false,"account_enable":false,"play_info_type":"netusb"},{"id":"mc_link","distribution_enable":false,"rename_enable":true,"account_enable":false,"play_info_type":"netusb"},{"id":"server","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"netusb"},{"id":"net_radio","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"netusb"},{"id":"bluetooth","distribution_enable":true,"rename_enable":false,"account_enable":false,"play_info_type":"netusb"},{"id":"usb","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"netusb"},{"id":"tuner","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"tuner"},{"id":"hdmi1","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"hdmi2","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"hdmi3","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"hdmi4","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"av1","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"av2","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"av3","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"audio1","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"audio2","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"audio3","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"},{"id":"aux","distribution_enable":true,"rename_enable":true,"account_enable":false,"play_info_type":"none"}]},"zone":[{"id":"main","func_list":["power","sleep","volume","mute","sound_program","direct","enhancer","tone_control","dialogue_level","signal_info","prepare_input_change","link_control","link_audio_delay","link_audio_quality","scene","cursor","menu","surr_decoder_type","contents_display","actual_volume"],"input_list":["spotify","juke","qobuz","tidal","deezer","airplay","mc_link","server","net_radio","bluetooth","usb","tuner","hdmi1","hdmi2","hdmi3","hdmi4","av1","av2","av3","audio1","audio2","audio3","aux"],"sound_program_list":["munich","vienna","chamber","cellar_club","roxy_theatre","bottom_line","sports","action_game","roleplaying_game","music_video","standard","spectacle","sci-fi","adventure","drama","mono_movie","2ch_stereo","5ch_stereo","surr_decoder","straight"],"surr_decoder_type_list":["toggle","dolby_pl2x_movie","dolby_pl2x_music","dolby_pl2x_game","dts_neo6_cinema","dts_neo6_music"],"tone_control_mode_list":["manual"],"link_control_list":["speed","standard","stability"],"link_audio_delay_list":["audio_sync","lip_sync"],"link_audio_quality_list":["compressed","uncompressed"],"range_step":[{"id":"volume","min":0,"max":161,"step":1},{"id":"tone_control","min":-12,"max":12,"step":1},{"id":"dialogue_level","min":0,"max":3,"step":1},{"id":"actual_volume_db","min":-80.5,"max":16.5,"step":0.5},{"id":"actual_volume_numeric","min":0.0,"max":97.0,"step":0.5}], "scene_num":4,"cursor_list":["up","down","left","right","select","return"],"menu_list":["on_screen","top_menu","menu","option","display","red","green","yellow","blue"],"actual_volume_mode_list":["db","numeric"]},{"id":"zone2","zone_b":true,"func_list":["power","volume","mute","prepare_input_change","actual_volume"],"input_list":["spotify","juke","qobuz","tidal","deezer","airplay","mc_link","server","net_radio","bluetooth","usb","tuner","hdmi1","hdmi2","hdmi3","hdmi4","av1","av2","av3","audio1","audio2","audio3","aux"],"range_step":[{"id":"volume","min":0,"max":161,"step":1},{"id":"actual_volume_db","min":-80.5,"max":16.5,"step":0.5},{"id":"actual_volume_numeric","min":0.0,"max":97.0,"step":0.5}],"actual_volume_mode_list":["db","numeric"]}],"tuner":{"func_list":["am","fm","rds"],"range_step":[{"id":"am","min":531,"max":1611,"step":9},{"id":"fm","min":87500,"max":108000,"step":50}],"preset":{"type":"common","num":40}},"netusb":{"func_list":["recent_info","play_queue","mc_playlist","streaming_service_use"],"preset":{"num":40},"recent_info":{"num":40},"play_queue":{"size":200},"mc_playlist":{"size":200,"num":5},"net_radio_type":"airable","pandora":{"sort_option_list":["recent","alphabet"]},"siriusxm":{"api_type":"everest"}},"distribution":{"version":2.00,"compatible_client":[2],"client_max":9,"server_zone_list":["main"]},"ccs":{"supported":true}}"
        'names':      {'read': True,  'write': False, 'opcode': 'v1/system/getNameText', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},    # {"response_code":0,"zone_list":[{"id":"main","text":"Wohnzimmer"},{"id":"zone2","text":"Room"}],"input_list":[{"id":"tuner","text":"Tuner"},{"id":"hdmi1","text":"Blu-Ray"},{"id":"hdmi2","text":"TV"},{"id":"hdmi3","text":"Kodi"},{"id":"hdmi4","text":"HDMI4"},{"id":"av1","text":"AV1"},{"id":"av2","text":"AV2"},{"id":"av3","text":"Wii"},{"id":"aux","text":"AUX"},{"id":"audio1","text":"Audio1"},{"id":"audio2","text":"Audio2"},{"id":"audio3","text":"Audio3"},{"id":"usb","text":"USB"},{"id":"bluetooth","text":"Bluetooth"},{"id":"server","text":"Server"},{"id":"net_radio","text":"Net Radio"},{"id":"spotify","text":"Spotify"},{"id":"juke","text":"JUKE"},{"id":"airplay","text":"AirPlay"},{"id":"qobuz","text":"Qobuz"},{"id":"mc_link","text":"MC Link"},{"id":"tidal","text":"TIDAL"},{"id":"deezer","text":"Deezer"}],"sound_program_list":[{"id":"munich","text":"Hall in Munich"},{"id":"vienna","text":"Hall in Vienna"},{"id":"chamber","text":"Chamber"},{"id":"cellar_club","text":"Cellar Club"},{"id":"roxy_theatre","text":"The Roxy Theatre"},{"id":"bottom_line","text":"The Bottom Line"},{"id":"sports","text":"Sports"},{"id":"action_game","text":"Action Game"},{"id":"roleplaying_game","text":"Roleplaying Game"},{"id":"music_video","text":"Music Video"},{"id":"standard","text":"Standard"},{"id":"spectacle","text":"Spectacle"},{"id":"sci-fi","text":"Sci-Fi"},{"id":"adventure","text":"Adventure"},{"id":"drama","text":"Drama"},{"id":"mono_movie","text":"Mono Movie"},{"id":"2ch_stereo","text":"2ch Stereo"},{"id":"5ch_stereo","text":"5ch Stereo"},{"id":"surr_decoder","text":"Surround Decoder"},{"id":"straight","text":"Straight"}]}
    },
    'main': {
        'status':     {'read': True,  'write': False, 'opcode': 'v1/main/getStatus', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},        # {"response_code":0,"power":"on","sleep":0,"volume":12,"mute":false,"max_volume":161,"input":"hdmi3","distribution_enable":true,"sound_program":"surr_decoder","surr_decoder_type":"dts_neo6_cinema","direct":false,"enhancer":false,"tone_control":{"mode":"auto","bass":5,"treble":0},"dialogue_level":3,"link_control":"standard","link_audio_delay":"lip_sync","link_audio_quality":"compressed","disable_flags":0,"actual_volume":{"mode":"db","value":-74.5,"unit":"dB"},"contents_display":true}
        'power':      {'read': True,  'write': True,  'opcode': 'v1/main/setPower?power={RAW_VALUE}', 'reply_pattern': 'main.power', 'item_type': 'bool', 'dev_datatype': 'mc', 'lookup': 'power', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'sleep':      {'read': True,  'write': True,  'opcode': 'v1/main/setSleep?sleep={RAW_VALUE}', 'reply_pattern': 'main.sleep', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'input':      {'read': True,  'write': True,  'opcode': 'v1/main/setInput?input={RAW_VALUE}', 'reply_pattern': 'input', 'item_type': 'str', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'mute':       {'read': True,  'write': True,  'opcode': 'v1/main/setMute?enable={RAW_VALUE}', 'reply_pattern': 'mute', 'item_type': 'bool', 'dev_datatype': 'mc', 'lookup': 'bool', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'volume':     {'read': True,  'write': True,  'opcode': 'v1/main/setVolume?volume={RAW_VALUE}', 'reply_pattern': 'volume', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'volume_max': {'read': True,  'write': False, 'opcode': '', 'reply_pattern': 'max_volume', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'read_group_levels': 0}},
    },
    'netusb': {
        'playinfo':   {'read': True,  'write': False, 'opcode': 'v1/netusb/getPlayInfo', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},    # {'response_code': 0, 'input': 'server', 'play_queue_type': 'user', 'playback': 'play', 'repeat': 'all', 'shuffle': 'on', 'play_time': 119, 'total_time': 0, 'artist': 'Adele', 'album': '19', 'track': 'Daydreams', 'albumart_url': '/YamahaRemoteControl/AlbumART/AlbumART1623.jpg', 'albumart_id': 1623, 'usb_devicetype': 'unknown', 'auto_stopped': False, 'attribute': 83886591, 'repeat_available': ['off', 'one', 'all'], 'shuffle_available': ['off', 'on']}
        'preset':     {'read': True,  'write': True,  'opcode': 'v1/netusb/recallPreset?zone=main&num={RAW_VALUE}', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'playback':   {'read': True,  'write': True,  'opcode': 'v1/netusb/setPlayback?playback={RAW_VALUE}', 'reply_pattern': 'playback', 'item_type': 'str', 'dev_datatype': 'mc', 'cmd_settings': {'valid_list': ['play', 'stop', 'pause', 'play_pause', 'previous', 'next', 'fast_reverse_start', 'fast_reverse_stop', 'fast_forward_start', 'fast_forward_stop']}, 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'position':   {'read': True,  'write': True,  'opcode': 'v1/netusb/setPlayPosition?position={RAW_VALUE}', 'item_type': 'num', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
    },
    'alarm': {
        'update':     {'read': True,  'write': False, 'opcode': 'v1/clock/getSettings', 'item_type': 'bool', 'dev_datatype': 'mc', 'item_attrs': {'enforce': True, 'initial': True}},
        'enable':     {'read': True,  'write': True,  'opcode': 'v1/clock/setAlarmSettings', 'reply_pattern': 'alarm.alarm_on', 'item_type': 'bool', 'dev_datatype': 'al_on', 'lookup': 'bool', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'time':       {'read': True,  'write': True,  'opcode': 'v1/clock/setAlarmSettings', 'reply_pattern': 'alarm.oneday.time|response_code', 'item_type': 'str', 'dev_datatype': 'al_time', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
        'beep':       {'read': True,  'write': True,  'opcode': 'v1/clock/setAlarmSettings', 'reply_pattern': 'alarm.oneday.beep', 'item_type': 'bool', 'dev_datatype': 'al_beep', 'lookup': 'bool', 'item_attrs': {'enforce': True, 'read_group_levels': 0}},
    }
}

lookups = {
    'bool': {
        'true': True,
        'false': False
    },
    'power': {
        'on': True,
        'standby': False
    },
    'error': {
        0: 'Successful request',
        1: 'Initializing',
        2: 'Internal Error',
        3: 'Invalid Request (A method did not exist, a method wasn’t appropriate etc.)',
        4: 'Invalid Parameter (Out of range, invalid characters etc.)',
        5: 'Guarded (Unable to setup in current status etc.)',
        6: 'Time Out',
        99: 'Firmware Updating',
        100: 'Access Error',
        101: 'Other Errors',
        102: 'Wrong User Name',
        103: 'Wrong Password',
        104: 'Account Expired',
        105: 'Account Disconnected/Gone Off/Shut Down',
        106: 'Account Number Reached to the Limit',
        107: 'Server Maintenance',
        108: 'Invalid Account',
        109: 'License Error',
        110: 'Read Only Mode',
        111: 'Max Stations',
        112: 'Access Denied',
        113: 'There is a need to specify the additional destination Playlist',
        114: 'There is a need to create a new Playlist',
        115: 'Simultaneous logins has reached the upper limit',
        200: 'Linking in progress',
        201: 'Unlinking in progress',
    }
}
