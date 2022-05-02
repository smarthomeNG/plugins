#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
#  upwards.
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
import ast

import requests
import json

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class InfluxDB2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.1.0'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.items = Items.get_instance()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.host = self.get_parameter_value('host')
        self.http_port = self.get_parameter_value('http_port')
        self.api_token = self.get_parameter_value('api_token')
        self.org = self.get_parameter_value('org')
        self.bucket = self.get_parameter_value('bucket')
        self.recognize_database = self.get_parameter_value('recognize_database')

        self.tags = self.get_parameter_value('tags')
        self.value_field = self.get_parameter_value('value_field')

        self.str_value_field = self.get_parameter_value('str_value_field')

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.warning(f"_plugin_item_dict:\n{self._plugin_item_dict }\n")
        self.logger.warning(f"_lookop_plugin_item_dict:\n{self._lookop_plugin_item_dict }\n")

        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        influxdb2_attr = 'false'
        if self.has_iattr(item.conf, 'influxdb2'):
            influxdb2_attr = self.get_iattr_value(item.conf, 'influxdb2').lower()
        elif self.recognize_database:
            if self.has_iattr(item.conf, 'database'):
                influxdb2_attr = self.get_iattr_value(item.conf, 'database').lower()

        if influxdb2_attr != 'false':
            #self.logger.debug(f"parse item (influxdb2/database): {item}")


            #if item.type() not in ['num', 'bool']:
            #    self.logger.error(f"Item {item.id()} has type {item.type()}, only 'num' and 'bool' are supported by influxdb2")
            #    return

            config_data = {}

            # define item_name for InfluxDB
            if self.has_iattr(item.conf, 'influxdb2_name'):
                config_data['name'] = self.get_iattr_value(item.conf, 'influxdb2_name')
            else:
                config_data['name'] = item.property.name

            # define InfluxDB bucket for item
            if self.has_iattr(item.conf, 'influxdb2_bucket'):
                config_data['bucket'] = self.get_iattr_value(item.conf, 'influxdb2_bucket')
            else:
                config_data['bucket'] = self.bucket

            # add item specific tag definitions
            if self.has_iattr(item.conf, 'influxdb2_tags'):
                tags_json = self.get_iattr_value(item.conf, 'influxdb2_tags')
                try:
                    # config_data['tags'] = json.loads( tags_json.replace("'", "\"") )
                    import ast
                    config_data['tags'] = ast.literal_eval( tags_json )
                    #for k in config_data['tags'].keys():
                    #    config_data['tags'][k] = config_data['tags'][k].replace(" ", "\ ")
                except Exception as e:
                    self.logger.error(f"parse_item: Item {item.property.path} has invalid data in 'influxdb2_tags' attribute: {tags_json}, ast.literal_eval failed with: {e}")

            # store plugin specific configuration information for this item
            self.add_pluginitem(item.property.path, config_data, device_command=None)

            return self.update_item

        return

        # todo
        # if interesting item for sending values:
        #   self._itemlist.append(item)
        #   return self.update_item

        return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            #self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            config_data = self.get_pluginitem_configdata(item.property.path)

            tags = {}
            tags['caller'] = caller.replace(' ', '\ ')
            if source is not None:
                tags['source'] = source.replace(' ', '\ ')
            if dest is not None:
                tags['dest'] = dest.replace(' ', '\ ')
            tags['item'] = item.property.path

            tags.update(self.tags)                 # add global tag definitions to actual tags
            if config_data.get('tags', None) is not None:
                tags.update(config_data['tags'])   # add item specific tag definitions to actual tags

            fields = {}
            if item.type() in ['num', 'bool']:
                fields[self.value_field] = float(item())
            else:
                fields[self.value_field] = 0
                tags[self.str_value_field] = str(item())
            #fields[self.str_value_field] = '"'+str(item())+'"'

            #line = self.create_line(name, tags, fields)
            line = self.create_line(config_data['name'], tags, fields)
            self.influx_writedata(config_data['bucket'], line)


    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # # get the value from the device
        # device_value = ...
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item by calling item(value, caller, source=None, dest=None)
        #     # - value and caller must be specified, source and dest are optional
        #     #
        #     # The simple case:
        #     item(device_value, self.get_shortname())
        #     # if the plugin is a gateway plugin which may receive updates from several external sources,
        #     # the source should be included when updating the the value:
        #     item(device_value, self.get_shortname(), source=device_source_id)
        pass


