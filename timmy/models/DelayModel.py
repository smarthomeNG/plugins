class DelayModel():
    def __init__(self, target_item, delay_on=0, delay_off=0):
        self.__target_item = target_item

        if delay_on is None:
            delay_on = 0
        self.__delay_on = delay_on

        if delay_off is None:
            delay_off = 0
        self.__delay_off = delay_off

        self.__intent_pending = False
        self.__intended_target_state = None

    def __get_intent_pending(self):
        return self.__intent_pending

    def __set_intent_pending(self, x):
        self.__intent_pending = x

    intent_pending = property(
        __get_intent_pending, __set_intent_pending)

    def __get_intended_target_state(self):
        return self.__intended_target_state

    def __set_intended_target_state(self, x):
        self.__intended_target_state = x

    intended_target_state = property(
        __get_intended_target_state, __set_intended_target_state)

    def __get_target_item(self):
        return self.__target_item

    def __set_target_item(self, x):
        self.__target_item = x

    target_item = property(__get_target_item, __set_target_item)

    def __get_delay_on(self):
        return self.__delay_on

    def __set_delay_on(self, x):
        self.__delay_on = x

    delay_on = property(__get_delay_on, __set_delay_on)

    def __get_delay_off(self):
        return self.__delay_off

    def __set_delay_off(self, x):
        self.__delay_off = x

    delay_off = property(__get_delay_off, __set_delay_off)
