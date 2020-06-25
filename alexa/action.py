#
#   https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference
#
import uuid

action_func_registry = []

# action-func decorator
def alexa(action_name, directive_type, response_type):
    def store_metadata(func):
        func.alexa_action_name = action_name
        func.alexa_directive_type = directive_type
        func.alexa_response_type = response_type

        action_func_registry.append( func )
        return func
    return store_metadata

class AlexaActions(object):
    def __init__(self, sh, logger, devices):
        self.actions = {}
        self.actions_by_directive = {}

        for func in action_func_registry:
            logger.debug("Alexa: initializing action {}".format(func.alexa_action_name))
            action = AlexaAction(sh, logger, devices, func, func.alexa_action_name, func.alexa_directive_type, func.alexa_response_type)
            self.actions[action.name] = action
            self.actions_by_directive[action.directive_type] = action

    def by_name(self, name):
        return self.actions[name] if name in self.actions else None

    def for_directive(self, directive):
        return self.actions_by_directive[directive] if directive in self.actions_by_directive else None

class AlexaAction(object):
    def __init__(self, sh, logger, devices, func, action_name, directive_type, response_type):
        self.sh = sh
        self.logger = logger
        self.devices = devices
        self.func = func
        self.name = action_name
        self.directive_type = directive_type
        self.response_type = response_type

    def __call__(self, payload):
        return self.func(self, payload)

    def items(self, device_id):
        device = self.devices.get(device_id)
        return device.items_for_action(self.name) if device else []

    def item_range(self, item, default=None):
        return item.alexa_range if hasattr(item, 'alexa_range') else default

    def header(self, name=None):
        return {
            'messageId': uuid.uuid4().hex,
            'name': name if name else self.response_type,
            'namespace': 'Alexa.ConnectedHome.Control',
            'payloadVersion': '2'
        }

    def respond(self, payload={}):
        return {
            'header': self.header(),
            'payload': payload
        }

# https://developer.amazon.com/public/solutions/alexa/alexa-skills-kit/docs/smart-home-skill-api-reference#error-messages
    def error(self, error_type, payload={}):
        return {
            'header': self.header(error_type),
            'payload': payload
        }
