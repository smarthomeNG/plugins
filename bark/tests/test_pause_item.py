"""Pause item handling of the bark plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestBarkPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.bark'
    CLASS_NAME = 'Bark'
    PARAMS = {'server_url': 'http://127.0.0.1:1', 'device_key': 'test-device-key'}
    MULTI_INSTANCE = True
