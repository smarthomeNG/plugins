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

# the following is only neccessary if you want to post to different Slack workspaces
SlackInstanceForSecondWorkspace:
    class_name: Slack
    class_path: plugins.slack
    token: jkl/mno/pqr # Token for posting to another workspace '<another_team>'
</pre>

## Usage
To enable posting to Slack you need to create an "incoming webhook" there, which gives you an authorization token.
Open the following URL for your team workspace and create a wehhook. Please select one channel of your workspace.
https://<your_team>.slack.com/apps/new/A0F7XDUAZ-incoming-webhooks.
Afterwards you need to setup your etc/plugin.yaml as described above and insert the webhook token.
The created API token authorizes posting to every channel in this workspace.

For most users a single instance would be sufficient.
If you want to send notifications to more than one Slack workspace, you need to generate a webhook / token in every Slack workspace.
For each of them you'll need to configure a section in plugin.yaml with different instance names.

To send a notification use the following syntax in your logics with the first parameter being the desired channel:

<pre>
# Default informational notification to channel #general
sh.SlackInstance.notify('#general', 'Ding Dong: Front door')
# Or use the following to set the default notification type to normal
sh.SlackInstance.notify('#otherChannel', 'Ding Dong: Front door', 'normal')
# Other notification types use warning, danger or good.
sh.SlackInstance.notify('#differentChannel', 'Alarm: Garage door open', 'danger')

# Sending a notification to the second workspace
sh.SlackInstanceForSecondWorkspace.notify('#general', 'Hello second workspace!')
</pre>
