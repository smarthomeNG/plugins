# UZSU

Provides universal time switches for items (German: *U*niverselle *Z*eit*s*chalt *U*hr)

## Requirements

Calculating of sunset/sunrise in triggers, requires installation of ephem (which should already be part of core)

Calculating interpolation requires installation of scipy. Install with:
pip3 install scipy

On Raspberry debian stretch you also have to run:
apt-get install libatlas-base-dev

## Configuration

### plugin.yaml

```yaml
uzsu:
    class_name: UZSU
    class_path: plugins.uzsu
```

### items.yaml

#### uzsu
You have to specify an item with `type = dict` and with the `uzsu_item` attribute set to the path of the item which will be set by this item. The dict has to have two keys. `active` which says if the whole list of entries should be active or not and `list` which contains a list of all entries (see the Item Data Format section for more details).

From version 1.4.1 on you can also specify an `interpolation` dictionary.


```yaml
# items/my.yaml
someroom:

    someitem:
        type: int

        anotheritem:
            type: dict
            uzsu_item: someroom.someitem #using smarthomeNG 1.5.1 develop you can use '..' to define a relative item
            cache: 'True'
```

If you specify the ``cache: True`` as well, then your switching entries will be there even if you restart smarthome.py.

## Item Data Format

Each UZSU item is of type list. Each list entry has to be a dict with specific key and value pairs. Here are the possible keys and what their for:

* __dtstart__: a datetime object. Exact datetime as start value for the rrule algorithm. Important e.g. for FREQ=MINUTELY rrules (optional).

* __value__: the value which will be set to the item.

* __active__: `True` if the entry is activated, `False` if not. A deactivated entry is stored to the database but doesn't trigger the setting of the value. It can be enabled later with the `update` method.

* __time__: time as string to use sunrise/sunset arithmetics like in the crontab eg. `17:00<sunset`, `sunrise>8:00`, `17:00<sunset`. You also can set the time with `17:00`.

* __rrule__: You can use the recurrence rules documented in the [iCalendar RFC](http://www.ietf.org/rfc/rfc2445.txt) for recurrence use of a switching entry.

## Interpolation
* __type__: string, sets the mathematical function to interpolate between values. Can be cubic, linear or none. If set to cubic or linear the value calculated for the current time will be set on startup and change.

* __interval__: integer, sets the time span in seconds between the automatic triggers based on the interpolation calculation

* __initage__: integer, sets the amount of seconds the plugin should go back in time at startup to find the last UZSU item and triggers that right on startup of the plugin. This is useless if interpolation is active as the interpolated time will get set an init anyhow.

* __itemtype__: the type of the item that should be changed by the UZSU. This is set automatically on init and should not be touched.

* __initizialized__: bool, gets set automatically at startup as soon as a valid UZSU entry was found in the specified initage and the item was indeed initialized with that value.

## Additional item functions

You can use these function in logics to query or set yout uzsu item:

```
# query the next scheduled value and time
sh.eg.wohnen.kugellampe.uzsu.planned()

# query the interpolation settings
sh.eg.wohnen.kugellampe.uzsu.interpolation()

# query whether the uzsu is set active or not
sh.eg.wohnen.kugellampe.uzsu.activate()

# set the uzsu active or inactive
sh.eg.wohnen.kugellampe.uzsu.activate(True/False)

# set interpolation options
sh.eg.wohnen.kugellampe.uzsu.activate(type='linear/none/cubic', interval=5, backintime=0)

# clear your settings of the uzsu item. BE CAREFUL!
sh.eg.wohnen.kugellampe.uzsu.clear(True)


```


## Example

Activates the light every other day at 16:30 and deactivates it at 17:30 for five times:

```python
sh.eg.wohnen.kugellampe.uzsu({'active':True, 'list':[
{'value':1, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2;COUNT=5', 'time': '16:30'},
{'value':0, 'active':True, 'rrule':'FREQ=DAILY;INTERVAL=2;COUNT=5', 'time': '17:30'}],
{'interval': 5, 'type': 'cubic', 'initialized': False, 'itemtype': 'num', 'initage': 0}
})
```

## SmartVISU

There is a widget available which gives an interface to the UZSU. The structure has changed from SmartVISU 2.8 to 2.9 slightly. Interpolation feature is supported in 2.9 only. Please consult the corresponding forum.
