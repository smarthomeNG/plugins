# Executor Plugin

The executor plugin is used to test **eval expressions** and **Python code** often used within **logics**.

Be aware that enabling this plugin might be a security risk if other person get access to the webinterface
one can control the whole SmartHomeNG beast. So be careful!!!

## Requirements

Nothing

## Configuration

Just enable it.

## Examples

### eval Expressions

A typical example is 

``12 if 23 % 3 == 5 else None``

this will return ``None``

* relative Item addressing will not work since no item structure is present


### Python code

A mockup of ``logger`` and ``print`` should work for output. The intention is that most parts of a logic can be copied and pasted here from a logic for test purposes.

#### Test the logger

```
logger.warning("Eine Warnung")
logger.info("Eine Info")
logger.debug("Eine Debugmeldung")
logger.error("Eine Debugmeldung")
```

#### Print Series Data for an item

Another with data from database plugin for an item <your item here>:

```
import json

def myconverter(o):
    import datetime
    if isinstance(o, datetime.datetime):
      return o.__str__()
data = sh.<your item here>.series('max','1d','now')
pretty = json.dumps(data, default = myconverter, indent = 2, separators=(',', ': '))
print(pretty)
```

results in 

```
{
  "sid": "ArbeitszimmerOG.Raumtemperatur|max|1d|now|100",
  "cmd": "series",
  "update": "2019-11-09 17:54:22.205668+01:00",
  "params": {
    "sid": "ArbeitszimmerOG.Raumtemperatur|max|1d|now|100",
    "update": true,
    "start": 1573317598203,
    "end": "now",
    "func": "max",
    "item": "ArbeitszimmerOG.Raumtemperatur",
    "step": 864000
  },
  "series": [
    [
      1573231198203,
      21.0
    ],
    [
      1573232535421,
      21.2
    ],
    
    etc...
```

#### Count datasets in your database for each item

The following snippet will wall all items and count the entries they have in the database.
A word of warning: This might take very long time if you got quite a bunch of items with database attribute.

```python
from lib.item import Items
items = Items.get_instance()
myfiller = "                                                            "
allItems = items.return_items()
for myItem in allItems:
    if not hasattr(myItem,'db'):
        continue
    mycount = myItem.db('countall', 0)
    print (myItem.property.name + myfiller[0:len(myfiller)-len(myItem.property.name)]+ ' - Anzahl Datensätze :'+str(mycount))
```