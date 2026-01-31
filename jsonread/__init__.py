#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Torsten Dreyer                torsten (at) t3r (dot) de
#  Copyright 2021 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
#
#########################################################################

import logging
import json
import requests
from requests_file import FileAdapter
import re
from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from .webif import WebInterface

def jq_compile(expr):
    """Split filter expression into pipe steps"""
    return tuple(p.strip() for p in expr.strip().split("|"))

def jq_full(pipes, value):
    """Apply pipe chain like jq"""
    for pipe in pipes:
        pipe = pipe.strip()
        if not isinstance(value, list):
            value = [value]
        out = []
        for v in value:
            res = jq_step(pipe, v)
            if isinstance(res, list):
                out.extend(res)
            elif res is not None:
                out.append(res)
        value = out
    return value

def jq_step(expr, value):
    expr = expr.strip()

    # select() über Listen
    if expr.startswith("select(") and expr.endswith(")"):
        cond = expr[7:-1]
        if isinstance(value, list):
            return [v for v in value if jq_condition(cond, v)]
        return [value] if jq_condition(cond, value) else []

    # [] Operator
    if expr.endswith("[]"):
        base = expr[:-2]
        res = jq_path(base, value)
        if isinstance(res, list):
            return res
        return []

    # normal path
    return jq_path(expr, value)

def jq_condition(cond, obj):
    m = re.match(r'\.(.+?)\s*==\s*("?)(.*?)\2$', cond)
    if m:
        key, _, val = m.groups()
        if isinstance(obj, dict):
            return str(obj.get(key)) == val
    return False

def jq_path(path, data):
    """Resolve a dot-separated path, handling [] and quoted keys"""
    path = path.lstrip(".")
    if path == "":
        return data

    # Split respecting quoted keys
    parts = []
    buf = ""
    in_quotes = False
    for ch in path:
        if ch == '"':
            in_quotes = not in_quotes
            buf += ch
        elif ch == "." and not in_quotes:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf:
        parts.append(buf)

    def normalize_key(k):
        k = k.strip()
        if k.startswith('"') and k.endswith('"'):
            return k[1:-1]
        return k

    vals = [data]
    for part in parts:
        key = normalize_key(part)
        is_list = False
        if key.endswith("[]"):
            key = key[:-2]
            is_list = True
        new_vals = []
        for v in vals:
            if isinstance(v, dict) and key in v:
                val = v[key]
                if is_list:
                    if isinstance(val, list):
                        new_vals.extend(val)
                    else:
                        new_vals.append(val)
                else:
                    new_vals.append(val)
            elif isinstance(v, list):
                for e in v:
                    if isinstance(e, dict) and key in e:
                        val = e[key]
                        if is_list and isinstance(val, list):
                            new_vals.extend(val)
                        else:
                            new_vals.append(val)
        vals = new_vals
    # pyjq.first() compatibility
    if len(vals) == 0:
        return None
    if len(vals) == 1:
        return vals[0]
    return vals

def jq_unwrap(value):
    """pyjq.first()-compatibility"""
    if isinstance(value, list):
        if len(value) == 0:
            return None
        if len(value) == 1:
            return value[0]
    return value

# ============================================================
# JSONREAD Plugin (Turbo + jq kompatibel)
# ============================================================

class JSONREAD(SmartPlugin):
    PLUGIN_VERSION = "2.0.0"

    def __init__(self, sh):
        super().__init__()

        self._url = self.get_parameter_value('url')
        self._cycle = self.get_parameter_value('cycle')

        self._session = requests.Session()
        self._session.mount('file://', FileAdapter())

        self._items = {}
        self._compiled_filters = {}

        self._lastresult = {}
        self._lastresultstr = ""
        self._lastresultjq = ""

        self.init_webinterface(WebInterface)

    def run(self):
        self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add(self.get_fullname(), self.poll_device, cycle=self._cycle)

    def stop(self):
        self.logger.debug("Stop method called")
        self.scheduler_remove(self.get_fullname())
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'jsonread_filter'):
            expr = self.get_iattr_value(item.conf, 'jsonread_filter')
            self._items[item] = expr
            self._compiled_filters[item] = jq_compile(expr)

    def poll_device(self):
        try:
            response = self._session.get(self._url)
        except Exception as ex:
            self.logger.error(f"GET failed {self._url}: {ex}")
            return

        if response.status_code != 200:
            self.logger.error(f"Bad HTTP {response.status_code} from {self._url}")
            return

        try:
            json_obj = response.json()
        except Exception:
            self.logger.error(f"Response from {self._url} is not JSON")
            return

        # Store debug info (Unicode-safe)
        try:
            self._lastresult = json_obj
            self._lastresultstr = json.dumps(json_obj, indent=4, sort_keys=True, ensure_ascii=False)
            self._lastresultjq = '\n'.join(pathes(json_obj))
        except Exception:
            self._lastresultstr = "<format error>"

        # Process items (Turbo mode)
        for item, expr in self._items.items():
            try:
                compiled = self._compiled_filters[item]
                jqres = jq_full(compiled, json_obj)
                jqres = jq_unwrap(jqres)
            except Exception as ex:
                self.logger.error(f"jq failed: {expr} => {ex}")
                continue

            try:
                item(jqres)
            except Exception as ex:
                self.logger.error(f"Item update failed {item}: {ex}")

# ============================================================
# Debug helper
# ============================================================

def pathes(d, stem=""):
    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, (dict, list, tuple)):
                yield from pathes(value, f"{stem}.{key}")
            else:
                yield f"{stem}.{key} => {value}"
    elif isinstance(d, (list, tuple)):
        for value in d:
            if isinstance(value, (dict, list, tuple)):
                yield from pathes(value, stem)
            else:
                yield f"{stem} => {value}"
    else:
        yield f"{stem}.{d}"
