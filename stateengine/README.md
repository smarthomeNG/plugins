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
### v1.7.3
* Implement new items for suspend_end (date_time and unix timestamp) as well as for suspend_start
* Update some functions to use shtime instead of sh lib

### v1.7.2
* Implemented changedyby and updatedby conditions
* Implemented regular expression possibility
* Improved/fixed handling of mixed list definitions

### v1.7.1
* Implemented item attributes and prefixes in plugin.yaml
* Option to set log level for each SE item individually

## Changelog
### v1.7.0
* Improved struct in plugin.yaml
* Improved suspend item evaluation
* Improved logging
* Added parameter instanteval for actions (see documentation)
* conditionset regex now uses re.fullmatch instead of re.match and therefore allows for a more precise regular expression
* Original caller now checks for the source of the item update instead of item change
* Web interface translation
* Eval result values are now cast correctly (type conversion based on the type of the relevant item)
* The wait loop to avoid contemporaneous runs of actions and/or states is replaced by a threading queue. Therefore simultaneous triggers (like automatic evaluation and a suspend item at the same time) are now taken into concideration correctly.

### v1.6.2
* Further fixes and improvements
* Webinterface including StateEngine visualization

### v1.6.1
* Some problem fixes
* Log improvements
* Docu improvements
* Leave actions can now be immediately triggered as soon as current state gets left (parameter: instant_leaveactions)
* Standard shng evals with relative items can now be used (e.g. sh...() + sh...test.property.last_change_age)

### v1.6.0
* Get relative items at startup for all se_item_* attributes
* Check for source_details in manual_exclude/include functions
* Improve logging and some code parts, better problem handling
* Allow list entries for conditions (original_caller, laststate, min/max, etc.)
* Functions can now be used by se_eval instead of stateengine_eval
* New functions: get_attributevalue, get_relative_item, get_relative_itemproperty
* Query current and last condition set is possible, also executing actions based on condition sets
* Implement a new special function to retrigger the state machine
* Defining an item to be changed by an action can now be done via eval functions (se_eval_bla: xyz)
* New function to add and remove entries from Items with type list
* New se_template feature to use templates in conditions or actions

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
