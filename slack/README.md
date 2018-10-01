# smarthome-slack
Plugin to send push notifications to Slack 

## Installation
<pre>
cd smarthome.py directory
cd plugins
git clone https://github.com/rthill/slack.git
</pre>

## Configuration
### etc/plugin.yaml
<pre>
SlackForChannelGeneral:
    class_name: Slack
    class_path: plugins.slack
    token: abc/def/ghi # Token for posting to channel '#general'
</pre>

## Usage
Generate a token using https://<your_team>.slack.com/apps/new/A0F7XDUAZ-incoming-webhooks for every channel you want to post to.

To send a notification to channel '#general' use the following syntax in your logics:

<pre>
# Default informational notification
sh.slack.notify('#general', 'Ding Dong: Front door')
# Or use the following to set the default notification type to normal
sh.slack.notify('#general', 'Ding Dong: Front door', 'normal')
# Other notification types use warning, danger or good.
sh.slack.notify('#general', 'Alarm: Garage door open', 'danger')
</pre>
