#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Sebastian Helms                    yamahayxc@shelms.de
#  based on original yamaha plugin by Raoul Thill
#########################################################################
#  This file is part of SmartHomeNG.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


import requests
import secrets
import socket
import json
import inspect
from typing import Callable, NamedTuple
from lib.model.smartplugin import SmartPlugin
from lib.network import Udp_server


class _CmdSpec(NamedTuple):
    """
    one entry per update_item()-dispatchable yamahayxc_cmd, interpreted by
    YamahaYXC._dispatch_cmd_build() - see that method for exactly how each
    field is used. 'build' is always a real bound method, never a lambda -
    either an existing self._build_cmd_X (for the common check+build shape)
    or a small dedicated self._handle_X method for the handful of cmds that
    need more than that (stateful tuner cmds, the link_* orchestrators,
    passthru, volume_percent).
    """

    build: Callable
    label: str = ''
    func_check: str | None = None
    list_check: str | None = None
    clamp_range: str | None = None
    full_context: bool = False


# func_list values (per getFeatures) that indicate some DSP capability -
# used by YamahaYXC._update_zone_flags() to derive the 'dsp_available'
# indicator. Matches the func_check strings already established for these
# cmds in _yamaha_cmd_specs. 'sound_program' isn't here - its availability
# signal is a non-empty sound_program_list, not a func_list entry (see
# _update_zone_flags()).
_DSP_FUNC_NAMES = {'surround_3d', 'direct', 'pure_direct', 'enhancer', 'tone_control', 'equalizer', 'balance'}


