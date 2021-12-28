from .MessageSourceModel import MessageSourceModel


class RingReader:

    def __init__(self, ring_merger):
        self.__current_index = -1
        self.__last_value = None
        self.__ring_merger = ring_merger

    def __get_merger(self):
        return self.__ring_merger

    def __set_merger(self, x):
        self.__ring_merger = x
        self.reset()
    merger = property(__get_merger, __set_merger)

    def __repr__(self):
        return f"RingReader, CI: {self.__current_index}, LV: {self.__last_value}"

    def reset(self):
        self.__current_index = -1
        self.__last_value = None
        self.__ring_merger.reset()

    def introspect(self):
        content = ", ".join(map(lambda s: str(s), self.read()))
        return f"RingReader, ({content}), based on: {self.__ring_merger.introspect()}"

    def dump(self):
        slots = self.__ring_merger.get_slots()
        return slots

    def has_relevant_messages(self):
        return any(slot.is_relevant for slot in self.__ring_merger.get_slots())

    def read(self):
        slots = self.__ring_merger.get_slots()
        for slot in slots:
            if slot.is_relevant:
                yield slot

    def read_next(self) -> MessageSourceModel:
        last_slot_num = self.__current_index
        self.__current_index += 1
        slots = self.__ring_merger.get_slots()

        if len(slots) <= self.__current_index:
            self.__current_index = 0

        for slot_num in range(self.__current_index, len(slots)):
            slot = slots[slot_num]
            if slot.is_relevant and (slot.content != self.__last_value or slot_num == last_slot_num):
                self.__current_index = slot_num
                self.__last_value = slot.content
                return slot

        for slot_num in range(0, self.__current_index):
            slot = slots[slot_num]
            if slot.is_relevant and (slot.content != self.__last_value or slot_num == last_slot_num):
                self.__current_index = slot_num
                self.__last_value = slot.content
                return slot

        self.__current_index = -1
        self.__last_value = None
        return None
