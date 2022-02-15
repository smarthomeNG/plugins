#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    from MD_Device import MD_Device
    from MD_Globals import JSON_MOVE_KEYS
else:
    from ..MD_Device import MD_Device
    from ..MD_Globals import JSON_MOVE_KEYS


class MD_Device(MD_Device):
    """
    Device class for Kodi Mediacenter.

    The protocol work is a bit more complex than e.g. the Pioneer/Denon family
    device classes, therefore we need to write some additional code for handling
    responses. See for yourself...

    Complex response or notification datagrams with multiple data points can not
    easily - and usefully - be crammed into a single item, so we need a logic
    to separate the data points and split them into different items (better:
    command responses). This is mostly handled in ``on_data_received()``.

    Due to multiple device namespaces, some responses require us to ask for
    additional specific information from the device. This is handled by
    ``send_command()`` and ``_update_status()``.

    The "special" (a.k.a. fake) commands (as they are not a single command to
    send to the device) have to be recognized, so we also tamper with
    ``is_valid_command()``.

    NOTE: quite some of the logic in ``on_data_received()``, especially most of
          the code for handling notifications could be achieved by adding complex
          commands which control the ``playpause`` and ``stop`` command; the
          dependent settings could then be accomplished by more or less complex
          item and eval constructs.

          As this is - foremost - a port of the kodi plugin and a demonstrator
          for how to and how not to use the MultiDevice capabilities, I've not
          yet changed much.

          Any complexity moved out of the ``device.py`` code will need to find
          another place, in ``commands.py`` and/or the item configuration.
    """

    def _set_device_defaults(self):
        self._use_callbacks = True
        self._params[JSON_MOVE_KEYS] = ['playerid', 'properties']

    def _post_init(self):
        if not self.disabled:

            self._activeplayers = []
            self._playerid = 0

            # these commands are not meant to control the kodi device, but to
            # communicate with the device class, e.g. triggering updating
            # player info or returning the player_id. As these commands are not
            # sent (directly) to the device, they should not be processed via
            # the MD_Commands class and not listed in commands.py
            self._special_commands = {'read': ['info.player'], 'write': ['status.update']}

    def on_connect(self, by=None):
        super().on_connect(by)
        self._update_status()

    def on_data_received(self, by, data, command=None):
        """
        Callback function for received data e.g. from an event loop
        Processes data and dispatches value to plugin class

        :param command: the command in reply to which data was received
        :param data: received data in 'raw' connection format
        :type command: str
        """
        if command is not None:
            self.logger.debug(f'received data "{data}" for command {command}')
        else:
            self.logger.debug(f'data "{data}" did not identify a known command')

        if not self._data_received_callback:
            self.logger.error('on_data_received callback not set, can not process device reply data, ignoring it')
            return

        if not isinstance(data, dict):
            self.logger.error(f'received data {data} not in JSON (dict) format, ignoring')

        if 'error' in data:
            # errors are handled on connection level
            return

        try:
            result_data = data.get('result')
        except Exception as e:
            self.logger.error(f'Invalid response to command {command} received: {data}, ignoring. Error was: {e}')
            return
        if 'id' in data and result_data is None:
            self.logger.info(f'Empty response to command {command} received, ignoring')
            return

        query_playerinfo = []

        processed = False

        # replies to requests sent by us
        if 'id' in data:
            if command == 'Player.GetActivePlayers':
                processed = True
                if len(result_data) == 1:
                    # one active player
                    query_playerinfo = self._activeplayers = [result_data[0].get('playerid')]
                    self._playerid = self._activeplayers[0]
                    self.logger.debug(f'received GetActivePlayers, set playerid to {self._playerid}')
                    self._data_received_callback(self.device_id, 'info.player', self._playerid)
                    self._data_received_callback(self.device_id, 'info.media', result_data[0].get('type').capitalize())
                elif len(result_data) > 1:
                    # multiple active players. Have not yet seen this happen
                    self._activeplayers = []
                    for player in result_data:
                        self._activeplayers.append(player.get('playerid'))
                        query_playerinfo.append(player.get('playerid'))
                    self._playerid = min(self._activeplayers)
                    self.logger.debug(f'received GetActivePlayers, set playerid to {self._playerid}')
                else:
                    # no active players
                    self._activeplayers = []
                    self._data_received_callback(self.device_id, 'info.state', 'No active player')
                    self._data_received_callback(self.device_id, 'info.player', 0)
                    self._data_received_callback(self.device_id, 'info.title', '')
                    self._data_received_callback(self.device_id, 'info.media', '')
                    self._data_received_callback(self.device_id, 'control.stop', True)
                    self._data_received_callback(self.device_id, 'control.playpause', False)
                    self._data_received_callback(self.device_id, 'info.streams', None)
                    self._data_received_callback(self.device_id, 'info.subtitles', None)
                    self._data_received_callback(self.device_id, 'control.audio', '')
                    self._data_received_callback(self.device_id, 'control.subtitle', '')
                    self._playerid = 0
                    self.logger.debug('received GetActivePlayers, reset playerid to 0')

            # got status info
            elif command == 'Application.GetProperties':
                processed = True
                muted = result_data.get('muted')
                volume = result_data.get('volume')
                self.logger.debug(f'received GetProperties: change mute to {muted} and volume to {volume}')
                self._data_received_callback(self.device_id, 'control.mute', muted)
                self._data_received_callback(self.device_id, 'control.volume', volume)

            # got favourites
            elif command == 'Favourites.GetFavourites':
                processed = True
                if not result_data.get('favourites'):
                    self.logger.debug('No favourites found.')
                else:
                    item_dict = {item['title']: item for item in result_data.get('favourites')}
                    self.logger.debug(f'favourites found: {item_dict}')
                    self._data_received_callback(self.device_id, 'status.get_favourites', item_dict)

            # got item info
            elif command == 'Player.GetItem':
                processed = True
                title = result_data['item'].get('title')
                player_type = result_data['item'].get('type')
                if not title:
                    title = result_data['item'].get('label')
                self._data_received_callback(self.device_id, 'info.media', player_type.capitalize())
                if player_type == 'audio' and 'artist' in result_data['item']:
                    artist = 'unknown' if len(result_data['item'].get('artist')) == 0 else result_data['item'].get('artist')[0]
                    title = artist + ' - ' + title
                if title:
                    self._data_received_callback(self.device_id, 'info.title', title)
                self.logger.debug(f'received GetItem: update player info to title={title}, type={player_type}')

            # got player status
            elif command == 'Player.GetProperties':
                processed = True
                self.logger.debug('Received Player.GetProperties, update media data')
                self._data_received_callback(self.device_id, 'control.speed', result_data.get('speed'))
                self._data_received_callback(self.device_id, 'control.seek', result_data.get('percentage'))
                self._data_received_callback(self.device_id, 'info.streams', result_data.get('audiostreams'))
                self._data_received_callback(self.device_id, 'control.audio', result_data.get('currentaudiostream'))
                self._data_received_callback(self.device_id, 'info.subtitles', result_data.get('subtitles'))
                if result_data.get('subtitleenabled'):
                    subtitle = result_data.get('currentsubtitle')
                else:
                    subtitle = 'Off'
                self._data_received_callback(self.device_id, 'control.subtitle', subtitle)

                # speed != 0 -> play; speed == 0 -> pause
                if result_data.get('speed') == 0:
                    self._data_received_callback(self.device_id, 'info.state', 'Paused')
                    self._data_received_callback(self.device_id, 'control.stop', False)
                    self._data_received_callback(self.device_id, 'control.playpause', False)
                else:
                    self._data_received_callback(self.device_id, 'info.state', 'Playing')
                    self._data_received_callback(self.device_id, 'control.stop', False)
                    self._data_received_callback(self.device_id, 'control.playpause', True)

        # not replies, but event notifications.
        elif 'method' in data:

            # no id, notification or other
            if data['method'] == 'Player.OnResume':
                processed = True
                self.logger.debug('received: resumed player')
                self._data_received_callback(self.device_id, 'info.state', 'Playing')
                self._data_received_callback(self.device_id, 'control.stop', False)
                self._data_received_callback(self.device_id, 'control.playpause', True)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnPause':
                processed = True
                self.logger.debug('received: paused player')
                self._data_received_callback(self.device_id, 'info.state', 'Paused')
                self._data_received_callback(self.device_id, 'control.stop', False)
                self._data_received_callback(self.device_id, 'control.playpause', False)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnStop':
                processed = True
                self.logger.debug('received: stopped player, set playerid to 0')
                self._data_received_callback(self.device_id, 'info.state', 'No active player')
                self._data_received_callback(self.device_id, 'info.media', '')
                self._data_received_callback(self.device_id, 'info.title', '')
                self._data_received_callback(self.device_id, 'info.player', 0)
                self._data_received_callback(self.device_id, 'control.stop', True)
                self._data_received_callback(self.device_id, 'control.playpause', False)
                self._data_received_callback(self.device_id, 'info.streams', None)
                self._data_received_callback(self.device_id, 'info.subtitles', None)
                self._data_received_callback(self.device_id, 'control.audio', '')
                self._data_received_callback(self.device_id, 'control.subtitle', '')
                self._activeplayers = []
                self._playerid = 0

            elif data['method'] == 'GUI.OnScreensaverActivated':
                processed = True
                self.logger.debug('received: activated screensaver')
                self._data_received_callback(self.device_id, 'info.state', 'Screensaver')

            elif data['method'][:9] == 'Player.On':
                processed = True
                self.logger.debug('received: player notification')
                try:
                    p_id = data['params']['data']['player']['playerid']
                    if p_id:
                        self._playerid = p_id
                        self._activeplayers.append(p_id)
                        self._data_received_callback(self.device_id, 'info.player', p_id)
                    query_playerinfo.append(p_id)
                except KeyError:
                    pass

                try:
                    self._data_received_callback(self.device_id, 'info.media', data['params']['data']['item']['channeltype'])
                    self._data_received_callback(self.device_id, 'info.title', data['params']['data']['item']['title'])
                except KeyError:
                    pass

            elif data['method'] == 'Application.OnVolumeChanged':
                processed = True
                self.logger.debug('received: volume changed, got new values mute: {} and volume: {}'.format(data['params']['data']['muted'], data['params']['data']['volume']))
                self._data_received_callback(self.device_id, 'control.mute', data['params']['data']['muted'])
                self._data_received_callback(self.device_id, 'control.volume', data['params']['data']['volume'])

        # if active playerid(s) was changed, update status for active player(s)
        if query_playerinfo:
            self.logger.debug(f'player info query requested for playerid(s) {query_playerinfo}')
            for player_id in set(query_playerinfo):
                self.logger.debug(f'getting player info for player #{player_id}')
                self._connection._send_rpc_message('Player.GetItem', {'properties': ['title', 'artist'], 'playerid': player_id})
                self._connection._send_rpc_message('Player.GetProperties', {'properties': ['speed', 'percentage', 'currentaudiostream', 'audiostreams', 'subtitleenabled', 'currentsubtitle', 'subtitles'], 'playerid': player_id})

        if processed:
            return

        # if we reach this point, no special handling case was detected, so just go on normally...

        try:
            # try and transform the JSON RPC method into the matching command
            command = self._commands.get_command_from_reply(command)
            value = self._commands.get_shng_data(command, data)
        except Exception as e:
            self.logger.info(f'received data "{data}" for command {command}, error occurred while converting. Discarding data. Error was: {e}')
            return

        # pass on data for regular item assignment
        self.logger.debug(f'received data "{data}" for command {command} converted to value {value}')
        self._data_received_callback(self.device_id, command, value)

    def send_command(self, command, value=None, **kwargs):
        """
        Checks for special commands and handles them, otherwise call the
        base class' method

        :param command: the command to send
        :param value: the data to send, if applicable
        :type command: str
        :return: True if send was successful, False otherwise
        :rtype: bool
        """
        if not self.alive:
            self.logger.warning(f'trying to send command {command} with value {value}, but device is not active.')
            return False

        if not self._connection:
            self.logger.warning(f'trying to send command {command} with value {value}, but connection is None. This shouldn\'t happen...')
            return False

        if not self._connection.connected:
            self._connection.open()
            if not self._connection.connected:
                self.logger.warning(f'trying to send command {command} with value {value}, but connection could not be established.')
                return False

        if command in self._special_commands['read' if value is None else 'write']:
            if command == 'status.update':
                if value:
                    self._update_status()
                return True
            elif value is None:
                self.logger.debug(f'Special command {command} called for reading, which is not intended. Ignoring request')
                return True
            else:
                # this shouldn't happen
                self.logger.warning(f'Special command {command} found, no action set for processing. Please inform developers. Ignoring request')
                return True
        else:
            return super().send_command(command, value, playerid=self._playerid, **kwargs)

    def is_valid_command(self, command, read=None):
        """
        In addition to base class method, allow 'special'
        commands not defined in commands.py which are meant
        to control the plugin device, e.g. 'update' to read
        player status.
        If not special command, call base class method

        :param command: the command to test
        :type command: str
        :param read: check for read (True) or write (False), or both (None)
        :type read: bool | NoneType
        :return: True if command is valid, False otherwise
        :rtype: bool
        """
        if command in self._special_commands['read' if read else 'write']:
            self.logger.debug(f'Acknowledging special command {command}, read is {read}')
            return True
        else:
            return super().is_valid_command(command, read)

#
# new methods
#

    def notify(self, title, message, image=None, display_time=10000):
        """
        Send a notification to Kodi to be displayed on the screen

        :param title: the title of the message
        :param message: the message itself
        :param image: an optional image to be displayed alongside the message
        :param display_time: how long the message is displayed in milli seconds
        """
        params = {'title': title, 'message': message, 'displaytime': display_time}
        if image is not None:
            params['image'] = image
        self._connection._send_rpc_message('GUI.ShowNotification', params)

    def _update_status(self):
        """
        This method requests several status infos
        """
        if self.alive:
            self.send_command('status.get_actplayer', None)
            self.send_command('status.get_status_au', None)
            if self._playerid:
                self.send_command('status.get_status_play', None)
                self.send_command('status.get_item', None)
