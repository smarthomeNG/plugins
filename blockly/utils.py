#!/usr/bin/env python3
# -*- coding: utf8 -*-
#########################################################################
# Copyright 2016-       Martin Sinn                         m.sinn@gmx.de
#                       René Frieß                  rene.friess@gmail.com
#                       Bernd Meiners
#########################################################################
#  Blockly plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import json
import os
import collections
from collections import OrderedDict

def remove_prefix(string, prefix):
    """
    Remove prefix from a string

    :param string: String to remove the profix from
    :param prefix: Prefix to remove from string
    :type string: str
    :type prefix: str

    :return: Strting with prefix removed
    :rtype: str
    """
    if string.startswith(prefix):
        return string[len(prefix):]
    return string


def html_escape(str):
    str = str.rstrip().replace('<', '&lt;').replace('>', '&gt;')
    str = str.rstrip().replace('(', '&#40;').replace(')', '&#41;')
    html = str.rstrip().replace("'", '&#39;').replace('"', '&quot;')
    return html
