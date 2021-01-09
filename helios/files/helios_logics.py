#!/usr/bin/env python
# smarthome/logics/helios_logics.py - feel free to use / modify.
# Logics for extending the smarthome.py Helios plugin by Johannes and Marcel.
# Rev. 2016-11-16 by René Jahncke aka Tom Bombadil of http://knx-user-forum.de/smarthome-py

import time
import logging

logger = logging.getLogger("")

trigger_source 			= trigger['source']
trigger_value  			= trigger['value']

boost_mode              = sh.ventilation.logics_settings.boost_mode()     # 1 Helios, 2 fixed, 3 interactive
boost_fanspeed 			= sh.ventilation.logics_settings.boost_fanspeed() # 1..8
boost_time				= sh.ventilation.logics_settings.boost_time()     # eg 2700  ->   45 min * 60 sec


#1) Time-controlled fan speed adjustment including "on/off". Requires UZSU. ########################
if trigger_source == "ventilation.uzsu.fanspeed_uzsu":
	
	if sh.ventilation.rs485._power_state() == 1:				# Ventilation is currently ON

		if trigger_value == 0:
			sh.ventilation.rs485._power_state(0)
			logger.debug("Ventilation switched OFF")
		else: 
			if trigger_value > 0 and trigger_value < 9:
				sh.ventilation.rs485._fanspeed(trigger_value)
				logger.debug("Fan speed set to " + str(trigger['value']))

	else: 												# Ventilation is on standby ("OFF")

		sh.ventilation.rs485._power_state(1)
		logger.debug("Ventilation switched ON")
		time.sleep(10)
		sh.ventilation.rs485._fanspeed(trigger_value)
		logger.debug("Fan speed set to " + str(trigger['value']))

		
#2) Booster mode including timer and restoring of previous fan speed. ##############################
elif trigger_source == "ventilation.booster.logics.switch":

	if sh.ventilation.rs485._power_state() == 0:				# Switch it on first (if necessary)
		sh.ventilation.rs485._power_state(1)
		logger.debug("Ventilation switched ON")
		time.sleep(10)	
	
	if trigger_value == True:							# Booster mode on
		sh.ventilation.booster.logics.value_after_boost(sh.ventilation.rs485._fanspeed())
		sh.ventilation.rs485._fanspeed(boost_fanspeed)
		logic.trigger(dt=sh.now()+datetime.timedelta(seconds=boost_time), value="helios_boost_off")
		logger.debug("Booster mode activated for " + str(boost_time) + " seconds")

	else: 												# Booster mode off
		# hier zur sicherheit 30 sekunden warten ---> einfach auf  item(age) warten
		sh.ventilation.rs485._fanspeed(sh.ventilation.booster.logics.value_after_boost())
		logger.debug("Ventilation switched back to fan speed " + str(sh.ventilation.booster.logics.value_after_boost()))


#3) The heat is on - happy summer time! Temperature controlled mode. ###############################
#3) Sommer-Hitzemodus: Auto-Aus-An ab xx °C und bei Aussentemperatur < oder > Innentemperatur
#   Optionale Idee: Luftaustausch (Stoßlüftung) nachts um 0x Uhr, aber noch kein Plan dafür
#   Umsetzung noch nicht bis zum Ende durchdacht

	
#4) Various items ##################################################################################
else:

	if trigger_value == "helios_boost_off":
		logger.debug("Boost mode switched off by logic")
		sh.ventilation.booster.logics.switch(False)

		
	else:		#### Starting point for new (yet unknown) items .... ###############################
		logger.debug("Logic triggered by " + str(trigger_source) + " --> " + str(trigger_value))


# Known issues and limitations:
# 1)	Currently there is no documentation on how to switch on the remote control after standby.
#		So, when the ventilation is started by any bus member, the RC will remain OFF. When the RC
#		is switched on manually afterwards, it will automatically adjust fan speed to default value.
#		As the default value is usually not the same as the current fan speed, this behavior *will*
#		break the logic until the next fan speed adjustment takes place (by RC, UZSU, SV, whatever).
#		This problem is not related to this logic, but a general issue of ANY Helios plugin I found
#		for the various home automation systems like sh, Lox, oh and others.		
		

####################################################################################################		
		
# Derzeit unbenutzte Variablen

trigger_item   = str(sh.return_item(trigger_source))
trigger_dest   = trigger['dest']
trigger_by     = trigger['by']

# Logic nach xx sec erneut triggern und item.value manuell setzen als "merker"
# logic.trigger(dt=sh.now() + datetime.timedelta(seconds=30), value='zweiter Versuch') 
# denn time.sleep(xx) ist böse ;)


# direkte Itemabfragen immer mit Klammer!
# if sh.Haus.Status.Abwesend.led() and sh.Haus.Status.Abwesend.led.age() > 30:
#        sh.notify('ACHTUNG!', 'Seitentuer wurde im ABWESEND geöffnet', 2, '', '','Haus')
#        sh.whatsapp("ACHTUNG!', 'Seitentuer wurde im ABWESEND geoeffnet", "491xxxx")
#        logger.debug("Seitentür wurde im ABWESEND geöffnet")


#Wertzuweisung
#!/usr/bin/env python
#put on the light in the living room, if it is not on
#if not sh.living_room.light():
#    sh.living_room.light('on')


#Das hier funktioniert bit Boolschem Intem + Schalter:
#logger.debug("Schalter betätigt")
#if (trigger['value'] == 1):
#  logger.debug(' **** An')
#else:
#  logger.debug(' **** Aus ')

# Für zusammengebastelte item-Namen:
#   current_value = eval('sh.' + floor + '_floor.ventilation_status' + '()' )

