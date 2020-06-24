import binascii
import hashlib
import hmac
import locale
import time
import requests
import logging

from lib.model.smartplugin import *


class Robot:
    def __init__(self, email, password, vendor):
        self.logger = logging.getLogger(__name__)
        self.__email = email
        self.__password = password
        self.__vendor = ''

        if (vendor.lower() == 'neato'):
            self.__urlBeehive = "https://beehive.neatocloud.com"
            self.__vendor = 'neato'
        elif (vendor.lower() == 'vorwerk'):
            self.__urlBeehive = "https://beehive.ksecosys.com/"
            self.__vendor = 'vorwerk'
        else:
            self.logger.error("Robot: No or wrong vendor defined!")

        self.__urlNucleo = ""
        self.__secretKey = ""

        self._session = requests.Session()
        self._timeout = 10


        # Cleaning
        self.category = ''
        self.mode = ''
        self.modifier = ''
        self.navigationMode = ''
        self.spotWidth = ''
        self.spotHeight = ''

        # Meta
        self.name = ""
        self.serial = ""
        self.modelname = ""
        self.firmware = ""

        # Neato Details
        self.isCharging = False
        self.isDocked = False
        self.isScheduleEnabled = False
        self.dockHasBeenSeen = None
        self.chargePercentage = ''
        self.isCleaning = None

        self.state = '0'
        self.state_action = '0'

        # Neato Available Services
        self.findMe = ''
        self.generalInfo = ''
        self.houseCleaning = ''
        self.IECTest = ''
        self.logCopy = ''
        self.maps = ''
        self.preferences = ''
        self.schedule = ''
        self.softwareUpdate = ''
        self.spotCleaning = ''
        self.wifi = ''

    # Neato Available Commands
    def robot_command(self, command):
        if command == 'start':
            n = self.__cleaning_start_string()
        elif command == 'pause':
            n = '{"reqId": "77","cmd": "pauseCleaning"}'
        elif command == 'resume':
            n = '{"reqId": "77","cmd": "resumeCleaning"}'
        elif command == 'stop':
            n = '{"reqId": "77","cmd": "stopCleaning"}'
        elif command == 'findme':
            n = '{"reqId": "77","cmd": "findMe"}'
        elif command == 'sendToBase':
            n = '{"reqId": "77","cmd": "sendToBase"}'
        elif command == 'enableSchedule':
            n = '{"reqId": "77","cmd": "enableSchedule"}'
        elif command == 'disableSchedule':
            n = '{"reqId": "77","cmd": "disableSchedule"}'
        else:
            self.logger.warning("Robot: Command unknown '{}'".format(command))
            return None
        message = self.serial.lower() + '\n' + self.__get_current_date() + '\n' + n
        h = hmac.new(self.__secretKey.encode('utf-8'), message.encode('utf8'), hashlib.sha256)

