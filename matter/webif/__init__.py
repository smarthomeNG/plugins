#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Web interface for the Matter plugin: pairing-code form, endpoint/cluster
#  discovery browser, and a per-device "suggest an item" action producing
#  copy-paste struct-reference YAML (see server/discovery.py's own
#  docstring for why this suggests plugin.yaml item_structs references
#  rather than a full per-attribute dump or a written file).
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

        # Post-Redirect-Get support: index() renders directly after a POST
        # action, so the last request in the browser's history was a POST -
        # pressing F5 asks to resubmit it (e.g. re-commissioning a device),
        # which is essentially always the wrong thing to do. Every action's
        # result is stashed here and index() redirects to itself afterward,
        # so the browser's last request becomes a plain GET; the redirected-to
        # GET shows the stashed result once, then clears it - a minimal
        # hand-rolled flash message, not CherryPy sessions (unused anywhere
        # else in shng - not worth adding for one plugin). Single shared slot,
        # not per-session: fine for a single-admin local tool, would show the
        # wrong tab's result if two browser tabs both submitted actions around
        # the same time - an accepted, narrow edge case, not engineered around.
        self._flash: dict | None = None

    @cherrypy.expose
    def index(
        self,
        view=None,
        reload=None,
        pairing_code=None,
        unlink_node_id=None,
        share_node_id=None,
        fabrics_node_id=None,
        remove_fabric_node_id=None,
        remove_fabric_index=None,
        interview_node_id=None,
        ip_addresses_node_id=None,
        alias_create_name=None,
        alias_create_node_id=None,
        alias_repoint_name=None,
        alias_repoint_node_id=None,
        alias_remove_name=None,
        open_bridge_window=None,
        remove_bridge_fabric_index=None,
        suggest_item_node_id=None,
    ):
        """
        Render the plugin's index page - the server-role view by default, or
        the separate bridge-role view when `view=bridge` (see index.html's
        "Bridge" header button and bridge.html's own "Server" button back -
        a distinct top-level page, not another tab, so the bridge role isn't
        structurally capped to competing with the server role's 6 tabs for
        space; same mechanism the `database` plugin uses for its item-detail
        drill-down). A POST with `pairing_code` (via the page's own pairing
        form) triggers commissioning; a POST with `unlink_node_id` (via a
        per-row button on the devices table) decommissions that node;
        `share_node_id` opens a fresh commissioning window on that node (for
        a second controller, e.g. Apple Home, to join); `fabrics_node_id`
        lists that node's current fabrics; `remove_fabric_node_id`+
        `remove_fabric_index` removes one; `interview_node_id` forces a
        fresh attribute read, replacing matter-server's cached copy the
        Devices/Discovery tabs otherwise show unchanged since the last
        commission/reconnect; `ip_addresses_node_id` looks up which address
        (and network interface) that node's operational session is
        currently using - on-demand, not shown by default, since it's a
        diagnostic for a specific misbehaving device, not steady-state info
        (see client.py's get_node_ip_addresses()); `alias_create_name`+
        `alias_create_node_id` creates a new alias definition item;
        `alias_repoint_name`+`alias_repoint_node_id` changes which node_id
        an existing alias points to; `alias_remove_name` deletes an alias
        definition; `suggest_item_node_id` computes the copy-paste item
        suggestion for that node (see server/discovery.py's
        generate_suggested_item()); `open_bridge_window` reopens the bridge's own basic
        commissioning window (view=bridge only); `remove_bridge_fabric_index`
        removes one controller from the bridge (view=bridge only) - all
        happen before the page is (re-)rendered.

        A POST (any action param set) redirects to this same page afterward
        instead of rendering directly - see __init__'s self._flash comment
        for why. Plain GETs (including the one the browser makes right after
        that redirect) fall through to the render at the bottom, showing
        whatever the redirect just stashed - once. A bridge-view POST
        redirects to `index?view=bridge`, not bare `index`, so the browser
        lands back on the bridge view, not the server view.
        """
        if cherrypy.request.method != 'POST':
            flash = self._flash or {}
            self._flash = None
            if view == 'bridge':
                return self._render_bridge(flash)
            return self._render(flash)

        if view == 'bridge':
            open_bridge_window_error = None
            if open_bridge_window:
                try:
                    self.plugin.open_bridge_commissioning_window()
                except Exception as ex:
                    self.logger.error(f'opening bridge commissioning window failed: {ex}')
                    open_bridge_window_error = str(ex)

            remove_bridge_fabric_error = None
            if remove_bridge_fabric_index is not None:
                try:
                    self.plugin.remove_bridge_fabric(int(remove_bridge_fabric_index))
                except Exception as ex:
                    self.logger.error(f'removing bridge fabric {remove_bridge_fabric_index} failed: {ex}')
                    remove_bridge_fabric_error = str(ex)

            self._flash = {
                'open_bridge_window_error': open_bridge_window_error,
                'remove_bridge_fabric_error': remove_bridge_fabric_error,
            }
            raise cherrypy.HTTPRedirect('index?view=bridge')

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

        ip_addresses_error = None
        ip_addresses_result = None
        if ip_addresses_node_id:
            try:
                ip_addresses_result = {
                    'node_id': int(ip_addresses_node_id),
                    'addresses': self.plugin.get_node_ip_addresses(int(ip_addresses_node_id)),
                }
            except Exception as ex:
                self.logger.error(f'getting IP addresses for node {ip_addresses_node_id} failed: {ex}')
                ip_addresses_error = str(ex)

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

        suggested_item_error = None
        suggested_item_result = None
        if suggest_item_node_id:
            try:
                suggested_item_result = {
                    'node_id': int(suggest_item_node_id),
                    'yaml': self.plugin.get_suggested_item_yaml(int(suggest_item_node_id)),
                }
            except Exception as ex:
                self.logger.error(f'suggesting an item for node {suggest_item_node_id} failed: {ex}')
                suggested_item_error = str(ex)

        self._flash = {
            'commission_result': commission_result,
            'commission_error': commission_error,
            'unlink_error': unlink_error,
            'share_result': share_result,
            'share_error': share_error,
            'fabrics_result': fabrics_result,
            'fabrics_error': fabrics_error,
            'interview_error': interview_error,
            'ip_addresses_result': ip_addresses_result,
            'ip_addresses_error': ip_addresses_error,
            'alias_error': alias_error,
            'suggested_item_result': suggested_item_result,
            'suggested_item_error': suggested_item_error,
        }
        raise cherrypy.HTTPRedirect('index')

    def _render(self, flash: dict):
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(
            p=self.plugin,
            items=self.plugin.get_matter_items(),
            devices=self.plugin.get_node_summaries(),
            commission_result=flash.get('commission_result'),
            commission_error=flash.get('commission_error'),
            unlink_error=flash.get('unlink_error'),
            share_result=flash.get('share_result'),
            share_error=flash.get('share_error'),
            fabrics_result=flash.get('fabrics_result'),
            fabrics_error=flash.get('fabrics_error'),
            interview_error=flash.get('interview_error'),
            ip_addresses_result=flash.get('ip_addresses_result'),
            ip_addresses_error=flash.get('ip_addresses_error'),
            aliases=self.plugin.get_aliases(),
            alias_error=flash.get('alias_error'),
            discovery_rows=self.plugin.get_discovery_rows(),
            suggested_item_result=flash.get('suggested_item_result'),
            suggested_item_error=flash.get('suggested_item_error'),
        )

    def _render_bridge(self, flash: dict):
        bridge_status = self.plugin.get_bridge_status()
        # Computed here, not in the template, for the same reason share_result's qr_svg
        # already is - _qr_svg() needs self, not available as a bare Jinja filter.
        bridge_qr_svg = self._qr_svg(bridge_status['qr_pairing_code']) if bridge_status.get('available') else None
        tmpl = self.tplenv.get_template('bridge.html')
        return tmpl.render(
            p=self.plugin,
            bridge_status=bridge_status,
            bridge_qr_svg=bridge_qr_svg,
            bridge_fabrics=self.plugin.get_bridge_fabrics(),
            bridge_items=self.plugin.get_bridge_items(),
            open_bridge_window_error=flash.get('open_bridge_window_error'),
            remove_bridge_fabric_error=flash.get('remove_bridge_fabric_error'),
        )

    @cherrypy.expose
    def get_data_html(self, dataSet=None, params=None):
        """
        Periodic live-update data for the standard shng webif auto-refresh
        mechanism (see doc/user/.../webinterface_automatic_update.rst) -
        item values (Items tab), device availability (Devices tab, drives
        disabling Share/Fabrics/Neu einlesen while a device is unreachable,
        see index.html), and raw discovery values (Discovery tab). All three
        are cheap: matter-server's own get_nodes() is a synchronous local
        cache read, no live query to the actual devices - safe at the
        default update_interval. 'discovery' is keyed the same way the
        Discovery table's own row IDs are built (index.html), node_id and
        path joined with '_' - path alone ("endpoint/cluster/attribute")
        isn't unique across nodes, only per-node.

        Discovery values only change when a device reports a new value on
        its own (matter-server pushes those into its cache asynchronously) or
        after a manual "Neu einlesen" - this poll never triggers a fresh
        device read itself, same "cached, not live-queried" contract the
        Discovery tab's own caption already states. Payload size grows with
        total known attribute count across every commissioned node, unlike
        items/devices which stay proportional to configured items/devices -
        fine at today's device counts, worth revisiting if that ever becomes
        large enough to matter.
        """
        if dataSet is None:
            data = {
                'items': {item.property.path: item() for item in self.plugin.get_matter_items()},
                'devices': {device['node_id']: device['available'] for device in self.plugin.get_node_summaries()},
                'discovery': {
                    f'{row["node_id"]}_{row["path"]}': row['value'] for row in self.plugin.get_discovery_rows()
                },
                # Drained once, not re-sent on the next poll - a commission_with_code answer
                # that arrived after this client's own timeout already gave up on it (see
                # server/client.py's _timed_out/on_late_result). Almost always empty.
                'late_commission_results': self.plugin.get_late_commission_results(),
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
