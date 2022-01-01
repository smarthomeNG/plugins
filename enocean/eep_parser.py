import logging

class EEP_Parser():

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Eep-parser instantiated')

    def CanParse(self, eep):
        found = callable(getattr(self, "_parse_eep_" + eep, None))
        if (not found):
            self.logger.error(f"eep-parser: missing parser for eep {eep} - there should be a _parse_eep_{eep}-function!")
        return found

    def Parse(self, eep, payload, status):
        #self.logger.debug('Parser called with eep = {} / payload = {} / status = {}'.format(eep, ', '.join(hex(x) for x in payload), hex(status)))
        results = getattr(self, "_parse_eep_" + eep)(payload, status)
        #self.logger.info('Parser returns {results}')
        return results

#####################################################
### --- Definitions for RORG =  A5 / ORG = 07 --- ###
#####################################################
    def _parse_eep_A5_02_01(self, payload, status):
        return {'TMP': (0 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_02(self, payload, status):
        return {'TMP': (10 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_03(self, payload, status):
        return {'TMP': (20 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_04(self, payload, status):
        return {'TMP': (30 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_05(self, payload, status):
        return {'TMP': (40 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_06(self, payload, status):
        return {'TMP': (50 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_07(self, payload, status):
        return {'TMP': (60 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_08(self, payload, status):
        return {'TMP': (70 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_09(self, payload, status):
        return {'TMP': (80 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_0A(self, payload, status):
        return {'TMP': (90 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_0B(self, payload, status):
        return {'TMP': (100 - (payload[2] * 40 / 255))}

    def _parse_eep_A5_02_10(self, payload, status):
        return {'TMP': (20 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_11(self, payload, status):
        return {'TMP': (30 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_12(self, payload, status):
        return {'TMP': (40 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_13(self, payload, status):
        return {'TMP': (50 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_14(self, payload, status):
        return {'TMP': (60 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_15(self, payload, status):
        return {'TMP': (70 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_16(self, payload, status):
        return {'TMP': (80 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_17(self, payload, status):
        return {'TMP': (90 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_18(self, payload, status):
        return {'TMP': (100 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_19(self, payload, status):
        return {'TMP': (110 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_1A(self, payload, status):
        return {'TMP': (120 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_1B(self, payload, status):
        return {'TMP': (130 - (payload[2] * 80 / 255))}

    def _parse_eep_A5_02_20(self, payload, status):
        return {'TMP': (41.2 - (((payload[1] & 0x03) * 256.0 + payload[2]) * 51.2 / 1023))}

    def _parse_eep_A5_02_30(self, payload, status):
        return {'TMP': (62.3 - (((payload[1] & 0x03) * 256.0 + payload[2]) * 102.3 / 1023))}

    def _parse_eep_A5_04_01(self, payload, status):
        result = {}
        result['HUM'] = (payload[1] / 250.0 * 100)
        result['TMP'] = (payload[2] / 250.0 * 40.0)
        return result

    def _parse_eep_A5_04_02(self, payload, status):
        # Energy (optional), humidity and temperature, for example eltako FBH65TFB
        result = {}
        # voltage of energy buffer in Volts
        result['ENG'] = 0.47 + (payload[0] * 1.5 / 66)
        # relative humidity in percent
        result['HUM'] = (payload[1] / 250.0 * 100)
        # temperature in degree Celsius from -20.0 degC - 60degC
        result['TMP'] = -20.0 + (payload[2] / 250.0 * 80.0)
        return result
        
    def _parse_eep_A5_06_01(self, payload, status):
        # Brightness sensor, for example Eltako FAH60
        self.logger.debug('Parsing A5_06_01: Brightness sensor')
        result = {}
        # Calculation of brightness in lux
        if (payload[3] == 0x0F) and (payload[1] > 0x00) and (payload[1] <= 0xFF):
            # If Data-Messege AND DataByte 2 is between: 0x00 = 300 lux and 0xFF = 30.000 lux
            result['BRI'] = round(((payload[1] / 255.0 * (30000 - 300)) + 300), 2)
        elif (payload[3] == 0x0F) and (payload[1] == 0x00):
            # If Data-Messege AND DataByte 2: 0x00 then read DataByte 3
            result['BRI'] = (payload[0])
        else:
            # No Data Message
            result['BRI'] = (-1)
        # only trigger the logger info when 'BRI' > 0
        if (result['BRI'] > 0):
            self.logger.info(f"Brightness: {result['BRI']}")
        return result

    def _parse_eep_A5_07_03(self, payload, status):
        # Occupancy sensor with supply voltage monitor, NodOne
        self.logger.debug("Parsing A5_07_03: Occupancy sensor")
        result = {}
        is_data = ((payload[3] & 0x08) == 0x08)                           # learn or data telegeram: 1:data, 0:learn
        if not is_data:
            self.logger.info("Occupancy sensor: Received learn telegram.")
            return result

        if payload[0] > 250:
            self.logger.error(f"Occupancy sensor issued error code: {payload[0]}")
        else:
            result['SVC'] = (payload[0] / 255.0 * 5.0)                  # supply voltage in volts
        result['ILL'] = (payload[1] << 2) + ((payload[2] & 0xC0) >> 6)  # 10 bit illumination in lux
        result['PIR'] = ((payload[3] & 0x80) == 0x80)                   # Movement flag, 1:motion detected
        self.logger.debug(f"Occupancy: PIR:{result['PIR']} illumination: {result['ILL']}lx, voltage: {result['SVC']}V")
        return result

    def _parse_eep_A5_08_01(self, payload, status):
        # Brightness and movement sensor, for example eltako FBH65TFB
        self.logger.debug("Parsing A5_08_01: Movement sensor")
        result = {}
        result['BRI'] = (payload[1] / 255.0 * 2048)          # brightness in lux
        result['MOV'] = not ((payload[3] & 0x02) == 0x02)    # movement
        #self.logger.debug(f"Movement: {result['MOV']}, brightness: {result['BRI']}")
        return result

    def _parse_eep_A5_11_04(self, payload, status):
        # 4 Byte communication (4BS) Telegramm
        # For example dim status feedback from eltako FSUD-230 actor.
        # Data_byte3 = 0x02
        # Data_byte2 = Dimmwert in % von 0-100 dez.
        # Data_byte1 = 0x00
        # Data_byte0 = 0x08 = Dimmer aus, 0x09 = Dimmer an
        self.logger.debug("Processing A5_11_04: Dimmer Status on/off")
        results = {}
        # if !( (payload[0] == 0x02) and (payload[2] == 0x00)):
        #    self.logger.error("Error in processing A5_11_04: static byte missmatch")
        #    return results
        results['D'] = payload[1]
        if (payload[3] == 0x08):
            # Dimmer is off
            results['STAT'] = 0
        elif (payload[3] == 0x09):
            # Dimmer is on
            results['STAT'] = 1
        return results

    def _parse_eep_A5_12_01(self, payload, status):
        # Status command from switch actor with powermeter, for example Eltako FSVA-230
        results = {}
        status_byte = payload[3]
        is_data = (status_byte & 0x08) == 0x08
        if(is_data == False):
            self.logger.debug("Processing A5_12_01: powermeter: is learn telegram. Aborting.")
            return results
        is_power = (status_byte & 0x04) == 0x04
        div_enum = (status_byte & 0x03)
        divisor = 1.0
        if(div_enum == 0):
            divisor = 1.0
        elif(div_enum == 1):
            divisor = 10.0
        elif(div_enum == 2):
            divisor = 100.0
        elif(div_enum == 3):
            divisor = 1000.0
        else: 
            self.logger.warning(f"Processing A5_12_01: Unknown enum ({div_enum}) for divisor")

        self.logger.debug(f"Processing A5_12_01: divisor is {divisor}")

        if(is_power):
            self.logger.debug("Processing A5_12_01: powermeter: Unit is Watts")
        else:
            self.logger.debug("Processing A5_12_01: powermeter: Unit is kWh")
        value = (payload[0] << 16) + (payload[1] << 8) + payload[2]
        value = value / divisor
        self.logger.debug(f"Processing A5_12_01: powermeter: {value} W")

        #debug output for wrong power values:
        if value > 1500:
            self.logger.warning(f"A5_12_01 exception: value {value}, divisor {divisor}, divenum {div_enum}, statusPayload {status_byte}, header status {status}")
            self.logger.warning(f"A5_12_01 exception: payloads 0-3: {payload[0]},{payload[1]},{payload[2]},{payload[3]}")
            results['DEBUG'] = 1

        results['VALUE'] = value
        return results

    def _parse_eep_A5_20_04(self, payload, status):
        # Status command from heating radiator valve, for example Hora smartdrive MX
        self.logger.debug("Processing A5_20_04")
        results = {}
        status_byte = payload[3]
        #1: temperature setpoint, 0: feed temperature
        TS = ((status_byte & 1 << 6) == 1 << 6)
        #1: failure, 0: normal
        FL = ((status_byte & 1 << 7) == 1 << 7)
        #1: locked, 0: unlocked
        BLS= ((status_byte& 1 << 5) == 1 << 5)
        results['BLS'] = BLS
        # current valve position 0-100%
        results['CP'] = payload[0]
        # Current feet temperature or setpoint
        if(TS == 1):
            results['TS'] = 10 + (payload[1]/255*20)
        else:
           results['FT'] = 20 + (payload[1]/255*60)
        # Current room temperature or failure code
        if (FL == 0): 
            results['TMP'] = 10 + (payload[2]/255*20)
        else: 
            results['FC'] = payload[2]
        results['STATUS'] = status_byte
        return results

    def _parse_eep_A5_30_01(self, payload, status):
        results = {}
        self.logger.debug("Processing A5_30_01")
        lernTelegram = not ((payload[3] & 1 << 3) == 1 << 3)
        if lernTelegram:
            self.logger.warning("A5_30_03 is learn telegram")
            return results
        # Data_byte1 = 0x00 / 0xFF
        results['ALARM'] = (payload[2]  == 0x00)
        # Battery linear: 0-120 (bat low), 121-255(bat high)
        results['BAT'] = payload[1]
        return results

    def _parse_eep_A5_30_03(self, payload, status):
        results = {}
        self.logger.warning("Debug: Processing A5_30_03")
        lernTelegram = not ((payload[3] & 1 << 3) == 1 << 3)
        if lernTelegram:
            self.logger.warning("A5_30_03 is learn telegram")
            return results
        # Data_byte0 = 0x0F
        if not (payload[3] == 0x0F):
            self.logger.error("EEP A5_30_03 not according to spec.")
            return results
        # Data_byte2 = Temperatur 0..40°C (255..0)
        results['TEMP']  = 40 - (payload[1]/255*40) 
        # Data_byte1 = 0x0F = Alarm, 0x1F = kein Alarm
        results['ALARM'] = (payload[2]  == 0x0F)
        return results


    def _parse_eep_A5_38_08(self, payload, status):
        results = {}
        if (payload[1] == 2):  # Dimming
            results['EDIM'] = payload[2]
            results['RMP'] = payload[3]
            results['LRNB'] = ((payload[4] & 1 << 3) == 1 << 3)
            results['EDIM_R'] = ((payload[4] & 1 << 2) == 1 << 2)
            results['STR'] = ((payload[4] & 1 << 1) == 1 << 1)
            results['SW'] = ((payload[4] & 1 << 0) == 1 << 0)
        return results

    def _parse_eep_A5_3F_7F(self, payload, status):
        self.logger.debug("Processing A5_3F_7F")
        results = {'DI_3': (payload[3] & 1 << 3) == 1 << 3, 'DI_2': (payload[3] & 1 << 2) == 1 << 2, 'DI_1': (payload[3] & 1 << 1) == 1 << 1, 'DI_0': (payload[3] & 1 << 0) == 1 << 0}
        results['AD_0'] = (((payload[1] & 0x03) << 8) + payload[2]) * 1.8 / pow(2, 10)
        results['AD_1'] = (payload[1] >> 2) * 1.8 / pow(2, 6)
        results['AD_2'] = payload[0] * 1.8 / pow(2, 8)
        return results

    def _parse_eep_A5_0G_03(self, payload, status):
        '''
        4 Byte communication(4BS) Telegramm
        Status command from bidirectional shutter actors:
            Eltako FSB61NP-230V, FSB71, FJ62/12-36V DC, FJ62NP-230V
        If actor is stopped during run it sends the feedback of runtime and the direction
        This enables to calculate the actual shutter position
        Key Description:
            MOVE: runtime of movement in s (with direction: "-" = up; "+" = down)
        '''
        self.logger.debug("eep-parser processing A5_0G_03 4BS telegram: shutter movement feedback")
        self.logger.debug("eep-parser input payload = [{}]".format(', '.join(['0x%02X' % b for b in payload])))
        self.logger.debug(f"eep-parser input status = {status}")
        results = {}
        runtime_s = ((payload[0] << 8) + payload[1]) / 10
        if (payload[2] == 1):
            self.logger.debug(f"Shutter moved {runtime_s} s 'upwards'")
            results['MOVE'] = runtime_s * -1
        elif (payload[2] == 2):
            self.logger.debug(f"Shutter moved {runtime_s} s 'downwards'")
            results['MOVE'] = runtime_s
        return results

#####################################################
### --- Definitions for RORG = D2  / ORG = D2 --- ###
#####################################################
    def _parse_eep_D2_01_07(self, payload, status):
        # self.logger.debug("Processing D2_01_07: VLD Switch")
        results = {}
        # self.logger.info(f'D2 Switch Feedback  0:{payload[0]} 1:{payload[1]} 2:{payload[2]}')
        if (payload[2] == 0x80):
            # Switch is off
            results['STAT'] = 0
            self.logger.debug('D2 Switch off')
        elif (payload[2] == 0xe4):
            # Switch is on
            results['STAT'] = 1
            self.logger.debug('D2 Switch on')
        return results

    def _parse_eep_D2_01_12(self, payload, status):
        # self.logger.debug("Processing D2_01_12: VLD Switch")
        results = {}
        # self.logger.info(f'D2 Switch Feedback  0:{payload[0]} 1:{payload[1]} 2:{payload[2]}')
        if (payload[1] == 0x60) and (payload[2] == 0x80):
            # Switch is off
            results['STAT_A'] = 0
            self.logger.debug('D2 Switch Channel A: off')
        elif (payload[1] == 0x60) and (payload[2] == 0xe4):
            # Switch is on
            results['STAT_A'] = 1
            self.logger.debug('D2 Channel A: Switch on')
        elif (payload[1] == 0x61) and (payload[2] == 0x80):
            # Switch is off
            results['STAT_B'] = 0
            self.logger.debug('D2 SwitchChannel A:  off')
        elif (payload[1] == 0x61) and (payload[2] == 0xe4):
            # Switch is on
            results['STAT_B'] = 1
            self.logger.debug('D2 Switch Channel B: on')
        return results

####################################################
### --- Definitions for RORG = D5 / ORG = 06 --- ###
####################################################
    def _parse_eep_D5_00_01(self, payload, status):
        # Window/Door Contact Sensor, for example Eltako FTK, FTKB
        self.logger.debug("Processing D5_00_01: Door contact")
        return {'STATUS': (payload[0] & 0x01) == 0x01}


####################################################
### --- Definitions for RORG = F6 / ORG = 05 --- ###
####################################################
    def _parse_eep_F6_02_01(self, payload, status):
        self.logger.debug("Processing F6_02_01: Rocker Switch, 2 Rocker, Light and Blind Control - Application Style 1")
        results = {}
        R1 = (payload[0] & 0xE0) >> 5
        EB = (payload[0] & (1<<4) == (1<<4))
        R2 = (payload[0] & 0x0E) >> 1
        SA = (payload[0] & (1<<0) == (1<<0))
        NU = (status & (1<<4) == (1<<4))

        if (NU):
            results['AI'] = (R1 == 0) or (SA and (R2 == 0))
            results['AO'] = (R1 == 1) or (SA and (R2 == 1))
            results['BI'] = (R1 == 2) or (SA and (R2 == 2))
            results['BO'] = (R1 == 3) or (SA and (R2 == 3))
        elif (not NU) and (payload[0] == 0x00):
            results = {'AI': False, 'AO': False, 'BI': False, 'BO': False}
        else:
            self.logger.error("Parser detected invalid state encoding - check your switch!")
            pass
        return results

    def _parse_eep_F6_02_02(self, payload, status):
        self.logger.debug("Processing F6_02_02: Rocker Switch, 2 Rocker, Light and Blind Control - Application Style 2")
        return self._parse_eep_F6_02_01(payload, status)

    def _parse_eep_F6_02_03(self, payload, status):
        '''
        Repeated switch communication(RPS) Telegramm
        Status command from bidirectional actors, for example eltako FSUD-230, FSVA-230V or switches (for example Gira)
        '''
        self.logger.debug("Processing F6_02_03: Rocker Switch, 2 Rocker")
        results = {}
        # Button A1: Dimm light down
        results['AI'] = (payload[0]) == 0x10
        # Button A0: Dimm light up
        results['AO'] = (payload[0]) == 0x30
        # Button B1: Dimm light down
        results['BI'] = (payload[0]) == 0x50
        # Button B0: Dimm light up
        results['BO'] = (payload[0]) == 0x70
        if (payload[0] == 0x70):
            results['B'] = True
        elif (payload[0] == 0x50):
            results['B'] = False
        elif (payload[0] == 0x30):
            results['A'] = True
        elif (payload[0] == 0x10):
            results['A'] = False
        return results 

    def _parse_eep_F6_10_00(self, payload, status):
        self.logger.debug("Processing F6_10_00: Mechanical Handle")
        results = {}
        if (payload[0] == 0xF0):
            results['STATUS'] = 0
        elif ((payload[0]) == 0xE0) or ((payload[0]) == 0xC0):
            results['STATUS'] = 1
        # Typo error in older Eltako Datasheet for 0x0D instead of the right 0xD0
        elif (payload[0] == 0xD0):
            results['STATUS'] = 2
        else:
            self.logger.error(f"Error in F6_10_00 handle status, payload: {payload[0]} unknown")
        return results

    def _parse_eep_F6_0G_03(self, payload, status):
        '''
        Repeated switch communication(RPS) Telegramm
        Status command from bidirectional shutter actors
        Repeated switch Command for Eltako FSB61NP-230V, FSB71
        Key Description:
            POSITION: 0 -> upper endposition; 255 -> lower endposition
            STATUS: Info what the shutter does
            B: status of the shutter actor (command) 
        '''
        self.logger.debug("Processing F6_0G_03: shutter actor")
        results = {}
        if (payload[0] == 0x70):
            results['POSITION'] = 0
            results['B'] = 0
        elif (payload[0] == 0x50):
            results['POSITION'] = 255
            results['B'] = 0
        elif (payload[0] == 0x01):
            results['STATUS'] = 'Start movin up'
            results['B'] = 1
        elif (payload[0] == 0x02):
            results['STATUS'] = 'Start movin down'
            results['B'] = 2
        return results
