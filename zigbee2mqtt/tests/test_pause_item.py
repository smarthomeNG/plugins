"""
The pause item stops and resumes the plugin; the plugin's own write-backs of it are ignored.
"""

from tests import common

from .base import Zigbee2MqttTestBase


class TestPauseItem(Zigbee2MqttTestBase):
    ITEMS_FILE = common.BASE + '/plugins/zigbee2mqtt/tests/test_items_pause.yaml'
    PARAMETERS = {'pause_item': 'pause'}

    def setUp(self):
        self.calls = []
        self.zigbee = self.plugin()
        self.pause = self.sh.return_item('pause')
        self.zigbee.stop = self._record_stop
        self.zigbee.run = self._record_run

    def _record_stop(self):
        self.calls.append('stop')
        self.zigbee.alive = False

    def _record_run(self):
        self.calls.append('run')
        self.zigbee.alive = True

    def test_item_is_registered_as_pause_item(self):
        self.assertIs(self.pause, self.zigbee._pause_item)

    def test_external_pause_stops_running_plugin(self):
        self.pause(True, 'test')

        self.zigbee.update_item(self.pause, caller='test')

        self.assertEqual(['stop'], self.calls)

    def test_external_resume_runs_stopped_plugin(self):
        self.zigbee.alive = False
        self.pause(False, 'test')

        self.zigbee.update_item(self.pause, caller='test')

        self.assertEqual(['run'], self.calls)

    def test_own_write_back_of_pause_is_ignored(self):
        self.pause(True, self.zigbee.get_fullname())
        self.zigbee.update_item(self.pause, caller=self.zigbee.get_fullname())
        self.zigbee.alive = False
        self.pause(False, self.zigbee.get_fullname())
        self.zigbee.update_item(self.pause, caller=self.zigbee.get_fullname())

        self.assertEqual([], self.calls)
