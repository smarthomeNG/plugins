# Visualisation

This plugin provides an WebSocket interface for the smartVISU visualisation framework.
Right now the WebSocket interface only supports unencrypted connections. Please use a internal network or VPN to connect to the service.

# Requirements
None.

# Configuration

## plugin.conf
<pre>
[visu]
    class_name = WebSocket
    class_path = plugins.visu
#	visu_dir = False
#	generator_dir = False
#   ip='0.0.0.0'
#   port=2424
#	tls = no
#	wsproto = 3
#   acl = ro
#   smartvisu_dir = False
</pre>

### visu_dir ###
** Only used for **old visu** (not for smartVISU) **

 Directory in which the generated web pages of the old visa are stored

### generator_dir
** Only used for **old visu** (not for smartVISU) **

Source directory of the templates for generating web pages

### ip
This plugins listens by default on every IP address of the host.

### port
This plugins listens by default  on the TCP port 2424.

### tls
Encryption can be turned on by this parameter. 

??? Details unknown ???

### wsproto
The version of the web socket protocol can be specified. By default the plugin uses version 3. For smartVISU version > v2.7 the web socket protocol has to be set to 4.

### acl
The plugin provides by default read only access to every item. By changing the **`acl`** attribute to `rw` or `no` you could modify this behaviour to gain write access or no access to the items in smarthome.py.

### smartvisu_dir
You could generate pages for the smartVISU visualisation if you specify the **`smartvisu_dir`** which should be set to the root directory of your smartVISU installation.

In the examples directory you could find a configuration with every supported element. `examples/items/smartvisu.conf` 


## items.conf
Most of the entries in item.conf are specific to smartVISU. These parameters beginn with **`sv_`**.

### visu_acl
Simply set the **`visu_acl`** attribute to something to allow read/write access to the item.

### sv_page
 Set **`sv_page`** to to one of the following values generate a page for this item. Every widget beneath this item will be included in the page.

Valid values are:

| value              | description                                                                 |  
| :----------- | :--------------------------------------------  |  
|  **room**      |  The page appears in the room view of smartVISU    	|  
|  **category** | The page appears in the category view of smartVISU   |  
| **overview**  | ???              |
[values for **`sv_page`**]

--> In dict room.conf


### sv_img
By setting **`sv_img`** you could assign an icon or picture for a page or widget.

--> In dict room.conf


### sv_widget
**`sv_widget`** has to be a double quoted encapsulated string with the smartVISU widget. You could define multiple widgets by separating them by a comma. See the example below:

--> In dict room.conf

### sv_heading_right
--> In dict room.conf

### sv_heading_center
--> In dict room.conf

### sv_heading_left
--> In dict room.conf

### sv_item_type
--> In dict item.conf

If one of the **`sv_heading_...`** parameters is defined, heading.html from the template directory ?tpldir? is added to the page.

--> tpldir = directory + '/pages/base/tpl'
--> directory = parameter to pages() in smartvisu.py -> self.smartvisu_dir

### Example
<pre>
[second]
    [[sleeping]]
        name = Sleeping Room
        sv_page = room
        sv_img = scene_sleeping.png
        [[[light]]]
            name = Light
            type = bool
            visu_acl = rw
            sv_widget = &#123;&#123; device.dimmer('second.sleeping.light', 'Light', 'second.sleeping.light', 'second.sleeping.light.level') &#125;&#125;
            knx_dpt = 1
            knx_listen = 3/2/12
            knx_send = 3/2/12
            [[[[level]]]]
                type = num
                visu_acl = rw
                knx_dpt = 5
                knx_listen = 3/2/14
                knx_send = 3/2/14
</pre>

But instead of giving the widget distinct options you could use **`item`** as a keyword.

The page generator will replace it with the current path. This way you could easily copy widget calls and don't type the item path every time.

<pre>
[second]
    [[sleeping]]
        name = Sleeping Room
        sv_page = room
        sv_img = scene_sleeping.png
        [[[light]]]
            name = Light
            type = bool
            visu_acl = rw
            sv_widget = &#123;&#123; device.dimmer('item', 'item.name', 'item', 'item.level') &#125;&#125;
            knx_dpt = 1
            knx_listen = 3/2/12
            knx_send = 3/2/12
            [[[[level]]]]
                type = num
                visu_acl = rw
                knx_dpt = 5
                knx_listen = 3/2/14
                knx_send = 3/2/14
</pre>



## logic.conf
You could specify the **`visu_acl`** attribute to every logic in your logic.conf. This way you could trigger the logic via the interface.

<pre>
[dialog]
    filename = 'dialog.py'
    visu_acl = true
</pre>

.

# Files of the Plugin
The plugin is made up by several files, which are described below.


## __ init __.py
Main file of the plugin

## smartvisu.py
This file contains the code for interfacing with smartVISU

## generator.py
This file contains code for generating a visu, if not using smartVISU. The was the way to create a visualization before the Interfacing with smartVISU was done.

It is unknown it the code is functional, because it hasn't been tested.

.

# WebSocket Interface

The visa plugin implements a WebSocket server. This section describes the implemented WebSocket command, which the visu plugin handles. 

## item
With the **`item`** command a client requests to change the value of an item. 

.

## monitor
With the **`monitor`** command a client requests the actual value of an item.

.

## ping
With the **`ping`** command a client checks if the connection to the plugin is alive.

.

## logic
With the **`logic`** command a client requests a logic to be triggered.

.

## series
With the **`series`** command a client requests a series of values for an item. The values which are requested are stored in a database using the sqlite plugin. 

.

## log
With the **`log`** command a client requests the last entries of a specified log. The example command requests the last 10 log entries of the core log:

```
	{"cmd":"log","name":"env.core.log","max":"10"}
```

.

## proto
With the **`proto`** command a client requests the WebSocket protocol version, it wants to use for communication:

```
	{"cmd":"proto","ver":4}
```

The plugin answers with the protocol version it supports. Additionally it sends the actual date time and timezone:

```
	{'cmd': 'proto', 'ver': 4, 'time': datetime.datetime(2016, 4, 13, 21, 43, 12, 934553, tzinfo=tzfile('/usr/share/zoneinfo/Europe/Berlin'))}
```