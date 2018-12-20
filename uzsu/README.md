# UZSU

Provides universal time switches for items (German: *U*niverselle *Z*eit*s*chalt *U*hr)

## Requirements

Calculating of sunset/sunrise in triggers, requires installation of ephem (which should already be part of core)

Calculating interpolation requires installation of scipy. Install with:
pip3 install scipy

Update your Python packages first (but make sure they still meet the requirements for smarthomeng)!

On Raspberry debian stretch you also have to run:
sudo apt install libatlas-base-dev

If that does not work you can use:
sudo apt update
sudo apt install -y python3-scipy

## Changelog

### v1.5.3
* Remove useless dictionary parts from uzsu items (to make double entry check work better)
* Added SciPy as a requirements
* Added User Documentation

### v1.5.2
* Make the plugin compatible with the master 1.5.1 version
* Correctly write cache file when changing the uzsu item
* Automatically activate all days of the week if no day is set via Visu
* Variety of bug fixes and optimizations
* Corrected information on web interface concerning (in)active entries

### v1.4.1 - 1.5.1
* Added a web interface for easier debugging
* Added "back in time"/initage feature to re-trigger missed uzsu evaluations on smarthomeng startup
* Added interpolation feature: the UZSU can now be used for smooth transitions of values (e.g. for light dimming, etc.)
* Added item functions to (de)activate, change interpolation and query some settings from the uzsu item via logic
* Fixed uzsu evaluation for entries without an rrule setting (day of week)
* Automatic deactivating older entries when new entry for exactly the same time (and day) is created (only works with specific VISU widgets)
* Improved error handling (detecting wrong items to be set by UZSU, empty entries, etc.)

## Configuration

### plugin.yaml

If remove_duplicates is set to True (default), existing entries with exactly the same settings except the value get replaced by the new entry.

```yaml
uzsu:
    class_name: UZSU
    class_path: plugins.uzsu
    #remove_duplicates: True
```

### items.yaml

You have to specify an item with `type: dict` and with the `uzsu_item` attribute set to the path of the item which will be set by this item. The hierarchy doesn't matter but it is recommended to define the UZSU item as a child of the item to be set and use the relative item reference '..' for the uzsu_item parameter. It is highly recommended to specify the ``cache: True`` as well for persistent storage of the UZSU information.

```yaml
# items/my.yaml
someroom:

    someitem:
        type: int

        UZSU:
            type: dict
            uzsu_item: someroom.someitem #using smarthomeNG 1.6 you can use '..' to define a relative item
            cache: 'True'

            active: #This can be used to simply (de)activate your uzsu via an item call
                type: bool
                eval: sh...activate(value)
                visu_acl: rw
```

## Item Data Format

Each UZSU item is of type list. Each list entry has to be a dict with specific key and value pairs. Here are the possible keys and what their for:

* __dtstart__: a datetime object. Exact datetime as start value for the rrule algorithm. Important e.g. for FREQ=MINUTELY rrules (optional).

* __value__: the value which will be set to the item.

* __active__: `True` if the entry is activated, `False` if not. A deactivated entry is stored to the database but doesn't trigger the setting of the value. It can be enabled with the `activate` function.

* __time__: time as string to use sunrise/sunset arithmetics like in the crontab eg. `17:00<sunset`, `sunrise>8:00`, `17:00<sunset`. You also can set the time with `17:00`.

* __rrule__: You can use the recurrence rules documented for [rrule](https://dateutil.readthedocs.io/en/stable/rrule.html) for recurrence use of a switching entry.

## Interpolation
Note: If Interpolation is activated the value will always be set in the given interval even if the next event is not on the same day. If you an entry at 11pm with a value of 100 and tomorrow at 1am one entry with value 0, with a linear interpolation the uzsu will write the interpolated value 50 at midnight.

Interpolation is a separate dict within the uzsu dict-entry with the following keys:

* __type__: string, sets the mathematical function to interpolate between values. Can be cubic, linear or none. If set to cubic or linear the value calculated for the current time will be set on startup and change.

* __interval__: integer, sets the time span in seconds between the automatic triggers based on the interpolation calculation

* __initage__: integer, sets the amount of minutes the plugin should go back in time at startup to find the last UZSU item and triggers that right on startup of the plugin. This is useless if interpolation is active as the interpolated time will get set on init anyhow.

* __itemtype__: the type of the item that should be changed by the UZSU. This is set automatically on init and should not be touched.

* __initizialized__: bool, gets set automatically at startup as soon as a valid UZSU entry was found in the specified initage and the item was indeed initialized with that value.

## Additional item functions

You can use these function in logics to query or set your uzsu item:

```python
# query the next scheduled value and time
sh.eg.wohnen.kugellampe.uzsu.planned()

# query whether the uzsu is set active or not
sh.eg.wohnen.kugellampe.uzsu.activate()

# set the uzsu active or inactive
sh.eg.wohnen.kugellampe.uzsu.activate(True/False)

# query the interpolation settings
sh.eg.wohnen.kugellampe.uzsu.interpolation()

# set interpolation options
sh.eg.wohnen.kugellampe.uzsu.interpolation(type='linear/none/cubic', interval=5, backintime=0)

# clear your settings of the uzsu item. BE CAREFUL!
sh.eg.wohnen.kugellampe.uzsu.clear(True)
```

## Web Interface
The web interface gives you the following information:
* list of all UZSU items with color coded info: gray = inacitve, green = active, red = problem
* items to be set as well as their item type (bool, string, num, etc.)
* current value of the item to be set as well as the planned next value + timestamp of that scheduling
* interpolation type and interval
* back in time value
* show the complete dictionary entry of an UZSU entry as a popup by clicking on it

## Example

Activates the light with a dim value of 100% every other day at 16:30 and shuts it off at 17:30. Between the UZSU entries the values are interpolated every 5 minutes linearly meaning at 17:00 the value will be 50%.

```python
sh.eg.wohnen.kugellampe.uzsu({'active':True, 'list':[
{'value':100, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '16:30'},
{'value':0, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2', 'time': '17:30'}],
{'interval': 5, 'type': 'linear', 'initialized': False, 'itemtype': 'num', 'initage': 0}
})
```

## More information

Have a look at the [SmarthomeNG blog entries](https://www.smarthomeng.de/tag/uzsu) on the UZSU plugin!

## SmartVISU

There is a widget available which gives an interface to the UZSU. The structure has changed from SmartVISU 2.8 to 2.9 slightly. Interpolation feature is supported in 2.9 only as a popup and graph. Please consult the corresponding forum.
