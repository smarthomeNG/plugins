# XMPP

## Requirements/Description

This Plugin uses sleekxmpp as basis to connect to XMPP etc services: https://pypi.python.org/pypi/sleekxmpp

At this stage the XMPP plugin module only supports in sending messages. Recevied messages are ignored. OTR not supported
as the sleekxmpp libraries do not support this as yet.

## Configuration

### plugin.yaml

```yaml
xmpp:
    class_name: XMPP
    class_path: plugins.xmpp
    jid: 'user account eg skender@somexmppserver.com'
    password: your xmpp server password
    #use_ipv6: 1
```

Description of the attributes:

* jid: jabber/xmpp user account
* password: jabber/xmpp user password
* use_ipv6: enable IPv6 support, which is the default

### logic.yaml
At this stage there are no specific logic files. But in order to use this module you can create a logic file for another attribute and execute
or send messages to your xmpp account via sh.xmpp.send

## Functions
* sending a Message

```python
sh.xmpp.send("skender@somexmppserver.me", "ALARM: Triggered, Danger.", 'chat')
```

Send a message via xmpp
Requires:
        * mto = To whom eg 'skender@haxhimolla.im'
        * msgsend = body of the message eg 'Hello world'
        * mtype = message type, could be 'chat' or 'groupchat'


### Example for an action/logic file

```python
msg = trigger['value']

if sensor == "athome?":
    answer = "Someone has entered the house" if sh.myitem.athome() else "All secure"
    sh.xmpp.send("skender@haxhimolla.me", answer, 'chat')
```
