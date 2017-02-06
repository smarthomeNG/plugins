# RCswitch
RCswithc is a plugin for smarthomeNG to send RC switch commands. With this plugin 433mhz remote controlled power plugs can be controlled from the smarthomeNG environment.

## plugin.conf
Adding following lines to plugin.conf in smarthomeNG will enable the rcswitch plugin:
<pre>[rc]
    class_name = RCswitch
    class_path = plugins.rcswitch
    rcswitch_dir = {path of rc switch} # optional parameter. Default: /etc/local/bin/rcswitch-pi
    rcswitch_sendDuration = {minimum time in s between sending commands} # optional parameter. Default: 0.5
</pre>
Example:
<pre>[rc]
    class_name = RCswitch
    class_path = plugins.rcswitch
    rcswitch_dir = /etc/local/bin/rcswitch-pi # optional
    rcswitch_sendDuration = 0.5 # optional
</pre>
The parameter rcswitch_dir has to point to the directory where the rcswitch-pi send command can be found.

The parameter rcswitch_sendDuration is intended for trouble shooting. Increase this parameter in case switching several power plugs does not work reliable.

Background: In case several power plugs (with different codes / device numbers) shall be switched at the same time, there must be a short gap between sending the serval commands. Otherwise, the several send commands are executed in parallel, gernerating jam on the rc signal.
## items.conf
Just add following attributes to the items which shall be connected with rcswitch:
<pre>
rc_device = number of device [1-5]
rc_code = code of device [00000 - 11111]
</pre>
Example:
<pre>
[Basement]
	[[LivingRoom]]
		[[[RCpowerPlug]]]
			[[[[TV]]]]
				[[[[[switch]]]]]
					type = bool
					knx_dpt = 1
					knx_listen = 14/0/10
					knx_send = 14/0/13
					rc_code = 11111
					rc_device = 2
</pre>
----------------------------
## Necessary Hardware
- RaspberryPi or any other board having digital GPIO
- [433 Mhz transmitter](https://www.google.de/search?q=433+mhz+transmitter&client=opera&hs=aeh&source=lnms&tbm=isch&sa=X&ved=0ahUKEwjzsYKo7vHRAhXKWxoKHdk1D6YQ_AUICSgC&biw=1163&bih=589)
- 433 Mhz controlled power plug, e.g. Brennenstuhl RCS 1000 N

Connect the VCC of the 433Mhz transmitter to any 5V output pin of your board, the GND to a ground pin and the ATAD to any GPIO pin. In this example, pin 17 is used. I recommend also to connect a (long) cable to the ANT pin of the 433Mhz transmitter - this extends the range of the sender.

## Installation of 3rd party software
The plugin depends on two 3rd party software packages:
- wiringPi
- rcswitch-pi

### Installation of wiringPi:
In case not already done, update the system and install git:
<pre>
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install git-core
</pre>
Then download wiringPi to /usr/local/bin/wiringPi
<pre>
cd /usr/local/bin
sudo git clone git://git.drogon.net/wiringPi
</pre>
and install it:
<pre>
cd wiringPi
sudo ./build
</pre>

>Soure: https://raspiprojekt.de/machen/basics/software/10-wiringpi.html?showall=&start=1

### Installation of rcswitch-pi
Download the sources into /etc/local/bin/rcswitch-pi:
<pre>
cd /usr/local/bin
sudo git clone https://github.com/r10r/rcswitch-pi.git
</pre>
Before building rcswitch-pi, the port has to be defined the code has to be changed slightly. Therefore edit the file send.cpp and the change the port to your needs and replace the command wiringPiSetup() to wiringPiSetupSys(). For editing the file:
<pre>
cd rcswitch-pi
sudo nano send.cpp
</pre>
In our example the file send.cpp has to look like follows:
<pre>
int PIN = 17;
  char* systemCode = argv[1];
  int unitCode = atoi(argv[2]);
  int command = atoi(argv[3]);

  if (wiringPiSetupSys() == -1) return 1;
     printf("sending systemCode[%s] unitCode[%i] command[%i]\n", systemCode, unitCode, command);
     RCSwitch mySwitch = RCSwitch();
     mySwitch.enableTransmit(PIN);

  switch(command) {
      case 1:
          mySwitch.switchOn(systemCode, unitCode);
          break;
      case 0:
          mySwitch.switchOff(systemCode, unitCode);
          break;
      default:
</pre>
Save the file (ctrl + o) and leave nano (ctrl+x)
Now rcswitch pi can be compiled:
<pre>
cd rcswitch-pi
make
</pre>
> source https://raspiprojekt.de/anleitungen/schaltungen/28-433-mhz-funksteckdosen-schalten.html?showall=&start=1

##Send as non-root and testing
For a first basic test, write access to non-root users can be granted with the command:
<pre>gpio export 17 out</pre>
Now, with the send command the power plugs can be switched. Assuming, the power plug has code 11111 and address 2 (=B), the command to switch it on is:
<pre>./send 11111 2 1</pre>
If the power plug does not switch at this point, you need to figure out why before proceeding.

Because the setting of port 17, done with the command 'gpio export 17 out' will be lost after reboot, it has to made persistent. Therefore create file /usr/local/scripts/exportGPIO17
<pre>sudo mkdir /usr/local/scripts/
cd /usr/local/scripts/
sudo nano exportGPIO17
</pre>
... and add following content:
<pre>#!/bin/sh  
echo "17" > /sys/class/gpio/export
echo "out" > /sys/class/gpio/gpio17/direction
chmod 666 /sys/class/gpio/gpio17/value
chmod 666 /sys/class/gpio/gpio17/direction</pre>
Save and close the file. Now the file has to be made executable with
<pre>sudo sudo chmod +x exportGPIO17</pre>
Last step is to ensure that the file is called during system boot. Therefore, add the following  line has to be added to /etc/rc.local, right before the 'exit 0' command:
<pre>/usr/local/scripts/exportGPIO17</pre>
Now even after reboot it should be possible to switch the power plugs with the rcswitch-pi 'send' command.
## Further information
For discussion see https://knx-user-forum.de/forum/supportforen/smarthome-py/39094-logic-und-howto-für-433mhz-steckdosen 
