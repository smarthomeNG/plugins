class BlinkModel():
    def __init__(self, target_item, blink_pattern, blink_cycles, blink_loops):
        self.__target_item = target_item
        self.__return_to = None
        self.__enabled = False
        self.__blink_pattern = blink_pattern
        self.__blink_cycles = blink_cycles
        self.__blink_loops = blink_loops
        self.__loop_cursor = 0
        self.__cycle_cursor = 0

    def tick(self):
        pattern_value = self.__blink_pattern[self.__cycle_cursor]
        wait_period = self.__blink_cycles[self.__cycle_cursor]
        index = f"L{self.__loop_cursor}, S{self.__cycle_cursor}"
        
        self.__cycle_cursor = self.__cycle_cursor + 1
        if self.__cycle_cursor == len(self.__blink_pattern):
            self.__cycle_cursor = 0
            if self.__blink_loops > 0:
                self.__loop_cursor = self.__loop_cursor + 1
        if self.__blink_loops > 0 and self.__loop_cursor == self.__blink_loops:
            self.enabled = False

        return (pattern_value, wait_period, index)

    def __get_enabled(self):
        return self.__enabled

    def __set_enabled(self, x):
        if self.__enabled == x:
            return
        self.__loop_cursor = 0
        self.__cycle_cursor = 0
        self.__enabled = x

    enabled = property(__get_enabled, __set_enabled)

    def __get_return_to(self):
        return self.__return_to

    def __set_return_to(self, x):
        self.__return_to = x

    return_to = property(__get_return_to, __set_return_to)

    def __get_blink_pattern(self):
        return self.__blink_pattern

    def __set_blink_pattern(self, x):
        self.__blink_pattern = x

    blink_pattern = property(__get_blink_pattern, __set_blink_pattern)

    def __get_blink_cycles(self):
        return self.__blink_cycles

    def __set_blink_cycles(self, x):
        self.__blink_cycles = x

    blink_cycles = property(__get_blink_cycles, __set_blink_cycles)

    def __get_blink_loops(self):
        return self.__blink_loops

    def __set_blink_loops(self, x):
        self.__blink_loops = x

    blink_loops = property(__get_blink_loops, __set_blink_loops)

    def __get_target_item(self):
        return self.__target_item

    def __set_target_item(self, x):
        self.__target_item = x

    target_item = property(__get_target_item, __set_target_item)