# =======================================================================================================
# Folgende Methoden sollen später in die SmartPlugin Klasse übergehen

    _plugin_item_dict = {}          # dict to hold the plugin specific information for an item
    _lookop_plugin_item_dict = {}   # dict for the reverse lookup from a device_command to an plugin_item
                                    # contains a list of item_pathes for each device_command

    def add_pluginitem(self, item_path, config_data_dict, device_command=None):
        """
        For items that are used/handled by a plugin, this method stores the configuration information
        that is individual for the plugin. The configuration information is/has to be stored in a dictionary

        The configuration information can be retrieved later by a call to the method get_pluginitem_configdata(<item_path>)

        If data is beeing received by the plugin, a 'device_command' has to be specified as an optional 3rd parameter.
        This allows a reverse lookup. The method get_pluginitemlist_for_devcie_command(<device_command>) returns a list
        of item-pathes for the items that have defined the <device_command>. In most cases, the list will have only one
        entry, but if multiple items should receive data from the same device (or command), the list can have more than
        one entry.

        :param item_path: Path of the item (item.property.path / item.id())
        :param config_data_dict: Dictionary with the plugin-specific configuration information for the item
        :param device_command: String identifing the origin (source/kind) of received data
        :type item_path: str
        :type config_data_dict: dict
        :type device_command: str

        :return: True, if the information has been added
        :rtype: bool
        """

        if self._plugin_item_dict.get(item_path, None) is not None:
            self.logging.error("Trying to add an plugin_item config for an plugin_item, which has a config already ")
            return False

        self._plugin_item_dict[item_path] = {}
        self._plugin_item_dict[item_path]['device_command'] = device_command
        self._plugin_item_dict[item_path]['config_data'] = config_data_dict

        if device_command is not None:
            if self._lookop_plugin_item_dict.get(device_command, None) is None:
                self._lookop_plugin_item_dict[device_command] = []
            self._lookop_plugin_item_dict[device_command].append(item_path)

        return True


    def remove_pluginitem(self, item_path):
        """
        Remove configuration data for an item (and remove the item from the device_command's list

        :param item_path: Path of the item (item.property.path / item.id()) to remove
        :type item_path: str

        :return: True, if the information has been removed
        :rtype: bool
        """
        if self._plugin_item_dict.get(item_path, None) is None:
            # There is no information stored for that item
            return False

        if self._plugin_item_dict[item_path]['device_command'] is not None:
            # if a device_command was given for the item, the item is being removed from the list of the device_command
            self._lookop_plugin_item_dict[self._plugin_item_dict[item_path]['device_command']].remove(item_path)

        del self._plugin_item_dict[item_path]
        return True


    def get_pluginitem_configdata(self, item_path):
        """
        Returns the plugin-specific configuration information for the given item_path

        :param item_path: Path of the item (item.property.path / item.id()) to get config info for
        :type item_path: str

        :return: dict with the configuration information for the given item_path
        :rtype: dict
        """

        return self._plugin_item_dict[item_path]['config_data']


    def get_pluginitem_list(self):

        return self._plugin_item_dict.keys()


    def get_pluginitems(self):

        result = []
        for path in self.get_pluginitem_list():
            result.append(self.items.return_item(path))
        return result


    def get_pluginitemlist_for_devcie_command(self, device_command):
        """
        Returns a list with item_pathes that should receive data for the given device_command

        :param device_command: device_command, for which the receiving items should be returned
        :type device_command: str

        :return: List of item_pathes
        :rtype: list
        """

        return self._lookop_plugin_item_dict.get(device_command, [])


# =======================================================================================================
# Folgende Methoden sind InfuxDB spezifisch

    def replace_unwanted_chars(self, str):

        str = str.replace(' ', '\ ').replace('ß', 'ss')
        str = str.replace('ä', 'ae').replace('Ä', 'Ae')
        str = str.replace('ö', 'oe').replace('Ö', 'Oe')
        str = str.replace('ü', 'ue').replace('Ü', 'Ue')
        return str


    def create_line(self, name, tags, fields):

        # build name and tags
        name = self.replace_unwanted_chars(name)
        kvs = [name]
        for tag_key in sorted(tags.keys()):
            k = tag_key
            v = tags[tag_key]
            # escape '=' in tag values
            if v is not None:
                v = v.replace("=", "\=")
                v = v.replace(" ", "\ ")
            kvs.append(f"{k}={v}")
        line_tags = ','.join(kvs)

        # build fields (which include the actual value)
        kvs = []
        for field_key in sorted(fields.keys()):
            kvs.append("{k}={v}".format(k=field_key, v=fields[field_key]))
        lineproto_fields = ','.join(kvs)
        #if tags['item'].startswith('test') or name.startswith('Spann'):
        #    self.logger.warning(f"create_line: {name} -> line_fields -> {lineproto_fields}")
        #    self.logger.warning(f"create_line: {name} -> line_tags   -> {line_tags}")

        return line_tags + ' ' + lineproto_fields


    def _url_base(self):
        """
        Build url base string from protocol, host address and port

        :return: url base string
        :rtype: str
        """
        return f"http://{self.host}:{self.http_port}"


    def influx_writedata(self, bucket, data):
        try:
            url_string = self._url_base() + f"/api/v2/write?bucket={bucket}&org={self.org}"
            r = requests.post(url_string, data=data, headers={'Authorization': 'Token '+self.api_token})
            if(r.status_code != 204):
                self.logger.error(f"Request returns http {r.status_code} [{r.text}]")
        except Exception as e:
            self.logger.error(f"Failed sending HTTP datagram [{data}] to {url_string} with error: {e}")
        else:
            #self.logger.debug(f"senthttp to {url_string} - Datagram [{data}] ")
            #self.logger.debug(f"- r.text = {r.status_code} [{r.text}] ")
            pass


    def gethttp(self, endpoint, data=None, auth=False):
        try:
            url_string = self._url_base()
            # r = requests.get(url_string, data=data, headers={'Authorization': 'Token '+self.api_token})
            if auth:
                r = requests.get(url_string + endpoint, headers={'Authorization': 'Token ' + self.api_token})
            else:
                r = requests.get(url_string + endpoint)
            self.logger.debug(f"Sent HTTP GET request [{url_string + endpoint}]")
            if not (r.status_code in [200, 204]):
                self.logger.error(f"Request {url_string + endpoint} returns http {r.status_code} [{r.text}]")
                return json.loads(r.text)
            else:
                self.logger.debug(f"Returns http {r}]")
        except Exception as e:
            self.logger.error(f"Failed sending HTTP datagram [{data}] to {'127.0.0.1:8086'} with error: {e}")
        else:
            if r.text:
                self.logger.debug(f"Received datagram text [{r.text}]")
            try:
                self.logger.debug(f"Received datagram json: {json.loads(r.text)}")
                return json.loads(r.text)
            except Exception as e:
                pass
            self.logger.debug(f"gethttp: Received datagram [{r}]")
        return


    def influx_getversion(self):
        healthdict = self.gethttp('/health', auth=False)
        return healthdict.get('version','-')
