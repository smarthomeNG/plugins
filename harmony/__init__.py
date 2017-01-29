import sched
import time
import json
import logging
from lib.model.smartplugin import SmartPlugin
import sleekxmpp
from sleekxmpp.xmlstream import ET
from lib.utils import Utils


class Harmony(SmartPlugin):
    PLUGIN_VERSION = "1.3.0.4"
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh, harmony_ip, harmony_port=5222, sleekxmpp_debug=False):
        self._is_active = False
        self._get_config_reconnect = 300  # scheduler time to get config from Hub and for possible reconnect
        self._scheduler = sched.scheduler(time.time, time.sleep)
        self._default_delay = 0.2
        self._devices = {}
        self._activities = {}
        self._dummy_activity = None
        self._logger = logging.getLogger(__name__)
        self._current_activity_id_items = []
        self._current_activity_name_items = []

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

    def _connect(self):
        self._client.connect_client(self._ip, self._port)

    def _event_socket_error(self, event):
        self._logger.error("Could not connect to Harmony Hub: {err}".format(err=event))
        self._logger.info("Try to re-connect after {sec}".format(sec=self._reconnect_timeout))
        self._sh.scheduler.add(self._scheduler_name, self._connect, prio=3, cron=None, cycle=self._reconnect_timeout,
                               value=None, offset=None, next=None)
        self._is_active = False

    def _event_session_negotiated(self, event):
        self._is_active = True
        self._logger.debug("Session started: {event}".format(event=event))
        self._sh.scheduler.remove(self._scheduler_name)
        self._get_config()

    def _event_session_end(self, event):
        self._logger.error("Session stopped: {err}".format(err=event))
        self._logger.info("Try to re-connect after {sec}".format(sec=self._reconnect_timeout))
        self._sh.scheduler.add(self._scheduler_name, self._connect, prio=3, cron=None, cycle=self._reconnect_timeout,
                               value=None, offset=None, next=None)
        self._is_active = False

    def _send_command(self, device, command):
        label = "unknown"
        if device in self._devices:
            label = self._devices[device]
        self._logger.debug("Trigger '{command}' for device '{label}'".format(command=command, label=label))
        self._client.send_command(device, command)

    def _get_config(self):
        if self._is_active:
            config = self._client.get_config()

            if 'activity' in config:
                for activity in config['activity']:
                    label = activity["label"].lower()
                    if label == "dummy":
                        self._dummy_activity = int(activity["id"])
                    self._activities[int(activity["id"])] = activity["label"]

            if 'device' in config:
                for device in config['device']:
                    if 'label' in device and 'id' in device:
                        self._devices[int(device['id'])] = device['label']

            self._set_current_activity()
        else:
            self._logger.debug("Trying to reconnect to Harmony Hub.")
            self._connect()

    def _set_current_activity(self):
        if self._is_active:
            current_activity = self._client.get_current_activity()
            activity_name = "unknown"
            activity_id = 0

            if current_activity is not None:
                activity_id = current_activity
                if current_activity in self._activities:
                    activity_name = self._activities[current_activity]

            for item in self._current_activity_id_items:
                item(activity_id)
            for item in self._current_activity_name_items:
                item(activity_name)

    def _send_activity(self, activity):
        label = "unknown"

        if activity in self._activities:
            label = self._activities[activity]

        if self._dummy_activity is not None:
            self._logger.debug("Trigger dummy activity")
            self._client.start_activity(self._dummy_activity)
            time.sleep(0.3)

        self._logger.debug("Trigger activity '{label}' with id '{activity}'".format(label=label, activity=activity))
        if self._client.start_activity(activity):
            self._set_current_activity()

    def run(self):
        self._connect()
        self._sh.scheduler.add("harmony_config", self._get_config, prio=3, cron=None, cycle=self._get_config_reconnect,
                               value=None, offset=None, next=None)
        self.alive = True

    def stop(self):
        self._client.del_event_handler('session_negotiated', self._event_session_negotiated)
        self._client.del_event_handler('socket_error', self._event_socket_error)
        self._client.del_event_handler('session_end', self._event_session_end)
        self._client.disconnect(reconnect=False)
        self._client.abort()
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'harmony_command_0') or self.has_iattr(item.conf, 'harmony_command_1'):
            return self.update_item

        if self.has_iattr(item.conf, 'harmony_item'):
            value = self.get_iattr_value(item.conf, 'harmony_item')
            if value.lower() == "current_activity_id":
                # check item is type int
                if item.type() != 'num':
                    self._logger.warning("The harmony item 'current_activity_id' has to be a 'num' type. "
                                         "Ignoring item.")
                    return
                self._current_activity_id_items.append(item)

            if value.lower() == "current_activity_name":
                # check item is type str
                if item.type() != 'str':
                    self._logger.warning("The harmony item 'current_activity_name' has to be a 'str' type. "
                                         "Ignoring item.")
                    return
                self._current_activity_name_items.append(item)
        return

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller == "Harmony":
            return
        if item is None:
            return

        suffix = '1' if item() else '0'

        command = self.get_iattr_value(item.conf, 'harmony_command_{suffix}'.format(suffix=suffix))
        if isinstance(command, str):
            command = command.split('|')

        if command is None:
            return

        absolute_delay = 0
        scheduler = sched.scheduler(time.time, time.sleep)

        for action in command:

            delay = self._default_delay

            action = action.split(":")
            if len(action) < 2 or len(action) > 3:
                self._logger.error("Invalid command {action} in item {item}".format(action=action, item=item))
                return
            # first item has to be an integer (device id) or an 'a' as an alias for activity
            if not Utils.is_int(action[0]) and str(action[0]).lower() != 'a' and str(action[0]).lower() != 'activity':
                self._logger.error("Invalid device id or 'activity' alias for action {action} in item {item}".
                                   format(action=action, item=item))
                continue

            is_activity = True if (str(action[0]).lower() == 'a' or str(action[0]).lower() == 'activity') else False

            action_label = "activity" if is_activity else "command"

            if len(action) == 3:
                if not Utils.is_float(action[2]):
                    self._logger.error("Invalid delay for action {action_label} in item {item}".
                                       format(action_label=action_label, item=item))
                    return
                delay = float(action[2])

            absolute_delay += delay

            if is_activity:
                self._logger.debug("activity {activity} scheduled".format(activity=action[1]))
                scheduler.enter(absolute_delay, 1, self._send_activity, (action[1], ))
            else:
                self._logger.debug("command {command} scheduled".format(command=action[1]))
                scheduler.enter(absolute_delay, 1, self._send_command, (int(action[0]), action[1]))

        scheduler.run()


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

    def get_current_activity(self):
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = 'connect.logitech.com'
        action_cmd.attrib['mime'] = (
            'vnd.logitech.harmony/vnd.logitech.harmony.engine?getCurrentActivity')
        iq_cmd.set_payload(action_cmd)
        try:
            result = iq_cmd.send(block=True)
        except Exception:
            result = iq_cmd.send(block=True)
        payload = result.get_payload()
        assert len(payload) == 1
        action_cmd = payload[0]
        assert action_cmd.attrib['errorcode'] == '200'
        activity = action_cmd.text.split("=")
        return int(activity[1])

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
        device = str(device)
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

    def start_activity(self, activity_id):
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = 'connect.logitech.com'
        action_cmd.attrib['mime'] = ('harmony.engine?startactivity')
        cmd = 'activityId=' + str(activity_id) + ':timestamp=0'
        action_cmd.text = cmd
        iq_cmd.set_payload(action_cmd)
        try:
            result = iq_cmd.send(block=True)
        except Exception:
            result = iq_cmd.send(block=True)
        payload = result.get_payload()
        assert len(payload) == 1
        action_cmd = payload[0]
        if action_cmd.text is None:
            return True
        else:
            return False