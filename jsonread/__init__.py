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

# PATCH: Move jq engine into JSONREAD class without breaking behavior
# Drop-in replacement for previous global jq_* functions


class JSONREAD(SmartPlugin):
    PLUGIN_VERSION = '2.0.0'

    def __init__(self, sh):
        super().__init__()

        self._url = self.get_parameter_value('url')
        self._cycle = self.get_parameter_value('cycle')

        self._session = requests.Session()
        self._session.mount('file://', FileAdapter())

        self._items = {}
        self._compiled_filters = {}

        self._lastresult = {}
        self._lastresultstr = ''
        self._lastresultjq = ''

        self.init_webinterface(WebInterface)

    def run(self):
        self.logger.debug('Run method called')
        self.alive = True
        self.scheduler_add('poll', self.poll_device, cycle=self._cycle)

    def stop(self):
        self.logger.debug('Stop method called')
        self.scheduler_remove_all()
        self.alive = False

    def pathes(self, d, stem=''):
        if isinstance(d, dict):
            for key, value in d.items():
                if isinstance(value, (dict, list, tuple)):
                    yield from self.pathes(value, f'{stem}.{key}')
                else:
                    yield f'{stem}.{key} => {value}'
        elif isinstance(d, (list, tuple)):
            for value in d:
                if isinstance(value, (dict, list, tuple)):
                    yield from self.pathes(value, stem)
                else:
                    yield f'{stem} => {value}'
        else:
            yield f'{stem}.{d}'

    def jq_compile(self, expr):
        """
        Split jq expression into pipe steps, respect parentheses and select()
        """
        expr = expr.strip()
        # entferne äußere Klammern
        if expr.startswith('(') and expr.endswith(')'):
            expr = expr[1:-1].strip()

        pipes = []
        buf = ''
        depth = 0
        i = 0
        while i < len(expr):
            ch = expr[i]
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            elif ch == '|' and depth == 0:
                pipes.append(buf.strip())
                buf = ''
                i += 1
                continue
            buf += ch
            i += 1

        if buf.strip():
            pipes.append(buf.strip())

        # Nachträglich: splitte select(...) von nachfolgenden Pfaden
        new_pipes = []
        for p in pipes:
            if p.startswith('select(') and ')' in p:
                idx = p.index(')') + 1
                select_part = p[:idx]
                rest = p[idx:].lstrip('.')
                new_pipes.append(select_part)
                if rest:
                    new_pipes.append('.' + rest if rest[0] != '.' else rest)
            else:
                new_pipes.append(p)

        return tuple(new_pipes)

    def jq_full(self, pipes, value):
        """
        Führt alle Pipe-Schritte aus
        """
        if not isinstance(value, list):
            value = [value]

        for pipe in pipes:
            pipe = pipe.strip()
            out = []
            for v in value:
                res = self.jq_step(pipe, v)
                if isinstance(res, list):
                    out.extend(res)
                elif res is not None:
                    out.append(res)
            value = out
        return value

    def jq_step(self, expr, value):
        expr = expr.strip()
        if expr.startswith('select('):
            # split at first ')'
            depth = 0
            for i, ch in enumerate(expr):
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        break
            cond = expr[7:i]  # Inhalt von select(...)
            rest = expr[i + 1 :].lstrip('.')  # alles danach

            if not isinstance(value, list):
                value = [value]

            out = []
            for v in value:
                if self.jq_condition(cond, v):
                    # traverse weiter, auch wenn rest leer
                    if rest:
                        out.extend(self._traverse(v, rest))
                    else:
                        out.append(v)
            return out

        # normaler Pfad
        return self._traverse(value, expr)

    def _split_key_indices(self, token):
        """
        Split a path token like ``Data["0"]`` or ``Data[0]`` or ``Data[]``
        into its base key name and a list of bracket-index strings, e.g.
        ``('Data', ['"0"'])`` / ``('Data', ['0'])`` / ``('Data', [''])``.
        A bare key with no brackets returns an empty index list.
        """
        m = re.match(r'^([^\[\]]*)((?:\[[^\[\]]*\])*)$', token)
        if not m:
            return token, []
        name, bracket_part = m.groups()
        indices = re.findall(r'\[([^\[\]]*)\]', bracket_part)
        return name, indices

    def _resolve_index(self, val, idx):
        """
        Resolve a single bracket-index token (already stripped of the
        brackets) against val. '' means "flatten" (jq's ``[]``): every
        element of a list, or the value itself if it's not a list. A
        quoted or unquoted index is tried as a list index first (jq
        allows array indices written as ``[0]`` or ``["0"]``), falling
        back to a dict-key lookup.
        """
        if idx == '':
            return val if isinstance(val, list) else [val]

        idx = idx.strip()
        if idx.startswith('"') and idx.endswith('"'):
            idx = idx[1:-1]

        if isinstance(val, list):
            try:
                return [val[int(idx)]]
            except (ValueError, IndexError):
                return []
        if isinstance(val, dict) and idx in val:
            return [val[idx]]
        return []

    def _traverse(self, obj, keypath):
        if not keypath:
            if isinstance(obj, list):
                return obj
            return [obj]

        if keypath.startswith('.'):
            keypath = keypath[1:]

        parts = keypath.split('.', 1)
        token = parts[0]
        rest = parts[1] if len(parts) > 1 else ''

        key, indices = self._split_key_indices(token)

        if key:
            if isinstance(obj, dict) and key in obj:
                values = [obj[key]]
            elif isinstance(obj, list):
                out = []
                for v in obj:
                    out.extend(self._traverse(v, keypath))
                return out
            else:
                return []
        else:
            values = [obj]

        for idx in indices:
            new_values = []
            for v in values:
                new_values.extend(self._resolve_index(v, idx))
            values = new_values

        out = []
        for v in values:
            if rest:
                out.extend(self._traverse(v, rest))
            else:
                out.append(v)
        return out

    def jq_condition(self, cond, obj):
        # Unterstützt ==, !=, >, <, >=, <=
        m = re.match(r'\.(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)', cond)
        if not m:
            return False

        keypath, op, raw_val = m.groups()
        raw_val = raw_val.strip().strip('"')

        # Konvertiere Werte
        if raw_val.lower() == 'true':
            cmp_val = True
        elif raw_val.lower() == 'false':
            cmp_val = False
        else:
            try:
                cmp_val = float(raw_val)
            except Exception:
                cmp_val = raw_val

        # Traversiere verschachtelte Keys
        vals = self._traverse(obj, keypath)
        for val in vals:
            # Versuche numerischen Vergleich
            try:
                val_num = float(val)
                cmp_num = float(cmp_val)
                val = val_num
                cmp_val = cmp_num
            except Exception:
                pass

            if op == '==':
                if val == cmp_val:
                    return True
            elif op == '!=':
                if val != cmp_val:
                    return True
            elif op == '>':
                if val > cmp_val:
                    return True
            elif op == '<':
                if val < cmp_val:
                    return True
            elif op == '>=':
                if val >= cmp_val:
                    return True
            elif op == '<=':
                if val <= cmp_val:
                    return True

        return False

    def jq_path(self, path, data):
        path = path.lstrip('.')
        if path == '':
            return data

        parts = []
        buf = ''
        in_quotes = False
        for ch in path:
            if ch == '"':
                in_quotes = not in_quotes
                buf += ch
            elif ch == '.' and not in_quotes:
                parts.append(buf)
                buf = ''
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
            if key.endswith('[]'):
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

        if len(vals) == 0:
            return None
        if len(vals) == 1:
            return vals[0]
        return vals

    def jq_unwrap(self, value):
        if isinstance(value, list):
            if len(value) == 0:
                return None
            if len(value) == 1:
                return value[0]
        return value

    def evaluate_filter(self, expr, data):
        """
        Resolve a single ``jsonread_filter`` expression against a parsed
        JSON document and return the matched value (or None if nothing
        matched). This is the one seam between "what an item's filter
        string means" and "how that's actually computed" — poll_device()
        and the test suite both go through here rather than calling
        jq_compile/jq_full/jq_unwrap directly, so swapping the underlying
        engine (e.g. for a real jmespath/jq library) only requires
        reimplementing this one method; callers and the filter-contract
        tests (tests/test_filter_contract.py) don't change.
        """
        compiled = self._compiled_filters.get(expr)
        if compiled is None:
            compiled = self.jq_compile(expr)
            self._compiled_filters[expr] = compiled
        return self.jq_unwrap(self.jq_full(compiled, data))

    # MODIFY parse_item
    def parse_item(self, item):
        if self.has_iattr(item.conf, 'jsonread_filter'):
            expr = self.get_iattr_value(item.conf, 'jsonread_filter')
            self._items[item] = expr

    # MODIFY poll_device jq call
    def poll_device(self):
        try:
            response = self._session.get(self._url)
        except Exception as ex:
            self.logger.error(f'GET failed {self._url}: {ex}')
            return

        if response.status_code != 200:
            self.logger.error(f'Bad HTTP {response.status_code} from {self._url}')
            return

        try:
            json_obj = response.json()
        except Exception:
            self.logger.error(f'Response from {self._url} is not JSON')
            return

        # Store debug info (Unicode-safe)
        try:
            self._lastresult = json_obj
            self._lastresultstr = json.dumps(json_obj, indent=4, sort_keys=True, ensure_ascii=False)
            self._lastresultjq = '\n'.join(self.pathes(json_obj))
        except Exception:
            self._lastresultstr = '<format error>'

        for item, expr in self._items.items():
            try:
                jqres = self.evaluate_filter(expr, json_obj)
                self.logger.debug(f'Item {item} resolved to {jqres}')
            except Exception as ex:
                self.logger.error(f'jq failed: {expr} => {ex}')
                continue

            try:
                item(jqres)
            except Exception as ex:
                self.logger.error(f'Item update failed {item}: {ex}')
