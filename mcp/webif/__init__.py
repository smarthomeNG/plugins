"""Web interface of the mcp plugin: the clients, their elevation and the connection snippet."""

import hmac
import secrets

import cherrypy

from lib.model.smartplugin import SmartPluginWebIf


class WebInterface(SmartPluginWebIf):
    """Status page served by the http module under the plugin's short name."""

    def __init__(self, webif_dir, plugin):
        """
        :param webif_dir: directory of the web interface inside the plugin
        :param plugin: the running :class:`~plugins.mcp.Mcp` instance
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment(autoescape_templates=('index.html',))
        self._csrf_token = secrets.token_urlsafe(16)

    @cherrypy.expose
    def index(self):
        """Render the status page."""
        template = self.tplenv.get_template('index.html')
        return template.render(
            p=self.plugin,
            clients=self.plugin.client_status(),
            endpoint=self.plugin.endpoint_url(),
            item_count=len(self.plugin.get_item_path_list()),
            csrf=self._csrf_token,
        )

    @cherrypy.expose
    def elevate(self, client='', csrf=''):
        """Raise a client's ceiling for its configured time, then show the status page again."""
        self._check_post(csrf)
        try:
            self.plugin.elevate_client(client)
        except ValueError as e:
            raise cherrypy.HTTPError(400, str(e))
        raise cherrypy.HTTPRedirect('.')

    @cherrypy.expose
    def revoke(self, client='', csrf=''):
        """End a client's elevation, then show the status page again."""
        self._check_post(csrf)
        self.plugin.revoke_client(client)
        raise cherrypy.HTTPRedirect('.')

    def _check_post(self, csrf: str) -> None:
        """
        Accept only a POST that carries the page's token, so another web page cannot trigger it.

        :raises cherrypy.HTTPError: 405 for another method, 403 for a wrong token
        """
        if cherrypy.request.method != 'POST':
            raise cherrypy.HTTPError(405)
        if not hmac.compare_digest(str(csrf), self._csrf_token):
            raise cherrypy.HTTPError(403, 'invalid form token')
