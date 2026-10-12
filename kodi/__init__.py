#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023-      Sebastian Helms           Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG
#
#  Kodi Media Center plugin for SmartDevicePlugin class
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
#  along with SmartHomeNG  If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import builtins
import os
import sys

if __name__ == '__main__':
    builtins.SDP_standalone = True

    class SmartPlugin:
        pass

    class SmartPluginWebIf:
        pass

    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)

else:
    # don't clobber a True set by the real __main__ run - loading
    # commands.py via pydoc.locate('plugins.kodi.commands') imports
    # this file a second time under its package name, hitting this branch
    # with __name__ != '__main__' even in standalone mode
    if not hasattr(builtins, 'SDP_standalone'):
        builtins.SDP_standalone = False

from lib.model.sdp.declarations import TransportRule
from lib.model.sdp.globals import CONN_NET_TCP_CLI, PROTO_JSONRPC

from lib.model.smartdeviceplugin import SmartDevicePlugin, Standalone

# from .webif import WebInterface


class kodi(SmartDevicePlugin):
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

    The info.* commands are pseudo commands (neither read nor write in
    commands.py), filled by the plugin from Kodi's replies and notifications;
    status.update and info.macro writes are handled by the plugin.

    NOTE: quite some of the logic in ``on_data_received()``, especially most of
          the code for handling notifications could be achieved by adding complex
          commands which control the ``playpause`` and ``stop`` command; the
          dependent settings could then be accomplished by more or less complex
          item and eval constructs.

          As this is - foremost - a port of the kodi plugin and a demonstrator
          for how to and how not to use the SmartDevicePlugin capabilities, I've
          not yet changed much.

          Any complexity moved out of the ``device.py`` code will need to find
          another place, in ``commands.py`` and/or the item configuration.
    """

    PLUGIN_VERSION = '1.7.3'

    TRANSPORTS = (TransportRule(CONN_NET_TCP_CLI, requires='host'),)
    PROTOCOL = PROTO_JSONRPC
    COMMAND_CLASS = 'SDPCommandJSON'
    JSON_MOVE_KEYS = ('playerid', 'properties')

    def _post_init(self):
        self._activeplayers = []
        self._playerid = 0

        # writes handled by the plugin, not sent to Kodi
        self._plugin_writes = ('status.update', 'info.macro')

        # actions which run only when their item is set to a truthy value
        self._truthy_only_commands = ('control.power', 'control.quit')

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
        if self.suspended:
            self.logger.debug(f'received data for command {command} suspended, discarding data.')
            return

        if command is not None:
            self.logger.debug(f'received data "{data}" for command {command}')
        else:
            self.logger.debug(f'data "{data}" did not identify a known command')

        if not isinstance(data, dict):
            self.logger.error(f'received data {data} not in JSON (dict) format, ignoring')
            return

        if 'error' in data:
            # errors are handled on protocol level
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
                    self._dispatch_callback('info.player', self._playerid, by)
                    media_type = result_data[0].get('type')
                    self._dispatch_callback('info.media', media_type.capitalize() if media_type else '', by)
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
                    self._dispatch_callback('info.state', 'No active player', by)
                    self._dispatch_callback('info.player', 0, by)
                    self._dispatch_callback('info.title', '', by)
                    self._dispatch_callback('info.media', '', by)
                    self._dispatch_callback('control.stop', True, by)
                    self._dispatch_callback('control.playpause', False, by)
                    self._dispatch_callback('info.streams', None, by)
                    self._dispatch_callback('info.subtitles', None, by)
                    self._dispatch_callback('control.audio', '', by)
                    self._dispatch_callback('control.subtitle', '', by)
                    self._playerid = 0
                    self.logger.debug('received GetActivePlayers, reset playerid to 0')

            # got status info
            elif command == 'Application.GetProperties':
                processed = True
                muted = result_data.get('muted')
                volume = result_data.get('volume')
                self.logger.debug(f'received GetProperties: change mute to {muted} and volume to {volume}')
                self._dispatch_callback('control.mute', muted, by)
                self._dispatch_callback('control.volume', volume, by)

            # got favourites
            elif command == 'Favourites.GetFavourites':
                processed = True
                if not result_data.get('favourites'):
                    self.logger.debug('No favourites found.')
                else:
                    item_dict = {item['title']: item for item in result_data.get('favourites')}
                    self.logger.debug(f'favourites found: {item_dict}')
                    self._dispatch_callback('status.get_favourites', item_dict, by)

            # got item info
            elif command == 'Player.GetItem':
                processed = True
                title = result_data['item'].get('title')
                player_type = result_data['item'].get('type')
                if not title:
                    title = result_data['item'].get('label')
                self._dispatch_callback('info.media', player_type.capitalize() if player_type else '', by)
                if player_type == 'audio' and 'artist' in result_data['item']:
                    artist = (
                        'unknown'
                        if len(result_data['item'].get('artist')) == 0
                        else result_data['item'].get('artist')[0]
                    )
                    title = artist + ' - ' + (title or '')
                if title:
                    self._dispatch_callback('info.title', title, by)
                self.logger.debug(f'received GetItem: update player info to title={title}, type={player_type}')

            # got player status
            elif command == 'Player.GetProperties':
                processed = True
                self.logger.debug('Received Player.GetProperties, update media data')
                self._dispatch_callback('control.speed', result_data.get('speed'), by)
                self._dispatch_callback('control.seek', result_data.get('percentage'), by)
                self._dispatch_callback('info.streams', result_data.get('audiostreams'), by)
                self._dispatch_callback('control.audio', result_data.get('currentaudiostream'), by)
                self._dispatch_callback('info.subtitles', result_data.get('subtitles'), by)
                if result_data.get('subtitleenabled'):
                    subtitle = result_data.get('currentsubtitle')
                else:
                    subtitle = 'Off'
                self._dispatch_callback('control.subtitle', subtitle, by)

                # speed != 0 -> play; speed == 0 -> pause
                if result_data.get('speed') == 0:
                    self._dispatch_callback('info.state', 'Paused', by)
                    self._dispatch_callback('control.stop', False, by)
                    self._dispatch_callback('control.playpause', False, by)
                else:
                    self._dispatch_callback('info.state', 'Playing', by)
                    self._dispatch_callback('control.stop', False, by)
                    self._dispatch_callback('control.playpause', True, by)

        # not replies, but event notifications.
        elif 'method' in data:
            # no id, notification or other
            if data['method'] == 'Player.OnResume':
                processed = True
                self.logger.debug('received: resumed player')
                self._dispatch_callback('info.state', 'Playing', by)
                self._dispatch_callback('control.stop', False, by)
                self._dispatch_callback('control.playpause', True, by)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnPause':
                processed = True
                self.logger.debug('received: paused player')
                self._dispatch_callback('info.state', 'Paused', by)
                self._dispatch_callback('control.stop', False, by)
                self._dispatch_callback('control.playpause', False, by)
                query_playerinfo.append(data['params']['data']['player']['playerid'])

            elif data['method'] == 'Player.OnStop':
                processed = True
                self.logger.debug('received: stopped player, set playerid to 0')
                self._dispatch_callback('info.state', 'No active player', by)
                self._dispatch_callback('info.media', '', by)
                self._dispatch_callback('info.title', '', by)
                self._dispatch_callback('info.player', 0, by)
                self._dispatch_callback('control.stop', True, by)
                self._dispatch_callback('control.playpause', False, by)
                self._dispatch_callback('info.streams', None, by)
                self._dispatch_callback('info.subtitles', None, by)
                self._dispatch_callback('control.audio', '', by)
                self._dispatch_callback('control.subtitle', '', by)
                self._activeplayers = []
                self._playerid = 0

            elif data['method'] == 'GUI.OnScreensaverActivated':
                processed = True
                self.logger.debug('received: activated screensaver')
                self._dispatch_callback('info.state', 'Screensaver', by)

            elif data['method'][:9] == 'Player.On':
                processed = True
                self.logger.debug('received: player notification')
                try:
                    p_id = data['params']['data']['player']['playerid']
                    if p_id:
                        self._playerid = p_id
                        self._activeplayers.append(p_id)
                        self._dispatch_callback('info.player', p_id, by)
                    query_playerinfo.append(p_id)
                except KeyError:
                    pass

                try:
                    self._dispatch_callback('info.media', data['params']['data']['item']['channeltype'], by)
                    self._dispatch_callback('info.title', data['params']['data']['item']['title'], by)
                except KeyError:
                    pass

            elif data['method'] == 'Application.OnVolumeChanged':
                processed = True
                self.logger.debug(
                    'received: volume changed, got new values mute: {} and volume: {}'.format(
                        data['params']['data']['muted'], data['params']['data']['volume']
                    )
                )
                self._dispatch_callback('control.mute', data['params']['data']['muted'], by)
                self._dispatch_callback('control.volume', data['params']['data']['volume'], by)

        # if active playerid(s) was changed, update status for active player(s)
        if query_playerinfo:
            self.logger.debug(f'player info query requested for playerid(s) {query_playerinfo}')
            for player_id in set(query_playerinfo):
                self.logger.debug(f'getting player info for player #{player_id}')
                self._connection._send_rpc_message(
                    'Player.GetItem', {'properties': ['title', 'artist'], 'playerid': player_id}
                )
                self._connection._send_rpc_message(
                    'Player.GetProperties',
                    {
                        'properties': [
                            'speed',
                            'percentage',
                            'currentaudiostream',
                            'audiostreams',
                            'subtitleenabled',
                            'currentsubtitle',
                            'subtitles',
                        ],
                        'playerid': player_id,
                    },
                )

        if processed:
            return

        # if we reach this point, no special handling case was detected, so just go on normally...
        try:
            # try and transform the JSON RPC method into the matching command
            commands = self._commands.get_commands_from_reply(command)
            if not isinstance(commands, list):
                commands = [commands]

            for command in commands:
                value = self._commands.get_shng_data(command, data)

                # pass on data for regular item assignment
                self.logger.debug(f'received data "{data}" for command {command} converted to value {value}')
                self._dispatch_callback(command, value, by)
        except Exception as e:
            self.logger.info(
                f'received data "{data}" for command {command}, error occurred while converting. Discarding data. Error was: {e}'
            )
            return

    def _do_before_send(self, command, value, kwargs):
        """
        Checks for special commands and handles them
        """
        if command in self._plugin_writes:
            if command == 'status.update' and value:
                self._update_status()
            return (False, True)

        if command in self._truthy_only_commands and not value:
            self.logger.debug(f'Command {command} with value {value} ignored, it only runs for a truthy value')
            return (False, True)

        # add playerid to kwargs for further processing
        kwargs['playerid'] = self._playerid
        return (True, True)

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
        if self.suspended:
            self.logger.info(f'trying to send notification {title}, but plugin is suspended. Discarding notification.')
            return

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


if __name__ == '__main__':
    s = Standalone(kodi, sys.argv[0])
