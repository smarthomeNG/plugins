# Telegram

Send and receive information or commands over Telegram messaging service.  

## Requirements

Library ``python-telegram-bot`` and ``urllib3`` need to be installed prior to usage of the plugin.

Install it manually with either ``sudo pip install -r requirements.txt``    or    
by using ``pip install -r requirements.txt``

SmartHomeNG version 1.7 and later will install the necessary requirements at start of SmartHomeNG.

## Configuration

* Send command "/newbot" to "BotFather" in order to create your new bot
* you will asked for a bot name and unique username 
* BotFather will send you a token (=shared secred key) you will need for plugin registration
* configure some bot details starting by sending "/mybots" to BotFather
* You will need your chat id to enter it in an item. After first configuring your telegram plugin
  visit the bot from telegram client. Use command ``/start`` to start the bot. Unless you already 
  added your chat id to the list of trusted chat ids you will get a message that you are not allowed to
  use your chat. If you added it like shown in example below the message will change appropriately.
  There are three access rights so far: no access, readonly and read and write access.

### plugin.yaml

If configuration is done manually the following needs to be put into ``etc/plugin.yaml``

```
telegram:
    name: My Home
    class_name: Telegram
    class_path: plugins.telegram
    token: 123456789:BBCCfd78dsf98sd9ds-_HJKShh4z5z4zh22
```

#### name

Visible name of the bot in hello messages like ``my wonderful smarthome``

#### token

Shared secret key to authenticate to telegram network. Botfather reveals this token upon creation of the bot.

### items.yaml

#### trusted_chat_ids

Telegram communication is handled over chat(-channels) with unique ids.
So a communication is bound to a chat id (=connected user) which can be adressed with broadcast messages.
To get your current chat id, send a /start command to the bot, which will reply with your chatid.

By design negative chat ids are those belonging to a group.

The trusted chat ids need to put into an item, they can be changed then by backend and during runtime. 
See example:

```yaml
MyTelegramTest:
    Chat_Ids:
        type: dict
        telegram_chat_ids: True
        cache: 'True'
        # e.g. value: "{ 3234123342: 1, 9234123341: 0 }"
        # a dict with chat id and 1 for read and write access or 0 for readonly access
        # the following grants r/w access to 3234123342 and readonly to 9234123341
        value: "{ 3234123342: 1, 9234123341: 0 }"
```

#### telegram_message 

Send (broadcast) message on item change to registered chats. 
It is possible to use placeholder tags in the message string, to use a template based communication.

Available tags:

* [ID]
* [NAME]
* [VALUE]
* [CALLER]
* [SOURCE]
* [DEST]

Example without tags

```yaml
doorbell:
    type: bool
    knx_dpt: 1
    telegram_message: Doorbell rings!
```

The same example but extended with an additional item to send a camera snapshot via telegram:

```yaml
doorbell:
    type: bool
    visu_acl: r
    knx_dpt: 1
    knx_listen: x/x/x
    telegram_message: Doorbell rings!
    telegram_value_match_regex: (true|True|1)  # Only send when 1 (True)
    info:
        type: bool
        eval_trigger: doorbell
        eval: sh.telegram.photo_broadcast("http://<IP-address>/cgi-bin/xxx&user=username&password=passwd","Door camera") if sh.doorbell() == 1 else None
```

``http://<IP-address>/cgi-bin/xxx&user=username&password=passwd`` needs to be set according to the camera URL of course.

Example with tags

The following example shows an integration in Stateengine.
If the state changes, a message with the current state name is broadcasted 

```yaml
state_name:
    name: Name of current state
    type: str
    visu_acl: r
    cache: 'on'
    telegram_message: 'New Stateengine state: [VALUE]'
```

#### telegram_value_match_regex

In some cases it is usefull to check a value against a condition before sending the message. 
Messages are used to monitor defined value groups. Therefore messaging is limited with
this attribute to matching regular expressions only.

Example:

