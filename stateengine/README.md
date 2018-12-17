# StateEngine
Created by i-am-offline

## Description
Finite state machine plugin for smarthomeNG, previously known as AutoBlind

## Support
If you require support, please raise an issue at GitHub: <https://github.com/i-am-offline/smarthome.plugin.autoblind>

## Documentation
The manual can be found on the official SmarthomeNG plugin documentation: <https://www.smarthomeng.de/user/plugins/stateengine/user_doc.html>.

A "Getting Started" blog entry can be found at the [SmarthomeNG Blog]
(https://www.smarthomeng.de/starting-with-state-machine-automation-autoblind-plugin)
## Configuration

### plugin.yaml
See the [manual at SmarthomeNG](https://www.smarthomeng.de/user/plugins/stateengine/user_doc.html)

### items.yaml
See the [manual at SmarthomeNG](https://www.smarthomeng.de/user/plugins/stateengine/user_doc.html)

## Changelog
### v1.4.2
* Added and fixed documentation (onkelandy)

### v1.4.1
* Added to official develop repository (onkelandy)
* Renamed to StateEngine (onkelandy)
* Fixed compatibility of logic trigger for SmarthomeNG 1.4+ (onkelandy)
* Changed state condition evaluation to OrderedDict to keep original order (onkelandy)
* Added additional option for manual item called "manual_on" to figure out if item WAS trigger by specific KNX GA (onkelandy)
* Added Webinterface with documentation (german)

### v1.4.0
* Make compatible with SmarthomeNG 1.4+ (i-am-offline)

### before v1.4.0
* Constant improvements to infinite state machine (complete plugin development by i-am-offline)
