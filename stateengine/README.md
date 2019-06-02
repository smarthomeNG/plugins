# StateEngine
Created by i-am-offline

## Description
Finite state machine plugin for smarthomeNG, previously known as AutoBlind

## Documentation
For info on the features and detailed setup see the [User Documentation](https://www.smarthomeng.de/user/plugins/stateengine/user_doc.html "Manual")
For info on how to configure the plugin see the [Configuration Documentation](https://www.smarthomeng.de/plugins_doc/config/stateengine "Configuration")

### smartvisu widget
Copy stateengine.example.html from the sv_widgets folder to your smartvisu/dropins/widgets folder and use the URL in your browser:
http://URL/index.php?page=widgets/stateengine.example

## Changelog
### v1.5.2
* Get relative items at startup for all se_item_* attributes
* Check for source_details in manual_exclude/include functions
* Improve logging and some code parts, better problem handling
* Allow list entries for conditions (original_caller, laststate, min/max, etc.)

### v1.5.1
* Include original 1.4.2 version in subfolder
* Some fixes

### v1.5.0
* Use new item property feature
* Fix exception if rules item does not exist

### v1.4.2
* Added and fixed documentation
* Added a smartvisu widget
* Added conversion script for easy change from autoblind to stateengine plugin

### v1.4.1
* Added to official develop repository
* Renamed to StateEngine
* Fixed compatibility of logic trigger for SmarthomeNG 1.4+
* Changed state condition evaluation to OrderedDict to keep original order
* Added additional option for manual item called "manual_on" to figure out if item WAS trigger by specific KNX GA
* Added Webinterface with documentation (german)

### v1.4.0
* Make compatible with SmarthomeNG 1.4+ (i-am-offline)

### before v1.4.0
* Constant improvements to infinite state machine (complete plugin development by i-am-offline)
