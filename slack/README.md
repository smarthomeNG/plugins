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
SlackInstance:
    class_name: Slack
    class_path: plugins.slack
    token: abc/def/ghi # Token for posting to workspace '<your_team>'
</pre>

## Usage
Generate a "incoming webhook" with a token using https://<your_team>.slack.com/apps/new/A0F7XDUAZ-incoming-webhooks. You need to select a single channel when generating the token, but the token can be used for posting to multiple channels in the same workspace.

If you want to send notifications to different workspaces you need to generate a token for each workspace and you need to configure a SlackInstance section for every workspace/token.

To send a notification use the following syntax in your logics with the first parameter being the desired channel:

<pre>
# Default informational notification to channel #general
sh.SlackInstance.notify('#general', 'Ding Dong: Front door')
# Or use the following to set the default notification type to normal
sh.SlackInstance.notify('#otherChannel', 'Ding Dong: Front door', 'normal')
# Other notification types use warning, danger or good.
sh.SlackInstance.notify('#differentChannel', 'Alarm: Garage door open', 'danger')
</pre>
