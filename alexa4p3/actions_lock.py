from datetime import date
from .action import alexa

DEFAULT_RANGE = (True, False)

@alexa('getLockState', 'GetLockStateRequest', 'GetLockStateResponse','',[])
def get_lock_state(self, payload):
    items = self.items( payload['appliance']['applianceId'] )

    current_lock_state = None
    for item in items:
        locked, unlocked = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: getLockState({})".format(item.id(), on))
        current_lock_state = 'LOCKED' if item() == locked else 'UNLOCKED'

    return self.respond({
        'lockState': current_lock_state,
        'applianceResponseTimestamp': date.today().isoformat()
    })

@alexa('setLockState', 'SetLockStateRequest', 'SetLockStateConfirmation','',[])
def set_lock_state(self, payload):
    items = self.items( payload['appliance']['applianceId'] )
    requested_state = payload['lockState']

    actual_lock_state = None
    for item in items:
        locked, unlocked = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: setLockState({}, {})".format(item.id(), locked))
        item( locked if requested_state == 'LOCKED' else unlocked )
        actual_lock_state = 'LOCKED' if item() == locked else 'UNLOCKED'

    return self.respond({
        'lockState': actual_lock_state
    })
