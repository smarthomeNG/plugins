# Nokia Health

Version 0.1

## Description

This plugin allows to retrieve data from the Nokia Health API (https://developer.health.nokia.com/api). Currently it 
only has support for Withings WS-50 Smart Body Analyzer, a wifi capabale scale.

## Requirements

This plugin requires lib requests. You can install this lib with: 

```bash
sudo pip3 install requests --upgrade
```

You have to go through the registration and oauth process on https://developer.health.nokia.com/api.
You will need a temporary callback url!.
In the end after step 4, you see the 4 variables needed for the plugin to work in the URL the page is forwarding you to.

## Configuration

### plugin.yaml
```yaml
nokia_health:
    class_name: NokiaHealth
    class_path: plugins.nokia_health
    oauth_consumer_key: <your_oauth_consumer_key>
    oauth_nonce: <your_oauth_nonce>
    oauth_signature: <your_oauth_signature>
    oauth_token: <your_oath_token>
    userid: <your_userid>
    instance: nokia_health
```

### items.yaml

Please be aware that there are dependencies for the values. E.g. the body measurement index will only be calculated if a
height exists. From what i saw so far is, that the height is transmitted only one time, the first time the scale 
communicates with the Nokia servers. In case you miss it, set the item value manually!

```yaml
body:

    weight:
        type: num
        visu_acl: ro
        nh_type@nokia_health: weight
        database@mysqldb: init

    height:
        type: num
        visu_acl: ro
        nh_type@nokia_health: height
        database@mysqldb: init

    bmi:
        type: num
        visu_acl: ro
        nh_type@nokia_health: bmi
        database@mysqldb: init

    fat_ratio:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_ratio
        database@mysqldb: init

    fat_free_mass:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_free_mass
        database@mysqldb: init

    fat_mass_weight:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_mass_weight
        database@mysqldb: init

    heart_pulse:
        type: num
        visu_acl: ro
        nh_type@nokia_health: heart_pulse
        database@mysqldb: init

    last_update:
        type: num
        visu_acl: ro
        nh_type@nokia_health: last_update
        database@mysqldb: init
```

## Functions

### get_last_measure():
Gets the last measurement values.