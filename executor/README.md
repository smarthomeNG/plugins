# Executor Plugin

The executor plugin is used to test eval expressions and Python code often used with in eval or logics.

## Requirements

Nothing

## Configuration

Just enable it.

## Examples

### eval Expressions

A typical example is 

``12 if 23 % 3 == 5 else None``

this will return ``None``

* relative Item adressing will not work since no item structure is present


### Python code

A mockup of ``logger`` and ``print`` should work for output. The intention is that most parts of a logic can be copied and pasted here from a logic for test purposes.

A typical example is:

```
logger.warning("Eine Warnung")
logger.info("Eine Info")
logger.debug("Eine Debugmeldung")
logger.error("Eine Debugmeldung")
```

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