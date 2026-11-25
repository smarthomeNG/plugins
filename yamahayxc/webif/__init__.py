"""Web interface of the yamahayxc plugin: bound items, device information and struct advice."""

import json

import cherrypy

from lib.model.smartplugin import SmartPluginWebIf


class WebInterface(SmartPluginWebIf):
    """thin cherrypy layer over YamahaYXC.bound_items()/devices_overview()/query_device()"""

    def __init__(self, webif_dir, plugin):
        """
        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment(autoescape_templates=('index.html',))

    def _known_structs(self):
        """names of the plugin's item structs"""
        return set(self.plugin.metadata.itemstructs or {})

    @cherrypy.expose
    def index(self, reload=None):
        """render index.html"""
        return self.tplenv.get_template('index.html').render(p=self.plugin)

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """return the data of the items and devices tabs as JSON"""
        return json.dumps(
            {'items': self.plugin.bound_items(), 'devices': self.plugin.devices_overview(self._known_structs())},
            default=str,
        )

    @cherrypy.expose
    @cherrypy.tools.allow(methods=['POST'])
    def query_device(self, host=''):
        """query a device that is not configured and return its info and struct advice as JSON"""
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(self.plugin.query_device(host, self._known_structs()), default=str).encode()
