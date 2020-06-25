class AlexaDevices(object):
    def __init__(self):
        self.devices = {}

    def exists(self, id):
        return id in self.devices

    def get(self, id):
        return self.devices[id]

    def put(self, device):
        self.devices[device.id] = device

    def all(self):
        return list( self.devices.values() )
    
    def delete(self,id):
        del self.devices[id]

class AlexaDevice(object):
    def __init__(self, id):
        self.id = id
        self.name = None
        self.description = None
        self.action_items = {}
        self.types = []
        self.alias = []
        #P3 - Properties - A.Kohler
        self.thermo_config = '0:AUTO'       # default if nothing is in Config-File
        self.icon = []
        self.retrievable = False
        self.proactivelyReported = False
        self.camera_setting = {}
        self.camera_uri = ''
        self.camera_imageUri = ''
        self.alexa_auth_cred = ''
        self.alexa_color_value_type = ''
        self.proxied_Urls = {}
        self.alexa_proxy_credentials=''
        self.alias_for = ''
        self.alexa_cam_modifiers = ''

    @classmethod
    def create_id_from_name(cls, name):
        import unicodedata
        import re
        id = name.strip()
        id = unicodedata.normalize('NFKD', id).encode('ascii', 'ignore').decode('ascii')
        id = id.lower()
        return re.sub('[^a-z0-9_-]', '-', id)

    def register(self, action_name, item):
        if action_name in self.action_items:
            self.action_items[action_name].append(item)
        else:
            self.action_items[action_name] = [item]

    def supported_actions(self):
        return list( self.action_items.keys() )

    def supports_action(self, action_name):
        return action_name in self.action_items

    def backed_items(self):
        item_set = set()
        for items in self.action_items.values():
            for item in items:
                item_set.add( item )
        return list( item_set )

    def items_for_action(self, action_name):
        return self.action_items[action_name] if action_name in self.action_items else []

    def item_range(self, item):
        return self.item_ranges[item] if item in self.item_ranges else None

    def create_alias_devices(self):
        alias_devices = []
        for idx, alias_name in enumerate(self.alias):
            alias_device_id = "{}-alias{}".format(self.id, idx+1)

            alias_device = AlexaDevice(alias_device_id)
            alias_device.name = alias_name
            alias_device.description = self.description
            alias_device.action_items = self.action_items
            alias_device.types = self.types
            # P3-properties 
            alias_device.icon = self.icon
            alias_device.thermo_config = self.thermo_config
            alias_device.retrievable = self.retrievable
            alias_device.proactivelyReported = self.proactivelyReported
            alias_device.camera_setting = self.camera_setting
            alias_device.camera_uri = self.camera_uri
            alias_device.camera_imageUri = self.camera_imageUri
            alias_device.alexa_auth_cred = self.alexa_auth_cred
            alias_device.alexa_color_value_type = self.alexa_color_value_type
            alias_device.proxied_Urls = self.proxied_Urls
            alias_device.alexa_proxy_credentials = self.alexa_proxy_credentials
            alias_device.alias_for = self.name
            alias_devices.append( alias_device )

        return alias_devices

    def validate(self, logger ,proto):
        if not self.id:
            msg = "Alexa-Device {}: empty identifier".format(self.id)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            return False
        elif len(self.id) > 128:
            msg = "Alexa-Device: {}: identifier '{}' too long >128".format(self.id, self.id)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            return False

        if not self.name:
            msg = "Alexa-Device {}: empty name".format(self.id)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            return False
        elif len(self.name) > 128:
            msg = "Alexa-Device: {}: name '{}' too long >128".format(self.id, self.name)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            return False

        if not self.description:
            msg = "Alexa-Device {}: empty description, fallback to name '{}' - please set `alexa_description`".format(self.id, self.name)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            self.description = self.name
        elif len(self.description) > 128:
            msg = "Alexa-Device {}: description '{}' too long >128".format(self.id, self.description)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)
            return False

        if not self.action_items:
            msg="Alexa-Device {}: no actions/items registered - please set `alexa_actions`".format(self.id)
            logger.warning(msg)
            proto.addEntry('WARNING',msg)

        return True
