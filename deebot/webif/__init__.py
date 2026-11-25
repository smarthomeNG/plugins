#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
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

"""Web interface of the deebot plugin."""

import json
import zlib

import cherrypy

from lib.model.smartplugin import SmartPluginWebIf

from ..features import FEATURES
from ..session import SessionStatus


def _display(value: object) -> str:
    """Text shown for an item or feature value."""
    return json.dumps(value) if isinstance(value, (dict, list)) else str(value)


class WebInterface(SmartPluginWebIf):
    def __init__(self, webif_dir, plugin):
        """
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment(autoescape_templates=('index.html',))

    def get_status_data(self) -> dict:
        """Connection state, device identity and current values, as sent to the page."""
        session = self.plugin.session
        values = [
            {
                'name': name,
                'value': _display(value),
                'items': [item.property.path for item in self.plugin.get_items_for_mapping(name)],
            }
            for name, value in sorted(self.plugin.values.items())
            if name != 'map_svg'
        ]
        pending = session is not None and session.status == SessionStatus.VERIFICATION_REQUIRED
        return {
            'status': session.status.value if session else 'stopped',
            'verification_message': self.plugin.verification_message if pending else '',
            'status_text': session.status_text if session else '',
            'device': session.device_info if session else {},
            'values': values,
            'map_version': self._map_version(),
        }

    def _map_svg(self) -> bytes | None:
        """Current map as SVG document, ``None`` before the first one."""
        svg = self.plugin.values.get('map_svg')
        return svg.encode() if isinstance(svg, str) and svg else None

    def _map_version(self) -> str:
        """Checksum of the current map, empty without map; the page reloads the map when it changes."""
        svg = self._map_svg()
        return f'{zlib.crc32(svg):08x}' if svg is not None else ''

    def get_items_data(self) -> list[dict]:
        """Items connected to the plugin."""
        rows = []
        for item in sorted(self.plugin.get_item_list(), key=lambda i: i.property.path):
            feature = FEATURES[self.plugin.get_item_mapping(item)]
            rows.append(
                {
                    'path': item.property.path,
                    'feature': feature.name,
                    'type': item.type(),
                    'value': '(svg)' if feature.name == 'map_svg' else _display(item()),
                    'writable': feature.writable,
                    'last_update': item.property.last_update.strftime('%d.%m.%y %H:%M:%S'),
                    'last_change': item.property.last_change.strftime('%d.%m.%y %H:%M:%S'),
                }
            )
        return rows

    @cherrypy.expose
    def index(self):
        """
        Build index.html for cherrypy

        :return: contents of the template after beeing rendered
        """
        try:
            tmpl = self.tplenv.get_template('index.html')
        except Exception:
            self.logger.error("Template file 'index.html' not found")
            return
        return tmpl.render(
            p=self.plugin,
            w=self,
            item_count=len(self.plugin.get_item_list()),
            verification_required=SessionStatus.VERIFICATION_REQUIRED.value,
        )

    @cherrypy.expose
    def request_code(self):
        """Have Ecovacs e-mail a device verification code."""
        self.plugin.request_verification_code()
        raise cherrypy.HTTPRedirect('index')

    @cherrypy.expose
    def verify(self, code=''):
        """Complete the device verification with the e-mailed code."""
        self.plugin.verify_device(code)
        raise cherrypy.HTTPRedirect('index')

    @cherrypy.expose
    def map_svg(self, v=None):
        """
        Current map as SVG image.

        :param v: map version from the status data, makes the URL change with the map
        """
        svg = self._map_svg()
        if svg is None:
            raise cherrypy.HTTPError(404, 'No map available')
        cherrypy.response.headers['Content-Type'] = 'image/svg+xml'
        return svg

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: json with the data needed to update the web page.
        """
        result = self.get_status_data()
        result['items'] = self.get_items_data()
        try:
            return json.dumps(result)
        except Exception as e:
            self.logger.error(f'get_data_html exception: {e}')
        return '{}'
