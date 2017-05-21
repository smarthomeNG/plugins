# OperationLog

This plugins can be used to create logs which are cached, written to file and stored in memory to be used by items or other
plugins. Furthermore the logs can be visualised by smartVISU using the standard widget "status.log".

# Requirements

No special requirements.

# Configuration

## plugin.conf

Use the plugin configuration to configure the logs.

```
[mylogname1]
    class_name = OperationLog
    class_path = plugins.operationlog
    name = mylogname1
#   maxlen = 50
#   cache = yes
#   logtofile = yes
#   filepattern = {year:04}-{month:02}-{day:02}-{name}.log

[mylogname2]
    class_name = OperationLog
    class_path = plugins.operationlog
    name = mylogname2
    maxlen = 0
    cache = no
    logtofile = yes
    filepattern = yearly_log-{name}-{year:04}.log
```

This will register two logs named mylogname1 and mylogname2. 
The first one named mylogname1 is configured with the default configuration as shown,
caching the log to file (smarthome/var/cache/mylogname1) and logging to file (smarthome/var/log/operationlog/yyyy-mm-dd-mylogname1.log). 
Every day a new logfile will be created. The last 50 entries will be kept in memory.

The entries of the second log will not be kept in memory, only logged to a yearly file with the pattern yearly_log-mylogname2-yyyy. 

The logging file can be named as desired. The keys `{name}`, `{year}`, `{month}` and `{day}` are replaced by the log name and current time respectively. 
Every time a log entry is written, the file name is checked and a new file is created upon change. 


## items
Configure an item to be logged as follows:

```
[foo]
    name = Foo
    [[bar]]
        type = num
        olog = mylogname1
    #   olog_rules = *:value
    #   olog_txt = {id} = {value} 
    #   olog_level = INFO
```

foo.bar uses the minimum configuration and default values. 
When the item gets updated a new log entry using loglevel 'INFO' will be generated in the log mylogname1. 
The format of the entry will be "foo.bar = value". 
The default value `olog_rules = *:value` defines all values to trigger a log entry. 
Item types `num`, `bool` and `str` can be used.

Define a list of parameters in `olog_rules` to map item values to string properties using the format `key:value` where the item value is used as key. 
Limit the values to be logged by defining `lowlimit:<lowest value>` and `highlimit:<highest value>`, see examples below. A log entry is generated for `lowlim` <= item value < `highlim`.

The logtext can be defined using the `olog_txt` attribute. The following predefined keys can be used in the text:

Key         | Description
----------- | -----------
`{value}`   | item value
`{mvalue}`  | mapped value defined in `olog_rules` from key `value`
`{name}`    | name attribute of item
`{age}`     | time since the previous change of the item value
`{pname}`   | name attribute of the parent item
`{id}`      | item id
`{pid}`     | id of the parent item
`{lowlim}`  | lower limit of the item value generating a log entry
`{highlim}` | upper limit of the item value generating a log entry

Furthermore user defined python expressions can be used in the logtext. Define as follows:

`{eval=<python code>}`

The code is replaced by the return value of the \<python code> for the logtext. Multiple `{eval=<python code>}` statements can be used.   

### item log examples:

```
[foo]
    name = Foo
    [[bar1]]
        type = num
        name = Bar1
        olog = mylogname1
        olog_rules = 2:two | 0:zero | 1:one | *:value
        olog_txt = This is a log text for item with name {name} and value {value} mapped to {mvalue}, parent item name is {pname}
        olog_level = ERROR

    [[bar2]]
        type = bool
        name = Bar2
        olog = mylogname1
        olog_rules = True:the value is true | False:the value is false 
        olog_txt = This is a log text for {value} mapped to '{mvalue}', {name} changed after {age} seconds
        olog_level = warning

    [[bar3]]
        type = str
        name = Bar3
        olog = mylogname1
        olog_rules = t1:text string number one | t2:text string number two | *:value 
        olog_txt = text {value} is mapped to logtext '{mvalue}', expression with syntax errors: {eval=sh.this.item.doesnotexist()*/+-42}
        olog_level = critical

    [[bar4]]
        type = num
        name = Bar4
        olog = mylogname1
        olog_rules = lowlim:-1.0 | highlim:10.0
        olog_txt = Item with name {name} has lowlim={lowlim} <= value={value} < highlim={highlim}, the value {eval='increased' if sh.foo.bar4() > sh.foo.bar4.prev_value() else 'decreased'} by {eval=round(abs(sh.foo.bar4() - sh.foo.bar4.prev_value()), 3)} 
        olog_level = info
```

## Functions

```
sh.mylogname1('<level_keyword>', msg)
```


Logs the message in `msg` parameter with the given log level specified in the `<level_keyword>` parameter. 

Using the loglevel keywords `INFO`, `WARNING` and `ERROR` (upper or lower case) will cause the smartVISU plugin "status.log" to mark the entries with the colors green, yellow and red respectively. Alternative formulation causing a red color are `EXCEPTION` and `CRITICAL`. Using other loglevel keyword will result in log entry without a color mark.

```
sh.mylogname1(msg)
```

Logs the message in the `msg` parameter with the default loglevel `INFO`.

```
data = sh.mylogname1()
```

will return a deque object containing the log with the last `maxlen` entries.





This plugin is inspired from the plugins MemLog and AutoBlind, reusing some of their sourcecode.
