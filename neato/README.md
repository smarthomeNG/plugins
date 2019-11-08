# Neato/Vorwerk Vacuum Robot

#### Version 1.0.0

This plugin connects your Neato (https://www.neatorobotics.com/) or Vorwerk Robot with SmarthomeNG.
- Command start, stop, pause, resume cleaning and trigger sendToBase and FindMe mode.
- Read status of your robot

## Change history

### Changes Since version 1.x.x

- No Changes so far


## Requirements

- locale en_US.utf8 must be installed (sudo dpkg-reconfigure locales)

### Needed software

* Python > 3.5
* pip install requests
* SmarthomeNG >= 1.6.0


### Supported Hardware

| Robot             | Supported    | Tested |
| ----------------- |:------------:| ------:|
| Neato Botvac D3   | yes          | no     |
| Neato Botvac D4   | yes          | no     |
| Neato Botvac D5   | yes          | yes    |
| Neato Botvac D6   | yes          | no     |
| Neato Botvac D7   | yes          | no     |
| Vorwerk VR300     | yes          | yes    |

## Configuration

### 1) /smarthome/etc/plugin.yaml

Enable the plugin in plugin.yaml, type in your Neato or Vorwerk credentials and define whether you are using a Neato or Vorwerk robot.

```yaml
Neato:
    plugin_name: neato
    account_email: 'your_neato_account_email'
    account_pass: 'your_neato_account_password!'
    robot_vendor: 'neato or vorwerk'
```

### 2) /smarthome/items/robot.yaml

Create an item based on the template below:

```yaml
Neato:
  Robot:
    Name:
      type: str
      neato_name: ''
      visu_acl: ro
    State:
      type: str
      neato_state: ''
      visu_acl: ro
    StateAction:
      type: str
      neato_state_action: ''
      visu_acl: ro
    Command:
      type: num
      neato_command: 0
      visu_acl: rw
    IsDocked:
      type: bool
      neato_isdocked: ''
      visu_acl: ro
    ChargePercentage:
      type: str
      neato_chargepercentage: ''
      visu_acl: ro
```

## Examples

Thats it! Now you can start using the plugin within SmartVisu, for example:

#### Get status from robot:
```html
<p>Name: {{ basic.value('RobotName', 'Neato.Robot.Name') }}</p>
/** Get the robots name (str)*/

<p>Cleaning status: {{ basic.value('RobotState', 'Neato.Robot.State') }}</p>
/** Get the robots cleaning status (str) */

<p>Cleaning status action: {{ basic.value('RobotStateAction', 'Neato.Robot.StateAction') }}</p>
/** Get the robots cleaning status action (str). Only when it's busy */

<p>Docking status: {{ basic.value('RobotDockingStatus', 'Neato.Robot.IsDocked') }}</p>
/** Get the robots docking status (bool) */

<p>Battery status: {{ basic.value('RobotBatteryState', 'Neato.Robot.ChargePercentage') }}</p>
/** Get the robots battery charge status (num) */
```

Following cleaning states are currently available:

| Neato.Robot.State |
| ----------------- |
| idle              |
| busy              |
| paused            |
| error             |

If Neato.Robot.State == 'busy' than you can find the current cleaning activity in Neato.Robot.StateAction.


#### Send commands to the robot:

```html

<p> {{ basic.button('RobotButton_Start', 'Neato.Robot.Command', 'Start', '', '61', 'midi') }} </p>
<p> {{ basic.button('RobotButton_Stop', 'Neato.Robot.Command', 'Stop', '', '62', 'midi') }} </p>
<p> {{ basic.button('RobotButton_Pause', 'Neato.Robot.Command', 'Pause', '', '63', 'midi') }} </p>
<p> {{ basic.button('RobotButton_Resume', 'Neato.Robot.Command', 'Resume', '', '64', 'midi') }} </p>
<p> {{ basic.button('RobotButton_Find', 'Neato.Robot.Command', 'Find', '', '65', 'midi') }}</p>

```

Following commands are currently available:

| Command (num) | Action           |
| ------------- |------------------|
| 61            | Start cleaning   |
| 62            | Stop cleaning    |
| 63            | Pause cleaning   |
| 64            | Resume cleaning  |
| 65            | Find the robot   |
| 66            | Send to base     |





