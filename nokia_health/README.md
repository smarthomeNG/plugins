# Nokia Health

## Description

This plugin allows to retrieve data from the Nokia Health API (https://developer.health.nokia.com/api). Currently it 
only has support for "Withings WS-50 Smart Body Analyzer", a wifi capabale scale.

Support Thread: https://knx-user-forum.de/forum/supportforen/smarthome-py/1141179-nokia-health-plugin

## Requirements

This plugin requires lib nokia. You can install this lib with: 

```bash
sudo pip3 install nokia --upgrade
```

You have to register at https://account.health.nokia.com/partner/dashboard_oauth2.
The callback URL does not need to be reachable from the internet. You will have to start a small webserver for the oauth2
process.  The script can be found at https://github.com/orcasgit/python-nokia and is installed with the pypi package. 
```
nokia saveconfig --consumer-key [consumerkey] --consumer-secret [consumersecret] --callback-url [callbackurl] --config nokia.cfg
```
The script for me only worked, when running it on the machine where i used the browser for accessing the callback url.
Once the script finishs, the required data for the plugin will be written to the config file and can be used for the plugin.

In future i will provide the oauth2 process in the web interface of the plugin!

## Configuration

### plugin.yaml
```yaml
nokia_health:
    access_token: <your access token>
    token_expiry: <your token expiry>
    token_type: <token type>
    refresh_token: <your refresh token>
    user_id: <your user id>
    client_id: <your client id>
    consumer_secret: <your consumer secret>
    cycle: 300
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

    height:
        type: num
        visu_acl: ro
        nh_type@nokia_health: height

    bmi:
        type: num
        visu_acl: ro
        nh_type@nokia_health: bmi

    bmi_text:
        type: str
        visu_acl: ro
        nh_type@nokia_health: bmi_text

    fat_ratio:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_ratio

    fat_free_mass:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_free_mass

    fat_mass_weight:
        type: num
        visu_acl: ro
        nh_type@nokia_health: fat_mass_weight

    heart_pulse:
        type: num
        visu_acl: ro
        nh_type@nokia_health: heart_pulse
```

