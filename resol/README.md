# resol

SmarthomeNG-Plugin to read Resol datalogger: 
http://www.resol.de/index/produktdetail/kategorie/4/id/8/sprache/de
http://www.cosmo-info.de/fileadmin/user_upload/DL/COSMO-Solarregelung/COSMO-Multi.pdf

## Notes

This plugin is still __under development__! 
Many thanks to @MARKOV
https://knx-user-forum.de/forum/supportforen/smarthome-py/919242-neues-plugin-resol-vbus-cosmo-multi-solarthermie-logging/page2

## Prerequisite

The following python packages need to be installed on your system:
- none

```

### plugin.yaml

```
resol:
    class_name: Resol
    class_path: plugins.resol
    ip: 192.168.178.111    # ip of VBUS LAN
    cycle: 60
    port: 7053    # port of VBUS LAN usualy is 7053!
    password: xxx
```
More information of resol parameter and sources, see here: https://danielwippermann.github.io/resol-vbus/vbus-packets.html
Install Programm Resol Service Center to read offset und Bituse:
- They are provided in XML by RESOL as part of the RSC (Resol Service Center) download. Just download, install (on linux use wine, it will work) and get the required file for your installation from: {Install_dir}/eclipse/plugins/de.resol.servicecenter.vbus.resol_2.0.0/ -

### items.yaml

```yaml

resol:
    resol_source: '0x7821'
    resol_destination: '0x0010'
    resol_command: '0x0100'

    temperature_soll:
        type: num
        visu_acl: ro
        enforce_updates: 'true'
        resol_offset: 24
        resol_bituse: 7
        resol_factor:
         - '1.0'

    temperatur_2:
        type: num
        visu_acl: ro
        enforce_updates: 'true'
        resol_offset: 2
        resol_bituse: 15
        resol_factor: 
         - '0.1'
         - '25.6'

    waermemenge:
        type: num
        visu_acl: ro
        enforce_updates: 'true'
        #json_variable: 'Waermemenge'
        resol_offset: 28
        resol_bituse: 48
        resol_factor: 
         - '1'
         - '256'
         - '1000'
         - '256000'
         - '1000000'
         - '256000000'



```

Resol protocol:

Synch byte beween messages: 0xAA

Message:
    Byte    Content
    0-1     Destination
    2-3     Source
    4       Protocol Version,        0x10 -> "PV1", 0x20 -> "PV2", 0x30 -> "PV3"
    5-6     Command
    7-8     Frame count,             Example 0x1047-> 104 bytes

    


```
