import os
from types import SimpleNamespace

import cherrypy
import pytest
from cherrypy.lib.httputil import Host
from jinja2 import Environment, FileSystemLoader

import lib
from plugins.mcp.webif import WebInterface

from .test_plugin import make_plugin

PLUGIN_TEMPLATES = os.path.join(os.path.dirname(__file__), '..', 'webif', 'templates')
GLOBAL_TEMPLATES = os.path.join(os.path.dirname(lib.__file__), '..', 'modules', 'http', 'webif', 'gtemplates')
CLIENT_TOKEN = 'desktop-token-0123456789'
CLIENTS = {
    'desktop': {
        'token': CLIENT_TOKEN,
        'default_access': 'ro',
        'expose': ['system'],
        'write_paths': ['lights.*'],
        'elevate_to': 'rw',
        'elevate_minutes': 5,
    },
    'viewer': {'token': 'viewer-token-0123456789'},
}


@pytest.fixture
def plugin():
    plugin = make_plugin(clients=CLIENTS)
    yield plugin
    plugin.stop()


@pytest.fixture
def webif(plugin):
    """A WebInterface on the real plugin, without the http module that would wire up its template environment."""
    webif = WebInterface.__new__(WebInterface)
    webif.plugin = plugin
    webif.logger = plugin.logger
    plugin._plgtype = 'gateway'
    environment = Environment(
        loader=FileSystemLoader([PLUGIN_TEMPLATES, GLOBAL_TEMPLATES]), autoescape=lambda name: name == 'index.html'
    )
    environment.globals.update(_=lambda text, *_args: text, isfile=lambda path: False, len=len, dark_mode_default=False)
    webif.tplenv = environment
    webif._csrf_token = 'page-token'
    return webif


def post(monkeypatch, method='POST'):
    """Make the running cherrypy request a request of the given method to the plugin's page."""
    request = cherrypy._cprequest.Request(Host('127.0.0.1', 8383), Host('127.0.0.1', 5555))
    request.method = method
    request.base = 'http://127.0.0.1:8383'
    request.path_info = '/elevate'
    setattr(request, 'app', SimpleNamespace(script_name='/mcp'))
    monkeypatch.setattr(cherrypy.serving, 'request', request, raising=False)


class TestPage:
    def test_the_page_lists_every_client_with_its_settings(self, webif):
        html = webif.index()
        for text in ('local', 'desktop', 'viewer', 'lights.*', 'system', 'http://127.0.0.1:0/mcp'):
            assert text in html

    def test_the_page_never_shows_a_token(self, webif, plugin):
        assert CLIENT_TOKEN not in webif.index()
        assert plugin._token not in webif.index()

    def test_only_a_client_that_can_be_elevated_gets_a_button(self, webif):
        html = webif.index()
        assert html.count('action="elevate"') == 1
        assert 'rw für 5 min' in html

    def test_a_running_elevation_shows_its_remaining_time_and_a_revoke_button(self, webif, plugin):
        plugin.elevate_client('desktop')
        html = webif.index()
        assert 'action="revoke"' in html
        assert 'action="elevate"' not in html
        assert 'noch 5 min' in html

    def test_names_from_the_configuration_are_escaped(self, webif, plugin, monkeypatch):
        row = {**plugin.client_status()[1], 'name': '<script>alert(1)</script>'}
        monkeypatch.setattr(plugin, 'client_status', lambda: [row])
        html = webif.index()
        assert '<script>alert(1)' not in html
        assert '&lt;script&gt;' in html


class TestActions:
    def test_elevating_with_the_page_token_raises_the_client(self, webif, plugin, monkeypatch):
        post(monkeypatch)
        with pytest.raises(cherrypy.HTTPRedirect):
            webif.elevate(client='desktop', csrf='page-token')
        assert plugin._clients.entitlement_for('desktop').max_access == 'rw'

    def test_revoking_ends_the_elevation(self, webif, plugin, monkeypatch):
        post(monkeypatch)
        plugin.elevate_client('desktop')
        with pytest.raises(cherrypy.HTTPRedirect):
            webif.revoke(client='desktop', csrf='page-token')
        assert plugin._clients.entitlement_for('desktop').max_access == 'ro'

    @pytest.mark.parametrize('csrf', ['', 'wrong'])
    def test_a_wrong_token_is_refused_and_changes_nothing(self, webif, plugin, monkeypatch, csrf):
        post(monkeypatch)
        with pytest.raises(cherrypy.HTTPError) as error:
            webif.elevate(client='desktop', csrf=csrf)
        assert error.value.status == 403
        assert plugin._clients.entitlement_for('desktop').max_access == 'ro'

    def test_a_get_request_is_refused(self, webif, plugin, monkeypatch):
        post(monkeypatch, method='GET')
        with pytest.raises(cherrypy.HTTPError) as error:
            webif.elevate(client='desktop', csrf='page-token')
        assert error.value.status == 405

    @pytest.mark.parametrize('client', ['local', 'nobody', 'viewer'])
    def test_a_client_that_cannot_be_elevated_is_a_bad_request(self, webif, monkeypatch, client):
        post(monkeypatch)
        with pytest.raises(cherrypy.HTTPError) as error:
            webif.elevate(client=client, csrf='page-token')
        assert error.value.status == 400
