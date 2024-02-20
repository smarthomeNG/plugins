import binascii
import hashlib
import hmac
import locale
import time
import requests
import json
import logging

from lib.model.smartplugin import *


class Robot:
    def __init__(self, email, password, vendor, token = ''):
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
        self._verifySSL = False
        self._token = token
        self._clientIDHash = 'KY4YbVAvtgB7lp8vIbWQ7zLk3hssZlhR'
        self._numberRobots = 0
        self._backendOnline = False

        # Cleaning
        self.category = ''
        self.mode = ''
        self.modifier = ''
        self.navigationMode = ''
        self.spotWidth = ''
        self.spotHeight = ''
        self.mapId = 'unknown'

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
        self.chargePercentage = 0
        self.isCleaning = None

        self.state = '0'
        self.state_action = '0'
        self.alert = '-'


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

        # Neato Available commands:
        self.commandStartAvailable = False
        self.commandStopAvailable = False
        self.commandPausetAvailable = False
        self.commandResumeAvailable = False
        self.commandGoToBaseAvailable = False

    def numberRobots(self):
        return self._numberRobots

    def clientIDHash(self):
        return self._clientIDHash 

    def setClientIDHash(self, hash):
        self._clientIDHash = hash

    # Send command to robot. Return None if not successful   
    def robot_command(self, command, arg1 = None, arg2 = None):

        if self.__secretKey == '':
            self.logger.warning("Robot: Cannot execute command. SecretKey still invalid. Aborting.")
            return None

        log_message = False

        # Neato Available Commands
        if command == 'start':
            n = self.__cleaning_start_string(arg1, arg2 )
        elif command == 'start_non-persistent-map':
            n = self.__cleaning_start_string(fallback_category=2)
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
        elif command == 'getMapBoundaries':
            jsonCommand  = {"reqId": "1", "cmd": "getMapBoundaries", "params": {"mapId": str(arg1)}}
            n = json.dumps(jsonCommand)
            log_message = True
        elif command == 'dismiss_current_alert':
            n = '{"reqId": "2", "cmd": "dismissCurrentAlert"}'
        else:
            self.logger.warning("Robot: Command unknown {0}".format(command))
            return None

        self.logger.debug("Robot: Json Command {0}".format(n))
        message = self.serial.lower() + '\n' + self.__get_current_date() + '\n' + n
        h = hmac.new(self.__secretKey.encode('utf-8'), message.encode('utf8'), hashlib.sha256)

        try:
            start_cleaning_response = self._session.post(
                self.__urlNucleo + "/vendors/"+self.__vendor+"/robots/" + self.serial + "/messages", data=n,
                headers={'X-Date': self.__get_current_date(), 'X-Agent': 'ios-7|iPhone 4|0.11.3-142',
                     'Date': self.__get_current_date(), 'Accept': 'application/vnd.neato.nucleo.v1',
                     'Authorization': 'NEATOAPP ' + h.hexdigest()}, timeout=self._timeout, verify=self._verifySSL )
        except Exception as e:
            self.logger.error("Robot: Exception during command request: %s" % str(e))
            return None

        #error handling
        responseJson = start_cleaning_response.json()
        self.logger.debug("Debug: send command response: {0}".format(start_cleaning_response.text))
        if log_message:
            self.logger.warning("INFO: Requested Info: {0}".format(start_cleaning_response.text))

        if 'result' in responseJson:
            if str(responseJson['result']) == 'ok':
                self.logger.debug("Sending command successful")
            elif str(responseJson['result']) == 'not_on_charge_base':
                self.logger.warning(f"Command returned {str(responseJson['result'])}: Retry starting with non-persistent-map")
                return self.robot_command(command = 'start_non-persistent-map')
            else:
                self.logger.error(f"Sending command {command} failed. Result: {str(responseJson['result'])}")
                self.logger.error(f"Debug: send command response: {start_cleaning_response.text}")
        else:
            if 'message' in responseJson:
                self.logger.error(f"Sending command {command} failed. Message: {str(responseJson['message'])}")
            if 'error' in responseJson:
                self.logger.error(f"Sending command {command} failed. Error: {str(responseJson['error'])}")

        # - NOT on Charge BASE
        return start_cleaning_response

    def update_robot(self):
        #self.logger.debug("Robot: Starting update_robot")

        # Authentication via email and passwort:
        if self._token == '':
            self.logger.debug("Robot: Using user/password interface")
            self.__secretKey = self.__get_secret_key()

        # Oauth2 Authentication via email and token (for Vorwerk only):    
        else:
            self.logger.debug("Robot: Using oAuth2 interface")
            if self.__secretKey == '':
                self.logger.info("Robot: Secret key is invalid. Requesting new one via token")
                self.__secretKey = self.get_secretKey_viaOauth()
                self.logger.debug("Robot: SecretKey is {0}".format(self.__secretKey))

        if self.__secretKey == '':
            self.logger.warning("Robot: Still no valid secret key. Aborting update fct.")
            self._backendOnline = False
            return 'error'

        #self.logger.debug("Returned secret key is {0}".format(self.__secretKey))

        m = '{"reqId":"77","cmd":"getRobotState"}'
        message = self.serial.lower() + '\n' + self.__get_current_date() + '\n' + m
        h = hmac.new(self.__secretKey.encode('utf-8'), message.encode('utf8'), hashlib.sha256)
        try:
            robot_cloud_state_response = self._session.post(self.__urlNucleo + "/vendors/"+self.__vendor+"/robots/" + self.serial + "/messages",
                                                    data=m, headers={'X-Date': self.__get_current_date(),
                                                                     'X-Agent': 'ios-7|iPhone 4|0.11.3-142',
                                                                     'Date': self.__get_current_date(),
                                                                     'Accept': 'application/vnd.neato.nucleo.v1',
                                                                     'Authorization': 'NEATOAPP ' + h.hexdigest()}, timeout=self._timeout, verify=self._verifySSL )
        except requests.exceptions.ConnectionError as e:
            self.logger.warning("Robot: Connection error: %s" % str(e))
            self._backendOnline = False
            return 'error'
        except requests.exceptions.Timeout as e:
            self.logger.warning("Robot: Timeout exception during cloud state request: %s" % str(e))
            self._backendOnline = False
            return 'error'
        except Exception as e:
            self.logger.error("Robot: Exception during cloud state request: %s" % str(e))
            self._backendOnline = False
            return 'error'

        statusCode = robot_cloud_state_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending cloud state request successful")
            self._backendOnline = True
        elif statusCode == 403:
            self.logger.debug("Sending cloud state request returned: Forbidden. Aquire new session key.")
        elif statusCode == 404:
            self.logger.warning("Robot is not reachable for backend. Is robot online?")
            return 'error'
        elif statusCode == 500:
            self.logger.warning(f"Internal Backend Server Error 500, Optional message: {robot_cloud_state_response.text}")
            return 'error'
        else:
            self.logger.error(f"Sending cloud state request error: {statusCode}, msg: {robot_cloud_state_response.text}")
            return 'error'

        response = robot_cloud_state_response.json()
        self.logger.debug("Robot update_robot: {0}".format(response))

        #Error message:
        if 'message' in response:
            self.logger.warning("Message: {0}".format(str(response['message'])))

        if 'error' in response and response['error']:
            if response['error'] == 'gen_picked_up':
                self.logger.warning("Robot: Picked-up")
            else:
                self.logger.error("Robot: Error {0}".format(str(response['error'])))

        # Readout alert messages, e.g. dustbin_full
        if 'alert' in response:
            if response['alert']:
                if self.alert != str(response['alert']):
                    self.logger.warning("Robot: Alert {0}".format(str(response['alert'])))
                self.alert = str(response['alert'])
            else:
                self.alert = '-'
        # Status
        if 'state' in response:
            self.state = str(response['state'])
        if 'action' in response:
            self.state_action = str(response['action'])

        # get the Details 
        if 'details' in response:
            self.isCharging = response['details']['isCharging']
            self.isDocked = response['details']['isDocked']
            self.isScheduleEnabled = response['details']['isScheduleEnabled']
            self.dockHasBeenSeen = response['details']['dockHasBeenSeen']
            self.chargePercentage = response['details']['charge']

        # get available commands for robot 
        if 'availableCommands' in response:
            self.commandStartAvailable = response['availableCommands']['start']
            self.commandStopAvailable = response['availableCommands']['stop']
            self.commandPausetAvailable = response['availableCommands']['pause']
            self.commandResumeAvailable = response['availableCommands']['resume']
            self.commandGoToBaseAvailable = response['availableCommands']['goToBase']

        # get available services for robot 
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
            if 'mapId' in response['cleaning']:
                self.mapId = response['cleaning']['mapId']

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
        if 'access_token' in responseJson:
            access_token = responseJson['access_token']
            #self.logger.debug("Robot: Access token received")
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
            return secret_key

        statusCode = secret_key_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending secret key request successful")
        else:
            self.logger.error("Sending secret key request error: {0}".format(statusCode))
            return ''

        if not secret_key_response.json():
            return ''

        self.logger.debug("secretkeyresponse: {0}".format(secret_key_response.json()))        
        self.logger.debug("secretkeyresponse0: {0}".format(secret_key_response.json()[0]))        

        # TODO readout number of robots. As a workaround set hardcoded to 1:
        self._numberRobots = 1

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
            self.logger.error("Robot: Locale setting error. Please install locale en_US.utf8: "+e)
            return None
        date = time.strftime('%a, %d %b %Y %H:%M:%S', time.gmtime()) + ' GMT'
        locale.setlocale(locale.LC_TIME, saved_locale)
        return date

    def __cleaning_start_string(self, boundary_id=None, map_id=None, fallback_category=None):
        # mode & navigation_mode used if applicable to service version
        # mode: 1 eco, 2 turbo
        # boundary_id: the id of the zone to clean
        # map_id: the id of the map to clean
        # category: 2 non-persistent map, 4 persistent map

        self.logger.debug("Robot: houseCleaning {0}, spotCleaning {1}".format(self.houseCleaning, self.spotCleaning ))

        local_category = self.category

        if ( (local_category is None) or (local_category == '') or (local_category != 4 and local_category != 2)):
            # Default to using the persistent map if we support basic-3 or basic-4.
            if self.houseCleaning in ["basic-3", "basic-4"]:
                local_category = 4
            else:
                local_category = 2

            self.logger.info("Robot: category changed for send command from {0} (received) to {1}".format(self.category, local_category ))

        # If external fallback category is given, overwrite local_category:
        # This feature is needed for instance if this method shall be triggered explicitly for using the non-persistant map (category = 2)
        if fallback_category != None:
            self.logger.info(f"Robot: category changed via external category for send command from {local_category} (received) to {fallback_category}")
            local_category = fallback_category
  
        if self.houseCleaning == 'basic-1':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                local_category) + ',"mode": ' + str(self.mode) + ', "modifier": ' + str(self.modifier) + '}}'
        if self.houseCleaning == 'minimal-2':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                local_category) + ',"navigationMode": ' + str(self.navigationMode) + '}}'
        if self.houseCleaning == 'minimal-3':
            return '{"reqId": "77","cmd": "startCleaning","params": {"category": ' + str(
                local_category) + ',"navigationMode": ' + str(self.navigationMode) + '}}'
        if self.houseCleaning in ["basic-3", "basic-4"]:
            jsonCommand = {
                "reqId": "77",
                "cmd": "startCleaning",
                "params": {
                    "category": str(local_category),
                    "mode": str(self.mode),
                    "navigationMode": str(self.navigationMode)}}
            if boundary_id:
                jsonCommand ["params"]["boundaryId"] = boundary_id
            if map_id:
                jsonCommand ["params"]["mapId"] = map_id

            self.logger.debug("Debug: Json.dumps: {0}".format(json.dumps(jsonCommand)))
            return json.dumps(jsonCommand)
        

    ########################
    # Oauth2 functions for new login feature with Vorwerk's myKobold APP
    #
    
    # Requesting authentication code to be sent to email account
    # Returns True on success and False otherwise
    def request_oauth2_code(self, hash = ''):

        if not hash == '':
            self.logger.debug("Robot: Overwriting clientIDHash with {0}.".format(str(hash)))
            self._clientIDHash = str(hash)
        self.logger.info("Requesting authentication code for {0} with challenge {1}".format(self.__email, self._clientIDHash))

        usedata = {"send": "code", "email": self.__email, "client_id": str(self._clientIDHash), "connection": "email"}
        self.logger.debug("Robot usedata: {0}".format(usedata))

        try:
            request_code_response = self._session.post("https://mykobold.eu.auth0.com/passwordless/start", json=usedata, headers={'Content-Type': 'application/json'}, timeout=self._timeout )

        except Exception as e:
            self.logger.error("Robot: Exception during code request: %s" % str(e))
            return False

        self.logger.info("Send code request command response: {0}".format(request_code_response.text))

        statusCode = request_code_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending authetication code request successful")
        else:
            self.logger.error("Error during auth code request: {0}".format(statusCode))
            return False
        
        return True

    # Requesting oauth2 token with the help of obtained code
    # Returns authentication token as as string on success and an empty string otherwise
    def request_oauth2_token(self, code, hash = ''):

        if not hash == '':
            self._clientIDHash = str(hash)
        self.logger.info("Requesting authentication token for {0} with code {1} and challenge {2}".format(self.__email, code, self._clientIDHash))
     
        usedata = {"prompt": "login",
           "grant_type": "http://auth0.com/oauth/grant-type/passwordless/otp",
           "scope": "openid email profile read:current_user",
           "locale": "en",
           "otp": str(code),
           "source": "vorwerk_auth0",
           "platform": "ios",
           "audience": "https://mykobold.eu.auth0.com/userinfo",
           "username": self.__email,
           "client_id": str(self._clientIDHash),
           "realm": "email",
           "country_code": "DE"}

        try:
            request_token_response = self._session.post("https://mykobold.eu.auth0.com/oauth/token", json=usedata, headers={'Content-Type': 'application/json'}, timeout=self._timeout )

        except Exception as e:
            self.logger.error("Robot: Exception during token request: %s" % str(e))
            return ''
        
        self.logger.info("Send token request command returned: {0}".format(request_token_response.text))

        statusCode = request_token_response.status_code
        if statusCode == 200:
            self.logger.debug("Sending authentication token request successful")
        else:
            self.logger.error("Error during authentication token request: {0}".format(statusCode))
            return ''

        responseJson = request_token_response.json()
        if 'id_token' in responseJson:
            id_token = responseJson['id_token']
            self.logger.info("Robot: Authentication token is {0}".format(id_token))
            return id_token
   
    # read secretKey and robot specific data with the help of obtained oauth2 token:
    def get_secretKey_viaOauth(self):
        secretKey = ''
        #self.logger.debug("Start function get secretKey via Oauth2")

        try:
            request_robots_response = self._session.get(self.__urlBeehive + "/dashboard", headers={'Authorization': 'Auth0Bearer ' + str(self._token)}, timeout=self._timeout, verify=False)

        except Exception as e:
            self.logger.error("Robot: Exception during secret key via token request: %s" % str(e))
            return ''

        #self.logger.debug("Response: {0}".format(request_robots_response.text))
        responseJson = request_robots_response.json()

        if 'robots' in responseJson:
            robots = responseJson['robots']
            self.logger.debug("{0} robots found".format(len(robots))) 
            self._numberRobots = len(robots)
    
            #Pick first robot in robot list:
            if 'nucleo_url' in robots[0]:
                self.__urlNucleo = robots[0]['nucleo_url']
                #self.logger.debug("NucleoUrl is {0}".format(self.__urlNucleo))

            if 'serial' in robots[0]:
                self.serial  = robots[0]['serial']
                #self.logger.debug("Serial number via oauth2 is {0}".format(self.serial))

            if 'name' in robots[0]:
                self.name  = robots[0]['name']
                #self.logger.debug("Name via oauth2 is {0}".format(self.name))

            if 'model' in robots[0]:
                self.modelname = robots[0]['model']
                #self.logger.debug("Model via oauth2 is {0}".format(self.modelname))

            if 'firmware ' in robots[0]:
                self.firmware = robots[0]['firmware']
                #self.logger.debug("Firmware via oauth2 is {0}".format(self.firmware))

            if 'secret_key' in robots[0]:
                secretKey  = robots[0]['secret_key']
                #self.logger.debug("Secret key via oauth2 is {0}".format(secretKey))
                self.__secretKey = secretKey
                return secretKey

        return ''
