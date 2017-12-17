import logging

class EEP_Parser():

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info('enocean: eep-parser instantiated')

    def CanParse(self, eep):
        found = callable(getattr(self, "_parse_eep_" + eep, None))
        if (not found):
            self.logger.error("eep-parser: missing parser for eep {} - there should be a _parse_eep_{}-function!".format(eep, eep))
        return found

    def Parse(self, eep, payload, status):
        #self.logger.debug('enocean: parser called with eep = {} / payload = {} / status = {}'.format(eep, ', '.join(hex(x) for x in payload), hex(status)))
        results = getattr(self, "_parse_eep_" + eep)(payload, status)
        #self.logger.info('enocean: parser returns {}'.format(results))
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
        self.logger.debug('enocean: parsing A5_06_01: Brightness sensor')
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
            self.logger.info('enocean: brightness: {0}'.format(result['BRI']))
        return result

    def _parse_eep_A5_08_01(self, payload, status):
        # Brightness and movement sensor, for example eltako FBH65TFB
        self.logger.debug("enocean: parsing A5_08_01: Movement sensor")
        result = {}
        result['BRI'] = (payload[1] / 255.0 * 2048)          # brightness in lux
        result['MOV'] = not ((payload[3] & 0x02) == 0x02)    # movement
        #self.logger.debug("enocean: movement: {0}, brightness: {1}".format(result['MOV'],result['BRI']))
        #self.logger.debug("enocean: movement data byte0: {0}".format(payload[3]))
        return result

    def _parse_eep_A5_11_04(self, payload, status):
        # 4 Byte communication (4BS) Telegramm
        # For example dim status feedback from eltako FSUD-230 actor.
        # Data_byte3 = 0x02
        # Data_byte2 = Dimmwert in % von 0-100 dez.
        # Data_byte1 = 0x00
        # Data_byte0 = 0x08 = Dimmer aus, 0x09 = Dimmer an
        self.logger.debug("enocean: processing A5_11_04: Dimmer Status on/off")
        results = {}
        # if !( (payload[0] == 0x02) and (payload[2] == 0x00)):
        #    self.logger.error("enocean: error in processing A5_11_04: static byte missmatch")
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
        # Status command from switche actor with powermeter, for example eltako FSVA-230
        self.logger.debug("enocean: processing A5_12_01")
        results = {}
        status = payload[3]
        value = (payload[0] << 16) + (payload[1] << 8) + payload[2]
        results['VALUE'] = value
        return results

    def _parse_eep_A5_20_04(self, payload, status):
        # Status command from heating radiator valve, for example Hora smartdrive MX
        self.logger.debug("enocean: processing A5_20_04")
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
        self.logger.debug("enocean: processing A5_3F_7F")
        results = {'DI_3': (payload[3] & 1 << 3) == 1 << 3, 'DI_2': (payload[3] & 1 << 2) == 1 << 2, 'DI_1': (payload[3] & 1 << 1) == 1 << 1, 'DI_0': (payload[3] & 1 << 0) == 1 << 0}
        results['AD_0'] = (((payload[1] & 0x03) << 8) + payload[2]) * 1.8 / pow(2, 10)
        results['AD_1'] = (payload[1] >> 2) * 1.8 / pow(2, 6)
        results['AD_2'] = payload[0] * 1.8 / pow(2, 8)
        return results

#####################################################
### --- Definitions for RORG = D2  / ORG = D2 --- ###
#####################################################
    def _parse_eep_D2_01_07(self, payload, status):
        # self.logger.debug("enocean: processing D2_01_07: VLD Switch")
        results = {}
        # self.logger.info('enocean: D2 Switch Feedback  0:{} 1:{} 2:{}').format(payload[0],payload[1],payload[2])
        if (payload[2] == 0x80):
            # Switch is off
            results['STAT'] = 0
            self.logger.debug('enocean: D2 Switch off')
        elif (payload[2] == 0xe4):
            # Switch is on
            results['STAT'] = 1
            self.logger.debug('enocean: D2 Switch on')
        return results


####################################################
### --- Definitions for RORG = D5 / ORG = 06 --- ###
####################################################
    def _parse_eep_D5_00_01(self, payload, status):
        # Window/Door Contact Sensor, for example Eltako FTK, FTKB
        self.logger.debug("enocean: processing D5_00_01: Door contact")
        return {'STATUS': (payload[0] & 0x01) == 0x01}


####################################################
### --- Definitions for RORG = F6 / ORG = 05 --- ###
####################################################
    def _parse_eep_F6_02_01(self, payload, status):
        self.logger.debug("enocean: processing F6_02_01: Rocker Switch, 2 Rocker, Light and Blind Control - Application Style 1")
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
            self.logger.error("enocean: parser detected invalid state encoding - check your switch!")
            pass
        return results

    def _parse_eep_F6_02_02(self, payload, status):
        self.logger.debug("enocean: processing F6_02_02: Rocker Switch, 2 Rocker, Light and Blind Control - Application Style 2")
        return self._parse_eep_F6_02_01(payload, status)

    def _parse_eep_F6_02_03(self, payload, status):
        # Repeated switch communication(RPS) Telegramm
        # Status command from bidirectional actors, for example eltako FSUD-230, FSVA-230V or switches (for example Gira)
        #self.logger.debug("enocean: processing F6_02_03: Rocker Switch, 2 Rocker")
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
        # special extension for ELTAKO FSB61NP-230V status message compatibility:
        elif (payload[0] == 0x02): 
            results['B'] = False
        return results

    def _parse_eep_F6_10_00(self, payload, status):
        self.logger.debug("enocean: processing F6_10_00: Mechanical Handle")
        results = {}
        if (payload[0] == 0xF0):
            results['STATUS'] = 0
        elif ((payload[0]) == 0xE0) or ((payload[0]) == 0xC0):
            results['STATUS'] = 1
        # Typo error in older Eltako Datasheet for 0x0D instead of the right 0xD0
        elif (payload[0] == 0xD0):
            results['STATUS'] = 2
        else:
            self.logger.error("enocean: error in F6_10_00 handle status, payload: {0} unknown".format(payload[0]))
        return results
