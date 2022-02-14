#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    from MD_Device import MD_Device
    from MD_Globals import (PLUGIN_ATTR_CONNECTION, CONN_NULL)
else:
    from ..MD_Device import MD_Device
    from ..MD_Globals import (PLUGIN_ATTR_CONNECTION, CONN_NULL)

from random import random


class MD_Device(MD_Device):
    """ Example class. 

    For most cases, the main work is in the commands definition in the
    ``commands.py`` file and - possibly - the datatype classes in
    ``datatypes.py``.
    Configuration of defaults is done in ``device.yaml``

    You can control initialization here, or do some work which can't be
    done by commands alone.
    """

    def _set_device_defaults(self):
        # you can set defaults, parameters or other before the main 
        # initialization takes place, so the values set here will all
        # be taken into account
        #
        # example: set to True to use on_connect and on_disconnect callbacks
        self._use_callbacks = False

        # example: set connection class to (nonfunctional) MD_Connection, e.g.
        # for testing.
        # By default, connection class should be set from ``device.yaml``
        self._params[PLUGIN_ATTR_CONNECTION] = CONN_NULL

    def _post_init(self):
        # you can call additional methods here after the device class'
        # initialization has finished
        #
        # possibly do things you need to do (assert?) after the base
        # class' __init__ has run

        self.logger.error('Init is done and I did something important.')

        # if for some reason necessary, you _can_ disable loading the
        # device, if so needed... maybe you might want to tell somebody
        # about it
        self.logger.critical('infinite improbability detected, device probably disabled')

        # probably disable...
        self.disabled = bool(int(random() + 0.7))

    def run_standalone(self):
        # this is just a demonstration of little value...

        # in standalone mode, by default only CRITICAL logs are printed
        self.logger.critical('Attention, example device class loaded')

        # if you run standalone mode with '-v', you get DEBUG logging
        self.logger.debug('You only see this if running with -v')
