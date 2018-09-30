#StateEngine
Created by i-am-offline

##Description
Finite state machine plugin for smarthomeNG, previously known as AutoBlind

## Support
If you require support, please raise an issue at GitHub: <https://github.com/i-am-offline/smarthome.plugin.autoblind>

## Documentation
The manual can be found in the Wiki at GitHub: <https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki>.

## Configuration

To update from autoblind to stateengine use the script "autoblind_update.sh" in the plugin folder!

### plugin.yaml
See the [manual at GitHub](https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki)

### items.yaml
See the [manual at GitHub](https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki)

##Changelog
### v1.4.1
Added to official develop repository
Renamed to StateEngine
Added script to change autoblind entries to stateengine entries in items, logics and cache
Fix compatibility of logic trigger for SmarthomeNG 1.4+
Changed state condition evaluation to OrderedDict to keep original order
Added additional option for manual item called "manual_on" to figure out if item WAS trigger by specific KNX GA

### v1.4.0
Make compatible with SmarthomeNG 1.4+ (i-am-offline)

### before v1.4.0
Constant improvements to infinite state machine (complete plugin development by i-am-offline)
