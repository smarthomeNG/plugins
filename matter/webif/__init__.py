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

import json

import cherrypy
import segno

from lib.model.smartplugin import SmartPluginWebIf


class WebInterface(SmartPluginWebIf):
    def __init__(self, webif_dir, plugin):
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(
        self,
        reload=None,
        pairing_code=None,
        unlink_node_id=None,
        share_node_id=None,
        fabrics_node_id=None,
        remove_fabric_node_id=None,
        remove_fabric_index=None,
        interview_node_id=None,
        alias_create_name=None,
        alias_create_node_id=None,
        alias_repoint_name=None,
        alias_repoint_node_id=None,
        alias_remove_name=None,
    ):
        """
        Render the plugin's index page. A POST with `pairing_code` (via the
        page's own pairing form) triggers commissioning; a POST with
        `unlink_node_id` (via a per-row button on the devices table)
        decommissions that node; `share_node_id` opens a fresh commissioning
        window on that node (for a second controller, e.g. Apple Home, to
        join); `fabrics_node_id` lists that node's current fabrics;
        `remove_fabric_node_id`+`remove_fabric_index` removes one;
        `interview_node_id` forces a fresh attribute read, replacing
        matter-server's cached copy the Devices/Discovery tabs otherwise
        show unchanged since the last commission/reconnect;
        `alias_create_name`+`alias_create_node_id` creates a new alias
        definition item; `alias_repoint_name`+`alias_repoint_node_id`
        changes which node_id an existing alias points to;
        `alias_remove_name` deletes an alias definition - all happen
        before the page is (re-)rendered.
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

        share_error = None
        share_result = None
        if share_node_id:
            try:
                share_result = {
                    'node_id': int(share_node_id),
                    **self.plugin.open_commissioning_window(int(share_node_id)),
                }
                share_result['qr_svg'] = self._qr_svg(share_result['setup_qr_code'])
            except Exception as ex:
                self.logger.error(f'opening commissioning window for node {share_node_id} failed: {ex}')
                share_error = str(ex)

        if remove_fabric_node_id and remove_fabric_index is not None:
            try:
                self.plugin.remove_matter_fabric(int(remove_fabric_node_id), int(remove_fabric_index))
            except Exception as ex:
                self.logger.error(
                    f'removing fabric {remove_fabric_index} from node {remove_fabric_node_id} failed: {ex}'
                )
            else:
                # Show the updated list right away rather than leaving the page
                # looking like nothing happened.
                fabrics_node_id = remove_fabric_node_id

        fabrics_error = None
        fabrics_result = None
        if fabrics_node_id:
            try:
                fabrics_result = {
                    'node_id': int(fabrics_node_id),
                    'fabrics': self.plugin.get_matter_fabrics(int(fabrics_node_id)),
                }
            except Exception as ex:
                self.logger.error(f'listing fabrics for node {fabrics_node_id} failed: {ex}')
                fabrics_error = str(ex)

        interview_error = None
        if interview_node_id:
            try:
                self.plugin.interview_node(int(interview_node_id))
            except Exception as ex:
                self.logger.error(f'interviewing node {interview_node_id} failed: {ex}')
                interview_error = str(ex)

        alias_error = None
        if alias_create_name and alias_create_node_id:
            try:
                self.plugin.create_alias(alias_create_name.strip(), int(alias_create_node_id))
            except Exception as ex:
                self.logger.error(f"creating alias '{alias_create_name}' failed: {ex}")
                alias_error = str(ex)
        elif alias_repoint_name and alias_repoint_node_id:
            try:
                self.plugin.repoint_alias(alias_repoint_name, int(alias_repoint_node_id))
            except Exception as ex:
                self.logger.error(f"repointing alias '{alias_repoint_name}' failed: {ex}")
                alias_error = str(ex)
        elif alias_remove_name:
            try:
                self.plugin.remove_alias(alias_remove_name)
            except Exception as ex:
                self.logger.error(f"removing alias '{alias_remove_name}' failed: {ex}")
                alias_error = str(ex)

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(
            p=self.plugin,
            items=self.plugin.get_matter_items(),
            devices=self.plugin.get_node_summaries(),
            commission_result=commission_result,
            commission_error=commission_error,
            unlink_error=unlink_error,
            share_result=share_result,
            share_error=share_error,
            fabrics_result=fabrics_result,
            fabrics_error=fabrics_error,
            interview_error=interview_error,
            aliases=self.plugin.get_aliases(),
            alias_error=alias_error,
            discovery_rows=self.plugin.get_discovery_rows(),
            item_generator_yaml=self.plugin.get_item_generator_yaml(),
        )

    @cherrypy.expose
    def get_data_html(self, dataSet=None, params=None):
        """
        Periodic live-update data for the standard shng webif auto-refresh
        mechanism (see doc/user/.../webinterface_automatic_update.rst) -
        item values (Items tab) and device availability (Devices tab,
        drives disabling Share/Fabrics/Neu einlesen while a device is
        unreachable, see index.html). Both reads are cheap: matter-server's
        own get_nodes() is a synchronous local cache read, no live query to
        the actual devices - safe at the default update_interval.
        """
        if dataSet is None:
            data = {
                'items': {item.property.path: item() for item in self.plugin.get_matter_items()},
                'devices': {device['node_id']: device['available'] for device in self.plugin.get_node_summaries()},
            }
            try:
                return json.dumps(data)
            except Exception as ex:
                self.logger.error(f'get_data_html exception: {ex}')
        return json.dumps({})

    def _qr_svg(self, text: str) -> str:
        """
        Inline-embeddable SVG for a Matter QR pairing code. segno - chosen
        over qrcode/pyqrcode after comparing actual output: segno's SVG for
        this exact kind of content is ~935 bytes (one combined <path>),
        qrcode's default SvgPathImage is ~4.7KB (one <path> per module) -
        and neither needs Pillow or any other dependency for SVG output.
        svg_inline() specifically omits the XML declaration/namespace that a
        standalone SVG file needs, producing markup meant to be embedded
        directly in HTML - exactly the Jinja `{{ ... | safe }}` use here.
        """
        return segno.make(text).svg_inline(scale=4, border=2)
