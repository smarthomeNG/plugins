class SerializedRingMerger:
    def __init__(self, rings=None):
        if rings is None:
            self.__rings = []
        else:
            self.__rings = rings
        self.__slots_cache = None

    def append_ring_model(self, ring_model):
        if ring_model is not None:
            self.__rings.append(ring_model)
            self.__slots_cache = None

    def get_slots(self):
        if self.__slots_cache is None:
            result = []
            for ring in self.__rings:
                for slot in ring.get_slots():
                    result.append(slot)
            self.__slots_cache = result
        return self.__slots_cache

    def reset(self):
        self.__slots_cache = None

    def introspect(self):
        content = ', '.join(map(lambda s: str(s), self.get_slots()))
        rings = ', '.join(map(lambda rm: rm.introspect(), self.__rings))
        return f'SerializedRingMerger, ({content}), based on rings ({rings})'
