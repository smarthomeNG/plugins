import logging
from .commands import CommandService

log = logging.getLogger(__name__)

class IPCam(object):

    def __init__(self, ip, ssl=False, auth_type=0, user=None, password=None):
        self.ip_address = ip
        self.user = user
        self.password = password
        self.auth_type = int(auth_type)  # 0: none, 1: basic, 2: digest
        self.ssl = ssl
        self.commands = CommandService(self)