#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT


# handle feedback if rescan is running or not
class DT_LMSRescan(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data in ["1", "done"] else False


class DT_LMSConnection(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data in ["1", "reconnect"] else False


class DT_LMSPlay(DT.Datatype):
    def get_send_data(self, data, type=None, **kwargs):
        return "play 3" if data is True else "pause 3"

    def get_shng_data(self, data, type=None, **kwargs):
        return True if data == "play" else False


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
