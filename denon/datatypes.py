#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT


# read only. Depending on a status field, the result is sliced.
class DT_DenonDisplay(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        infotype = data[3:4]
        if infotype.isdigit():
            if infotype == 0:
                data = data[4:]
            elif infotype == 1:
                data = data[5:]
            else:
                data = data[6:]
            return data

        return None


# handle pseudo-decimal values without decimal point
class DT_DenonVol(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if int(data) == data:
            # "real" integer
            return f'{int(data):02}'
        else:
            # float with fractional value
            return f'{int(data):02}5'

    def get_shng_data(self, data, type=None, **kwargs):
        if len(data) == 3:
            return int(data) / 10
        else:
            return data


class DT_DenonStandby(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'OFF' if data == 0 else f"{data:01}H"

    def get_shng_data(self, data, type=None, **kwargs):
        return 0 if data == 'OFF' else data.split('H')[0]


class DT_DenonStandby1(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'OFF' if data == 0 else f"{data:02}M"

    def get_shng_data(self, data, type=None, **kwargs):
        return 0 if data == 'OFF' else data.split('M')[0]


class DT_onoff(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'ON' if data else 'OFF'

    def get_shng_data(self, data, type=None, **kwargs):
        return False if data == 'OFF' else True


class DT_convert0(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'OFF' if data == 0 else f"{data:03}"

    def get_shng_data(self, data, type=None, **kwargs):
        return 0 if data in ['OFF', 'NON'] else data


class DT_convertAuto(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'AUTO' if data == 0 else data

    def get_shng_data(self, data, type=None, **kwargs):
        return 0 if data == 'AUTO' else data


class DT_remap50to0(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        if int(data) == data:
            # "real" integer
            return f'{(int(data)+50):02}'
        else:
            # float with fractional value
            return f'{(int(data)+50):02}5'

    def get_shng_data(self, data, type=None, **kwargs):
        if len(data) == 3:
            return int(data) / 10 - 50
        else:
            return int(data) - 50
