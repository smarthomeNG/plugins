#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2018 Sebastian Faulhaber          sebastian.faulhaber@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
#  upwards.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

from lib.module import Modules
from lib.model.smartplugin import *
from libsoundtouch import soundtouch_device
from libsoundtouch.utils import Source, Type

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class BoseSoundtouch(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """
    # Plugin parameters
    PLUGIN_VERSION = '1.0.1'
    PLUGIN_PARAMETER_IP = None
    PLUGIN_PARAMETER_PORT = None

    # Misc constants
    ITEM_ACTION_ATTR = 'bose_soundtouch_action'
    BOSE_STATE_STANDBY = 'STANDBY'
    BOSE_CMD_PLAY = 'PLAY'
    BOSE_CMD_PAUSE = 'PAUSE'
    BOSE_CMD_MUTE = 'MUTE'
    BOSE_CMD_NEXT_TRACK = 'NEXT_TRACK'
    BOSE_CMD_PREVIOUS_TRACK = 'PREVIOUS_TRACK'
    BOSE_CMD_SHUFFLE_ON = 'SHUFFLE_ON'
    BOSE_CMD_SHUFFLE_OFF = 'SHUFFLE_OFF'
    BOSE_CMD_REPEAT_ALL = 'REPEAT_ALL'
    BOSE_CMD_REPEAT_OFF = 'REPEAT_OFF'

    def __init__(self, sh, *args, **kwargs):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        # If an package import with try/except is done, handle an import error like this:

        # Exit if the required package(s) could not be imported
        # if not REQUIRED_PACKAGE_IMPORTED:
        #     self.logger.error("Unable to import Python package '<exotic package>'")
        #     self._init_complete = False
        #     return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.PLUGIN_PARAMETER_IP = self.get_parameter_value('ip')
        self.PLUGIN_PARAMETER_PORT = self.get_parameter_value('port')

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = self.get_parameter_value('cycle_time')

        #######################################################################
        # BOSE SOUNDTOUCH INITIALIZATION
        #######################################################################
        # Connect to device
        try:
            self.device = soundtouch_device(self.PLUGIN_PARAMETER_IP, self.PLUGIN_PARAMETER_PORT)
            self.logger.info("Initialized connection to Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "' at " + self.getSoundtouchDevice().config.device_ip)
        except Exception as e:
            self.logger.error("Fatal error during plugin initialization.")
            self.logger.error(e)
            self._init_complete = False

        #######################################################################

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # The following part of the __init__ method is only needed, if a webinterface is being implemented:

        # if plugin should start even without web interface
        # self.init_webinterface()

        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, self.ITEM_ACTION_ATTR):
            self.logger.debug("Parse item: {}".format(item))
            # Update item
            return self.update_item

    def parse_logic(self, logic):
        # NOT USED AT THE MOMENT
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != self.get_shortname():
            # code to execute, only if the item has not been changed by this this plugin:
            self.logger.debug("Update item: {}, item has been changed outside this plugin".format(item.id()))

            if self.has_iattr(item.conf, self.ITEM_ACTION_ATTR):
                action = self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR)
                self.logger.debug("Update item: was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item, caller, source, dest))
                self.logger.debug("Update item: Action = " + action + ", Item type = " + str(type(item())) + ", Item value = " + str(item()))

                # Execute logic according to requested action
                if (action == 'status.standby' and item() is False) or (action == 'actions.power_on'):
                    self.powerOnSoundtouch()
                elif (action == 'status.standby' and item() is True) or (action == 'actions.power_off'):
                    self.powerOffSoundtouch()
                elif action == 'actions.select_preset':
                    self.selectSoundtouchPreset(item())
                elif action == 'actions.play':
                    self.sendSoundtouchCommand(self.BOSE_CMD_PLAY)
                elif action == 'actions.pause':
                    self.sendSoundtouchCommand(self.BOSE_CMD_PAUSE)
                elif action == 'actions.mute':
                    self.sendSoundtouchCommand(self.BOSE_CMD_MUTE)
                elif action == 'actions.next_track':
                    self.sendSoundtouchCommand(self.BOSE_CMD_NEXT_TRACK)
                elif action == 'actions.previous_track':
                    self.sendSoundtouchCommand(self.BOSE_CMD_PREVIOUS_TRACK)
                elif action == 'actions.shuffle':
                    if item() is True:
                        self.sendSoundtouchCommand(self.BOSE_CMD_SHUFFLE_ON)
                    else:
                        self.sendSoundtouchCommand(self.BOSE_CMD_SHUFFLE_OFF)
                elif action == 'actions.repeat_all':
                    self.sendSoundtouchCommand(self.BOSE_CMD_REPEAT_ALL)
                elif action == 'actions.repeat_off':
                    self.sendSoundtouchCommand(self.BOSE_CMD_REPEAT_OFF)
                elif action == 'volume.actual':
                    self.setSoundtouchVolume(item())

                self.logger.debug("Update item: finished with Action = " + action)
            pass

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler.
        """
        # Update status
        self.updateSoundtouchStatus()
        self.updateSoundtouchPresets()
        self.updateSoundtouchVolume()
        pass

    def getSoundtouchDevice(self):
        return self.device

    def updateSoundtouchStatus(self):
        status = None
        self.logger.debug("Updating Soundtouch Status...")
        for item in self.get_sh().find_items(self.ITEM_ACTION_ATTR):
            if status is None:
                status = self.getSoundtouchDevice().status()
            if self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.album':
                item(status.album, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.artist':
                item(status.artist, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.description':
                item(status.description, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.image':
                item(status.image, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.source':
                item(status.source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.standby':
                if status.source == self.BOSE_STATE_STANDBY:
                    item(True, self.get_shortname())
                else:
                    item(False, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'status.track':
                item(status.track, self.get_shortname())

    def updateSoundtouchVolume(self):
        volume = None
        self.logger.debug("Updating Soundtouch Volume...")
        for item in self.get_sh().find_items(self.ITEM_ACTION_ATTR):
            if volume is None:
                volume = self.getSoundtouchDevice().volume()
            if self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'volume.actual':
                item(volume.actual, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'volume.muted':
                item(volume.muted, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'volume.target':
                item(volume.target, self.get_shortname())

    def updateSoundtouchPresets(self):
        presets = None
        self.logger.debug("Updating Soundtouch Presets...")
        for item in self.get_sh().find_items(self.ITEM_ACTION_ATTR):
            if presets is None:
                presets = self.getSoundtouchDevice().presets()
            if self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.0.name' and len(presets) > 0:
                item(presets[0].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.0.preset_id' and len(presets) > 0:
                item(presets[0].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.0.source' and len(presets) > 0:
                item(presets[0].source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.1.name' and len(presets) > 1:
                item(presets[1].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.1.preset_id' and len(presets) > 1:
                item(presets[1].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.1.source' and len(presets) > 1:
                item(presets[1].source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.2.name' and len(presets) > 2:
                item(presets[2].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.2.preset_id' and len(presets) > 2:
                item(presets[2].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.2.source' and len(presets) > 2:
                item(presets[2].source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.3.name' and len(presets) > 3:
                item(presets[3].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.3.preset_id' and len(presets) > 3:
                item(presets[3].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.3.source' and len(presets) > 3:
                item(presets[3].source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.4.name' and len(presets) > 4:
                item(presets[4].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.4.preset_id' and len(presets) > 4:
                item(presets[4].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.4.source' and len(presets) > 4:
                item(presets[4].source, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.5.name' and len(presets) > 5:
                item(presets[5].name, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.5.preset_id' and len(presets) > 5:
                item(presets[5].preset_id, self.get_shortname())
            elif self.get_iattr_value(item.conf, self.ITEM_ACTION_ATTR) == 'presets.5.source' and len(presets) > 5:
                item(presets[5].source, self.get_shortname())

    def powerOnSoundtouch(self):
        self.logger.info("Powering on Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "'.")
        self.getSoundtouchDevice().power_on()

    def powerOffSoundtouch(self):
        self.logger.info("Powering off Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "'.")
        self.getSoundtouchDevice().power_off()

    def setSoundtouchVolume(self, volume):
        self.logger.info("Setting volume to '" + str(volume) + "' for Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "'.")
        self.getSoundtouchDevice().set_volume(volume)

    def sendSoundtouchCommand(self, command):
        self.logger.info("Sending command '" + command + "' to Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "'.")
        if command == self.BOSE_CMD_PLAY:
            self.getSoundtouchDevice().play()
        elif command == self.BOSE_CMD_PAUSE:
            self.getSoundtouchDevice().pause()
        elif command == self.BOSE_CMD_MUTE:
            self.getSoundtouchDevice().mute()
        elif command == self.BOSE_CMD_NEXT_TRACK:
            self.getSoundtouchDevice().next_track()
        elif command == self.BOSE_CMD_PREVIOUS_TRACK:
            self.getSoundtouchDevice().previous_track()
        elif command == self.BOSE_CMD_SHUFFLE_ON:
            self.getSoundtouchDevice().shuffle(True)
        elif command == self.BOSE_CMD_SHUFFLE_OFF:
            self.getSoundtouchDevice().shuffle(False)
        elif command == self.BOSE_CMD_REPEAT_ALL:
            self.getSoundtouchDevice().repeat_all()
        elif command == self.BOSE_CMD_REPEAT_OFF:
            self.getSoundtouchDevice().repeat_off()

    def selectSoundtouchPreset(self, preset_id):
        self.logger.info("Selecting preset '" + str(preset_id) + "' for Bose Soundtouch device '" + self.getSoundtouchDevice().config.name + "'.")
        presets = self.getSoundtouchDevice().presets()
        self.getSoundtouchDevice().select_preset(presets[preset_id])
