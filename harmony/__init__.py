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

        self._pending_activities = []
        self._activities = {}
        self._logger = logging.getLogger(__name__)
        self._dummy_activity = None

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
        self._is_active_session = False
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
        self._is_active_session = False

    def _event_session_negotiated(self, event):
        self._logger.debug("Session started: {event}".format(event=event))
        self._is_active_session = True
        self._sh.scheduler.remove(self._scheduler_name)

    def _event_session_end(self, event):
        self._logger.error("Session stopped: {err}".format(err=event))
        self._is_active_session = False
        self._logger.info("Try to re-connect after {sec}".format(sec=self._reconnect_timeout))
        self._sh.scheduler.add(self._scheduler_name, self._connect, prio=3, cron=None, cycle=self._reconnect_timeout,
                               value=None, offset=None, next=None)

    def available_activities(self):
        activities = {}
        config = self._client.get_config()
        if "activity" in config:
            for action in config["activity"]:
                if "label" in action and "id" in action:
                    activities[int(action["id"])] = action["label"]
        self._logger.debug("Available Harmony Hub activities:")
        self._logger.debug(activities)
        return activities

    def run(self):
        if self._is_active_session:
            self._activities = self.available_activities()
            # if dummy activity was not set manually, search it
            if self._dummy_activity is None:
                found = False
                for id, activity in self._activities.items():
                    if activity.lower() == 'dummy':
                        self._dummy_activity = id
                        found = True
                        break
                if not found:
                    self._logger.warning("No dummy activity id was found. Set it up manually or call your dummy "
                                         "activity 'dummy'. Otherwise, the Harmony plugin won't working correctly.")
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
        has_harmony = False
        if self.has_iattr(item.conf, 'harmony_activity_0'):
            if not Utils.is_int(self.get_iattr_value(item.conf, 'harmony_activity_0')):
                return
            has_harmony = True

        if self.has_iattr(item.conf, 'harmony_activity_1'):
            if not Utils.is_int(self.get_iattr_value(item.conf, 'harmony_activity_1')):
                return
            has_harmony = True
        if has_harmony:
            return self.update_item
        return


    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller == "Harmony":
            return
        if item is None:
            return

        suffix = '1' if item() else '0'
        delay = 0

        activity = self.get_iattr_value(item.conf, 'harmony_activity_{suffix}'.format(suffix=suffix))
        if self.has_iattr(item.conf, 'harmony_delay_{suffix}'.format(suffix=suffix)):
            delay = self.get_iattr_value(item.conf, 'harmony_delay_{suffix}'.format(suffix=suffix))
            if not Utils.is_int(delay):
                self._logger.warning("attribute #harmony_delay_{suffix}' is not an integer, "
                                     "ignoring".format(suffix=suffix))
                delay = 0
            else:
                delay = int(delay)

        if not Utils.is_int(activity):
            self._logger.error("{item}: activity {activity} is not an integer.".format(item=item, activity=activity))
            return
        activity = int(activity)
        if activity not in self._activities:
            self._logger.warning("Activity '{activity}' not found in available activities.".format(activity=activity))
            self._logger.debug("Triggering '{val}'-activity UNKNOWN [{activity}] for item {item}".format(
                activity=activity, item=item, val=str(item()).upper()))
        else:
            self._logger.debug("Triggering '{val}'-activity {label} [{activity}] for item {item}".format(
                label=self._activities[activity], activity=activity, item=item, val=str(item()).upper()))

        if activity in self._pending_activities:
            self._logger.warning("Activity {activity} already pending, ignoring.")
            return

        self._pending_activities.append(activity)
        threading.Timer(delay, self.trigger_activity, [activity]).start()


    def trigger_activity(self, activity):
        self._logger.debug("triggering dummy activity")
        self._client.start_activity(self._dummy_activity)
        time.sleep(0.5)
        self._logger.debug("triggering activity {activity}".format(activity=activity))
        self._pending_activities.remove(activity)
        self._client.start_activity(str(activity))


class HarmonyClient(sleekxmpp.ClientXMPP):
    """An XMPP client for connecting to the Logitech Harmony."""

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
        """Retrieves the Harmony device configuration.
        Returns:
          A nested dictionary containing activities, devices, etc.
        """
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

    def get_current_activity(self):
        """Retrieves the current activity.
        Returns:
          A int with the activity ID.
        """
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = 'connect.logitech.com'
        action_cmd.attrib['mime'] = 'vnd.logitech.harmony/vnd.logitech.harmony.engine?getCurrentActivity'
        iq_cmd.set_payload(action_cmd)
        result = iq_cmd.send(block=True)
        payload = result.get_payload()
        assert len(payload) == 1
        action_cmd = payload[0]
        assert action_cmd.attrib['errorcode'] == '200'
        activity = action_cmd.text.split("=")
        return int(activity[1])

    def start_activity(self, activity_id):
        """Starts an activity.
        Args:
            activity_id: An int or string identifying the activity to start
        Returns:
          A nested dictionary containing activities, devices, etc.
        """
        iq_cmd = self.Iq()
        iq_cmd['type'] = 'get'
        action_cmd = ET.Element('oa')
        action_cmd.attrib['xmlns'] = 'connect.logitech.com'
        action_cmd.attrib['mime'] = 'harmony.engine?startactivity'
        cmd = 'activityId={id}:timestamp=0'.format(id=str(activity_id))
        action_cmd.text = cmd
        iq_cmd.set_payload(action_cmd)
        result = iq_cmd.send(block=True)
        payload = result.get_payload()
        assert len(payload) == 1
        return payload[0].text
