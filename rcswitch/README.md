# RCswitch
RCswitch is a plugin for smarthomeNG to send RC switch commands. With this plugin 433mhz remote controlled power plugs can be controlled from the smarthomeNG environment.
The plugin supports two setups:
* smarthomeNG runs on the same machine where the 433 MHz sender is connected to
* smarthomeNG accesses a 433 MHz transmitter installed on a remote machine

## Necessary Hardware
- RaspberryPi or any other board having digital GPIO
- [433 Mhz transmitter](https://www.google.de/search?q=433+mhz+transmitter&client=opera&hs=aeh&source=lnms&tbm=isch&sa=X&ved=0ahUKEwjzsYKo7vHRAhXKWxoKHdk1D6YQ_AUICSgC&biw=1163&bih=589)
- 433 Mhz controlled power plug, e.g. Brennenstuhl RCS 1000 N

Connect the VCC of the 433Mhz transmitter to any 5V output pin of your board, the GND to a ground pin and the ATAD to any GPIO pin. In this example, pin 17 is used. I recommend also to connect a (long) cable to the ANT pin of the 433Mhz transmitter - this extends the range of the sender.

## Requirements
The plugin depends on two 3rd party software packages:
- wiringPi (on the machine where the 433 MHz transmitter is installed)
- rcswitch-pi (on the machine where the 433 MHz transmitter is installed)
- ssh and sshpass (only if remote access is needed)

### Installation of wiringPi:
All steps have to be done on the machine where the on the machine where the 433 MHz transmitter is installed. In case not already done, update the system and install git:
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
All steps have to be done on the machine where the 433 MHz transmitter is installed. Download the sources into /usr/local/bin/rcswitch-pi:
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

### Send as non-root and testing
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
Last step is to ensure that the file is called during system boot. Therefore, the following line has to be added to /etc/rc.local, right before the 'exit 0' command:
<pre>/usr/local/scripts/exportGPIO17
</pre>
Now even after reboot it should be possible to switch the power plugs with the rcswitch-pi 'send' command.

### Installation of ssh and sshpass
Optional step: In case smarthomeNG wants to access the 433 MHz transmitter on an remote host, the following stepst have to be done on the machine where smarthomeNG runs:
<pre>apt-get update
apt-get upgrade
apt-get install ssh sshpass
</pre>
Also, ssh has to be installed on the machine where the 433 MHz transmitter is connected to:
<pre>apt-get update
apt-get upgrade
apt-get install ssh
</pre>

## Configuration
### plugin.conf
Adding following lines to plugin.conf in smarthomeNG will enable the rcswitch plugin:
<pre>[rc]
    class_name = RCswitch
    class_path = plugins.rcswitch
    rcswitch_dir = {path of rc switch} # optional parameter. Default: /usr/local/bin/rcswitch-pi
    rcswitch_sendDuration = {minimum time in s between sending commands} # optional parameter. Default: 0.5
    rcswitch_host = {ip}# optional parameter. Default: empty
    rcswitch_user = {user at remote host}#  optional parameter. Default: empty
    rcswitch_password = {password for user at remote host}# optional parameter. Default: empty
</pre>
####Attributes
* `rcswitch_dir`: has to point to the directory where the rcswitch-pi send command can be found.
* `rcswitch_sendDuration`: intended for trouble shooting. Increase this parameter in case switching several power plugs at the same time does not work reliable. Background: In case several power plugs (with different codes / device numbers) shall be switched at the same time, there must be a short gap between sending the serval commands. Otherwise, the several send commands are executed in parallel, gernerating jam on the rc signal.
* `rcswitch_host`: in case rcswitch is running on a remote machine, the IPv4 address has to be specified. Note: a SSH server has to be installed on the remote machine.
* `rcswitch_user`: user on the remote machine
* `rcswitch_password`: password for the user on the remote machine
####Example
<pre>[rc]
    class_name = RCswitch
    class_path = plugins.rcswitch
    rcswitch_dir = /usr/local/bin/rcswitch-pi # optional
    rcswitch_sendDuration = 0.5 # optional
    rcswitch_host = 192.168.0.4 # optional
    rcswitch_user = pi # optional
    rcswitch_password = raspberry # optional
</pre>

### items.conf
Just add following attributes to the items which shall be connected with rcswitch:
<pre>
rc_device = number of device [1-5]
rc_code = code of device [00000 - 11111]
</pre>
#### Attributes
* `rc_device`: Number or letter or the device. Valid values: 1,2,3,4,5,a,b,c,d,e,A,B,C,D,E
* `rc_code`: the code of the device. Must be 5 binary digits.

#### Example:
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

## Further information
For discussion see https://knx-user-forum.de/forum/supportforen/smarthome-py/39094-logic-und-howto-für-433mhz-steckdosen 
