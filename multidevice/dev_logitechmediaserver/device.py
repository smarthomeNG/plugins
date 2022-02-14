#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    from MD_Globals import (CUSTOM_SEP, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_NET_PORT, PLUGIN_ATTR_RECURSIVE)
    from MD_Device import MD_Device
else:
    from ..MD_Globals import (CUSTOM_SEP, PLUGIN_ATTR_NET_HOST, PLUGIN_ATTR_NET_PORT, PLUGIN_ATTR_RECURSIVE)
    from ..MD_Device import MD_Device


class MD_Device(MD_Device):
    """ Device class for Squeezebox function. """

    def _set_device_defaults(self):
        self._discard_unknown_command = False
        self.custom_commands = 1
        self._token_pattern = '([0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}'
        # for substitution in reply_pattern
        self._custom_patterns = {1: '(?:[0-9a-fA-F]{2}[-:]){5}[0-9a-fA-F]{2}', 2: '', 3: ''}
        self._use_callbacks = True
        self._params[PLUGIN_ATTR_RECURSIVE] = 1

    def _get_custom_value(self, command, data):
        """ extract custom value from data. At least PATTERN Needs to be overwritten """
        if not self.custom_commands:
            return None

        res = None
        if 'params' in data and isinstance(data['params'], list):
            res = data['params'][0]

        if not res:
            self.logger.debug(f'custom token not found in {data}, ignoring')
            return None
        elif res in self._custom_values[self.custom_commands] or res in ('', '-'):
            return res
        else:
            self.logger.debug(f'received custom token {res}, not in list of known tokens {self._custom_values[self.custom_commands]}')
            return None

    def _transform_received_data(self, data):
        if isinstance(data, dict) and 'result' in data and len(data['result']) == 1:
            data['result'] = list(data['result'].values())[0]
        return data

    def _transform_send_data(self, data_dict, **kwargs):
        host = self._params[PLUGIN_ATTR_NET_HOST]
        port = self._params[PLUGIN_ATTR_NET_PORT]

        data_dict['command'] = data_dict['payload']
        url = f'http://{host}:{port}/jsonrpc.js'
        data_dict['payload'] = url
        data_dict['method'] = 'slim.request'
        data_dict['request_method'] = 'post'
        data_dict['headers'] = {'Content-Type': 'application/json'}
        return data_dict

    def _process_additional_data(self, command, data, value, custom, by):

        def _dispatch(command, value, custom=None, send=False):
            if custom:
                command = command + CUSTOM_SEP + custom
            if send:
                self.send_command(command, value)
            elif self._data_received_callback:
                self._data_received_callback(self.device_id, command, value)

        def _trigger_read(command, custom=None):
            if custom:
                command = command + CUSTOM_SEP + custom
            self.logger.debug(f"Sending read command for {command}")
            self.send_command(command)

        if not custom:
            return

        # set alarm
        if command == 'player.control.alarms':
            # This does not really work currently. The created string is somehow correct.
            # However, much more logic has to be included to add/update/delete alarms, etc.
            try:
                for i in value.keys():
                    d = value.get(i)
                    alarm = f"id:{i} "
                    for k, v in d.items():
                        alarm += f"{k}:{v} "
                    alarm = f"update {alarm.strip()}"
                    self.logger.debug(f"Set alarm: {alarm} without executing the command.")
                    _dispatch('player.control.set_alarm', alarm, custom, False)
            except Exception as e:
                self.logger.error(f"Error setting alarm: {e}")

        # update on new song
        if command == 'player.info.status':
            data = data.get("result")
            _dispatch('player.info.name', data.get("player_name"), custom)
            _dispatch('player.info.connected', data.get("player_connected"), custom)
            _dispatch('player.info.signalstrength', data.get("signalstrength"), custom)
            _dispatch('player.info.playmode', data.get("mode"), custom)
            _dispatch('player.info.time', data.get("time"), custom)
            _dispatch('player.info.rate', data.get("rate"), custom)
            _dispatch('player.info.duration', data.get("duration"), custom)
            _dispatch('player.info.title', data.get("current_title"), custom)
            _dispatch('player.control.power', data.get("power"), custom)
            _dispatch('player.control.volume', data.get("mixer volume"), custom)
            _dispatch('player.playlist.repeat', data.get("playlist repeat"), custom)
            _dispatch('player.playlist.shuffle', data.get("playlist shuffle"), custom)
            _dispatch('player.playlist.mode', data.get("playlist mode"), custom)
            _dispatch('player.playlist.seq_no', data.get("seq_no"), custom)
            _dispatch('player.playlist.index', data.get("playlist_cur_index"), custom)
            _dispatch('player.playlist.timestamp', data.get("playlist_timestamp"), custom)
            _dispatch('player.playlist.tracks', data.get("playlist_tracks"), custom)
            pdata = data.get("playlist_loop")
            if pdata:
                for id, i in enumerate(pdata):
                    if id > 0 and id <= 5:
                        _dispatch(f'player.playlist.nextsong{id}', i.get("title"), custom)
