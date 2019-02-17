from .action import alexa

DEFAULT_RANGE = (True, False)

@alexa('turnOn', 'TurnOnRequest', 'TurnOnConfirmation','',[])
def turn_on(self, payload):
    items = self.items( payload['appliance']['applianceId'] )

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: turnOn({}, {})".format(item.id(), on))
        if on != None:
            item( on )

    return self.respond()

@alexa('turnOff', 'TurnOffRequest', 'TurnOffConfirmation','',[])
def turn_off(self, payload):
    items = self.items( payload['appliance']['applianceId'] )

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: turnOff({}, {})".format(item.id(), off))
        if off != None:
            item( off )

    return self.respond()