#        start_cleaning_response = requests.post(
#            self.__urlNucleo + "/vendors/"+self.__vendor+"/robots/" + self.serial + "/messages", data=n,
#            headers={'X-Date': self.__get_current_date(), 'X-Agent': 'ios-7|iPhone 4|0.11.3-142',
#                     'Date': self.__get_current_date(), 'Accept': 'application/vnd.neato.nucleo.v1',
#                     'Authorization': 'NEATOAPP ' + h.hexdigest()}, )

        start_cleaning_response = self._session.post(
            self.__urlNucleo + "/vendors/"+self.__vendor+"/robots/" + self.serial + "/messages", data=n,
            headers={'X-Date': self.__get_current_date(), 'X-Agent': 'ios-7|iPhone 4|0.11.3-142',
                     'Date': self.__get_current_date(), 'Accept': 'application/vnd.neato.nucleo.v1',
                     'Authorization': 'NEATOAPP ' + h.hexdigest()}, timeout=self._timeout )
        

        #error handling
        responseJson = start_cleaning_response.json()
        self.logger.debug("Debug: send command response: {0}".format(start_cleaning_response.text))

        if 'result' in responseJson:
            if str(responseJson['result']) == 'ok':
                self.logger.debug("Sending command successful")
        else:
            if 'message' in responseJson:
                self.logger.error("Sending command failed. Message: {0}".format(str(responseJson['message'])))
            if 'error' in responseJson:
                self.logger.error("Sending command failed. Error: {0}".format(str(responseJson['error'])))

        # - NOT on Charge BASE
        return start_cleaning_response

    def update_robot(self):
        #self.logger.debug("Robot: Starting update_robot")

        self.__secretKey = self.__get_secret_key()
        if not self.__secretKey:
            self.logger.error("Robot: Could not obtain valid secret key")
            return 'error'

        m = '{"reqId":"77","cmd":"getRobotState"}'
        message = self.serial.lower() + '\n' + self.__get_current_date() + '\n' + m
        h = hmac.new(self.__secretKey.encode('utf-8'), message.encode('utf8'), hashlib.sha256)
        try:
            robot_cloud_state_response = self._session.post(self.__urlNucleo + "/vendors/"+self.__vendor+"/robots/" + self.serial + "/messages",
                                                    data=m, headers={'X-Date': self.__get_current_date(),
                                                                     'X-Agent': 'ios-7|iPhone 4|0.11.3-142',
                                                                     'Date': self.__get_current_date(),
                                                                     'Accept': 'application/vnd.neato.nucleo.v1',
                                                                     'Authorization': 'NEATOAPP ' + h.hexdigest()}, timeout=self._timeout )
 
        except:
            self.logger.warning("Robot: Error during API request unknown '{}'")
            # todo error handling_
            return 'error'

        response = robot_cloud_state_response.json()

        #Error message:
        if 'message' in response:
            #self.logger.warning("Message: {0}".format(robot_cloud_state_response.text))
            self.logger.warning("Message: {0}".format(str(response['message'])))
        # Status
        if 'state' in response:
            self.state = str(response['state'])
        if 'action' in response:
            self.state_action = str(response['action'])

        # get the Details first
        if 'details' in response:
            self.isCharging = response['details']['isCharging']
            self.isDocked = response['details']['isDocked']
            self.isScheduleEnabled = response['details']['isScheduleEnabled']
            self.dockHasBeenSeen = response['details']['dockHasBeenSeen']
            self.chargePercentage = response['details']['charge']

        # get available services for robot second
        if 'availableServices' in response:
            self.findMe = response['availableServices']['findMe']
            self.generalInfo = response['availableServices']['generalInfo']
            self.houseCleaning = response['availableServices']['houseCleaning']
            self.IECTest = response['availableServices']['IECTest']
            self.logCopy = response['availableServices']['logCopy']
            self.maps = response['availableServices']['maps']
            self.preferences = response['availableServices']['preferences']
            self.schedule = response['availableServices']['schedule']
            self.softwareUpdate = response['availableServices']['softwareUpdate']
            self.spotCleaning = response['availableServices']['spotCleaning']
            self.wifi = response['availableServices']['wifi']

        # Cleaning Config
        if 'cleaning' in response:
            self.category = response['cleaning']['category']
            self.mode = response['cleaning']['mode']
            self.modifier = response['cleaning']['modifier']
            self.navigationMode = response['cleaning']['navigationMode']
            self.spotWidth = response['cleaning']['spotWidth']
            self.spotHeight = response['cleaning']['spotHeight']

        return response

    def __get_access_token(self):
        #self.logger.debug("Robot: Getting access token")

        json_data = {'email': self.__email, 'password': self.__password, 'platform': 'ios',
                     'token': binascii.hexlify(os.urandom(64)).decode('utf8')}
        try:
            access_token_response = self._session.post(self.__urlBeehive + "/sessions", json=json_data,
                                              headers={'Accept': 'application/vnd.neato.nucleo.v1+json'}, timeout=self._timeout)
        except Exception as e:
            self.logger.error("Robot: Exception during access token request: %s" % str(e))
            return ''
                
        responseJson = access_token_response.json()
        self.logger.debug("Robot Debug: responseTokenRequest: {0}".format(responseJson))
        if 'access_token' in responseJson:
            access_token = responseJson['access_token']
            self.logger.debug("Robot: Access token received")
        else:
            access_token = ''
            if 'message' in responseJson:
                messageText = responseJson['message']
                self.logger.error("Failed to receive access token. Message: {0}".format(messageText))
            else:
                self.logger.error("Failed to receive access token.")

        return access_token

    def __get_secret_key(self):
        #self.logger.debug("Robot: Retrieving secret key")
        secret_key = ''
        access_token = self.__get_access_token()
        if not access_token:
            return secret_key

        auth_data = {'Authorization': 'Token token=' + access_token}
        
        try:
            secret_key_response = self._session.get(self.__urlBeehive + "/users/me/robots", data=auth_data,
                                           headers={'Authorization': 'Bearer ' + access_token}, timeout=self._timeout)
        except Exception as e:
            self.logger.error("Robot: Exception during secret key request: %s" % str(e))
            return ''

        secret_key = secret_key_response.json()[0]['secret_key']
        self.serial = secret_key_response.json()[0]['serial']
        self.name = secret_key_response.json()[0]['name']
        self.__urlNucleo = secret_key_response.json()[0]['nucleo_url']
        self.modelname = secret_key_response.json()[0]['model']
        self.firmware = secret_key_response.json()[0]['firmware']
        #self.logger.debug("Robot: secret key retrieved")

        return secret_key

    def __get_current_date(self):
        saved_locale = locale.getlocale(locale.LC_TIME)
        try:
            locale.setlocale(locale.LC_TIME, 'en_US.utf8')
        except locale.Error as e:
            self.logger.error("Robot: Locale setting Error. Please install locale en_US.utf8: "+e)
            return None
        date = time.strftime('%a, %d %b %Y %H:%M:%S', time.gmtime()) + ' GMT'
        locale.setlocale(locale.LC_TIME, saved_locale)
        return date

    def __cleaning_start_string(self):
        if self.houseCleaning == 'basic-1':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                self.category) + ',"mode": ' + str(self.mode) + ', "modifier": ' + str(self.modifier) + '}}'
        if self.houseCleaning == 'minimal-2':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                self.category) + ',"navigationMode": ' + str(self.navigationMode) + '}}'
        if self.houseCleaning == 'minimal-3':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                self.category) + ',"navigationMode": ' + str(self.navigationMode) + '}}'
        if self.houseCleaning == 'basic-3':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                self.category) + ',"mode": ' + str(self.mode) + ', "navigationMode": ' + str(self.navigationMode) + '}}'
        if self.houseCleaning == 'basic-4':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                self.category) + ',"mode": ' + str(self.mode) + ', "navigationMode": ' + str(self.navigationMode) + '}}'
