#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#  Copyright 2020- Sebastian Helms                  Morg @ knx-user-forum
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
#########################################################################

import logging
from collections import OrderedDict
import urllib.parse
import http.client
from lib.model.smartplugin import SmartPlugin


class Prowl(SmartPlugin):
    '''
    This plugin enables SmartHomeNG to send Prowl notifications.

    You can use the `notify()` function to send Prowl notifications from logics
    or (e.g.) eval expressions.

    The item attributes allow simple sending predefined texts if the item changes.
    Note: Not all parameters of `notify()` can be set by item attributes. If you need
    more control, maybe use a logic to call `notify()` with all relevant parameters.
    '''
    PLUGIN_VERSION = '1.3.3'

    _host = 'api.prowlapp.com'
    _api = '/publicapi/add'

    def __init__(self, smarthome):
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._prowl_items = {}

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._apikey = self.get_parameter_value('apikey')

    def run(self):
        '''
        Run method for the plugin
        '''
        self.logger.debug('Run method called')
        self.alive = True

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.logger.debug('Stop method called')
        self.alive = False

    def parse_item(self, item):
        '''
        Check if item is associated with plugin
        '''

        # only process item if event and at least one of values and text is set
        if self.has_iattr(item.conf, 'prowl_event') and (self.has_iattr(item.conf, 'prowl_text') or self.has_iattr(item.conf, 'prowl_values')):

            params = {}
            params['event'] = self.get_iattr_value(item.conf, 'prowl_event')
            params['text'] = self.get_iattr_value(item.conf, 'prowl_text')

            vals = {}
            vlist = self.get_iattr_value(item.conf, 'prowl_values')
            if vlist:
                for entry in vlist:
                    if isinstance(entry, OrderedDict):
                        for arg in entry.keys():

                            # store parameters
                            vals[arg] = entry[arg]
            params['vals'] = vals
            params['swap'] = self.get_iattr_value(item.conf, 'prowl_swap')
            params['url'] = self.get_iattr_value(item.conf, 'prowl_url')

            # store item params
            self._prowl_items[item] = params
            self.logger.debug(f'Item {item} registered for prowl notification')
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        '''
        Item was changed, process changes
        '''
        if self.alive:

            self.logger.debug(f'Update_item was called with item "{item}" from caller {caller}, source {source} and dest {dest}')

            # test if source of item change was not the item's device...
            if caller != self.get_shortname() and item() != item.property.last_value:
                params = self._prowl_items[item]

                # just to make sure...
                if params:
                    event = params['event'].replace('VAL', str(item()))

                    text = None
                    if item() in params['vals']:

                        # choose text from dict
                        text = str(params['vals'][item()])
                    elif params['text']:
                        text = params['text'].replace('VAL', str(item()))

                    url = None
                    if 'url' in params and params['url'] is not None:
                        url = params['url'].replace('VAL', str(item()))

                    # got any result?
                    if text:
                        if params['swap']:
                            (text, event) = (event, text)
                        self.logger.info(f'Notifying prowl for item {item}: "{event}" -> "{text}"')
                        self.notify(event, text, url=url)
                    else:
                        self.logger.info(f'Not notifying prowl for item {item}: value {item()} not in prowl_values and no prowl_text set')
                        return
                else:
                    self.logger.error(f'update_item called for item {item}, but no parameters stored. This should not happen...')

    def notify(self, event='', description='', priority=None, url=None, apikey=None, application='SmartHomeNG'):
        '''Provides an exposed function to send a notification'''
        self.__call__(event, description, priority, url, apikey, application)

    def __call__(self, event='', description='', priority=None, url=None, apikey=None, application='SmartHomeNG'):
        '''does the work to send a notification to prowl api'''
        if not self.alive:
            self.logger.warning('Could not send prowl notification, the plugin is not alive!')
            return

        data = {}
        origin = application
        if self.get_instance_name() != '':
            origin += ' (' + self.get_instance_name() + ')'
        headers = {'User-Agent': application, 'Content-Type': 'application/x-www-form-urlencoded'}
        data['event'] = event[:1024].encode()
        data['description'] = description[:10000].encode()
        data['application'] = origin[:256].encode()
        if apikey:
            data['apikey'] = apikey
        else:
            data['apikey'] = self._apikey.encode()
        if priority:
            data['priority'] = priority
        if url:
            data['url'] = url[:512]
        try:
            conn = http.client.HTTPSConnection(self._host, timeout=4)
#
            print(data)
            conn.request('POST', self._api, urllib.parse.urlencode(data), headers)
            resp = conn.getresponse()
            conn.close()
            if resp.status != 200:
                raise Exception(f'{resp.status} {resp.reason}')
        except Exception as e:
            self.logger.warning(f'Could not send prowl notification: {event}. Error: {e}')
