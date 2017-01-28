__author__ = 'pfischi'

import argparse
import time
import json
import sleekxmpp
from sleekxmpp.xmlstream import ET


class HarmonyClient(sleekxmpp.ClientXMPP):

    def __init__(self):
        user = "guest@x.com/gatorade"
        password = "guest"
        plugin_config = {
            'feature_mechanisms': {'unencrypted_plain': True},
        }
        super(HarmonyClient, self).__init__(user, password, plugin_config=plugin_config)

    def get_config(self, ip_address, port):
        self.connect(address=(ip_address, port), use_tls=False, use_ssl=False)
        self.process(block=False)

        duration = 30
        while not self.sessionstarted and duration != 0:
            time.sleep(0.1)
            duration -= 1
        if not self.sessionstarted:
            exit("Could not connect to Harmony Hub")

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
        config = json.loads(device_list)

        for device in config["device"]:
            model = "%s %s     device id: %s" % (device["manufacturer"], device["model"], device["id"])
            print("\n")
            print(model)
            print("-" * len(model))
            for group in device["controlGroup"]:
                print("\t%s" % group["name"])
                for function in group["function"]:
                    action = json.loads(function["action"])
                    print("\t\tcommand: %s" % action["command"])

        self.disconnect()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Get Harmony Hub activities',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    required_flags = parser.add_argument_group('required arguments')
    required_flags.add_argument('-i',
                                required=True,
                                help='IP Address of the Harmony device.')
    parser.add_argument('-p',
                        required=True,
                        default=5222,
                        type=int,
                        help='Network port that the Harmony is listening on.')
    args = parser.parse_args()
    hub = HarmonyClient()
    hub.get_config(args.i, args.p)
