#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

if MD_standalone:
    from MD_Device import MD_Device
else:
    from ..MD_Device import MD_Device


class MD_Device(MD_Device):
    """ Example class for TCP request connections.

    This class reads arbitrary URLs or parametrized URLs using plugin configuration
    for `host` and `port`.

    See ``commands.py`` for command usage.
    """
    pass
