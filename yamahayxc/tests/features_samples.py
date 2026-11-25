"""getFeatures responses of real devices, trimmed to the keys the struct recommendation reads."""

WX_010 = {
    'zone': [
        {
            'id': 'main',
            'func_list': [
                'power',
                'sleep',
                'volume',
                'mute',
                'equalizer',
                'signal_info',
                'prepare_input_change',
                'link_control',
                'link_audio_quality',
            ],
        }
    ],
    'netusb': {'func_list': ['recent_info', 'play_queue', 'mc_playlist', 'streaming_service_use']},
}

ISX_18D = {
    'zone': [
        {
            'id': 'main',
            'func_list': [
                'power',
                'sleep',
                'volume',
                'mute',
                'equalizer',
                'signal_info',
                'prepare_input_change',
                'link_control',
                'link_audio_delay',
                'link_audio_quality',
            ],
        }
    ],
    'tuner': {'func_list': ['fm', 'dab', 'fm_auto_preset', 'dab_initial_scan', 'dab_tune_aid']},
    'netusb': {'func_list': ['recent_info', 'play_queue', 'mc_playlist', 'streaming_service_use']},
    'clock': {'func_list': ['date_and_time', 'alarm', 'format']},
}

RX_V483 = {
    'zone': [
        {
            'id': 'main',
            'func_list': [
                'power',
                'sleep',
                'volume',
                'mute',
                'sound_program',
                'direct',
                'enhancer',
                'tone_control',
                'dialogue_level',
                'signal_info',
                'prepare_input_change',
                'link_control',
                'link_audio_delay',
                'link_audio_quality',
                'scene',
                'cursor',
                'menu',
                'surr_decoder_type',
                'contents_display',
                'actual_volume',
            ],
        },
        {'id': 'zone2', 'func_list': ['power', 'volume', 'mute', 'prepare_input_change', 'actual_volume']},
    ],
    'tuner': {'func_list': ['am', 'fm', 'rds']},
    'netusb': {'func_list': ['recent_info', 'play_queue', 'mc_playlist', 'streaming_service_use']},
}

RX_S602D = {
    'zone': [
        {
            'id': 'main',
            'func_list': [
                'power',
                'sleep',
                'volume',
                'mute',
                'sound_program',
                'direct',
                'enhancer',
                'tone_control',
                'dialogue_level',
                'subwoofer_volume',
                'signal_info',
                'prepare_input_change',
                'link_control',
                'link_audio_delay',
                'scene',
                'contents_display',
                'cursor',
                'menu',
                'actual_volume',
                'surr_decoder_type',
                'extra_bass',
                'adaptive_drc',
            ],
        },
        {
            'id': 'zone2',
            'func_list': ['power', 'sleep', 'volume', 'mute', 'prepare_input_change', 'scene', 'actual_volume'],
        },
    ],
    'tuner': {'func_list': ['fm', 'rds', 'dab']},
    'netusb': {'func_list': ['recent_info', 'play_queue', 'mc_playlist', 'streaming_service_use', 'previous_force']},
}
