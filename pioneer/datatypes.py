#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT
import re


class DT_PioDisplay(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        tempvalue = "".join(list(map(lambda i: chr(int(data[2 * i:][:2], 0x10)), range(14)))).strip()
        data = re.sub(r'^[^A-Z0-9]*', '', tempvalue)
        return data


class DT_PioSleep(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if data == 0:
            return "000"
        elif data == 999 or data == 9:
            return "999"
        elif data <= 30:
            return "030"
        elif data <= 60:
            return "060"
        else:
            return "090"

    def get_shng_data(self, data, type=None, **kwargs):
        return int(data)

class DT_PioStandby(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if data == 0:
            return "0000"
        elif data <= 15:
            return "0150"
        elif data <= 30:
            return "0300"
        else:
            return "0600"

    def get_shng_data(self, data, type=None, **kwargs):
        return int(data)

class DT_PioStandby2(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if data == 0:
            return "0000"
        elif data == 0.5:
            return "0300"
        elif data <= 1:
            return "0011"
        elif data <= 3:
            return "0031"
        elif data <= 6:
            return "0061"
        else:
            return "0091"

    def get_shng_data(self, data, type=None, **kwargs):
        if data == "0000":
            return 0
        elif data == "0300":
            return 0.5
        elif data == "0011":
            return 1
        elif data == "0031":
            return 3
        elif data == "0061":
            return 6
        elif data == "0091":
            return 9

class DT_PioInitVol(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if int(data) == 999:
            _returnvalue = "999"
        elif int(data) < -80:
            _returnvalue = "000"
        elif float(data) >= 0:
            _returnvalue = f"{int(((x - 0) / 12) * (185 - 161) + 161):03}"
        elif float(data) < 0:
            _returnvalue = f"{int(161 - ((x - 0) / -80) * 160):03}"
        return _returnvalue

    def get_shng_data(self, data, type=None, **kwargs):
        if data == "999":
            _returnvalue = 999
        elif data == "000":
            _returnvalue = -81
        elif int(data) >= 161:
            _returnvalue =  ((data - 161) / (185 - 161)) * 12
        elif int(data) < 161:
            _returnvalue = ((data - 161) / 160) * 80
        return _returnvalue

class DT_PioChannelVol(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return f"{int(data * 2 + 50):02}"

    def get_shng_data(self, data, type=None, **kwargs):
        return (int(data) - 50) / 2

class DT_PioName(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return f"{len(data):02}{data}"

class DT_onoff(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'O' if data else 'F'

    def get_shng_data(self, data, type=None, **kwargs):
        if type is None or type == 'bool':
            return True if data == '0' else False

        return super().get_shng_data(data, type)
