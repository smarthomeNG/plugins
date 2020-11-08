#!/usr/bin/env python3
from soco import discover


def find_speakers():
    zones = discover(timeout=5)
    for zone in zones:
        info = zone.get_speaker_info(timeout=5)
        print()
        print("---------------------------------------------------------")
        print("{uid}".format(uid=zone.uid.lower()))
        print("\tip           : {ip}".format(ip=zone.ip_address))
        print("\tspeaker name : {name} ".format(name=zone.player_name))
        print("\tspeaker model: {model} ".format(model=info['model_name']))
    print("---------------------------------------------------------")
    print()

if __name__ == '__main__':
    find_speakers()
