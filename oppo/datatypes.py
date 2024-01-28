#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT


class DT_onoff(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'ON' if data else 'OF'

    def get_shng_data(self, data, type=None, **kwargs):
        return False if (data == 'OFF' or data == '0') else True

class DT_playpause(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return '#PLA' if data == 'PLAY' else '#PAU'

class DT_ok(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return True if data == "OK" else False if data.startswith("ER ") else data

class DT_openclose(DT.Datatype):
    def get_shng_data(self, data, type=None, **kwargs):
        return False if data.startswith('CLOS') else True
