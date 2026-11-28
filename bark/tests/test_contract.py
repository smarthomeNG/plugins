"""SmartPlugin contract tests."""

from plugins.bark import Bark
from tests.plugin_contract.base import BasePluginContractTest
from tests.plugin_contract.with_yaml import YamlPluginContractTest


class TestBarkContract(BasePluginContractTest, YamlPluginContractTest):
    PLUGIN_CLASS = Bark
    PLUGIN_INIT_PARAMS = {'server_url': 'http://127.0.0.1:1', 'device_key': 'test-device-key'}
    ITEM_ATTR_SETS = [{'bark_text': 'text'}, {'bark_values': [{True: 'text'}]}]