```yaml
TestNum:
    type: num
    cache: True
    telegram_message: TestNum: [VALUE]
    telegram_value_match_regex: [0-1][0-9]     # only send when numbers between 0 - 19 are set to item 
TestBool:
    type: bool
    cache: True
    telegram_message: TestBool: [VALUE]
    telegram_value_match_regex: (true|True|1)   # only send if 1 (True)
```

#### telegram_info

Read (broadcast) a list with specific item-values provided with the attribute.
The attribute parameter is also the command. 
e.g. ``/wetter``
All attribute parameters (commands) are listed with the ``/info``-command in a keyboard menu
Commands are limited to 32 characters, can consist of lower latin letters, digits and underscore.
Thus the attribute parameter ``Light`` or ``Temps`` is not allowed, whilst ``light`` and ``temps`` are fine.

Example:

```yaml
Aussentemperatur:
    name: Aussentemperatur in °C
    type: num
    knx_dpt: 9
    telegram_info: wetter

Wind_kmh:
    name: Wingeschwindigkeit in kmh
    type: num
    knx_dpt: 9
    telegram_info: wetter

Raumtemperatur:
    name: Raumtemperatur Wohnzimmer in °C
    type: num
    knx_dpt: 9
    telegram_info: rtr_ist
```

/info broadcast all info-commands in a bot-keyboard-menu e.g.

    [ /wetter] [/rtr_ist]

/wetter broadcast all items and values provided with the attribute 'telegram_info = "wetter"'

    Wetterstation.Aussentemperatur = -10,6
    Wetterstation.Wind_kmh = 12.6

/rtr_ist broadcast all items and values provided with the attribute 'telegram_info = "rtr_ist"'

    Dg.Wohnzimmer.Raumtemperatur = 22.6
    Dg.Kueche.Raumtemperatur = 22.3
    Dg.Bad.Raumtemperatur = 23.5
    Dg.Schlafzimmer.Raumtemperatur = 20.1

#### telegram_text

Write message-text into the SH-item whit this attribut

Simple Example

```yaml
telegram_message:
    name: Textnachricht von Telegram
    type: str
    telegram_text: true
```

## Example

At first you need to put your token you got from **botfather** into the ``plugin.yaml`` 

Then create an item like the following to present the authorized chat ids to the telegram plugin:

```yaml
MyTelegramTest:
    Chat_Ids:
        type: dict
        telegram_chat_ids: True
        cache: 'True'
        # e.g. value: "{ 3234123342: 1, 9234123341: 0 }"
        # a dict with chat id and 1 for read and write access or 0 for readonly access
        # the following grants r/w access to 3234123342
        value: "{ 3234123342: 1 }"
```

After a restart create a logic within admin interface or manually:

```python
# send a Hello world! message to all your trusted chat ids
msg = "Hello world!"
sh.telegram.msg_broadcast(msg)

# send an image on an external server, the URL will be prepared by telegram thus 
# no image data will be processed locally
sh.telegram.photo_broadcast("https://cdn.pixabay.com/photo/2018/10/09/16/20/dog-3735336_960_720.jpg", "A dog", None, False)

# local server
# there is no authentification yet built in so you can not access a secured webinterface
# change my_webcam_url
my_webcam_url = "http:// .... put the path here"
sh.telegram.photo_broadcast(my_webcam_url, "My webcam at {:%Y-%m-%d %H:%M:%S}".format(sh.shtime.now()))

# Send again the picture from above but first download the image data into memory and then send to telegram server
sh.telegram.photo_broadcast("https://cdn.pixabay.com/photo/2018/10/09/16/20/dog-3735336_960_720.jpg", "The dog again (data locally prepared)")

local_file = "/usr/local/smarthome/var/ ... some image file here ..."
sh.telegram.photo_broadcast(local_file, local_file)
```


## Todo and feature requests

* Implement full /subscribe mechanism to join broadcast messages
* Implement interface to operationlog plugin for message broadcast
* Implement r/w access to items
* Implement fast and menu based (read-only) navigation through item-tree
