#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Web interface for the Matter plugin: pairing-code form (Phase 1),
#  endpoint/cluster discovery browser + copy-paste item-generator YAML
#  (Phase 2, see plugins/matter/discovery.py for why this is generated
#  text rather than shng's item_structs mechanism or a written file).
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

import cherrypy

from lib.model.smartplugin import SmartPluginWebIf


class WebInterface(SmartPluginWebIf):
    def __init__(self, webif_dir, plugin):
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, pairing_code=None, unlink_node_id=None):
        """
        Render the plugin's index page. A POST with `pairing_code` (via the
        page's own pairing form) triggers commissioning; a POST with
        `unlink_node_id` (via a per-row button on the devices table)
        decommissions that node - both happen before the page is
        (re-)rendered.
        """
        commission_error = None
        commission_result = None
        pairing_code = (pairing_code or '').strip()
        if pairing_code:
            try:
                commission_result = self.plugin.commission(pairing_code)
            except Exception as ex:
                self.logger.error(f'commissioning with code failed: {ex}')
                commission_error = str(ex)

        unlink_error = None
        if unlink_node_id:
            try:
                self.plugin.remove_node(int(unlink_node_id))
            except Exception as ex:
                self.logger.error(f'removing node {unlink_node_id} failed: {ex}')
                unlink_error = str(ex)

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(
            p=self.plugin,
            items=self.plugin.get_matter_items(),
            devices=self.plugin.get_node_summaries(),
            commission_result=commission_result,
            commission_error=commission_error,
            unlink_error=unlink_error,
            discovery_rows=self.plugin.get_discovery_rows(),
            item_generator_yaml=self.plugin.get_item_generator_yaml(),
        )
