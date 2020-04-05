from requests import Session
import json
import re
import time
from typing import Pattern, Dict, Union


class LoggedInException(Exception):

    def __init__(self, *args, **kwargs):
        super(LoggedInException, self).__init__(*args, **kwargs)


class DataException(Exception):

    def __init__(self, *args, **kwargs):
        super(DataException, self).__init__(*args, **kwargs)


class DeviceCacheEntry(object):

    def __init__(self):
        self.age = 0
        self.data = {}
        self.valid = False


class API(object):
    """
    Unifi API for the Unifi Controller.

    """
    _login_data = {}

    _is_logged_in = False

    _client_list = {}
    _client_list_from = 0
    _port_profiles = {}
    _mac_to_id = {}
    _device_cache = {}
    _request_count = 0

    def __init__(self, username: str = "ubnt", password: str = "ubnt", site: str = "default", baseurl: str = "https://unifi:8443", verify_ssl: bool = True):
        """
        Initiates tha api with default settings if none other are set.

        :param username: username for the controller user
        :param password: password for the controller user
        :param site: which site to connect to (Not the name you've given the site, but the url-defined name)
        :param baseurl: where the controller is located
        :param verify_ssl: Check if certificate is valid or not, throws warning if set to False
        """
        self._login_data['username'] = username
        self._login_data['password'] = password
        self._site = site
        self._verify_ssl = verify_ssl
        self._baseurl = baseurl
        self._session = Session()
        self._request_count = 0

    def __enter__(self):
        """
        Contextmanager entry handle

        :return: isntance object of class
        """
        return self

    def __exit__(self, *args):
        """
        Contextmanager exit handle

        :return: None
        """
        if self._is_logged_in:
            self.logout()
            self._is_logged_in = False

    def _get_url(self, url, recursion=False):
        try:
            self.login()

            r = self._session.get(url, verify=self._verify_ssl)
            self._request_count = self._request_count + 1
            current_status_code = r.status_code

            if not r.ok:
                if current_status_code == 401:
                    raise LoggedInException("Invalid login, or login has expired")

            data = r.json()['data']
            return data
        except LoggedInException:
            if recursion:
                raise DataException("Unable to log in or get data for url {}".format(url))
            self._is_logged_in = False
            return self._get_url(url, True)

    def _put_url(self, url, body, recursion=False):
        try:
            self.login()

            r = self._session.put(url, verify=self._verify_ssl, data=body)
            self._request_count = self._request_count + 1
            current_status_code = r.status_code
            if not r.ok:
                if current_status_code == 401:
                    raise LoggedInException("Invalid login, or login has expired")
                else:
                    raise LoggedInException("code {}".format(current_status_code))

            data = r.json()['data']
            return data
        except LoggedInException:
            if recursion:
                raise DataException("Unable to log in or put data")
            self._is_logged_in = False
            return self._put_url(url, body, True)

    def login(self):
        """
        Log the user in

        :return: None
        """
        if self._is_logged_in:
            return

        current_status_code = self._session.post("{}/api/login".format(
            self._baseurl), data=json.dumps(self._login_data), verify=self._verify_ssl).status_code
        self._request_count = self._request_count + 1
        if current_status_code == 400:
            raise LoggedInException("Failed to log in to api with provided credentials")

        self._is_logged_in = True

    def logout(self):
        """
        Log the user out

        :return: None
        """
        self._session.get("{}/logout".format(self._baseurl))
        self._request_count = self._request_count + 1
        self._session.close()

    def list_clients(self, filters: Dict[str, Union[str, Pattern]] = None, order_by: str = None, max_age_seconds: int = 60) -> list:
        """
        List all available clients from the api or an internal cache

        :param filters: dict with valid key, value pairs, string supplied is compiled to a regular expression
        :param order_by: order by a valid client key, defaults to '_id' if key is not found
        :param max_age_seconds: number of seconds after which the controller is to be called again, defaults to 60
        :return: A list of clients on the format of a dict
        """
        if time.time() - self._client_list_from > max_age_seconds:
            self._client_list = self._get_url("{}/api/s/{}/stat/sta".format(self._baseurl,
                                                                            self._site))
            self._client_list_from = time.time()

        data = self._client_list

        if filters:
            for term, value in filters.items():
                value_re = value if isinstance(value, Pattern) else re.compile(value)

                data = [x for x in data if term in x.keys() and re.fullmatch(value_re, x[term])]

        if order_by:
            data = sorted(data, key=lambda x: x[order_by] if order_by in x.keys() else x['_id'])

        return data

    def device_disable(self, device_ids: list, disabled):
        """
        Dis- or enables the device
        """
        self.login()

        ap_data = {}
        ap_data['disabled'] = disabled
        for ids in device_ids:
            self._put_url("{}/api/s/{}/rest/device/{}".format(
                self._baseurl, self._site, ids), body=json.dumps(ap_data))

    def device_stat(self, mac: str):
        return self._get_url("{}/api/s/{}/stat/device/{}".format(self._baseurl,
                                                                 self._site, mac))

    def hierarchize(self, inventory, key_selector, subkey_selector, start_key):
        to_ret = []
        for entry in inventory:
            if key_selector(entry) == start_key:
                ret2 = {}
                ret2['node'] = entry
                ret2['children'] = self.hierarchize(inventory, key_selector, subkey_selector, subkey_selector(entry))
                to_ret.append(ret2)
        return sorted(to_ret, key=lambda x: str(x['node']['uplink_remote_port']) + x['node']['key'])

    def get_device_hierarchy(self):
        dvcs = self.device_stat("")
        mac_inventory = []
        for dvc in dvcs:
            entry = {}
            entry['mac'] = dvc['mac']
            entry['type'] = dvc['type']
            try:
                entry['name'] = dvc['name']
            except KeyError:
                entry['name'] = ''
            entry['key'] = entry['type'] + '_' + entry['name']
            try:
                entry['uplink_mac'] = dvc['last_uplink']['uplink_mac']
                entry['uplink_remote_port'] = dvc['last_uplink']['uplink_remote_port']
            except KeyError:
                try:
                    entry['uplink_mac'] = dvc['uplink']['uplink_mac']
                    entry['uplink_remote_port'] = dvc['uplink']['uplink_remote_port']
                except KeyError:
                    entry['uplink_mac'] = "no_mac"
                    entry['uplink_remote_port'] = -1
            mac_inventory.append(entry)

        flat_clients = []
        clnts = self.list_clients()
        for clnt in clnts:

            if clnt['is_wired']:
                entry = {}
                entry['mac'] = clnt['mac']
                try:
                    entry['name'] = clnt['name']
                except KeyError:
                    try:
                        entry['name'] = clnt['hostname']
                    except KeyError:
                        entry['name'] = 'mac_' + entry['mac'].replace(':', '_')

                try:
                    entry['uplink_mac'] = clnt['sw_mac']
                    entry['uplink_remote_port'] = clnt['sw_port']
                except KeyError:
                    continue

                entry['type'] = 'wired_client'
                entry['key'] = entry['type'] + '_' + entry['name']
                mac_inventory.append(entry)
            else:
                tmpcl = {}
                tmpcl['mac'] = clnt['mac']
                try:
                    tmpcl['name'] = clnt['name']
                except KeyError:
                    try:
                        tmpcl['name'] = clnt['hostname']
                    except KeyError:
                        tmpcl['name'] = 'mac_' + tmpcl['mac'].replace(':', '_')
                flat_clients.append(tmpcl)

        device_hr = self.hierarchize(mac_inventory, lambda x: x['uplink_mac'], lambda x: x['mac'], "no_mac")

        struct = {}
        struct['wireless_clients'] = flat_clients
        struct['devices'] = device_hr

        return struct

    def _get_port_profiles(self, filters: Dict[str, Union[str, Pattern]] = None):
        if len(self._port_profiles) < 1:
            self._port_profiles = self._get_url("{}/api/s/{}/rest/portconf".format(self._baseurl, self._site))

        data = self._port_profiles
        if filters:
            for term, value in filters.items():
                value_re = value if isinstance(value, Pattern) else re.compile(value)
                data = [x for x in data if term in x.keys() and re.fullmatch(value_re, x[term])]

        return data

    def _get_id_from_mac(self, mac: str):
        mac = mac.lower()
        if not self._mac_to_id.__contains__(mac):
            swData = self.device_stat(mac)
            if len(swData) == 0:
                return None
            self._mac_to_id[mac] = swData[0]['_id']

        return self._mac_to_id[mac]

    def set_device_disabled(self, device_mac: str, disabled: bool):
        did = self._get_id_from_mac(device_mac)
        if did is None:
            raise DataException("Cannot find switch with MAC {}".format(device_mac))
        self.device_disable([did], disabled)

    def get_port_profile_for(self, switch_mac: str, port_number: int):
        self.login()

        sid = self._get_id_from_mac(switch_mac)
        if sid is None:
            raise DataException("Cannot find switch with MAC {}".format(switch_mac))

        poData = self.get_device_info(switch_mac, 'port_overrides')
        poIndex = -1
        poFound = False
        for port in poData:
            poIndex = poIndex + 1
            if port['port_idx'] == port_number:
                poFound = True
                break
        if not poFound:
            raise DataException("Could not match any port in data to given port-number {}".format(port_number))
        port_prof = poData[poIndex]['portconf_id']

        profiles = self._get_port_profiles()
        if len(profiles) == 0:
            raise DataException("No port profiles found")
        for prof in profiles:
            if prof["_id"] == port_prof:
                return prof["name"]

        raise DataException("Cannot match profile {} in {}".format(port_prof, json.dumps(profiles)))

    def set_port_profile_for(self, switch_mac: str, port_number: int, profile_name: str):
        self.login()

        pp = self._get_port_profiles(filters={'name': profile_name})
        if len(pp) == 0:
            raise DataException("No port profile found for {}".format(profile_name))
        pid = pp[0]['_id']

        sid = self._get_id_from_mac(switch_mac)
        if sid is None:
            raise DataException("Cannot find switch with MAC {}".format(switch_mac))

        poData = self.get_device_info(switch_mac, 'port_overrides')
        poIndex = -1
        poFound = False
        for port in poData:
            poIndex = poIndex + 1
            if port['port_idx'] == port_number:
                poFound = True
                break
        if not poFound:
            raise DataException("Could not match any port in data to given port-number {}".format(port_number))

        poData[poIndex]['portconf_id'] = pid
        newPoData = {}
        newPoData['port_overrides'] = poData

        self._put_url("{}/api/s/{}/rest/device/{}".format(self._baseurl,
                                                          self._site, sid), body=json.dumps(newPoData))

    def get_client_presence(self, client_mac: str, last_seen_delta: int = 300):
        clnts = self.list_clients(filters={'mac': client_mac})
        if len(clnts) < 1:
            return False
        ls = clnts[0]['last_seen']
        return time.time() - ls < last_seen_delta

    def get_client_info(self, client_mac: str, property_id: str):
        clnts = self.list_clients(filters={'mac': client_mac})
        if len(clnts) < 1:
            return None

        if clnts[0].__contains__(property_id):
            return clnts[0][property_id]
        return None

    def get_device_info(self, device_mac: str, property_id: str, max_age: int = 30, if_no_dev=None, if_no_prop=None):
        if not self._device_cache.__contains__(device_mac):
            self._device_cache[device_mac] = DeviceCacheEntry()

        if time.time() - self._device_cache[device_mac].age > max_age:
            rsl = self.device_stat(device_mac)
            if len(rsl) > 0:
                self._device_cache[device_mac].data = rsl[0]
                self._device_cache[device_mac].valid = True
                self._device_cache[device_mac].age = time.time()
            else:
                self._device_cache[device_mac].age = time.time() - max_age + 5
                return if_no_dev
        try:
            if not self._device_cache[device_mac].valid:
                return if_no_dev
            return self._device_cache[device_mac].data[property_id]
        except KeyError:
            return if_no_prop

    def get_request_count(self):
        return self._request_count

    def get_connection_data(self):
        to_ret = {}
        to_ret['user'] = self._login_data['username']
        to_ret['site'] = self._site
        to_ret['url'] = self._baseurl
        return to_ret
