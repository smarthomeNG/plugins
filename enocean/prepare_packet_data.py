#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 Frank Häfele                       mail@frankhaefele.de
#########################################################################
#  Prepare Packet Data of Enocean plugin for SmartHomeNG.
#  https://github.com/smarthomeNG//
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################
import logging
from lib.utils import Utils



class Prepare_Packet_Data():

    def __init__(self, plugin_instance):
        """
        Init Method
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info('enocean-Prepare_Packet_Data-init: Init of Prepare_Packet_Data')
        # Get the plugin instance from encocean class
        self._plugin_instance = plugin_instance

    def CanDataPrepare(self, tx_eep):
        """
        This Method checks if there is an available Prepare Data Method for the tx_eep
        """
        found = callable(getattr(self, '_prepare_data_for_tx_eep_' + tx_eep, None))
        if (not found):
            self.logger.error('enocean-CanDataPrepare: missing tx_eep for pepare send data {} - there should be a _prepare_data_for_tx_eep_{}-function!'.format(tx_eep, tx_eep))
        return found

    def PrepareData(self, item, tx_eep):
        """
        This Method calculates the Data (id_offset, rorg, payload and optional data) for the
        corresponding EnOcean Device
        """
        self.logger.debug('enocean-PrepareData: data-preparer called with tx_eep = {}'.format(tx_eep))
        # Prepare ID-Offset
        if self._plugin_instance.has_iattr(item.conf, 'enocean_tx_id_offset'):
            self.logger.debug('enocean-PrepareData: item has valid enocean_tx_id_offset')
            id_offset = int(self._plugin_instance.get_iattr_value(item.conf, 'enocean_tx_id_offset'))
            if (id_offset < 0) or (id_offset > 127):
                self.logger.error('enocean-PrepareData: ID offset out of range (0-127). Aborting.')
                return None
        else:
            self.logger.info('enocean-PrepareData: {} item has no attribute ''enocean_tx_id_offset''! Set to default = 0'.format(tx_eep))
            id_offset = 0
        # start prepare data           
        rorg, payload, optional = getattr(self, '_prepare_data_for_tx_eep_' + tx_eep)(item, tx_eep)
        self.logger.info('enocean-PrepareData: {} returns [{:#04x}], [{}], [{}]'.format(tx_eep, rorg, ', '.join('{:#04x}'.format(x) for x in payload), ', '.join('{:#04x}'.format(x) for x in optional)))
        return id_offset, rorg, payload, optional


#####################################################
### --- Definitions for RORG =  A5 / ORG = 07 --- ###
### --> Definition of 4BS Telegrams               ###
#####################################################
    
    
    def _prepare_data_for_tx_eep_A5_20_04(self, item, tx_eep):
        """
        ### --- Data for radiator valve command --- ###
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xa5
        temperature = item()
        # define default values:
        MC  = 1 # off
        WUC = 3 # 120 seconds
        BLC = 0 # unlocked
        LRNB = 1 # data
        DSO = 0 # 0 degree
        valve_position = 50

        for sibling in get_children(item.parent):
            if hasattr(sibling, 'MC'):
                MC = sibling()
            if hasattr(sibling, 'WUC'):
                WUC = sibling()
            if hasattr(sibling, 'BLC'):
                BLC = sibling()
            if hasattr(sibling, 'LRNB'):
                LRNB = sibling()
            if hasattr(sibling, 'DSO'):
                DSO = sibling()
            if hasattr(sibling, 'VALVE_POSITION'):
                valve_position = sibling()
        TSP = int((temperature -10)*255/30)
        status =  0 + (MC << 1) + (WUC << 2) 
        status2 = (BLC << 5) + (LRNB << 4) + (DSO << 2)
        payload = [valve_position, TSP, status , status2]
        optional = []
        return rorg, payload, optional
    
    
    def _prepare_data_for_tx_eep_A5_38_08_01(self, item, tx_eep):    
        """
        ### --- Data for A5-38_08 command 1 --- ###
        Eltako Devices:
        FSR14-2x, FSR14-4x, FSR14SSR, FSR71 
        FSR61, FSR61NP, FSR61G, FSR61LN, FLC61NP
        This method has the function to prepare the packet data in case of switching device on or off
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xa5
        block = 0
        # check if item has attribute block_switch
        if self._plugin_instance.has_iattr(item.conf, 'block_switch'):
            block_value = self._plugin_instance.get_iattr_value(item.conf, 'block_switch')
            self.logger.debug('enocean-PrepareData: {} block_value has the value {}'.format(tx_eep, block_value))
            if Utils.to_bool(block_value):
                block = 4
        if not item():
            # if value is False --> Switch off
            payload = [0x01, 0x00, 0x00, int(8 + block)]
            self.logger.debug('enocean-PrepareData: {} prepare data to switch off'.format(tx_eep))
        else:
            payload = [0x01, 0x00, 0x00, int(9 + block)]
            self.logger.debug('enocean-PrepareData: {} prepare data to switch on'.format(tx_eep))
        optional = []
        return rorg, payload, optional
  
    
    def _prepare_data_for_tx_eep_A5_38_08_02(self, item, tx_eep):    
        """
        ### --- Data for A5-38_08 command 2 --- ###
        Eltako Devices:
        FDG14, FDG71L, FKLD61, FLD61, FRGBW71L, FSG14/1-10V, FSG71/1-10V
        FSUD-230V, FUD14, FUD14-800W, FUD61NP, FUD61NPN, FUD71
        This method has the function to prepare the packet data in case of switching the dimmer device on or off,
        but calculate also the correct data of dim_speed and dim_value for further solutions.
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xa5
        block = 0
        # check if item has attribute block_dim_value
        if self._plugin_instance.has_iattr(item.level.conf, 'block_dim_value'):
            block_value = self._plugin_instance.get_iattr_value(item.level.conf, 'block_dim_value')
            if Utils.to_bool(block_value):
                block = 4
        # check if item has attribite dim_speed
        if self._plugin_instance.has_iattr(item.level.conf, 'dim_speed'):
            dim_speed = self._plugin_instance.get_iattr_value(item.level.conf, 'dim_speed')
            # bound dim_speed values to [0 - 100] %
            dim_speed = max(0, min(100, int(dim_speed)))
            self.logger.debug('enocean-PrepareData: {} use dim_speed = {} %'.format(tx_eep, dim_speed))
            # calculate dimspeed from percent into integer
            # 0x01 --> fastest speed --> 100 %
            # 0xFF --> slowest speed --> 0 %
            dim_speed = (255 - (254 * dim_speed/100))
        else:
            # use intern dim_speed of the dim device
            dim_speed = 0
            self.logger.debug('enocean-PrepareData: no attribute dim_speed --> use intern dim speed')
        if not item():
            # if value is False --> Switch off
            dim_value = 0
            payload = [0x02, int(dim_value), int(dim_speed), int(8 + block)]
            self.logger.debug('enocean-PrepareData: prepare data to switch off for command for A5_38_08_02')
        else:
            # check if reference dim value exists
            if 'ref_level' in item.level.conf:
                dim_value = int(item.level.conf['ref_level'])
                # check range of dim_value [0 - 100] %
                dim_value = max(0, min(100, int(dim_value)))
                self.logger.debug('enocean-PrepareData: {} ref_level {} % found for A5_38_08_02'.format(tx_eep, dim_value))
            else:
                # set dim_value on 100 % == 0x64
                dim_value = 0x64
                self.logger.debug('enocean-PrepareData: {} no ref_level found! Setting to default 100 %'.format(tx_eep))
            payload = [0x02, int(dim_value), int(dim_speed), int(9 + block)]
        optional = []
        return rorg, payload, optional
        
    
    def _prepare_data_for_tx_eep_A5_38_08_03(self, item, tx_eep):    
        """
        ### --- Data for A5-38_08 command 3--- ###
        Eltako Devices:
        FDG14, FDG71L, FKLD61, FLD61, FRGBW71L, FSG14/1-10V, FSG71/1-10V
        FSUD-230V, FUD14, FUD14-800W, FUD61NP, FUD61NPN, FUD71
        This method has the function to prepare the packet data in case of dimming the light.
        In case of dim_value == 0 the dimmer is switched off.
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xa5
        block = 0
        # check if item has attribute block_dim_value
        if self._plugin_instance.has_iattr(item.conf, 'block_dim_value'):
            block_value = self._plugin_instance.get_iattr_value(item.conf, 'block_dim_value')
            if Utils.to_bool(block_value):
                block = 4
        # check if item has attribite dim_speed 
        if self._plugin_instance.has_iattr(item.conf, 'dim_speed'):
            dim_speed = self._plugin_instance.get_iattr_value(item.conf, 'dim_speed')
            # bound dim_speed values to [0 - 100] %
            dim_speed = max(0, min(100, int(dim_speed)))
            self.logger.debug('enocean-PrepareData: {} use dim_speed = {} %'.format(tx_eep, dim_speed))
            # calculate dimspeed from percent into hex
            # 0x01 --> fastest speed --> 100 %
            # 0xFF --> slowest speed --> 0 %
            dim_speed = (255 - (254 * dim_speed/100))
        else:
            # use intern dim_speed of the dim device
            dim_speed = 0x00
            self.logger.debug('enocean-PrepareData: {} no attribute dim_speed --> use intern dim speed',format(tx_eep))
        if item() == 0:
            # if value is == 0 switch off dimmer
            dim_value = 0x00
            payload = [0x02, int(dim_value), int(dim_speed), int(8 + block)]
            self.logger.debug('enocean-PrepareData: {} prepare data to switch off'.format(tx_eep))
        else:
            dim_value = item()
            # check range of dim_value [0 - 100] %
            dim_value = max(0, min(100, dim_value))
            self.logger.debug('enocean-PrepareData: {} dim_value set to {} %'.format(tx_eep, dim_value))
            dim_value = dim_value
            payload = [0x02, int(dim_value), int(dim_speed), int(9 + block)]
        optional = []
        return rorg, payload, optional
    
    
    def _prepare_data_for_tx_eep_A5_3F_7F(self, item, tx_eep):    
        """
        ### --- Data for A5-3F-7F - Universal Actuator Command --- ###
        Eltako Devices:
        FSB14, FSB61, FSB71
        This method has the function to prepare the packet data in case of actuation a shutter device.
        The Runtime is set in [0 - 255] s
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xa5
        block = 0
        # check if item has attribute block_switch
        if self._plugin_instance.has_iattr(item.conf, 'block_switch'):
            block_value = self._plugin_instance.get_iattr_value(item.conf, 'block_switch')
            if Utils.to_bool(block_value):
                block = 4
        # check if item has attribite enocean_rtime 
        if self._plugin_instance.has_iattr(item.conf, 'enocean_rtime'):
            rtime = self._plugin_instance.get_iattr_value(item.conf, 'enocean_rtime')
            # rtime [0 - 255] s
            rtime = max(0, min(255, int(rtime)))
            self.logger.debug('enocean-PrepareData: {} actuator runtime of {} s specified.'.format(tx_eep, rtime))
        else:
            # set rtime to 5 s
            rtime = 5
            self.logger.debug('enocean-PrepareData: {} actuator runtime not specified set to {} s.'.format(tx_eep, rtime)) 
        # check command (up, stop, or down)
        command = int(item())
        if(command == 0):
            # Stopp moving
            command_hex_code = 0x00
        elif(command == 1):
            # moving up
            command_hex_code = 0x01
        elif(command == 2):
            # moving down
            command_hex_code = 0x02
        else:
            self.logger.error('enocean-PrepareData: {} sending actuator command failed: invalid command {}'.format(tx_eep, command))
            return None
        # define payload
        payload = [0x00, rtime, command_hex_code, int(8 + block)]
        optional = []
        return rorg, payload, optional
        
    
    def _prepare_data_for_tx_eep_07_3F_7F(self, item, tx_eep):    
        """
        ### --- Data for 07-3F-7F Command --- ###
        Eltako Devices:
        Nur FRGBW71L: Freies Profi l (EEP 07-3F-7F)
        This method has the function to prepare the packet data for the RGB Dim device.
        See reference of Eltako device description.
        # Aufdimmen: [dim_speed, Color, 0x30, 0x0F]
        # Abdimmen:  [dim_speed, Color, 0x31, 0x0F]
        # Dimmstop:  [dim_speed, Color, 0x32, 0x0F]
        Color: bit0 = red, bit1= green, bit2 = blue, bit3 = white
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0x07
        # check if item has attribite dim_speed 
        if self._plugin_instance.has_iattr(item.conf, 'dim_speed'):
            dim_speed = self._plugin_instance.get_iattr_value(item.conf, 'dim_speed')
            dim_speed = max(0, min(100, int(dim_speed)))
            self.logger.debug('enocean-PrepareData: {} use dim_speed = {} %'.format(tx_eep, dim_speed))
            # calculate dimspeed from percent into hex
            # 0x01 --> fastest speed --> 100 %
            # 0xFF --> slowest speed --> 0 %
            dim_speed = (255 - (254 * dim_speed/100))
        else:
            # use intern dim_speed of the dim device
            dim_speed = 0x00
            self.logger.debug('enocean-PrepareData: {} no attribute dim_speed --> use intern dim speed'.format(tx_eep))
        # check the color of the item
        if self._plugin_instance.has_iattr(item.conf, 'color'):
            color = self._plugin_instance.get_iattr_value(item.conf, 'color')
            if (color == 'red'):
                color_hex = 0x01
            elif (color == 'green'):
                color_hex = 0x02
            elif (color == 'blue'):
                color_hex = 0x04
            elif (color == 'white'):
                color_hex = 0x08
        else:
            self.logger.error('enocean-PrepareData: {} has no attribute color --> please specify color!'.format(item))
            return None
        # Aufdimmen: [dim_speed, color_hex, 0x30, 0x0F]
        # Abdimmen:  [dim_speed, color_hex, 0x31, 0x0F]
        # Dimmstop:  [dim_speed, color_hex, 0x32, 0x0F]
        # check command (up, stop, or down)
        command = int(item())
        if(command == 0):
            # dim up
            command_hex_code = 0x30
        elif(command == 1):
            # dim down
            command_hex_code = 0x31
        elif(command == 2):
            # stop dim
            command_hex_code = 0x32
        else:
            self.logger.error('enocean-PrepareData: {} sending actuator command failed: invalid command {}'.format(tx_eep, command))
            return None
        # define payload
        payload = [int(dim_speed), color_hex, command_hex_code, 0x0F]
        optional = []
        return rorg, payload, optional
    
   
#############################################################
### --- Definitions for RORG = D2                     --- ###
### --> Definition EnOcean Variable Length Telegram (VLD) ###
#############################################################

    def _prepare_data_for_tx_eep_D2_01_07(self, item, tx_eep):    
        """
        ### --- Data for D2_01_07 (VLD) --- ###
        Prepare data for Devices with Varable Length Telegram.
        There is currently no device information available. 
        Optional 'pulsewidth' - Attribute was removed, it can be realized with the smarthomeNG    
        build in function autotimer!
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xD2
        SubTel = 0x03
        db = 0xFF
        Secu = 0x0
        if self._plugin_instance.has_iattr(item.conf, 'enocean_rx_id'):
            rx_id = int(self._plugin_instance.get_iattr_value(item.conf, 'enocean_rx_id'), 16)
            if (rx_id < 0) or (rx_id > 0xFFFFFFFF):
                self.logger.error('enocean-PrepareData: {} rx-ID-Offset out of range (0-127). Aborting.'.format(tx_eep))
                return None
            self.logger.debug('enocean-PrepareData: {} enocean_rx_id found.'.format(tx_eep))
        else:
            rx_id = 0
            self.logger.debug('enocean-PrepareData: {} no enocean_rx_id found!'.format(tx_eep))
        # Prepare Data Packet
        if (item() == 0):
            payload = [0x01, 0x1E, 0x00]
            optional = [SubTel, rx_id, db, Secu]
        elif (item() == 1):
            payload = [0x01, 0x1E, 0x01]
            optional = [SubTel, rx_id, db, Secu]
        else:
            self.logger.error('enocean-PrepareData: {} undefined Value. Error!'.format(tx_eep))
            return None
        # packet_data_prepared = (id_offset, 0xD2, payload, [0x03, 0xFF, 0xBA, 0xD0, 0x00, 0xFF, 0x0])
        self.logger.info('enocean-PrepareData: {} Packet Data Prepared for {} (VLD)'.format(tx_eep, tx_eep))
        optional = [SubTel, rx_id, db, Secu]
        return rorg, payload, optional

    def _prepare_data_for_tx_eep_D2_01_12(self, item, tx_eep):
        """
        ### --- Data for D2_01_12 (VLD) --- ###
        Prepare data for Devices with Varable Length Telegram.
        There is currently no device information available.
        Optional 'pulsewidth' - Attribute was removed, it can be realized with the smarthomeNG
        build in function autotimer!
        """
        self.logger.debug('enocean-PrepareData: prepare data for tx_eep {}'.format(tx_eep))
        rorg = 0xD2
        SubTel = 0x03
        db = 0xFF
        Secu = 0x0
        if self._plugin_instance.has_iattr(item.conf, 'enocean_rx_id'):
            rx_id = int(self._plugin_instance.get_iattr_value(item.conf, 'enocean_rx_id'), 16)
            if (rx_id < 0) or (rx_id > 0xFFFFFFFF):
                self.logger.error('enocean-PrepareData: {} rx-ID-Offset out of range (0-127). Aborting.'.format(tx_eep))
                return None
            self.logger.debug('enocean-PrepareData: {} enocean_rx_id found.'.format(tx_eep))
        else:
            rx_id = 0
            self.logger.debug('enocean-PrepareData: {} no enocean_rx_id found!'.format(tx_eep))
        if self._plugin_instance.has_iattr(item.conf, 'enocean_channel'):
            schannel = self._plugin_instance.get_iattr_value(item.conf, 'enocean_channel')
            if (schannel == "A"):
                channel = 0x00
            elif (schannel == "B"):
                channel = 0x01
            else:
                channel = 0x1E
            self.logger.debug('enocean-PrepareData: {} enocean_channel found: %s '.format(tx_eep), schannel)
        else:
            channel = 0x1E
            self.logger.debug('enocean-PrepareData: {} no enocean_channel found!'.format(tx_eep))
        # Prepare Data Packet
        if (item() == 0):
            payload = [0x01, channel, 0x00]
            optional = [SubTel, rx_id, db, Secu]
        elif (item() == 1):
            payload = [0x01, channel, 0x01]
            optional = [SubTel, rx_id, db, Secu]
        else:
            self.logger.error('enocean-PrepareData: {} undefined Value. Error!'.format(tx_eep))
            return None
        # packet_data_prepared = (id_offset, 0xD2, payload, [0x03, 0xFF, 0xBA, 0xD0, 0x00, 0xFF, 0x0])
        self.logger.info('enocean-PrepareData: {} Packet Data Prepared for {} (VLD)'.format(tx_eep, tx_eep))
        optional = [SubTel, rx_id, db, Secu]
        return rorg, payload, optional
