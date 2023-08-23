#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

import lib.model.sdp.datatypes as DT

class DT_onoff(DT.Datatype):
    def get_send_data(self, data, **kwargs):
        return 'ON' if data else 'OFF'

    def get_shng_data(self, data, type=None, **kwargs):
        return False if data == '0' else True if data == '1' else None
