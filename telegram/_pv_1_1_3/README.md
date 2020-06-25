# Telegram

Send and receive information or commands over Telegram messaging service.  

## Requirements

install telepot library (see requirements.txt)

## Configuration

* Send command "/newbot" to "BotFather" in order to create your new bot
* you will asked for a bot name and unique username
* BotFather will send you a token (=shard secred) you will need for plugin registration
* configure some bot details starting by sending "/mybots" to BotFather

### plugin.yaml

```
telegram:
    name: My Home
    class_name: Telegram
    class_path: plugins.telegram
    token: 123456789:BBCCfd78dsf98sd9ds-_HJKShh4z5z4zh22
    trusted_chat_ids: 123456789,9876543210
```

#### name

Visible name of the bot in hello messages

#### token

shared secret key to authenticate to telegram network

#### trusted_chat_ids

Telegram communication is handled over chat(-channels) with unique ids. So a communication is bound to a chat id (=connected user) which can be adressed with broadcast messages. To get your current chat id, send a /subscribe command to the bot, which will replay with your chatid.  

### items.yaml

#### telegram_message

Send (broadcast) message on item change to registered chats.
It is possible to use placeholder tags in the message string, to use a template based communication.

Available tags:

[ID]
[NAME]
[VALUE]
[CALLER]
[SOURCE]
[DEST]

#### telegram_value_match_regex

In some cases it is usefull to check a value against a condition before sending the message. Messages are used to monitor defined value groups. Therefore messaging is limited with this attribute to matching regular expressions only.

#### Simple Example

```yaml
doorbell:
    name: Türklingel (entprellt)
    type: bool
    knx_dpt: 1
    telegram_message: Es klingelt an der Tür
```

#### Example with tags

The following example shows an integration in AutoBlind.
If the state changes, a message with the current state name is broadcasted

```yaml
state_name:
    name: Name des aktuellen Zustands
    type: str
    visu_acl: r
    cache: 'on'
    telegram_message: 'New AutoBlind state: [VALUE]'
```

#### telegram_info

read (broadcast) a list with specific item-values provided with the attribute.
The attribute parameter is also the command.
e.g. /wetter
All attribute parameters (commands) are listed with the /info-command in a keyboard menu

#### Simple Example

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


## Todo and feature requests

* The connection is resetted by the server time by time. Improve internal error handling, because the reset is not really an "error"
* Implement full /subscribe meachanism to join broadcast messages
* Implement codition based messaging. Messages are only sent, if a condition is fulfilled, e.g. a bool value is true.
* Implement interface to operationlog plugin for message broadcast
* Implement fast and menu based (read-only) navigation through item-tree
* Implement r/w access to items
