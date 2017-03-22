# Telegram Plugin

Send and receive information or commands over Telegram messaging service.  

# Requirements

install telepot library

# Configuration

* Send command "/newbot" to "BotFather" in order to create your new bot
* you will asked for a bot name and unique username 
* BotFather will send you a token (=shard secred) you will need for plugin registration
* configure some bot details starting by sending "/mybots" to BotFather

## plugin.conf

<pre>

[telegram]
        class_name = Telegram
        class_path = plugins.telegram
        token = "123456789:BBCCfd78dsf98sd9ds-_HJKShh4z5z4zh22"
        trusted_chat_ids = 123456789,9876543210

</pre>

## items.conf



### telegram_message 

Send Message on Item change to registered chats:

### Example

<pre>
[doorbell]
	name = Türklingel (entprellt)
	type = bool
	knx_dpt = 1
	telegram_message = "Es klingelt an der Tür"
</pre>

