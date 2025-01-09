#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT
import re
from urllib.parse import unquote


# handle feedback if rescan is running or not
class DT_LMSRescan(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return False if data in ["0", "done"] else True


class DT_LMSWipecache(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data == "wipecache" else False
    def get_send_data(self, data, type=None, **kwargs):
        return "wipecache" if data is True else ""


class DT_LMSConnection(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data in ["1", "reconnect"] else False


class DT_LMSPlay(DT.Datatype):
    def get_send_data(self, data, type=None, **kwargs):
        return "play 3" if data is True else "pause 3"

    def get_shng_data(self, data, type=None, **kwargs):
        return True if data in ["play", "0"] else False


class DT_LMSSyncnames(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        pattern=r"sync_member_names:([^s]+(?: [^s]+)*)(?= sync_members|$)"
        return re.findall(pattern, data)


class DT_LMSSyncmembers(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        pattern=r"sync_members:([^s]+(?: [^s]+)*)(?= sync_member_names|$)"
        return re.findall(pattern, data)


class DT_LMSSyncstatus(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        if data in ["-", "?"]:
            return []
        elif data:
            return data.split(",")
        else:
            return []


class DT_LMSAlarms(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        dic = {}
        _id = None
        res = data.split()
        for i in res:
            key, value = i.split(':')
            if key == "id":
                _id = value
                dic[_id] = {}
            elif _id:
              dic[_id][key] = value
            else:
              dic[key] = value
        return dic


class DT_LMSPlayMode(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        if data in ["play", "pause 0"]:
            return_value = "play"
        elif data in ["pause", "pause 1"]:
            return_value = "pause"
        else:
            return_value = "stop"
        return return_value


class DT_LMSStop(DT.Datatype):
    def get_send_data(self, data, type=None, **kwargs):
        return "play 3" if data is False else "stop"

    def get_shng_data(self, data, type=None, **kwargs):
        return True if data == "stop" else False

class DT_LMSonoff(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data == "1" else False if data == "0" else None

class DT_LMSConvertSpaces(DT.Datatype):
    def get_send_data(self, data, type=None, **kwargs):
        return data.replace(" ", "%20")
    def get_shng_data(self, data, type=None, **kwargs):
        return data.replace("%20", " ")

class DT_LMSPlayers(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        player_pattern = r"(playerindex:\d+)(.*?)(?=playerindex:\d+|$)"
        players = re.findall(player_pattern, data)
        players_dict = {}

        for player in players:
            player_info = player[1].strip()
            info_pairs = re.findall(r"(\w+):([\w\.\-:]+)", player_info)
            player_data = {key: value for key, value in info_pairs}
            player_id = player_data.pop('playerid', None)
            if player_id:
                players_dict[player_id] = player_data
        players_dict['-'] = {'ip:': None, 'name': 'NONE', 'model': None, 'firmware': None}
        return players_dict

class DT_LMSPlaylists(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        entries = re.findall(r"id:(\d+)\s+playlist:([\_\-.\w%]+) (.*?)(?=id:\d+|$| count:\d+)", data)

        playlists_dict = {}
        for playlist_id, name, extra in entries:
            name = unquote(name)  # Decode URL-encoded name
            details = {"id": playlist_id}
            # Extract any additional fields (like url) from the extra part
            extra_fields = re.findall(r"(\w+):([\w%:/.\-]+)", extra)
            details.update({key: unquote(value) for key, value in extra_fields})
            playlists_dict[name] = details

        return playlists_dict

class DT_LMSPlaylistrename(DT.Datatype):
    def get_send_data(self, data, type=None, **kwargs):
        values = data.split(' ')
        try:
            data = f'playlist_id:{values[0]} newname:{values[1]}'
        except Exception:
            pass
        return data
    def get_shng_data(self, data, type=None, **kwargs):
        match = re.search(r"playlist_id:(\d+)\s+newname:(.*)", data)
        if match:
            playlist_id = match.group(1)
            new_name = match.group(2)
            result = f"{playlist_id} {new_name}"
        else:
            result = data
        return result