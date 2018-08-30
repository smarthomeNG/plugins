#AutoBlind

##Description
Finite state machine plugin for smarthomeNG

## Support
If you require support, please raise an issue at GitHub: <https://github.com/i-am-offline/smarthome.plugin.autoblind>

## Documentation
The manual can be found in the Wiki at GitHub: <https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki>.

## Configuration

### plugin.yaml
See the [manual at GitHub](https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki)

### items.yaml
See the [manual at GitHub](https://github.com/i-am-offline/smarthome.plugin.autoblind/wiki)

##Changelog
### v1.4.1
Added to official develop repository (onkelandy)
Fix compatibility of logic trigger for SmarthomeNG 1.4+ (onkelandy)
Changed state condition evaluation to OrderedDict to keep original order (onkelandy)
Added additional option for manual item called "manual_on" to figure out if item WAS trigger by specific KNX GA (onkelandy)

### v1.4.0
Make compatible with SmarthomeNG 1.4+ (i-am-offline)

### before v1.4.0
Constant improvements to infinite state machine (i-am-offline)
