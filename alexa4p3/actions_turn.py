from .action import alexa

DEFAULT_RANGE = (True, False)

@alexa('turnOn', 'TurnOnRequest', 'TurnOnConfirmation','',[],"2")
def turn_on(self, payload):
    items = self.items( payload['appliance']['applianceId'] )

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: turnOn({}, {})".format(item.property.path, on))
        if on != None:
            item( on )

    return self.respond()

@alexa('turnOff', 'TurnOffRequest', 'TurnOffConfirmation','',[],"2")
def turn_off(self, payload):
    items = self.items( payload['appliance']['applianceId'] )

    for item in items:
        on, off = self.item_range(item, DEFAULT_RANGE)
        self.logger.info("Alexa: turnOff({}, {})".format(item.property.path, off))
        if off != None:
            item( off )

    return self.respond()
