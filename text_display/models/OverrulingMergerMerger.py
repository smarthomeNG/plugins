from .MessageSourceProxy import MessageSourceProxy


class OverrulingMergerMerger():

    def __init__(self, base_merger, overruling_merger, overruler):
        self.__base_merger = base_merger
        self.__overruling_merger = overruling_merger
        self.__overruler = overruler
        self.__slots_cache = None

    def get_slots(self):
        if not self.__slots_cache is None:
            return self.__slots_cache

        temp = []
        for base_slot in self.__base_merger.get_slots():
            slot = MessageSourceProxy(base_slot, self.__overruler)
            temp.append(slot)

        for slot in self.__overruling_merger.get_slots():
            temp.append(slot)

        self.__slots_cache = temp
        return temp

    def reset(self):
        self.__base_merger.reset()
        self.__overruling_merger.reset()
        self.__slots_cache = None

    def introspect(self):
        content = ", ".join(map(lambda s: str(s), self.get_slots()))
        return f"OverrulingMergerMerger, ({content}), based on " \
               f"base_merger ({self.__base_merger.introspect()}) overruled by " \
               f"overruling_merger ({self.__overruling_merger.introspect()})"
