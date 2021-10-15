class MessageRingModel:
    def __init__(self, ring_name):
        self.__ring_slots = []
        self.__ring_name = ring_name

    def get_ring_size(self):
        return len(self.__ring_slots)

    def append_message_source(self, message_source):
        self.__ring_slots.append(message_source)

    def introspect(self):
        content = ", ".join(map(lambda s: str(s), self.__ring_slots))
        return f"Ring '{self.__ring_name}': ({content})"

    def get_slots(self):
        return self.__ring_slots

    def contains_relevant_message(self):
        for source in self.__ring_slots:
            if source.is_relevant:
                return True
        
        return False
