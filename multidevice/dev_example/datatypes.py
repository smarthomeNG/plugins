#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    import datatypes as DT
else:
    from .. import datatypes as DT


class DT_Example(DT.Datatype):
    """ Example class for Datatype definitions. Not used in class. """

    def __init__(self, fail_silent=True):
        super().__init__(fail_silent)

    def get_send_data(self, data, **kwargs):
        return data

    def get_shng_data(self, data, type=None, **kwargs):
        if type is None:
            return data

        # let the base class do some work if type is explicitly requested
        return super().get_shng_data(data, type)
