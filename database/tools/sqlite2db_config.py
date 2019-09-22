#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2018-       Oliver Hinckel                 github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################


"""
This will migrate the configuration file using sqlite settings to
settings for the database plugin (e.g sqlite=yes to database=yes)

The result is printed to stdout
"""

import os
import re
import argparse


def convert_config(filename):
    with open(filename, 'r') as f:
        data = f.read()
        data = re.sub(r'sqlite([\w\s@]*)(=|:)(\s*)(\w+)', r'database\1\2\3\4', data)
    print(data) 

if __name__ == '__main__':

    parser = argparse.ArgumentParser(add_help=False)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-c', '--config', dest='config', help='the configuration file to convert')
    args = parser.parse_args()

    if args.config:
        convert_config(args.config)
    else:
        print('')
        print(os.path.basename(__file__) + ' - Converts the configuration file for database plugin')
        print('')
        parser.print_help()
        print()