class YamahaYXC(SmartPlugin):
    """
    This is the main plugin class YamahaYXC to control YXC-compatible devices.
    """

    PLUGIN_VERSION = '2.0.0'
    ALLOW_MULTIINSTANCE = False
    # this single instance manages many independent physical devices (hosts);
    # SmartPlugin's default remove_item() would stop() the whole plugin (all
    # hosts) whenever a single item on any one host is deleted/edited live via
    # the admin UI. See the overridden remove_item() below, which instead only
    # removes that one item's bookkeeping.
    STOP_ON_ITEM_CHANGE = False

    #
    # public functions
    #

    def __init__(self, smarthome, **kwargs):
        """
        Default init function
        """
        super().__init__(**kwargs)
        self._sh = smarthome
        self.logger.info('Init YamahaYXC')

        # valid commands for use in item configuration 'yamahayxc_cmd = ...'
        self._yamaha_cmds = [
            'state',
            'power',
            'input',
            'playback',
            'preset',
            'volume',
            'mute',
            'track',
            'artist',
            'sleep',
            'total_time',
            'play_time',
            'pos',
            'albumart',
            'alarm_on',
            'alarm_time',
            'alarm_beep',
            'passthru',
            'tuner_band',
            'tuner_freq',
            'tuner_seek',
            'tuner_tuned',
            'tuner_station',
            'tuner_preset',
            'tuner_preset_store',
            'tuner_preset_clear',
            'tuner_preset_switch',
            'sound_program',
            'surround_3d',
            'direct',
            'pure_direct',
            'enhancer',
            'tone_control_mode',
            'tone_bass',
            'tone_treble',
            'equalizer_mode',
            'eq_low',
            'eq_mid',
            'eq_high',
            'balance',
            'link_control',
            'link_audio_delay',
            'link_audio_quality',
            'link_role',
            'link_group_id',
            'link_group_name',
            'link_server_zone',
            'link_audio_dropout',
            'link_join',
            'link_leave',
            'link_add_client',
            'link_remove_client',
            'link_disband',
            # derived/computed Link convenience cmds, see _update_link_state()
            'link_linked',
            'link_devices',
            'link_hosts',
            # capability (getFeatures-derived) read-only commands, see
            # _yamaha_range_cmds below
            'volume_min',
            'volume_max',
            'volume_step',
            'tone_bass_min',
            'tone_bass_max',
            'tone_bass_step',
            'tone_treble_min',
            'tone_treble_max',
            'tone_treble_step',
            'eq_low_min',
            'eq_low_max',
            'eq_low_step',
            'eq_mid_min',
            'eq_mid_max',
            'eq_mid_step',
            'eq_high_min',
            'eq_high_max',
            'eq_high_step',
            'balance_min',
            'balance_max',
            'balance_step',
            'volume_percent',
            'input_sources',
            'sound_program_values',
            'tone_control_mode_values',
            'equalizer_mode_values',
            'link_control_values',
            'link_audio_delay_values',
            'link_audio_quality_values',
            # tuner capability (getFeatures-derived) read-only commands, see
            # _update_tuner_capability_items()/_push_tuner_freq_range() below.
            # tuner_band_values is NOT tuner.func_list verbatim - that field
            # also carries 'rds' (RDS decoding available while on fm, not a
            # selectable band per setBand's own spec, which only accepts
            # am/fm/dab) - it's func_list filtered down to actually settable
            # bands. tuner_freq_min/max/step are band-dependent (am and fm
            # have different ranges) and get re-pushed on every band change,
            # unlike the zone range cmds above which are static per host/zone.
            'tuner_band_values',
            'tuner_freq_min',
            'tuner_freq_max',
            'tuner_freq_step',
            # zone-discovery/DSP-availability indicators, pushed by
            # _update_zone_flags() from getFeatures data (never read from
            # getStatus) - let a visu show/hide zone2/3/4 or DSP controls
            # instead of guessing. See zone2/3/4 and dsp's 'available' item.
            'zone_present',
            'dsp_available',
            # explicit refresh triggers, see update_item()'s trailing
            # cmd-routed refresh dispatch. 'state' (full-host refresh) is
            # the pre-existing one; these add scoped equivalents so the
            # per-category structs each have their own manual-poll item.
            'update_dsp',
            'update_netusb',
            'update_tuner',
            'update_link',
            # diagnostic introspection - dumps of this plugin's own internal
            # bookkeeping dicts, not part of the YXC protocol. See
            # _update_debug_items(). debug_features/debug_dev_zone are
            # per-zone, the rest are per-host (global).
            'debug_refresh',
            'debug_features',
            'debug_dev_zone',
            'debug_tuner_features',
            'debug_dev_global',
            'debug_dev_tuner',
            'debug_dev_link',
        ]

        # capability (getFeatures-derived, read-only) list-valued cmds ->
        # feature dict key holding the whole list (unlike _yamaha_range_cmds
        # below, no min/max/step indexing - the full list is the value).
        # Every zone-scoped writable cmd that has a matching getFeatures
        # *_list gets one of these - _update_list_items() is fully generic,
        # no per-entry code needed beyond this mapping. Some spec-defined
        # *_list fields (surr_decoder_type_list, cursor_list, menu_list,
        # audio_select_list) have no entry here because this plugin doesn't
        # implement the matching writable cmd at all yet.
        self._yamaha_list_cmds = {
            'input_sources': 'input_list',
            'sound_program_values': 'sound_program_list',
            'tone_control_mode_values': 'tone_control_mode_list',
            'equalizer_mode_values': 'equalizer_mode_list',
            'link_control_values': 'link_control_list',
            'link_audio_delay_values': 'link_audio_delay_list',
            'link_audio_quality_values': 'link_audio_quality_list',
        }

        # capability (getFeatures-derived, read-only) cmds -> (feature range
        # key, index into the (min, max, step) tuple stored under that key
        # in self._yamaha_features[host][zone], see _update_features()).
        # tone_bass/tone_treble share 'tone_control_range' and eq_low/eq_mid/
        # eq_high share 'equalizer_range' per spec (one range for the whole
        # group), exposed under each value item individually so each has its
        # own local min/max/step sub-items.
        self._yamaha_range_cmds = {
            'volume_min': ('volume_range', 0),
            'volume_max': ('volume_range', 1),
            'volume_step': ('volume_range', 2),
            'tone_bass_min': ('tone_control_range', 0),
            'tone_bass_max': ('tone_control_range', 1),
            'tone_bass_step': ('tone_control_range', 2),
            'tone_treble_min': ('tone_control_range', 0),
            'tone_treble_max': ('tone_control_range', 1),
            'tone_treble_step': ('tone_control_range', 2),
            'eq_low_min': ('equalizer_range', 0),
            'eq_low_max': ('equalizer_range', 1),
            'eq_low_step': ('equalizer_range', 2),
            'eq_mid_min': ('equalizer_range', 0),
            'eq_mid_max': ('equalizer_range', 1),
            'eq_mid_step': ('equalizer_range', 2),
            'eq_high_min': ('equalizer_range', 0),
            'eq_high_max': ('equalizer_range', 1),
            'eq_high_step': ('equalizer_range', 2),
            'balance_min': ('balance_range', 0),
            'balance_max': ('balance_range', 1),
            'balance_step': ('balance_range', 2),
        }

        # commands to ignore when checking for return values
        # these commands don't get / can't process (simple) return values
        self._yamaha_ignore_cmds_upd = (
            [
                'state',
                'preset',
                'alarm_on',
                'alarm_time',
                'alarm_beep',
                'link_join',
                'link_leave',
                'link_add_client',
                'link_remove_client',
                'link_disband',
                # link_role is pushed with the group_id=0 => 'none' override
                # applied, not the raw getDistributionInfo value directly;
                # link_linked/link_devices/link_hosts are fully derived -
                # see _update_link_state()/_update_link_hosts_item()
                'link_role',
                'link_linked',
                'link_devices',
                'link_hosts',
                # volume_percent is derived from 'volume' + volume_range, not
                # read from getStatus directly - see _push_volume_percent()
                'volume_percent',
                # explicit refresh triggers - write-only, nothing to read back
                'update_dsp',
                'update_netusb',
                'update_tuner',
                'update_link',
                # debug items are pushed directly by _update_debug_items(),
                # never read from a getStatus/getPlayInfo/etc response
                'debug_refresh',
                'debug_features',
                'debug_dev_zone',
                'debug_tuner_features',
                'debug_dev_global',
                'debug_dev_tuner',
                'debug_dev_link',
                # capability cmds come from getFeatures, not getStatus - never
                # look them up in a getStatus response
                'zone_present',
                'dsp_available',
            ]
            + list(self._yamaha_range_cmds)
            + list(self._yamaha_list_cmds)
        )

        # cmds whose value sits inside a nested object in the zone getStatus
        # response, e.g. state['tone_control']['bass'], instead of a flat
        # state[cmd] - see _get_value_from_response()
        self._yamaha_nested_cmds = {
            'tone_control_mode': ('tone_control', 'mode'),
            'tone_bass': ('tone_control', 'bass'),
            'tone_treble': ('tone_control', 'treble'),
            'equalizer_mode': ('equalizer', 'mode'),
            'eq_low': ('equalizer', 'low'),
            'eq_mid': ('equalizer', 'mid'),
            'eq_high': ('equalizer', 'high'),
        }

        # cmds whose name differs from the flat response field it reads -
        # see _get_value_from_response()
        self._yamaha_flat_rename_cmds = {
            'albumart': 'albumart_url',
            'link_role': 'role',
            'link_group_id': 'group_id',
            'link_group_name': 'group_name',
            'link_server_zone': 'server_zone',
            'link_audio_dropout': 'audio_dropout',
        }

        # cmds whose value is scoped to a single zone (v1/{zone}/... endpoints,
        # zone push notifications) vs. shared across all zones of a device
        # (netusb playback, clock/alarm, passthru) - see parse_item()
        self._yamaha_zone_cmds = (
            {
                'state',
                'power',
                'input',
                'volume',
                'volume_percent',
                'mute',
                'sleep',
                'sound_program',
                'surround_3d',
                'direct',
                'pure_direct',
                'enhancer',
                'tone_control_mode',
                'tone_bass',
                'tone_treble',
                'equalizer_mode',
                'eq_low',
                'eq_mid',
                'eq_high',
                'balance',
                'link_control',
                'link_audio_delay',
                'link_audio_quality',
                'update_dsp',
                'debug_features',
                'debug_dev_zone',
                'zone_present',
                'dsp_available',
            }
            | set(self._yamaha_range_cmds)
            | set(self._yamaha_list_cmds)
        )
        # tuner is a single global resource per device, like netusb, but has its
        # own response shape (nested am/fm/rds, not a flat cmd: value dict), so
        # it gets its own storage/update path instead of _yamaha_dev_global
        self._yamaha_tuner_cmds = {
            'tuner_band',
            'tuner_freq',
            'tuner_seek',
            'tuner_tuned',
            'tuner_station',
            'tuner_preset',
            'tuner_preset_store',
            'tuner_preset_clear',
            'tuner_preset_switch',
            'update_tuner',
            'tuner_band_values',
            'tuner_freq_min',
            'tuner_freq_max',
            'tuner_freq_step',
        }
        # dist/Link (multi-room grouping) is a single global resource per
        # device, like tuner - a device has one role/group at a time, not one
        # per zone (setLinkControl/setLinkAudioDelay/setLinkAudioQuality are
        # the exception, see _yamaha_zone_cmds above). Own storage/update path
        # since dist/getDistributionInfo is a distinct resource from netusb.
        self._yamaha_link_cmds = {
            'link_role',
            'link_group_id',
            'link_group_name',
            'link_server_zone',
            'link_audio_dropout',
            'link_join',
            'link_leave',
            'link_add_client',
            'link_remove_client',
            'link_disband',
            'update_link',
            'link_linked',
            'link_devices',
            'link_hosts',
        }
        # alarm/clock cmds are stored in _yamaha_dev_global like netusb (both
        # are host-global, not zone-scoped), but read back through a
        # separate function (_update_alarm_state() vs _update_global_state())
        # - split out as its own set so update_item() can route the
        # post-write refresh to the right one instead of guessing
        self._yamaha_alarm_cmds = {'alarm_on', 'alarm_time', 'alarm_beep'}
        # pure momentary-action cmds: writing True runs the action, any
        # other value is ignored (no payload built, no refresh triggered),
        # and the item resets itself back to False once the action has run
        # (see update_item()) - so a simple bool/checkbox UI doesn't need
        # to be manually toggled off before it can be triggered again.
        # Deliberately excludes link_join/link_add_client/link_remove_client
        # - those carry a target host as their value, not a bare trigger.
        self._yamaha_trigger_cmds = {
            'state',
            'update_dsp',
            'update_netusb',
            'update_tuner',
            'update_link',
            'debug_refresh',
            'link_leave',
            'link_disband',
        }
        self._yamaha_global_cmds = (
            set(self._yamaha_cmds)
            - self._yamaha_zone_cmds
            - self._yamaha_tuner_cmds
            - self._yamaha_link_cmds
            - self._yamaha_alarm_cmds
        )

        # dispatch table used by _dispatch_cmd_build() (called from
        # update_item() to build an outgoing payload for a written cmd).
        # Cmds absent here have no payload-building step at all (pure
        # refresh triggers, debug/capability read-only cmds).
        self._yamaha_cmd_specs = {
            'power': _CmdSpec(build=self._build_cmd_power, label='power', func_check='power'),
            'volume': _CmdSpec(
                build=self._build_cmd_volume, label='volume', func_check='volume', clamp_range='volume_range'
            ),
            'volume_percent': _CmdSpec(build=self._handle_volume_percent, full_context=True),
            'mute': _CmdSpec(build=self._build_cmd_mute, label='mute', func_check='mute'),
            'input': _CmdSpec(build=self._build_cmd_input, label='input', list_check='input_list'),
            'playback': _CmdSpec(build=self._build_cmd_playback),
            'preset': _CmdSpec(build=self._build_cmd_preset),
            'sleep': _CmdSpec(build=self._build_cmd_sleep, label='sleep', func_check='sleep'),
            'sound_program': _CmdSpec(
                build=self._build_cmd_sound_program, label='sound program', list_check='sound_program_list'
            ),
            'surround_3d': _CmdSpec(build=self._build_cmd_surround_3d, label='3D surround', func_check='surround_3d'),
            'direct': _CmdSpec(build=self._build_cmd_direct, label='direct', func_check='direct'),
            'pure_direct': _CmdSpec(build=self._build_cmd_pure_direct, label='pure direct', func_check='pure_direct'),
            'enhancer': _CmdSpec(build=self._build_cmd_enhancer, label='enhancer', func_check='enhancer'),
            'tone_control_mode': _CmdSpec(
                build=self._build_cmd_tone_control_mode, label='tone control', func_check='tone_control'
            ),
            'tone_bass': _CmdSpec(
                build=self._build_cmd_tone_bass,
                label='tone control',
                func_check='tone_control',
                clamp_range='tone_control_range',
            ),
            'tone_treble': _CmdSpec(
                build=self._build_cmd_tone_treble,
                label='tone control',
                func_check='tone_control',
                clamp_range='tone_control_range',
            ),
            'equalizer_mode': _CmdSpec(build=self._build_cmd_equalizer_mode, label='equalizer', func_check='equalizer'),
            'eq_low': _CmdSpec(
                build=self._build_cmd_eq_low, label='equalizer', func_check='equalizer', clamp_range='equalizer_range'
            ),
            'eq_mid': _CmdSpec(
                build=self._build_cmd_eq_mid, label='equalizer', func_check='equalizer', clamp_range='equalizer_range'
            ),
            'eq_high': _CmdSpec(
                build=self._build_cmd_eq_high, label='equalizer', func_check='equalizer', clamp_range='equalizer_range'
            ),
            'balance': _CmdSpec(
                build=self._build_cmd_balance, label='balance', func_check='balance', clamp_range='balance_range'
            ),
            'link_control': _CmdSpec(
                build=self._build_cmd_link_control, label='link control', list_check='link_control_list'
            ),
            'link_audio_delay': _CmdSpec(
                build=self._build_cmd_link_audio_delay, label='link audio delay', list_check='link_audio_delay_list'
            ),
            'link_audio_quality': _CmdSpec(
                build=self._build_cmd_link_audio_quality,
                label='link audio quality',
                list_check='link_audio_quality_list',
            ),
            'link_group_name': _CmdSpec(build=self._build_cmd_dist_set_group_name),
            'link_join': _CmdSpec(build=self._link_join, full_context=True),
            'link_leave': _CmdSpec(build=self._handle_link_leave, full_context=True),
            'link_add_client': _CmdSpec(build=self._link_add_client, full_context=True),
            'link_remove_client': _CmdSpec(build=self._link_remove_client, full_context=True),
            'link_disband': _CmdSpec(build=self._handle_link_disband, full_context=True),
            'alarm_on': _CmdSpec(build=self._build_cmd_alarm_on),
            'alarm_time': _CmdSpec(build=self._build_cmd_alarm_time),
            'alarm_beep': _CmdSpec(build=self._build_cmd_alarm_beep),
            'passthru': _CmdSpec(build=self._handle_passthru, full_context=True),
            'tuner_band': _CmdSpec(build=self._handle_tuner_band, full_context=True),
            'tuner_freq': _CmdSpec(build=self._handle_tuner_freq, full_context=True),
            'tuner_seek': _CmdSpec(build=self._handle_tuner_seek, full_context=True),
            'tuner_preset': _CmdSpec(build=self._handle_tuner_preset, full_context=True),
            'tuner_preset_store': _CmdSpec(build=self._build_cmd_tuner_store_preset),
            'tuner_preset_clear': _CmdSpec(build=self._handle_tuner_preset_clear, full_context=True),
            'tuner_preset_switch': _CmdSpec(build=self._build_cmd_tuner_switch_preset),
        }
        # cheap startup guard against self._yamaha_cmd_specs/_yamaha_zone_cmds
        # drifting apart (e.g. a build target's real signature no longer
        # matching what _dispatch_cmd_build() would call it with) - fails
        # loud at plugin load instead of a runtime TypeError on the first
        # affected write. Checked as a range, not an exact count, since
        # several _build_cmd_X targets have an optional trailing
        # cmd='PUT' parameter _dispatch_cmd_build() never passes.
        for cmd, spec in self._yamaha_cmd_specs.items():
            expected_params = 3 if spec.full_context else (2 if cmd in self._yamaha_zone_cmds else 1)
            params = inspect.signature(spec.build).parameters
            required_params = sum(1 for p in params.values() if p.default is inspect.Parameter.empty)
            if not required_params <= expected_params <= len(params):
                raise AssertionError(
                    f"_yamaha_cmd_specs['{cmd}'].build ({spec.build.__name__}) needs "
                    f'{required_params}-{len(params)} arg(s), _dispatch_cmd_build() passes {expected_params}'
                )

        # store zone-scoped items in 3D-array: _yamaha_dev_zone[host][zone][cmd] = [item, ...]
        # (a list, not a single item - see parse_item()/remove_item(), lets
        # a legacy flat item and its new nested-struct replacement both stay
        # registered for the same cmd during a struct migration)
        # also see parse_item()...
        self._yamaha_dev_zone = {}
        # store host-global items (netusb/clock/passthru): _yamaha_dev_global[host][cmd] = [item, ...]
        self._yamaha_dev_global = {}
        # store tuner items (host-global, own response shape): _yamaha_dev_tuner[host][cmd] = [item, ...]
        self._yamaha_dev_tuner = {}
        # store dist/Link items (host-global, own response shape): _yamaha_dev_link[host][cmd] = [item, ...]
        self._yamaha_dev_link = {}
        # store host addresses of devices
        self._yamaha_hosts = {}
        # resolved IP -> originally configured yamahayxc_host string, so log
        # messages can show a hostname the user actually typed instead of
        # just the resolved IP they may not recognize. See _lookup_host()/
        # _host_label().
        self._yamaha_host_labels = {}
        # store last known tuner band per host ('am'/'fm'), needed to build setFreq/
        # recallPreset/clearPreset URLs for tuner_freq/tuner_seek/tuner_preset* items,
        # since those don't carry the band themselves. Defaults to 'fm' if never polled.
        self._yamaha_tuner_band = {}
        # store which master host a link_join call joined, per client host - needed
        # by link_leave to also tell the master to remove this client, since
        # getDistributionInfo doesn't report the server's IP back to a client.
        # Best-effort only: lost on plugin restart, or if joined via the app/other means.
        self._yamaha_link_master = {}
        # simple incrementing counter used as the startDistribution 'num' parameter.
        # The spec documents this only as "Link distribution number on current
        # MusicCast Network" without defining its semantics precisely; this is a
        # best-effort interpretation (assumed to need a value that changes between
        # distribution (re)starts), unverified against real hardware.
        self._yamaha_link_distribution_num = 0
        # store discovered device capabilities per host, keyed by zone:
        # _yamaha_features[host][zone] = {'func_list': set, 'input_list': set, 'volume_range': (min, max, step) or None}
        # populated from getFeatures in _update_features(); left empty (validation skipped) if unreachable
        self._yamaha_features = {}
        # store discovered tuner capabilities per host:
        # _yamaha_tuner_features[host] = {'func_list': set, 'am_range': (min,max,step) or None,
        #                                  'fm_range': (min,max,step) or None, 'preset_type': 'common'/'separate'/None}
        self._yamaha_tuner_features = {}

        self.srv_port = 41100
        # HTTP request timeout for _submit_payload(). Without one, requests
        # blocks indefinitely on an unreachable host (no RST, e.g. powered
        # off) - and since _initialize() processes hosts synchronously in a
        # loop, one unreachable device would stall getFeatures/getStatus for
        # every other configured device behind it at startup.
        self._yamaha_http_timeout = 5
        self.sock = None
        self.last_total = 0

    def run(self):
        """
        Default run function

        Initializes class and starts the UDP listener (lib.network.Udp_server
        manages its own background thread/event loop; run() doesn't block).
        Incoming notifications are dispatched to _data_received().
        """
        self._sh.trigger(self.get_fullname(), self._initialize)
        self.logger.info('YamahaYXC starting listener')
        self.alive = True
        self.sock = Udp_server(self.srv_port)
        self.sock.set_callbacks(data_received=self._data_received)
        self.sock.start()
        if not self.sock.listening():
            self.logger.error('YamahaYXC UDP listener failed to start on port {}'.format(self.srv_port))

    def stop(self):
        """
        Default stop function

        Stops listener and shuts down plugin
        """
        self.alive = False
        if self.sock:
            self.sock.close()

    def _data_received(self, addr, data):
        """
        callback for lib.network.Udp_server - handle one push notification

        data is already UTF-8-decoded text (Udp_server's contract). addr is
        (remote_ip, remote_port); dispatches item updates and triggers
        targeted state refreshes based on notification content.
        """
        host = addr[0]
        if (
            host not in self._yamaha_dev_zone
            and host not in self._yamaha_dev_global
            and host not in self._yamaha_dev_tuner
            and host not in self._yamaha_dev_link
        ):
            self.logger.debug(f'Received notify from unknown host {self._host_label(host)}')
            return

        # connected device sends updates every second for
        # about 10 minutes without further interaction
        # self.logger.debug(
        #     "Yamaha unicast received from {}: {}".format(host, data))
        data = json.loads(data)

        # zone data arrives under separate top-level keys per zone
        # ('main' / 'zone2' / 'zone3' / 'zone4'), each shaped the same
        # way - handle each zone independently so multiple zones on
        # the same host don't clobber each other
        for zone, zone_items in self._yamaha_dev_zone.get(host, {}).items():
            zone_data = data.get(zone)
            if not zone_data:
                continue
            for cmd in self._yamaha_zone_cmds:
                if cmd in zone_data:
                    try:
                        notify_val = self._convert_value_yxc_to_plugin(zone_data[cmd], cmd, host)
                        for item in zone_items.get(cmd, []):
                            item(notify_val, self.get_fullname())
                        if cmd == 'volume':
                            self._push_volume_percent(host, zone, notify_val, zone_items)
                    except Exception:
                        pass
            if zone_data.get('status_updated') or zone_data.get('signal_info_updated'):
                self._update_zone_state(host, zone)

        # netusb data is shared across all zones of a device
        netusb_data = data.get('netusb')
        global_items = self._yamaha_dev_global.get(host)
        if netusb_data and global_items:
            for cmd in self._yamaha_global_cmds:
                if cmd in netusb_data:
                    try:
                        notify_val = self._convert_value_yxc_to_plugin(netusb_data[cmd], cmd, host)
                        for item in global_items.get(cmd, []):
                            item(notify_val, self.get_fullname())
                    except Exception:
                        pass

            # device told us new info is available?
            if netusb_data.get('play_info_updated'):
                # pull (full) status update from device
                self._update_global_state(host)

            # log possible play errors
            if netusb_data.get('play_error', 0) > 0:
                self.logger.info(
                    'Received netusb error {} from host {}'.format(netusb_data['play_error'], self._host_label(host))
                )

        # tuner push data only carries "something changed" flags, not
        # values directly (per spec) - re-poll getPlayInfo on change
        tuner_data = data.get('tuner')
        if tuner_data and host in self._yamaha_dev_tuner:
            if tuner_data.get('play_info_updated') or tuner_data.get('preset_info_updated'):
                self._update_tuner_state(host)

        # dist push data only carries a "something changed" flag - re-poll
        # getDistributionInfo on change (e.g. after group creation completes)
        dist_data = data.get('dist')
        if dist_data and host in self._yamaha_dev_link:
            if dist_data.get('dist_info_updated'):
                self._update_link_state(host)

    def parse_item(self, item):
        """
        parse all items at startup

        This function is called by the SmartPlugin manager in sh.py for every
        item. If item config "yamahayxc_cmd" is present, item ist stored together
        with associated host and zone.
        Returns update function for the item (update_item())
        """
        if self.has_iattr(item.conf, 'yamahayxc_cmd'):
            yamaha_host = self._lookup_host(item)
            self._add_host_info(yamaha_host)
            yamaha_cmd = self.get_iattr_value(item.conf, 'yamahayxc_cmd').lower()
            if yamaha_cmd not in self._yamaha_cmds:
                self.logger.warn('{} not in valid commands: {}'.format(yamaha_cmd, self._yamaha_cmds))
                return None

            if yamaha_cmd in self._yamaha_zone_cmds:
                yamaha_zone = self._lookup_zone(item)
                # a list, not a single item: lets a legacy (pre-restructure,
                # flat) item and its new nested-struct replacement both stay
                # registered for the same cmd at once during a migration -
                # both receive live push updates, see _push_volume_percent() etc.
                self._yamaha_dev_zone.setdefault(yamaha_host, {}).setdefault(yamaha_zone, {}).setdefault(
                    yamaha_cmd, []
                ).append(item)
                mapping = ('zone', yamaha_host, yamaha_zone, yamaha_cmd)
            elif yamaha_cmd in self._yamaha_tuner_cmds:
                self._yamaha_dev_tuner.setdefault(yamaha_host, {}).setdefault(yamaha_cmd, []).append(item)
                mapping = ('tuner', yamaha_host, None, yamaha_cmd)
            elif yamaha_cmd in self._yamaha_link_cmds:
                self._yamaha_dev_link.setdefault(yamaha_host, {}).setdefault(yamaha_cmd, []).append(item)
                mapping = ('link', yamaha_host, None, yamaha_cmd)
            else:
                self._yamaha_dev_global.setdefault(yamaha_host, {}).setdefault(yamaha_cmd, []).append(item)
                mapping = ('global', yamaha_host, None, yamaha_cmd)

            # register with SmartPlugin's own item bookkeeping too, so this
            # item participates in the core's introspection (get_item_list(),
            # get_item_mapping_list()) and so remove_item() below can find its
            # way back to the right _yamaha_dev_* dict via get_item_mapping()
            # without scanning all four. The nested dicts above remain the
            # actual lookup path for the hot paths (push notifications arrive
            # roughly every second; state polling iterates per host/zone) -
            # get_items_for_mapping() only supports exact-key lookup, not the
            # "all cmds for this host/zone" enumeration those paths need.
            self.add_item(item, config_data_dict=item.conf, mapping=mapping)

            return self.update_item

    def remove_item(self, item) -> bool:
        """
        remove item from plugin bookkeeping, including this plugin's own
        zone/global/tuner/link lookup dicts

        Called by SmartHomeNG core on live item deletion/edit (admin UI),
        not just on plugin shutdown - the default remove_item() only cleans
        up what add_item()/_item_lookup_dict track, not this plugin's own
        dicts. Without this override, a live-removed item would be left
        behind in _yamaha_dev_zone/_global/_tuner/_link and keep receiving
        stale notify-updates indefinitely (until a full plugin restart).
        """
        # get_item_mapping() raises KeyError for an item the base class never
        # tracked (e.g. remove_item() called twice, or for an item this
        # plugin was never registered for) - only look it up if add_item()
        # actually registered it, matching what super().remove_item() itself
        # checks internally
        mapping = self.get_item_mapping(item) if item.property.path in self._plg_item_dict else None
        if not super().remove_item(item):
            return False

        if mapping:
            scope, host, zone, cmd = mapping
            if scope == 'zone':
                zone_cmds = self._yamaha_dev_zone.get(host, {}).get(zone, {})
                self._remove_item_from_cmd_list(zone_cmds, cmd, item)
                if not zone_cmds:
                    self._yamaha_dev_zone.get(host, {}).pop(zone, None)
            elif scope == 'tuner':
                self._remove_item_from_cmd_list(self._yamaha_dev_tuner.get(host, {}), cmd, item)
            elif scope == 'link':
                self._remove_item_from_cmd_list(self._yamaha_dev_link.get(host, {}), cmd, item)
            else:
                self._remove_item_from_cmd_list(self._yamaha_dev_global.get(host, {}), cmd, item)

            # this was the item that carried yamahayxc_host - all its
            # sibling cmd items are children of it and are therefore
            # already gone too (SmartHomeNG removes an item tree
            # deepest-first), so once no cmd is left registered for host
            # anywhere, it really is gone, not just this one item
            if not self._host_has_items(host):
                self._forget_host(host)

        return True

    def _host_has_items(self, host):
        """
        whether any item is still registered for host, across all four
        storage dicts

        _yamaha_dev_zone nests one level deeper (by zone name) than the
        other three, so its truthiness has to be checked per-zone rather
        than at the host level - an empty {zone: {}} shell is otherwise
        indistinguishable from "still has items" by plain dict truthiness.
        """
        return (
            any(self._yamaha_dev_zone.get(host, {}).values())
            or bool(self._yamaha_dev_global.get(host))
            or bool(self._yamaha_dev_tuner.get(host))
            or bool(self._yamaha_dev_link.get(host))
        )

    def _forget_host(self, host):
        """
        drop all bookkeeping for a host once its last configured item has
        been removed (see remove_item()/_host_has_items())

        Prunes the now-empty per-scope shells, the local-interface-IP
        cache and the host label, then pushes the refreshed
        available_devices list live to every *other* host that still has
        one registered - this host's own available_devices item, if any,
        is already gone along with the rest of its item tree, so it needs
        no push of its own.
        """
        self._yamaha_dev_zone.pop(host, None)
        self._yamaha_dev_global.pop(host, None)
        self._yamaha_dev_tuner.pop(host, None)
        self._yamaha_dev_link.pop(host, None)
        self._yamaha_hosts.pop(host, None)
        self._yamaha_host_labels.pop(host, None)
        for other_host in self._yamaha_dev_link:
            self._update_link_hosts_item(other_host)

    def _remove_item_from_cmd_list(self, cmd_dict, cmd, item):
        """
        remove item from cmd_dict[cmd] (a list), pruning the cmd key once
        the list is empty

        Shared by remove_item()'s zone/tuner/link/global branches - all
        four _yamaha_dev_* dicts share this {cmd: [item, ...]} shape one
        level below host (and, for zone, below zone too). Only drops this
        one item, not the whole cmd entry - other items registered for the
        same cmd (e.g. a legacy item kept alive during a struct migration)
        must keep working.
        """
        items = cmd_dict.get(cmd)
        if items is None:
            return
        if item in items:
            items.remove(item)
        if not items:
            cmd_dict.pop(cmd, None)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        recall function if item is modified in sh.py

        Only for "write" commands: calls function to build cmd string
        for given item and runs network query to execute cmd
        In any case a refresh is triggered afterwards to update sh.py items,
        scoped to whatever category yamaha_cmd belongs to (see the
        cmd-routed dispatch at the end of this method)
        """
        if caller != self.get_fullname() and self.alive:
            yamaha_cmd = self.get_iattr_value(item.conf, 'yamahayxc_cmd')
            yamaha_host = self._lookup_host(item)
            yamaha_zone = self._lookup_zone(item)

            if yamaha_cmd in self._yamaha_trigger_cmds and item() is not True:
                return None

            yamaha_payload = self._dispatch_cmd_build(yamaha_cmd, item, yamaha_host, yamaha_zone)
            if yamaha_payload:
                self._submit_payload(yamaha_host, yamaha_payload)

            # refresh only what could plausibly have changed, instead of a
            # full host-wide refresh after every single write. Explicit
            # refresh-trigger cmds are routed first since their whole
            # purpose is a manual poll at a specific scope, independent of
            # their nominal cmd-category membership ('state'/'update_dsp'
            # are technically zone cmds for storage/lookup purposes, but
            # 'state' means "refresh everything", not "refresh this zone").
            if yamaha_cmd == 'state':
                self._update_state(yamaha_host)
            elif yamaha_cmd == 'update_dsp':
                self._update_zone_state(yamaha_host, yamaha_zone)
            elif yamaha_cmd == 'update_netusb':
                self._update_global_state(yamaha_host)
            elif yamaha_cmd == 'update_tuner':
                self._update_tuner_state(yamaha_host)
            elif yamaha_cmd == 'update_link':
                self._update_link_state(yamaha_host)
            elif yamaha_cmd == 'debug_refresh':
                self._update_debug_items(yamaha_host)
            elif yamaha_cmd in self._yamaha_zone_cmds:
                self._update_zone_state(yamaha_host, yamaha_zone)
            elif yamaha_cmd in self._yamaha_alarm_cmds:
                self._update_alarm_state(yamaha_host)
            elif yamaha_cmd in self._yamaha_global_cmds:
                self._update_global_state(yamaha_host)
            elif yamaha_cmd in self._yamaha_tuner_cmds:
                self._update_tuner_state(yamaha_host)
            elif yamaha_cmd in self._yamaha_link_cmds:
                self._update_link_state(yamaha_host)

            if yamaha_cmd in self._yamaha_trigger_cmds:
                item(False, self.get_fullname())
            return None

    def _dispatch_cmd_build(self, yamaha_cmd, item, yamaha_host, yamaha_zone):
        """
        build the outgoing payload for yamaha_cmd, or None if there's
        nothing to submit (unsupported/invalid on this host/zone, or the
        cmd has no payload-building step at all - a pure refresh trigger,
        for instance)

        Looks up yamaha_cmd's _CmdSpec in self._yamaha_cmd_specs (built
        once in __init__) and interprets it:
        - full_context specs (the handful of genuinely special cmds -
          stateful tuner cmds, the link_* orchestrators, passthru,
          volume_percent) are called directly as
          build(item, yamaha_host, yamaha_zone) and handle everything
          themselves, including their own check/warn logic where relevant.
        - every other spec goes through the shared check -> clamp -> build
          pipeline: an optional func_check (self._zone_func_allowed) or
          list_check (self._zone_list_allowed) gates the write, an
          optional clamp_range (self._clamp_zone_range) adjusts the value,
          then build() is called with (value, zone) or just (value)
          depending on whether yamaha_cmd is zone-scoped
          (self._yamaha_zone_cmds, already computed for refresh routing -
          reused here instead of a redundant per-entry flag).
        """
        spec = self._yamaha_cmd_specs.get(yamaha_cmd)
        if spec is None:
            return None
        if spec.full_context:
            return spec.build(item, yamaha_host, yamaha_zone)

        value = item()
        label = spec.label or yamaha_cmd
        if spec.func_check and not self._zone_func_allowed(yamaha_host, yamaha_zone, spec.func_check):
            self.logger.warn(f'{label} not supported on {self._host_label(yamaha_host)} zone {yamaha_zone}, ignoring')
            return None
        if spec.list_check and not self._zone_list_allowed(yamaha_host, yamaha_zone, spec.list_check, value):
            self.logger.warn(
                f'{label} {value} not valid on {self._host_label(yamaha_host)} zone {yamaha_zone}, ignoring'
            )
            return None
        if spec.clamp_range:
            value = self._clamp_zone_range(yamaha_host, yamaha_zone, spec.clamp_range, value)

        if yamaha_cmd in self._yamaha_zone_cmds:
            return spec.build(value, yamaha_zone)
        return spec.build(value)

    # shape-E dispatch targets: cmds that need more than the shared
    # check -> clamp -> build pipeline _dispatch_cmd_build() provides for
    # everything else. Each has the uniform (item, host, zone) signature
    # full_context specs are called with.

    def _handle_passthru(self, item, host, zone):
        """dispatch target for 'passthru' - the raw item value IS the payload, no builder function exists"""
        return item()

    def _handle_volume_percent(self, item, host, zone):
        """
        dispatch target for 'volume_percent' - shares volume's func_check
        and _build_cmd_volume, but needs the percent->native conversion
        (which can fail with its own distinct info-level message when the
        range isn't known yet) instead of a plain check+clamp+build
        """
        if not self._zone_func_allowed(host, zone, 'volume'):
            self.logger.warn(f'volume not supported on {self._host_label(host)} zone {zone}, ignoring')
            return None
        native = self._percent_to_native_volume(host, zone, item())
        if native is None:
            self.logger.info(
                f'volume range unknown for {self._host_label(host)} zone {zone}, cannot convert volume_percent'
            )
            return None
        return self._build_cmd_volume(native, zone)

    def _handle_tuner_band(self, item, host, zone):
        """
        dispatch target for 'tuner_band' - besides building the payload,
        remembers the selected band in self._yamaha_tuner_band[host] as a
        side effect, since tuner_freq/seek/preset*/preset_clear all need
        it as implicit context (see _handle_tuner_freq() etc. below) and
        don't carry it themselves
        """
        if not self._tuner_func_allowed(host, item()):
            self.logger.warn(f'tuner band {item()} not supported on {self._host_label(host)}, ignoring')
            return None
        self._yamaha_tuner_band[host] = item()
        return self._build_cmd_tuner_set_band(item())

    def _handle_tuner_freq(self, item, host, zone):
        """dispatch target for 'tuner_freq' - band comes from _yamaha_tuner_band, not the item itself"""
        band = self._yamaha_tuner_band.get(host, 'fm')
        clamped = self._clamp_tuner_freq(host, band, item())
        return self._build_cmd_tuner_set_freq_direct(band, clamped)

    def _handle_tuner_seek(self, item, host, zone):
        """dispatch target for 'tuner_seek' - band comes from _yamaha_tuner_band, not the item itself"""
        band = self._yamaha_tuner_band.get(host, 'fm')
        return self._build_cmd_tuner_seek(band, item())

    def _handle_tuner_preset(self, item, host, zone):
        """dispatch target for 'tuner_preset' - band comes from _yamaha_tuner_band, not the item itself"""
        band = self._yamaha_tuner_band.get(host, 'fm')
        return self._build_cmd_tuner_recall_preset(self._tuner_preset_band(host, band), item())

    def _handle_tuner_preset_clear(self, item, host, zone):
        """dispatch target for 'tuner_preset_clear' - band comes from _yamaha_tuner_band, not the item itself"""
        band = self._yamaha_tuner_band.get(host, 'fm')
        return self._build_cmd_tuner_clear_preset(self._tuner_preset_band(host, band), item())

    def _handle_link_leave(self, item, host, zone):
        """dispatch target for 'link_leave' - adapts _link_leave()'s (host, zone) signature to the uniform full_context call shape"""
        self._link_leave(host, zone)
        return None

    def _handle_link_disband(self, item, host, zone):
        """dispatch target for 'link_disband' - adapts _link_disband()'s (host, zone) signature to the uniform full_context call shape"""
        self._link_disband(host, zone)
        return None

    #
    # initialization functions
    #

    def _initialize(self):
        """
        Default initialization function

        Calls _update_features and _update_state for all registered hosts in _yamaha_hosts[]
        """
        self.logger.info('YamahaYXC now initializing current state')
        # available_devices is pure plugin bookkeeping (configured hosts),
        # not device state - seed it immediately, independent of any
        # network round trip, instead of waiting for the first link action
        # or push notification to populate it. Still needed even though
        # _update_state() below now pushes real items too: if a host is
        # unreachable at startup, _update_link_state() bails out before
        # ever reaching its own _update_link_hosts_item() call, so a
        # host's available_devices would otherwise stay empty until that
        # host comes back and something else triggers a refresh.
        for yamaha_host in self._yamaha_dev_link:
            self._update_link_hosts_item(yamaha_host)
        for yamaha_host in list(self._yamaha_hosts):
            self.logger.info('Initializing items for host: {}'.format(self._host_label(yamaha_host)))
            self._update_features(yamaha_host)
            self._update_state(yamaha_host)
            self._update_debug_items(yamaha_host)

    def _lookup_host(self, item):
        """
        get host IP configured for submitted item

        Item.find_attribute() (SmartHomeNG core, lib/item/_internal/
        _pathresolution.py) walks up the item tree to the nearest item
        (self or an ancestor) carrying yamahayxc_host - needed because cmd
        items aren't necessarily direct children of the item carrying
        yamahayxc_host/yamahayxc_zone; capability sub-items (e.g.
        volume_min/volume_max/volume_percent nested under volume) sit one
        level further down. Its silent ''-on-not-found default is turned
        back into a loud failure here - this plugin's own convention never
        puts yamahayxc_host on a cmd item itself, so a miss almost always
        means a genuinely broken config, and socket.gethostbyname('') can
        silently resolve to the local machine on some resolvers rather
        than erroring, which would be a far more confusing failure than a
        clear KeyError pointing at the offending item.
        Remembers the originally configured name against the resolved IP
        (see _host_label()) so log messages can show it even though the
        rest of the plugin only ever deals in resolved IPs from here on.
        """
        configured_name = item.find_attribute('yamahayxc_host')
        if not configured_name:
            raise KeyError('yamahayxc_host not found in any ancestor of {}'.format(item.property.path))
        resolved_ip = socket.gethostbyname(configured_name)
        self._register_host_label(resolved_ip, configured_name)
        return resolved_ip

    def _register_host_label(self, resolved_ip, configured_name):
        """
        remember a host's originally configured name against its resolved
        IP (see _host_label()/_yamaha_host_labels) - the counterpart to
        _forget_host()

        Runs on every _lookup_host() call, i.e. on every read/write for
        every item under this host, so it only actually writes (and only
        pushes a refresh) when the mapping is new or changed - otherwise
        this hot path would re-push available_devices to every host on
        every single item access.

        The live push itself is further gated on self.alive: during the
        initial item tree load (parse_item() for the whole config, before
        run()/_initialize()), self.alive is still False, so this stays
        silent and _initialize()'s own seed pass (see there) does one
        clean push once loading is done - it would otherwise fire once
        per newly-discovered host while still mid-load, pushing a
        different partial host list to already-parsed items each time.
        Once alive, a host added or renamed via a live item edit/create
        (see lib/item/items.py's edit_item()/create_item()) pushes the
        update immediately instead of waiting for the next network
        round trip.
        """
        if self._yamaha_host_labels.get(resolved_ip) == configured_name:
            return
        self._yamaha_host_labels[resolved_ip] = configured_name
        if self.alive:
            for other_host in self._yamaha_dev_link:
                self._update_link_hosts_item(other_host)

    def _host_label(self, host):
        """
        return a log-friendly label for a resolved host IP

        includes the originally configured hostname if one is known and
        differs from the IP (e.g. 'rx-av (192.168.2.130)') - a user who
        configured yamahayxc_host as a hostname may not recognize the bare
        IP in a log message. Falls back to just the IP if no name is known
        (e.g. before this host's first item has been parsed) or if the
        configured value already was the IP.
        """
        name = self._yamaha_host_labels.get(host)
        if name and name != host:
            return '{} ({})'.format(name, host)
        return host

    def _lookup_zone(self, item):
        """
        get zone config for item

        see _lookup_host() for why Item.find_attribute() is used and why
        its silent not-found default is turned back into a loud failure
        """
        yamaha_zone = item.find_attribute('yamahayxc_zone')
        if not yamaha_zone:
            raise KeyError('yamahayxc_zone not found in any ancestor of {}'.format(item.property.path))
        return yamaha_zone

    def _add_host_info(self, host):
        """
        store local interface IP for connection to a given host

        just exists in case the server is multihomed. in most cases not necessary
        """
        try:
            local_ip = self._yamaha_hosts[host]
            return
        except Exception:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((host, 80))
            local_ip = s.getsockname()[0]
            s.close()
            self._yamaha_hosts[host] = local_ip

    def _update_features(self, host):
        """
        query getFeatures for host and store per-zone and tuner capabilities

        parses zone().func_list (valid commands), zone().input_list/
        sound_program_list/tone_control_mode_list/equalizer_mode_list/
        link_control_list/link_audio_delay_list/link_audio_quality_list
        (valid values for each of those writable cmds - see
        self._yamaha_list_cmds/_update_list_items()) and zone().range_step
        (min/max/step for the ranged parameters this plugin writes: volume,
        tone_control - covers both bass and treble, equalizer - covers
        low/mid/high, balance) into self._yamaha_features[host][zone], and
        tuner.func_list (valid bands), tuner.range_step ('am'/'fm'
        min/max/step) and tuner.preset.type into
        self._yamaha_tuner_features[host].
        Leaves both unset on network error, so validation is skipped (fails
        open) rather than blocking all commands for that host.
        """
        data = self._submit_payload(host, self._build_cmd_get_features())
        if not data:
            self.logger.info(
                'Could not retrieve features for host {}, skipping capability validation'.format(self._host_label(host))
            )
            return

        zones = {}
        for zone in data.get('zone', []):
            zone_id = zone.get('id')
            if zone_id is None:
                continue
            ranges = {}
            for range_step in zone.get('range_step', []):
                range_id = range_step.get('id')
                if range_id in ('volume', 'tone_control', 'equalizer', 'balance'):
                    ranges[range_id + '_range'] = (range_step.get('min'), range_step.get('max'), range_step.get('step'))
            zones[zone_id] = {
                'func_list': set(zone.get('func_list', [])),
                'input_list': set(zone.get('input_list', [])),
                'sound_program_list': set(zone.get('sound_program_list', [])),
                'tone_control_mode_list': set(zone.get('tone_control_mode_list', [])),
                'equalizer_mode_list': set(zone.get('equalizer_mode_list', [])),
                'link_control_list': set(zone.get('link_control_list', [])),
                'link_audio_delay_list': set(zone.get('link_audio_delay_list', [])),
                'link_audio_quality_list': set(zone.get('link_audio_quality_list', [])),
                'volume_range': ranges.get('volume_range'),
                'tone_control_range': ranges.get('tone_control_range'),
                'equalizer_range': ranges.get('equalizer_range'),
                'balance_range': ranges.get('balance_range'),
            }
        self._yamaha_features[host] = zones
        self._update_range_items(host, zones)
        self._update_list_items(host, zones)
        self._update_zone_flags(host, zones)

        tuner = data.get('tuner')
        if tuner:
            am_range = fm_range = None
            for range_step in tuner.get('range_step', []):
                if range_step.get('id') == 'am':
                    am_range = (range_step.get('min'), range_step.get('max'), range_step.get('step'))
                elif range_step.get('id') == 'fm':
                    fm_range = (range_step.get('min'), range_step.get('max'), range_step.get('step'))
            self._yamaha_tuner_features[host] = {
                'func_list': set(tuner.get('func_list', [])),
                'am_range': am_range,
                'fm_range': fm_range,
                'preset_type': tuner.get('preset', {}).get('type'),
            }
        else:
            self._yamaha_tuner_features.pop(host, None)
        self._update_tuner_band_values_item(host)

    def _update_range_items(self, host, zones):
        """
        push discovered min/max/step values to registered capability items

        Called once per _update_features() run (capabilities don't change at
        runtime). Silently skips items whose range is unknown/unsupported
        for that host/zone (fails open, same convention as the rest of the
        getFeatures handling) instead of pushing a placeholder value.
        """
        for zone_id, zone_items in self._yamaha_dev_zone.get(host, {}).items():
            features = zones.get(zone_id)
            for yamaha_cmd, items in zone_items.items():
                if yamaha_cmd not in self._yamaha_range_cmds:
                    continue
                range_key, idx = self._yamaha_range_cmds[yamaha_cmd]
                range_tuple = features.get(range_key) if features else None
                if range_tuple is None or range_tuple[idx] is None:
                    continue
                for item in items:
                    item(range_tuple[idx], self.get_fullname())

    def _update_list_items(self, host, zones):
        """
        push discovered list-valued capabilities (e.g. input_sources) to
        registered capability items

        Same convention as _update_range_items(): called once per
        _update_features() run, skips items whose feature list is unknown
        for that host/zone rather than pushing an empty placeholder.
        """
        for zone_id, zone_items in self._yamaha_dev_zone.get(host, {}).items():
            features = zones.get(zone_id)
            for yamaha_cmd, items in zone_items.items():
                if yamaha_cmd not in self._yamaha_list_cmds:
                    continue
                feature_key = self._yamaha_list_cmds[yamaha_cmd]
                feature_list = features.get(feature_key) if features else None
                if feature_list is None:
                    continue
                value = sorted(feature_list)
                for item in items:
                    item(value, self.get_fullname())

    def _update_tuner_band_values_item(self, host):
        """
        push discovered valid tuner bands to the registered 'tuner_band_values' item

        Called once per _update_features() run, same convention as
        _update_list_items(). NOT tuner.func_list verbatim - that field also
        reports 'rds' (RDS decoding available while tuned to fm) alongside
        the actual selectable bands, but setBand only accepts am/fm/dab per
        spec - so this filters func_list down to that settable subset.
        Silently skips (leaves the item at its last value) if tuner
        capabilities are unknown for this host.
        """
        features = self._yamaha_tuner_features.get(host)
        if features is None:
            return
        bands = sorted(features['func_list'] & {'am', 'fm', 'dab'})
        for item in self._yamaha_dev_tuner.get(host, {}).get('tuner_band_values', []):
            item(bands, self.get_fullname())

    def _update_zone_flags(self, host, zones):
        """
        push 'zone_present'/'dsp_available' to registered capability items

        Same convention as _update_range_items()/_update_list_items():
        called once per _update_features() run, only touches zones with at
        least one registered item. Unlike those two, both indicators
        always get a value (default False) rather than being skipped when
        the zone is unknown - "unknown" and "genuinely absent" collapse to
        the same False here, since these are presence signals, not
        capability data that's meaningless without a real value.

        'zone_present': True iff zone_id is a key in zones, i.e. *this*
        getFeatures call actually reported it - correctly False for a zone
        the user configured items for but that doesn't exist on the
        device, not just "zone has no registered items" (which wouldn't
        even reach this loop).

        'dsp_available': True iff the zone's func_list intersects
        _DSP_FUNC_NAMES, or its sound_program_list is non-empty -
        sound_program's own availability signal is a non-empty list (see
        _zone_list_allowed()/_yamaha_cmd_specs['sound_program']), not a
        func_list entry, so both are checked.
        """
        for zone_id, zone_items in self._yamaha_dev_zone.get(host, {}).items():
            features = zones.get(zone_id)
            present = features is not None
            dsp_available = bool(
                features and (features['func_list'] & _DSP_FUNC_NAMES or features['sound_program_list'])
            )

            for item in zone_items.get('zone_present', []):
                item(present, self.get_fullname())
            for item in zone_items.get('dsp_available', []):
                item(dsp_available, self.get_fullname())

    def _jsonify(self, obj):
        """
        recursively convert sets/tuples to lists so a value is safe to push
        into a dict-typed debug item (sets aren't JSON-serializable, and
        show up oddly in the admin UI's dict view)

        Item objects are handled by callers directly (converted to their
        path string), not here.
        """
        if isinstance(obj, dict):
            return {key: self._jsonify(value) for key, value in obj.items()}
        if isinstance(obj, set):
            return [self._jsonify(value) for value in sorted(obj, key=str)]
        if isinstance(obj, (tuple, list)):
            return [self._jsonify(value) for value in obj]
        return obj

    def _update_debug_items(self, host):
        """
        push snapshots of this plugin's own internal bookkeeping dicts to
        registered debug items (struct yamahayxc.debug) - diagnostic only,
        no part of the YXC protocol.

        debug_features/debug_dev_zone are per-zone; debug_tuner_features/
        debug_dev_global/debug_dev_tuner/debug_dev_link are per-host
        (global). Registered items (not the cmd_dict values themselves,
        which are Item objects) are converted to their item path string, so
        the pushed value stays JSON/dict-friendly.
        """
        for zone, zone_items in self._yamaha_dev_zone.get(host, {}).items():
            features_items = zone_items.get('debug_features')
            if features_items:
                value = self._jsonify(self._yamaha_features.get(host, {}).get(zone, {}))
                for item in features_items:
                    item(value, self.get_fullname())

            dev_zone_items = zone_items.get('debug_dev_zone')
            if dev_zone_items:
                value = {cmd: [it.property.path for it in items] for cmd, items in zone_items.items()}
                for item in dev_zone_items:
                    item(value, self.get_fullname())

        global_items = self._yamaha_dev_global.get(host, {})

        tuner_features_items = global_items.get('debug_tuner_features')
        if tuner_features_items:
            value = self._jsonify(self._yamaha_tuner_features.get(host, {}))
            for item in tuner_features_items:
                item(value, self.get_fullname())

        dev_global_items = global_items.get('debug_dev_global')
        if dev_global_items:
            value = {cmd: [it.property.path for it in items] for cmd, items in global_items.items()}
            for item in dev_global_items:
                item(value, self.get_fullname())

        dev_tuner_items = global_items.get('debug_dev_tuner')
        if dev_tuner_items:
            tuner_items = self._yamaha_dev_tuner.get(host, {})
            value = {cmd: [it.property.path for it in items] for cmd, items in tuner_items.items()}
            for item in dev_tuner_items:
                item(value, self.get_fullname())

        dev_link_items = global_items.get('debug_dev_link')
        if dev_link_items:
            link_items = self._yamaha_dev_link.get(host, {})
            value = {cmd: [it.property.path for it in items] for cmd, items in link_items.items()}
            for item in dev_link_items:
                item(value, self.get_fullname())

    def _get_zone_features(self, host, zone):
        """
        return discovered feature dict for host/zone, or None if unknown

        None means either getFeatures hasn't been called yet / failed, or the
        configured zone isn't reported by the device. Callers must treat None
        as "skip validation", not as "zone invalid".
        """
        return self._yamaha_features.get(host, {}).get(zone)

    def _zone_func_allowed(self, host, zone, func):
        """
        return whether func is listed in the zone's discovered func_list

        fails open (returns True) if capabilities are unknown for host/zone
        """
        features = self._get_zone_features(host, zone)
        if features is None:
            return True
        return func in features['func_list']

    def _zone_list_allowed(self, host, zone, list_key, value):
        """
        return whether value is listed in the zone's discovered list_key (e.g.
        'input_list', 'sound_program_list')

        fails open (returns True) if capabilities are unknown for host/zone
        """
        features = self._get_zone_features(host, zone)
        if features is None:
            return True
        return value in features[list_key]

    def _zone_input_allowed(self, host, zone, value):
        """return whether value is listed in the zone's discovered input_list"""
        return self._zone_list_allowed(host, zone, 'input_list', value)

    def _zone_sound_program_allowed(self, host, zone, value):
        """return whether value is listed in the zone's discovered sound_program_list"""
        return self._zone_list_allowed(host, zone, 'sound_program_list', value)

    def _clamp_zone_range(self, host, zone, range_key, value):
        """
        clamp value to the zone's discovered min/max for range_key (e.g.
        'volume_range', 'tone_control_range', 'equalizer_range',
        'balance_range'), snapped to step

        returns value unchanged if capabilities/range are unknown for host/zone
        """
        features = self._get_zone_features(host, zone)
        if features is None or features[range_key] is None:
            return value
        range_min, range_max, range_step = features[range_key]
        if range_min is None or range_max is None:
            return value
        clamped = max(range_min, min(range_max, value))
        if range_step:
            clamped = range_min + round((clamped - range_min) / range_step) * range_step
        return clamped

    def _native_to_percent(self, host, zone, value):
        """
        convert a native volume value to 0..100, using the zone's
        discovered volume_range

        returns None if the range is unknown or degenerate (min == max) -
        callers must treat None as "can't scale yet", not as 0%
        """
        features = self._get_zone_features(host, zone)
        if features is None or features.get('volume_range') is None:
            return None
        range_min, range_max, _ = features['volume_range']
        if range_min is None or range_max is None or range_max == range_min:
            return None
        return round((value - range_min) / (range_max - range_min) * 100)

    def _percent_to_native_volume(self, host, zone, percent):
        """
        convert a 0..100 percent value to the zone's native volume range,
        clamped/step-snapped via _clamp_zone_range()

        returns None if the range is unknown - percent has nothing to scale
        against yet (e.g. getFeatures hasn't completed for this host)
        """
        features = self._get_zone_features(host, zone)
        if features is None or features.get('volume_range') is None:
            return None
        range_min, range_max, _ = features['volume_range']
        if range_min is None or range_max is None:
            return None
        native = range_min + (percent / 100) * (range_max - range_min)
        return self._clamp_zone_range(host, zone, 'volume_range', native)

    def _push_volume_percent(self, host, zone, native_value, zone_items):
        """
        derive and push the zone's volume_percent item (if configured) from
        a freshly-read native volume value

        Shared by _update_zone_state()'s getStatus polling loop and
        _data_received()'s push-notification handler, so both read paths
        keep volume_percent in sync with 'volume' the same way instead of
        duplicating the conversion.
        """
        percent_items = zone_items.get('volume_percent')
        if not percent_items:
            return
        percent = self._native_to_percent(host, zone, native_value)
        if percent is not None:
            for item in percent_items:
                item(percent, self.get_fullname())

    def _tuner_func_allowed(self, host, func):
        """
        return whether func (e.g. 'am'/'fm') is listed in the tuner's discovered func_list

        fails open (returns True) if capabilities/tuner are unknown for host
        """
        features = self._yamaha_tuner_features.get(host)
        if features is None:
            return True
        return func in features['func_list']

    def _tuner_preset_band(self, host, band):
        """
        return the band value to use for tuner preset ops (recallPreset/clearPreset)

        per spec, this must be 'common' if the device's preset type is common
        across bands, otherwise the actual band. Falls back to band unchanged
        if capabilities/tuner are unknown for host.
        """
        features = self._yamaha_tuner_features.get(host)
        if features is None:
            return band
        return 'common' if features.get('preset_type') == 'common' else band

    def _clamp_tuner_freq(self, host, band, value):
        """
        clamp value to the tuner's discovered am/fm min/max, snapped to step

        returns value unchanged if capabilities/range are unknown for host/band
        """
        features = self._yamaha_tuner_features.get(host)
        if features is None:
            return value
        band_range = features.get('{}_range'.format(band))
        if not band_range:
            return value
        freq_min, freq_max, freq_step = band_range
        if freq_min is None or freq_max is None:
            return value
        clamped = max(freq_min, min(freq_max, value))
        if freq_step:
            clamped = freq_min + round((clamped - freq_min) / freq_step) * freq_step
        return clamped

    def _push_tuner_freq_range(self, host, band):
        """
        push the given band's min/max/step to the registered tuner_freq_min/
        max/step items

        Unlike zone ranges (pushed once from _update_features(), static per
        host/zone), the tuner frequency range depends on which band is
        currently tuned (am and fm have different ranges) - called from
        _update_tuner_state() every time the current band becomes known
        (regular poll or post-write refresh), not just at capability
        discovery time. Silently skips if capabilities/range are unknown for
        this host/band (fails open, same convention as _clamp_tuner_freq()).
        """
        features = self._yamaha_tuner_features.get(host)
        band_range = features.get('{}_range'.format(band)) if features else None
        if not band_range:
            return
        tuner_items = self._yamaha_dev_tuner.get(host, {})
        for yamaha_cmd, idx in (('tuner_freq_min', 0), ('tuner_freq_max', 1), ('tuner_freq_step', 2)):
            if band_range[idx] is None:
                continue
            for item in tuner_items.get(yamaha_cmd, []):
                item(band_range[idx], self.get_fullname())

    #
    # process not individually accessible items
    #

    def _update_state(self, yamaha_host, update_items=True):
        """
        refresh full state for yamaha_host

        polls getStatus for every zone configured on this host, getPlayInfo
        (netusb, shared across zones) and the alarm clock settings. Each zone
        is polled and updated independently, so multiple zones on the same
        host (e.g. main + zone2 on one receiver) don't clobber each other -
        previously all zones were merged into a single response dict, which
        only worked correctly for a single zone per host.
        """
        for zone in list(self._yamaha_dev_zone.get(yamaha_host, {}).keys()):
            self._update_zone_state(yamaha_host, zone, update_items)

        if yamaha_host in self._yamaha_dev_global:
            self._update_global_state(yamaha_host, update_items)

        if yamaha_host in self._yamaha_dev_tuner:
            self._update_tuner_state(yamaha_host, update_items)

        if yamaha_host in self._yamaha_dev_link:
            self._update_link_state(yamaha_host, update_items)

        self._update_alarm_state(yamaha_host, update_items)

    def _update_zone_state(self, yamaha_host, zone, update_items=True):
        """
        retrieve status for a single zone via getStatus and update its items

        Return None prematurely if no network response was received
        Silently ignores invalid (None) values for commands
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_state(zone))
        if state is None:
            return None

        if update_items:
            zone_items = self._yamaha_dev_zone.get(yamaha_host, {}).get(zone, {})
            for yamaha_cmd, items in zone_items.items():
                if yamaha_cmd not in self._yamaha_ignore_cmds_upd:
                    value = self._get_value_from_response(state, yamaha_cmd, yamaha_host)
                    if value is not None:
                        for item in items:
                            item(value, self.get_fullname())
                        if yamaha_cmd == 'volume':
                            self._push_volume_percent(yamaha_host, zone, value, zone_items)

        return state

    def _update_global_state(self, yamaha_host, update_items=True):
        """
        retrieve netusb playback status via getPlayInfo and update host-global items

        netusb is a single shared source per device, not scoped to a zone
        Return None prematurely if no network response was received
        Silently ignores invalid (None) values for commands
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_play_state())
        if state is None:
            return None

        if update_items:
            global_items = self._yamaha_dev_global.get(yamaha_host, {})
            for yamaha_cmd, items in global_items.items():
                if yamaha_cmd not in self._yamaha_ignore_cmds_upd:
                    value = self._get_value_from_response(state, yamaha_cmd, yamaha_host)
                    if value is not None:
                        for item in items:
                            item(value, self.get_fullname())

        return state

    def _update_tuner_state(self, yamaha_host, update_items=True):
        """
        retrieve tuner status via getPlayInfo and update tuner items

        tuner is a single shared resource per device, like netusb, but its
        response is nested per band ('am'/'fm'/'dab', see _extract_tuner_value)
        instead of a flat cmd: value dict, so it can't reuse
        _get_value_from_response(). Also remembers the current band in
        self._yamaha_tuner_band, needed to build write URLs for tuner_freq/
        tuner_seek/tuner_preset* items.
        Return None prematurely if no network response was received
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_tuner_state())
        if state is None:
            return None

        band = state.get('band')
        if band:
            self._yamaha_tuner_band[yamaha_host] = band
            self._push_tuner_freq_range(yamaha_host, band)

        if update_items:
            tuner_items = self._yamaha_dev_tuner.get(yamaha_host, {})
            for yamaha_cmd, items in tuner_items.items():
                value = self._extract_tuner_value(state, yamaha_cmd)
                if value is not None:
                    for item in items:
                        item(value, self.get_fullname())

        return state

    def _extract_tuner_value(self, state, cmd):
        """
        extract a tuner item's value from a getPlayInfo response

        returns None for write-only cmds (preset recall/store/clear/switch,
        seek) - they have nothing to read back, same convention as
        _yamaha_ignore_cmds_upd for the flat-dict cmds. Also returns None
        (by falling through) for tuner_band_values/tuner_freq_min/max/step -
        those are getFeatures-derived, not part of a getPlayInfo response,
        and are pushed separately by _update_tuner_band_values_item()/
        _push_tuner_freq_range() instead.
        """
        band = state.get('band')
        band_data = state.get(band, {}) if band in ('am', 'fm') else {}
        if cmd == 'tuner_band':
            return band
        elif cmd == 'tuner_freq':
            return band_data.get('freq')
        elif cmd == 'tuner_tuned':
            return band_data.get('tuned')
        elif cmd == 'tuner_station':
            rds = state.get('rds')
            return rds.get('program_service', '') if rds else ''
        return None

    def _update_link_state(self, yamaha_host, update_items=True):
        """
        retrieve dist/Link status via getDistributionInfo and update link items

        response fields (group_id/group_name/server_zone/audio_dropout) are
        flat, so this reuses _get_value_from_response() like
        _update_zone_state()/_update_global_state(). 'role' is excluded from
        that generic loop (see _yamaha_ignore_cmds_upd) and pushed here with
        a group_id=0 => 'none' override instead of the raw device value -
        per the YXC Advanced spec, group_id is reset to all-zeros on
        disconnect but role has been observed lagging behind that on real
        hardware. link_linked/link_devices are fully derived, not raw
        response fields at all.
        Return None prematurely if no network response was received
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_link_state())
        if state is None:
            return None

        if update_items:
            link_items = self._yamaha_dev_link.get(yamaha_host, {})
            for yamaha_cmd, items in link_items.items():
                if yamaha_cmd not in self._yamaha_ignore_cmds_upd:
                    value = self._get_value_from_response(state, yamaha_cmd, yamaha_host)
                    if value is not None:
                        for item in items:
                            item(value, self.get_fullname())

            linked = self._link_is_grouped(state.get('group_id'))

            linked_items = link_items.get('link_linked')
            if linked_items:
                for item in linked_items:
                    item(linked, self.get_fullname())

            role_items = link_items.get('link_role')
            if role_items:
                role_value = state.get('role', 'none') if linked else 'none'
                for item in role_items:
                    item(role_value, self.get_fullname())

            devices_items = link_items.get('link_devices')
            if devices_items:
                devices_value = self._extract_link_devices(state)
                for item in devices_items:
                    item(devices_value, self.get_fullname())

            self._update_link_hosts_item(yamaha_host, link_items)

        return state

    def _link_is_grouped(self, group_id):
        """
        return whether group_id represents a real (non-empty, non-zero)
        Link group

        Per the YXC Advanced spec, group_id is reset to all-zero hex
        ("000...") when a device cancels its Link role - a plain truthiness
        or non-empty check isn't enough, that all-zero string is truthy.
        """
        if not group_id:
            return False
        try:
            return int(group_id, 16) != 0
        except (TypeError, ValueError):
            return bool(group_id)

    def _extract_link_devices(self, state):
        """
        extract currently registered client IP addresses from a
        getDistributionInfo response

        Per spec, 'client_list' is an array of {ip_address, data_type}
        objects (not the flat IP-string array setServerInfo's own
        client_list parameter takes to write it - the read and write shapes
        differ), and is only populated when this host's role is 'server' -
        a client device's own getDistributionInfo won't list its
        groupmates, only the server tracks the roster.
        """
        client_list = state.get('client_list') or []
        return sorted({entry.get('ip_address') for entry in client_list if entry.get('ip_address')})

    def _update_link_hosts_item(self, host, link_items=None):
        """
        push the list of all hosts this plugin instance currently knows
        about (i.e. has at least one configured item for) to the
        link_hosts item, if registered for this host

        Purely a plugin-bookkeeping convenience (e.g. for a visu dropdown
        picking a client.join/server.add_device target) - not derived from
        any device response, so it can (and does, see _initialize()) get
        populated before any network round trip. Uses the originally
        configured name/IP (see _yamaha_host_labels), not internal
        resolved-IP-only bookkeeping.
        """
        if link_items is None:
            link_items = self._yamaha_dev_link.get(host, {})
        items = link_items.get('link_hosts')
        if not items:
            return
        value = sorted(set(self._yamaha_host_labels.values()))
        for item in items:
            item(value, self.get_fullname())

    #
    # dist/Link (multi-room grouping) orchestration
    #
    # UNVERIFIED against real multi-device hardware - see the module-level TODO
    # note at the top of this file. Each of these fires a fixed sequence of
    # calls per the YXC Advanced spec's application notes (section 9.1) and
    # does not wait for the device-side "linking/unlinking in progress"
    # (response codes 200/201) to complete; the next state poll or push
    # notification is relied on to reflect the eventual result.
    #

    def _link_join(self, item, yamaha_host, yamaha_zone):
        """
        orchestrate this host/zone joining (or creating) a Link group led by
        the host given in item's value

        Sequence (spec 9.1.2 "Making a Group" / 9.1.4 "Adding a client"):
          1. query the target master's current dist status
          2. if it's already a server, reuse its group_id/server_zone;
             otherwise generate a new group_id and default the new server's
             zone to 'main' (this call only carries the master's host, not a
             zone there - same class of limitation as recallPreset's hardcoded
             zone=main elsewhere in this plugin)
          3. setClientInfo on self (this host/zone)
          4. setServerInfo(type=add) on the master, adding self as a client
          5. startDistribution on the master
        Tracks the master in self._yamaha_link_master so link_leave can find
        it again later.
        """
        master_value = item()
        if not master_value:
            self.logger.warn('link_join needs a target host value, got {!r}'.format(master_value))
            return
        try:
            master_host = socket.gethostbyname(master_value)
        except Exception:
            self.logger.warn('link_join: could not resolve host {!r}'.format(master_value))
            return

        master_info = self._submit_payload(master_host, self._build_cmd_get_link_state())
        if master_info is None:
            self.logger.warn('link_join: master {} not reachable'.format(self._host_label(master_host)))
            return

        if master_info.get('role') == 'server':
            group_id = master_info.get('group_id')
            master_zone = master_info.get('server_zone', 'main')
        else:
            group_id = secrets.token_hex(16).upper()
            master_zone = 'main'

        self._submit_payload(yamaha_host, self._build_cmd_dist_set_client_info(group_id, [yamaha_zone]))
        self._submit_payload(
            master_host, self._build_cmd_dist_set_server_info(group_id, master_zone, 'add', [yamaha_host])
        )
        self._yamaha_link_distribution_num += 1
        self._submit_payload(master_host, self._build_cmd_dist_start_distribution(self._yamaha_link_distribution_num))

        self._yamaha_link_master[yamaha_host] = master_host
        if master_host in self._yamaha_dev_link:
            self._update_link_state(master_host)

    def _link_leave(self, yamaha_host, yamaha_zone):
        """
        orchestrate this host/zone leaving its current Link group

        Clears this host's own client info. If link_join tracked which master
        this host joined, also removes it from that master's client list.
        Best-effort: if the master isn't tracked (plugin restarted since
        joining, or the join happened via the app/other means), only the
        local clear happens - use link_remove_client on the master to clean
        up manually in that case.
        """
        self._submit_payload(yamaha_host, self._build_cmd_dist_set_client_info('', [yamaha_zone]))

        master_host = self._yamaha_link_master.pop(yamaha_host, None)
        if not master_host:
            self.logger.info(
                'link_leave: no tracked master for {}, only cleared local client info'.format(
                    self._host_label(yamaha_host)
                )
            )
            return

        master_info = self._submit_payload(master_host, self._build_cmd_get_link_state())
        if master_info and master_info.get('role') == 'server':
            self._submit_payload(
                master_host,
                self._build_cmd_dist_set_server_info(
                    master_info.get('group_id'), master_info.get('server_zone', 'main'), 'remove', [yamaha_host]
                ),
            )
            self._yamaha_link_distribution_num += 1
            self._submit_payload(
                master_host, self._build_cmd_dist_start_distribution(self._yamaha_link_distribution_num)
            )
            if master_host in self._yamaha_dev_link:
                self._update_link_state(master_host)

    def _link_add_client(self, item, yamaha_host, yamaha_zone):
        """
        orchestrate adding a client to the group this host/zone leads

        self must already be (or become) the server: reads its own group_id
        if already a server, otherwise generates a new one. The target
        client's own zone defaults to 'main' (item's value only carries the
        client host, not a zone there).
        """
        client_value = item()
        if not client_value:
            self.logger.warn('link_add_client needs a target host value, got {!r}'.format(client_value))
            return
        try:
            client_host = socket.gethostbyname(client_value)
        except Exception:
            self.logger.warn('link_add_client: could not resolve host {!r}'.format(client_value))
            return

        self_info = self._submit_payload(yamaha_host, self._build_cmd_get_link_state())
        if self_info and self_info.get('role') == 'server':
            group_id = self_info.get('group_id')
        else:
            group_id = secrets.token_hex(16).upper()

        self._submit_payload(client_host, self._build_cmd_dist_set_client_info(group_id, ['main']))
        self._submit_payload(
            yamaha_host, self._build_cmd_dist_set_server_info(group_id, yamaha_zone, 'add', [client_host])
        )
        self._yamaha_link_distribution_num += 1
        self._submit_payload(yamaha_host, self._build_cmd_dist_start_distribution(self._yamaha_link_distribution_num))

        self._yamaha_link_master[client_host] = yamaha_host
        if client_host in self._yamaha_dev_link:
            self._update_link_state(client_host)

    def _link_remove_client(self, item, yamaha_host, yamaha_zone):
        """orchestrate removing a client from the group this host/zone leads"""
        client_value = item()
        if not client_value:
            self.logger.warn('link_remove_client needs a target host value, got {!r}'.format(client_value))
            return
        try:
            client_host = socket.gethostbyname(client_value)
        except Exception:
            self.logger.warn('link_remove_client: could not resolve host {!r}'.format(client_value))
            return

        self._submit_payload(client_host, self._build_cmd_dist_set_client_info('', ['main']))

        self_info = self._submit_payload(yamaha_host, self._build_cmd_get_link_state())
        if self_info and self_info.get('role') == 'server':
            self._submit_payload(
                yamaha_host,
                self._build_cmd_dist_set_server_info(self_info.get('group_id'), yamaha_zone, 'remove', [client_host]),
            )
            self._yamaha_link_distribution_num += 1
            self._submit_payload(
                yamaha_host, self._build_cmd_dist_start_distribution(self._yamaha_link_distribution_num)
            )

        self._yamaha_link_master.pop(client_host, None)
        if client_host in self._yamaha_dev_link:
            self._update_link_state(client_host)

    def _link_disband(self, yamaha_host, yamaha_zone):
        """cancel this host's server role entirely, tearing down the whole group"""
        self._submit_payload(yamaha_host, self._build_cmd_dist_set_server_info('', yamaha_zone, None, None))

    def _update_alarm_state(self, yamaha_host, update_items=True):
        """
        parses alarm status from query response 'state'

        as alarm configuration is too complex to mirror in item configuration,
        this is excluded from the loop in _update_state()
        As alarm handling might be expanded later, this is a separate function.
        At the moment it will only be called from _update_state()
        """
        state = self._submit_payload(yamaha_host, self._build_cmd_get_alarm_state())
        if state:
            try:
                alarm = state['alarm']
            except KeyError:
                return

            alarm_on = alarm['alarm_on']
            alarm_time = alarm['oneday']['time']
            alarm_beep = alarm['oneday']['beep']

            if update_items:
                for yamaha_cmd, items in self._yamaha_dev_global.get(yamaha_host, {}).items():
                    if yamaha_cmd == 'alarm_on':
                        value = alarm_on
                    elif yamaha_cmd == 'alarm_time':
                        value = alarm_time
                    elif yamaha_cmd == 'alarm_beep':
                        value = alarm_beep
                    else:
                        continue
                    for item in items:
                        item(value, self.get_fullname())

        return

    #
    # handle and format data values
    #

    def _get_value_from_response(self, state, cmd, host):
        """
        return value for selected command from response data

        tries to extract value for requested cmd
        returns None if state is None (network error), if cmd is missing
        from the response, or if value conversion fails - observed on real
        hardware (not just a theoretical config/coding-error case as
        originally assumed): some zone fields (surround_3d/pure_direct/
        tone.balance/equalizer.low/mid/high) can be transiently absent from
        getStatus right after power-on, before the device has settled.
        Skipping (like every other "unknown/unsupported" case in this file)
        is correct here - the caller already treats None as "nothing to
        push this round", the same field typically appears on the next poll.
        """
        if state is None:
            return None
        cmd = self._yamaha_flat_rename_cmds.get(cmd, cmd)
        try:
            if cmd in self._yamaha_nested_cmds:
                parent_key, sub_key = self._yamaha_nested_cmds[cmd]
                value = state[parent_key][sub_key]
            else:
                value = state[cmd]
        except Exception:
            self.logger.debug(
                '{} not present in response from {}, skipping this round: {}'.format(cmd, self._host_label(host), state)
            )
            return None
        return self._convert_value_yxc_to_plugin(value, cmd, host)

    def _convert_value_yxc_to_plugin(self, value, cmd, host):
        """
        convert network values to python format and
        return processed value depending on command

        formats and returns value from raw input value
        Needs valid cmd and value, no checking for None value
        called by self._return_value and self.run (push notify loop)
        """
        if cmd == 'input':
            return value
        elif cmd == 'volume':
            return int(value)
        elif cmd == 'mute':
            return value == 'true'
        elif cmd == 'power':
            if value == 'standby':
                return False
            elif value == 'on':
                return True
            return value
        elif cmd == 'playback':
            return value
        elif cmd == 'sleep':
            return value
        elif cmd == 'track':
            return value
        elif cmd == 'artist':
            return value
        elif cmd == 'play_time':
            if self.last_total == 0:
                return -1
            else:
                return int(100 * value / self.last_total)
        elif cmd == 'total_time':
            self.last_total = int(value)
            return int(value)
        elif cmd == 'albumart_url':
            value = 'http://{}{}'.format(host, value)
            return value
        elif cmd == 'alarm_on':
            return value == 'true'
        elif cmd == 'alarm_time':
            return value
        elif cmd == 'alarm_beep':
            if value == 'true':
                return True
            else:
                return False
        elif cmd == 'sound_program':
            return value
        elif cmd in ('surround_3d', 'direct', 'pure_direct', 'enhancer'):
            # per spec these are native JSON booleans (unlike mute/alarm_* above,
            # which observed real devices encode as "true"/"false" strings) -
            # untested against real hardware, following the documented type
            return value
        elif cmd == 'tone_control_mode' or cmd == 'equalizer_mode':
            return value
        elif cmd in ('tone_bass', 'tone_treble', 'eq_low', 'eq_mid', 'eq_high', 'balance'):
            return int(value)
        elif cmd in ('role', 'group_id', 'group_name', 'server_zone'):
            return value
        elif cmd == 'audio_dropout':
            # per spec a native JSON boolean - untested against real hardware
            return value
        elif cmd in ('link_control', 'link_audio_delay', 'link_audio_quality'):
            return value

    #
    # send network commands and receive responses
    #

    def _submit_payload(self, host, payload):
        """
        send cmd string to device and return response data as dict

        returns None on network error (no connection, device not plugged in?)
        always subscribes to unicast notification service
        log message "No payload received" probably indicates coding error or
        improper use of cmd 'passthru'

        payload can be
        - a string, will then be sent via HTTP GET
        - a list, will be sent via HTTP POST, needs
          payload[0] as URL, payload[1] as POST data
          Careful: POST data needs to be in proper JSON format
          MusicCast devices are quite picky about double quotes;
          single-quoted data is rewarded with errors!

        return data is None or a dict with json response data
        """
        if payload:
            if type(payload) is str:
                url = 'http://{}/YamahaExtendedControl/{}'.format(host, payload)
                headers = {
                    'X-AppName': 'MusicCast/{}'.format(self.PLUGIN_VERSION),
                    'X-AppPort': '{}'.format(self.srv_port),
                }
                try:
                    res = requests.get(url, headers=headers, timeout=self._yamaha_http_timeout)
                    response = res.text
                    del res
                except Exception:
                    self.logger.info('Device not answering: {}.'.format(self._host_label(host)))
                    response = None
            elif type(payload) is list:
                if len(payload) < 2:
                    self.logger.debug('Payload in list format, but insufficient arguments')
                    response = None
                else:
                    url = 'http://{}/YamahaExtendedControl/{}'.format(host, payload[0])
                    headers = {
                        'X-AppName': 'MusicCast/{}'.format(self.PLUGIN_VERSION),
                        'X-AppPort': '{}'.format(self.srv_port),
                    }
                    try:
                        res = requests.post(url, data=payload[1], headers=headers, timeout=self._yamaha_http_timeout)
                        response = res.text
                        del res
                    except Exception:
                        self.logger.info('Device not answering: {}.'.format(self._host_label(host)))
                        response = None
            try:
                jdata = json.loads(response)
            except Exception:
                self.logger.debug('Invalid data received (not JSON). Data discarded.')
                jdata = None

            return jdata
        else:
            self.logger.warn("No payload received. Used 'passthru' without argument?")
            return None

    #
    # functions to create network commands
    #

    def _build_cmd_power(self, value, zone, cmd='PUT'):
        """
        return cmd string for "set power"

        value is boolean:
            True means "power on"
            False means "standby"
        """
        if value is True:
            cmdarg = 'on'
        elif value is False:
            cmdarg = 'standby'
        cmd = 'v1/{}/setPower?power={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_input(self, value, zone, cmd='PUT'):
        """
        return cmd string for "set input"

        value is string and device-dependent, e.g.
            - tuner
            - cd
            - bluetooth
            - net_radio (internet radio stream)
            - server (UPNP client)
        """
        cmd = 'v1/{}/setInput?input={}'.format(zone, value)
        return cmd

    def _build_cmd_volume(self, value, zone, cmd='PUT'):
        """
        return cmd string for "set volume"

        volume is numeric from 0..60
        """
        cmd = 'v1/{}/setVolume?volume={}'.format(zone, value)
        return cmd

    def _build_cmd_mute(self, value, zone, cmd='PUT'):
        """
        return cmd string for "set mute"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = 'v1/{}/setMute?enable={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_playback(self, value, cmd='PUT'):
        """
        return cmd string for "set playback"

        value is string and can be (for netusb)
            - play
            - stop
            - pause
            - play_pause (toggle)
            - previous
            - next
            - fast_reverse_start
            - fast_reverse_stop
            - fast_forward_start
            - fast_forward_stop
        """
        cmd = 'v1/netusb/setPlayback?playback={}'.format(value)
        return cmd

    def _build_cmd_get_features(self):
        """
        return cmd string for "get features" -> get device/zone capabilities

        host-level call (not zone-specific), returns capabilities for all
        zones of the device in one response
        """
        cmd = 'v1/system/getFeatures'
        return cmd

    def _build_cmd_get_state(self, zone):
        """
        return cmd string for "get status" -> get general status for zone
        """
        cmd = 'v1/{}/getStatus'.format(zone)
        return cmd

    def _build_cmd_get_play_state(self):
        """
        return cmd string for "get playstatus" -> get playing status

        at the moment only netusb zone is supported, no other device to test
        """
        cmd = 'v1/netusb/getPlayInfo'
        return cmd

    def _build_cmd_get_alarm_state(self):
        """
        return cmd string for "get alarm status" -> get alarm clock info

        cmd will return empty result if alarm not supported
        """
        cmd = 'v1/clock/getSettings'
        return cmd

    def _build_cmd_preset(self, value):
        """
        return cmd string for "set preset"

        value is integer preset index (1..)

        at the moment only netusb zone is supported (see above)
        """
        cmd = 'v1/netusb/recallPreset?zone=main&num={}'.format(value)
        return cmd

    def _build_cmd_sleep(self, value, zone, cmd='PUT'):
        """
        return cmd string for "set sleep"

        volume is numeric 0 / 30 / 60 / 90 / 120 (minutes)
        """
        cmd = 'v1/{}/setSleep?sleep={}'.format(zone, value)
        return cmd

    def _build_cmd_sound_program(self, value, zone):
        """
        return cmd string for "set sound program"

        value is string, e.g. 'munich' / 'vienna' / 'straight' / ... (device-dependent)
        """
        cmd = 'v1/{}/setSoundProgram?program={}'.format(zone, value)
        return cmd

    def _build_cmd_surround_3d(self, value, zone):
        """
        return cmd string for "set 3D surround"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = 'v1/{}/set3dSurround?enable={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_direct(self, value, zone):
        """
        return cmd string for "set direct"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = 'v1/{}/setDirect?enable={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_pure_direct(self, value, zone):
        """
        return cmd string for "set pure direct"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = 'v1/{}/setPureDirect?enable={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_enhancer(self, value, zone):
        """
        return cmd string for "set enhancer"
        """
        if value is True:
            cmdarg = 'true'
        elif value is False:
            cmdarg = 'false'
        cmd = 'v1/{}/setEnhancer?enable={}'.format(zone, cmdarg)
        return cmd

    def _build_cmd_tone_control_mode(self, value, zone):
        """
        return cmd string for "set tone control mode"

        value is string, e.g. 'manual' / 'auto' / 'bypass' (device-dependent)
        """
        cmd = 'v1/{}/setToneControl?mode={}'.format(zone, value)
        return cmd

    def _build_cmd_tone_bass(self, value, zone):
        """
        return cmd string for "set tone control bass"

        only takes effect when tone control mode is 'manual'
        """
        cmd = 'v1/{}/setToneControl?bass={}'.format(zone, value)
        return cmd

    def _build_cmd_tone_treble(self, value, zone):
        """
        return cmd string for "set tone control treble"

        only takes effect when tone control mode is 'manual'
        """
        cmd = 'v1/{}/setToneControl?treble={}'.format(zone, value)
        return cmd

    def _build_cmd_equalizer_mode(self, value, zone):
        """
        return cmd string for "set equalizer mode"

        value is string, e.g. 'manual' / 'auto' / 'bypass' (device-dependent)
        """
        cmd = 'v1/{}/setEqualizer?mode={}'.format(zone, value)
        return cmd

    def _build_cmd_eq_low(self, value, zone):
        """
        return cmd string for "set equalizer low"

        only takes effect when equalizer mode is 'manual'
        """
        cmd = 'v1/{}/setEqualizer?low={}'.format(zone, value)
        return cmd

    def _build_cmd_eq_mid(self, value, zone):
        """
        return cmd string for "set equalizer mid"

        only takes effect when equalizer mode is 'manual'
        """
        cmd = 'v1/{}/setEqualizer?mid={}'.format(zone, value)
        return cmd

    def _build_cmd_eq_high(self, value, zone):
        """
        return cmd string for "set equalizer high"

        only takes effect when equalizer mode is 'manual'
        """
        cmd = 'v1/{}/setEqualizer?high={}'.format(zone, value)
        return cmd

    def _build_cmd_balance(self, value, zone):
        """
        return cmd string for "set L/R balance"

        value is negative for left, positive for right
        """
        cmd = 'v1/{}/setBalance?value={}'.format(zone, value)
        return cmd

    def _build_cmd_link_control(self, value, zone):
        """
        return cmd string for "set link control"

        value is string, e.g. 'normal' / 'stability_boost' (device-dependent)
        """
        cmd = 'v1/{}/setLinkControl?control={}'.format(zone, value)
        return cmd

    def _build_cmd_link_audio_delay(self, value, zone):
        """
        return cmd string for "set link audio delay"

        value is string, e.g. 'lip_sync' / 'audio_sync_on' / 'audio_sync_off' / 'balanced'
        """
        cmd = 'v1/{}/setLinkAudioDelay?delay={}'.format(zone, value)
        return cmd

    def _build_cmd_link_audio_quality(self, value, zone):
        """
        return cmd string for "set link audio quality"

        value is string, e.g. 'compressed' / 'uncompressed'
        """
        cmd = 'v1/{}/setLinkAudioQuality?mode={}'.format(zone, value)
        return cmd

    def _build_cmd_alarm_on(self, value, cmd='PUT'):
        """
        return cmd string for "switch alarm on/off"

        value is bool
        """
        cmd = 'v1/clock/setAlarmSettings'
        data = json.dumps({'alarm_on': 'true' if value else 'false'})
        return [cmd, data]

    def _build_cmd_alarm_time(self, value, cmd='PUT'):
        """
        return cmd string for "set alarm_time"

        value is string in 4 digit 24 hour time, e.g. "1430"
        """
        cmd = 'v1/clock/setAlarmSettings'
        data = json.dumps({'detail': {'day': 'oneday', 'time': value}})
        return [cmd, data]

    def _build_cmd_alarm_beep(self, value, cmd='PUT'):
        """
        return cmd string for "set alarm beep"

        value is bool
        """
        cmd = 'v1/clock/setAlarmSettings'
        data = json.dumps({'detail': {'day': 'oneday', 'beep': 'true' if value else 'false'}})
        return [cmd, data]

    def _build_cmd_get_tuner_state(self):
        """
        return cmd string for "get tuner playinfo" -> get band/freq/station info

        tuner is a single shared resource per device, not scoped to a zone
        """
        cmd = 'v1/tuner/getPlayInfo'
        return cmd

    def _build_cmd_tuner_set_band(self, value):
        """
        return cmd string for "set tuner band"

        value is string, "am" or "fm"
        """
        cmd = 'v1/tuner/setBand?band={}'.format(value)
        return cmd

    def _build_cmd_tuner_set_freq_direct(self, band, value):
        """
        return cmd string for "set tuner frequency" (direct tuning)

        value is frequency in kHz
        """
        cmd = 'v1/tuner/setFreq?band={}&tuning=direct&num={}'.format(band, value)
        return cmd

    def _build_cmd_tuner_seek(self, band, value):
        """
        return cmd string for "seek tuner frequency"

        value is one of "up" / "down" / "cancel" / "auto_up" / "auto_down" /
        "tp_up" / "tp_down" (RDS traffic program only)
        """
        cmd = 'v1/tuner/setFreq?band={}&tuning={}'.format(band, value)
        return cmd

    def _build_cmd_tuner_recall_preset(self, band, num):
        """
        return cmd string for "recall tuner preset"

        always recalls into zone=main - same pre-existing limitation as
        _build_cmd_preset() for netusb, no per-zone tuner preset support
        """
        cmd = 'v1/tuner/recallPreset?zone=main&band={}&num={}'.format(band, num)
        return cmd

    def _build_cmd_tuner_store_preset(self, num):
        """
        return cmd string for "store current tuner station to preset"
        """
        cmd = 'v1/tuner/storePreset?num={}'.format(num)
        return cmd

    def _build_cmd_tuner_clear_preset(self, band, num):
        """
        return cmd string for "clear tuner preset"
        """
        cmd = 'v1/tuner/clearPreset?band={}&num={}'.format(band, num)
        return cmd

    def _build_cmd_tuner_switch_preset(self, value):
        """
        return cmd string for "switch to next/previous tuner preset"

        value is "next" or "previous"
        """
        cmd = 'v1/tuner/switchPreset?dir={}'.format(value)
        return cmd

    def _build_cmd_get_link_state(self):
        """
        return cmd string for "get distribution info" -> get dist/Link role/group status

        host-global call (not zone-specific): a device has one Link role/group
        at a time, not one per zone
        """
        cmd = 'v1/dist/getDistributionInfo'
        return cmd

    def _build_cmd_dist_set_client_info(self, group_id, zones):
        """
        return [url, json_data] for "set Link distributed client"

        group_id is a 32-hex-digit string, or '' to cancel this host being a
        client. zones is a list of zone IDs to become clients (e.g. ['main'])
        """
        cmd = 'v1/dist/setClientInfo'
        data = json.dumps({'group_id': group_id, 'zone': zones})
        return [cmd, data]

    def _build_cmd_dist_set_server_info(self, group_id, zone, op_type, client_list):
        """
        return [url, json_data] for "set Link distribution server (master)"

        group_id is a 32-hex-digit string, or '' to cancel this host being a
        server (tears down the whole group). op_type is 'add'/'remove' to
        add/remove clients in client_list, or None to omit both (used when
        just setting/canceling the server role without touching the client list)
        """
        cmd = 'v1/dist/setServerInfo'
        data = {'group_id': group_id, 'zone': zone}
        if op_type is not None:
            data['type'] = op_type
        if client_list is not None:
            data['client_list'] = client_list
        return [cmd, json.dumps(data)]

    def _build_cmd_dist_start_distribution(self, num):
        """
        return cmd string for "start Link distribution"

        num is a "Link distribution number on current MusicCast Network" per
        spec - exact semantics aren't fully defined there; see module-level
        TODO note and _yamaha_link_distribution_num
        """
        cmd = 'v1/dist/startDistribution?num={}'.format(num)
        return cmd

    def _build_cmd_dist_set_group_name(self, name):
        """
        return [url, json_data] for "set Link group name"

        name is UTF-8, max 128 bytes. Group name is reserved in volatile
        memory only (not persisted across device reboot, per spec)
        """
        cmd = 'v1/dist/setGroupName'
        data = json.dumps({'name': name})
        return [cmd, data]
