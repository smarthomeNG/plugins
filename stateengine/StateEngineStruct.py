#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
#########################################################################
#  Finite state machine plugin for SmartHomeNG
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
from . import StateEngineTools
import collections.abc
from lib.item import Items


class StructProperty:
    def __init__(self, parent):
        self._item = parent

    @property
    def path(self):
        return self._item.struct_path

    @property
    def valid_se_use(self):
        return self._item.valid_se_use


# Class representing an object state, consisting of name, conditions to be met and configured actions for state
class SeStruct(StateEngineTools.SeItemChild):
    # Return configuration
    @property
    def conf(self):
        return self._conf

    @property
    def id(self):
        return self.struct_path

    def return_children(self):
        for child in self._conf.keys():
            yield child

    # Constructor
    # abitem: parent SeItem instance
    # struct_path: string defining struct
    def __init__(self, abitem, struct_path, global_struct):
        super().__init__(abitem)
        self.itemsApi = Items.get_instance()
        self.struct_path = struct_path
        self._conf = {}
        self._full_conf = {}
        self._struct = None
        self._global_struct = global_struct # copy.deepcopy(self.itemsApi.return_struct_definitions())
        self._struct_rest = None
        self._children_structs = []
        self._parent_struct = None
        self.valid_se_use = False
        self.property = StructProperty(self)
        self.convert()

    def __repr__(self):
        return "SeStruct {}".format(self.struct_path)

    @staticmethod
    # Usage: dict_get(mydict, 'some.deeply.nested.value', 'my default')
    def dict_get(_dict, path, default=None):
        for key in path.split('.'):
            try:
                _dict = _dict[key]
            except KeyError:
                return default
        return _dict

    def convert(self):
        try:
            struct = ""
            struct_rest = ""
            for i in self.struct_path.split("."):
                struct = "{}.{}".format(struct, i) if struct != "" else i
                if self._global_struct.get(struct):
                    _, struct_rest = StateEngineTools.partition_strip(self.struct_path, "{}.".format(struct))
                    break
            self._struct = struct
            self._struct_rest = struct_rest
            self.get()
        except Exception as ex:
            _issue = "Conversion error: {}".format(ex)
            self._abitem.update_issues('struct', {self.struct_path: {'issue': _issue}})
            raise Exception("Struct {} {}".format(self.struct_path, _issue))

    def get(self):
        raise NotImplementedError("Class {} doesn't implement get()".format(self.__class__.__name__))


# Class representing struct child
class SeStructMain(SeStruct):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, struct_path, global_struct):
        super().__init__(abitem, struct_path, global_struct)
        #self._log_debug("Struct path {} for {}", self.struct_path, __class__.__name__)

    def __repr__(self):
        return "SeStructMain {}".format(self.struct_path)

    def create_parent(self):
        try:
            parent = SeStructParent(self._abitem, self.struct_path, self._global_struct)
            self._parent_struct = parent
        except Exception as ex:
            _issue = "Create parent error: {}".format(ex)
            self._abitem.update_issues('struct', {self.struct_path: {'issue': _issue}})
            raise Exception("Struct {} {}".format(self.struct_path, _issue))

    def return_parent(self):
        return self._parent_struct

    def create_children(self):
        _se_ok = False
        try:
            _temp_dict = collections.OrderedDict(
                {key: value for (key, value) in self._full_conf.items() if isinstance(value, collections.abc.Mapping)})
            for c in _temp_dict:
                if c.startswith("enter"):
                    _se_ok = True
                c = SeStructChild(self._abitem, '{}.{}'.format(self.struct_path, c), self._global_struct)
                self._children_structs.append(c)
        except Exception as ex:
            _issue = "Create children error: {}".format(ex)
            self._abitem.update_issues('struct', {self.struct_path: {'issue': _issue}})
            raise Exception("Struct {} {}".format(self.struct_path, _issue))
        self.valid_se_use = _se_ok

    def return_children(self):
        return self._children_structs

    def get(self):
        _temp_dict = self.dict_get(self._global_struct.get(self._struct) or {}, self._struct_rest,
                                   self._global_struct.get(self._struct) or {})
        self._full_conf = _temp_dict
        try:
            _temp_dict = collections.OrderedDict(
                {key: value for (key, value) in _temp_dict.items() if not isinstance(value, collections.abc.Mapping)})
            self._conf = _temp_dict
            _test_dict = self.dict_get(self._global_struct.get(self._struct) or {}, self._struct_rest)
            self.create_parent()
            if _test_dict or self._struct_rest == '':
                self.create_children()
                self.valid_se_use = True if "se_use" in self._full_conf else self.valid_se_use
            else:
                _issue = "Item '{}' does not exist".format( self._struct_rest)
                self._abitem.update_issues('struct', {self.struct_path: {'issue': _issue}})
                self._log_error("{} in struct {}", _issue, self._struct)
        except Exception as ex:
            _issue = "Problem getting struct {}".format(ex)
            self._abitem.update_issues('struct', {self.struct_path: {'issue': _issue}})
            self._log_error("Problem getting struct {}: {}", self._conf, ex)
            self._conf = {}


# Class representing struct child
class SeStructChild(SeStruct):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, struct_path, global_struct):
        super().__init__(abitem, struct_path, global_struct)
        #self._log_debug("Struct path {} for {}", self.struct_path, __class__.__name__)

    def __repr__(self):
        return "SeStructChild {}".format(self.struct_path)

    def get(self):
        try:
            self._conf = self.dict_get(self._global_struct.get(self._struct) or {}, self._struct_rest, self._global_struct.get(self._struct) or {})
        except Exception:
            self._conf = {}


# Class representing struct parent
class SeStructParent(SeStruct):
    # Initialize the action
    # abitem: parent SeItem instance
    # name: Name of action
    def __init__(self, abitem, struct_path, global_struct):
        super().__init__(abitem, struct_path, global_struct)
        #self._log_debug("Struct path {} for {}", self.struct_path, __class__.__name__)

    def __repr__(self):
        return "SeStructParent {}".format(self.struct_path, self._conf)

    def get(self):
        try:
            parent_name = self.struct_path.split(".")[-2]
            _temp_dict = self.dict_get(self._global_struct.get(self._struct) or {}, parent_name, self._global_struct.get(self._struct) or {})
            _temp_dict = collections.OrderedDict(
                {key: value for (key, value) in _temp_dict.items() if not isinstance(value, collections.abc.Mapping)})
            self._conf = _temp_dict
        except Exception:
            self._conf = {}
