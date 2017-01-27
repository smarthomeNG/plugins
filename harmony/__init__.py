__author__ = 'pfischi'

import threading
import time
import json
import logging
from lib.model.smartplugin import SmartPlugin
import sleekxmpp
from sleekxmpp.xmlstream import ET
from lib.utils import Utils


class Harmony(SmartPlugin):
    PLUGIN_VERSION = "1.3.0.3"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, harmony_ip, harmony_port=5222, sleekxmpp_debug=False, harmony_dummy_activity=None):

        self._devices = {}
        self._threadLock = threading.Lock()
        self._logger = logging.getLogger(__name__)

        if Utils.is_int(harmony_dummy_activity):
            self._dummy_activity = harmony_dummy_activity
            self._logger.debug("Setting dummy activity to id {activity}".format(activity=self._dummy_activity))

        if Utils.to_bool(sleekxmpp_debug):
            self._logger.debug("debug output for sleekxmpp library")
            logging.getLogger("sleekxmpp").setLevel(logging.DEBUG)
        else:
            logging.getLogger("sleekxmpp").setLevel(logging.ERROR)

        self._sh = sh
        self._ip = harmony_ip
        self._port = harmony_port
        self._reconnect_timeout = 60
        self._scheduler_name = "harmony_reconnect"
        self._client = HarmonyClient()
        self._client.add_custom_handler('stream_negotiated', self._event_session_negotiated)
        self._client.add_custom_handler('socket_error', self._event_socket_error)
        self._client.add_custom_handler('session_end', self._event_session_end)
        self._client.whitespace_keepalive = True
        self._client.whitespace_keepalive_interval = 30
        self._connect()

    def _connect(self):
        self._client.connect_client(self._ip, self._port)

    def _event_socket_error(self, event):
        self._logger.error("Could not connect to Harmony Hub: {err}".format(err=event))
        self._logger.info("Try to re-connect after {sec}".format(sec=self._reconnect_timeout))
        self._sh.scheduler.add(self._scheduler_name, self._connect, prio=3, cron=None, cycle=self._reconnect_timeout,
                               value=None, offset=None, next=None)

    def _event_session_negotiated(self, event):
        self._logger.debug("Session started: {event}".format(event=event))
        self._sh.scheduler.remove(self._scheduler_name)

        # get device names and their ids
        config = self._client.get_config()

        if 'device' in config:
            for device in config['device']:
                if 'label' in device and 'id' in device:
                    self._devices[int(device['id'])] = device['label']

    def _event_session_end(self, event):
        self._logger.error("Session stopped: {err}".format(err=event))
        self._logger.info("Try to re-connect after {sec}".format(sec=self._reconnect_timeout))
        self._sh.scheduler.add(self._scheduler_name, self._connect, prio=3, cron=None, cycle=self._reconnect_timeout,
                               value=None, offset=None, next=None)

    def run(self):
        self.alive = True

    def stop(self):
        self._client.del_event_handler('session_negotiated', self._event_session_negotiated)
        self._client.del_event_handler('socket_error', self._event_socket_error)
        self._client.del_event_handler('session_end', self._event_session_end)
        self._client.disconnect(reconnect=False)
        self._client.abort()
        self.alive = False

    def parse_item(self, item):
        if item.type() != 'bool':
            return
        if self.has_iattr(item.conf, 'harmony_command_0') or self.has_iattr(item.conf, 'harmony_command_1'):
            return self.update_item
        return

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller == "Harmony":
            return
        if item is None:
            return

        if not self._threadLock.acquire(False):
            self._logger.warning("Couldn't trigger Harmony Hub command. Another command is already pending.")
            return
        else:
            try:
                suffix = '1' if item() else '0'

                command = self.get_iattr_value(item.conf, 'harmony_command_{suffix}'.format(suffix=suffix))
                if isinstance(command, str):
                    command = command.split('|')

                if command is None:
                    return
                for action in command:

                    delay = 0.2

                    action = action.split(":")
                    if len(action) < 2 or len(action) > 3:
                        self._logger.error("Invalid command {action} in item {item}".format(action=action, item=item))
                        return
                    # first item has to be an integer (device id)
                    if not Utils.is_int(action[0]):
                        self._logger.error("Invalid device id for action {action} in item {item}".format(action=action,
                                                                                                         item=item))
                        return

                    if len(action) == 3:
                        if not Utils.is_float(action[2]):
                            self._logger.error("Invalid delay for action {action} in item {item}".format(action=action,
                                                                                                         item=item))
                            return
                        else:
                            delay = float(action[2])
                            # max delay 60 sec
                            if delay > 60:
                                self._logger.error(
                                    "Invalid delay (>60sec) for action {action} in item {item}".format(action=action,
                                                                                                       item=item))
                                return

                    label = "unknown"
                    if int(action[0]) in self._devices:
                        label = self._devices[int(action[0])]

                    self._logger.debug("trigger command {command} for device '{label}'".format(command=command,
                                                                                             label=label))
                    self._client.send_command(action[0], action[1])
                    time.sleep(delay)
            finally:
                self._threadLock.release()


class HarmonyClient(sleekxmpp.ClientXMPP):

    def __init__(self):
        user = "guest@x.com/gatorade"
        password = "guest"
        plugin_config = {
            'feature_mechanisms': {'unencrypted_plain': True},
        }
        super(HarmonyClient, self).__init__(user, password, plugin_config=plugin_config)

    def connect_client(self, ip_address, port):

        self.connect(address=(ip_address, port), use_tls=False, use_ssl=False)
        self.process(block=False)

        duration = 30
        while not self.sessionstarted and duration != 0:
            time.sleep(0.1)
            duration -= 1
        if self.sessionstarted:
            return True
        return False

    def add_custom_handler(self, event_name, event_handler):
        self.add_event_handler(event_name, event_handler)

    def get_config(self):
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = "connect.logitech.com"
        action_cmd.attrib['mime'] = "vnd.logitech.harmony/vnd.logitech.harmony.engine?config"
        iq_cmd.set_payload(action_cmd)
        result = iq_cmd.send(block=True)
        payload = result.get_payload()
        assert len(payload) == 1
        action_cmd = payload[0]
        assert action_cmd.attrib['errorcode'] == '200'
        device_list = action_cmd.text
        return json.loads(device_list)

    def send_command(self, device, command):
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        iq_cmd['id'] = '5e518d07-bcc2-4634-ba3d-c20f338d8927-2'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = 'connect.logitech.com'
        action_cmd.attrib['mime'] = (
            'vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction')
        action_cmd.text = 'action={"type"::"IRCommand","deviceId"::"' + device + '","command"::"' + command + \
                          '"}:status=press'
        iq_cmd.set_payload(action_cmd)
        iq_cmd.send(block=False)

        action_cmd.attrib['mime'] = (
            'vnd.logitech.harmony/vnd.logitech.harmony.engine?holdAction')
        action_cmd.text = 'action={"type"::"IRCommand","deviceId"::"' + device + '","command"::"' + command + \
                          '"}:status=release'
        iq_cmd.set_payload(action_cmd)
        result = iq_cmd.send(block=False)
        return result