"""Links from the web interface into shngadmin are relative to the server the web interface was opened on."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from plugins.database import Database


def adminui_path(admin_module):
    plugin = Database.__new__(Database)
    modules = SimpleNamespace(get_module=lambda name: admin_module if name == 'admin' else None)
    with patch('plugins.database.Modules.get_instance', return_value=modules):
        return plugin.adminui_url_root()


class TestAdminuiLink(unittest.TestCase):
    def test_path_of_the_admin_interface(self):
        admin = SimpleNamespace(url_path='/admin', url_root='http://192.0.2.1:8383/admin')

        self.assertEqual('/admin', adminui_path(admin))

    def test_admin_interface_at_the_server_root(self):
        self.assertEqual('', adminui_path(SimpleNamespace(url_path='', url_root='http://192.0.2.1:8383')))

    def test_without_admin_module(self):
        self.assertIsNone(adminui_path(None))
