class PrioritizedRingMerger:
    def __init__(self, rings=None):
        if rings is None:
            self.__rings = []
        else:
            self.__rings = rings
        self.__slots_cache = None

    def append_ring_model(self, ring_model):
        if not ring_model is None:
            self.__rings.append(ring_model)
            self.__slots_cache = None

    def traverse(self, liste, start_index, count, selector):
        result = []
        if(count > 1):
            higher_prios = self.traverse(
                liste, start_index + 1, count - 1, selector)
            this_level = selector(liste[start_index])
            for this_level_item in this_level:
                result.extend(higher_prios)
                result.append(this_level_item)
            else:
                result.extend(higher_prios)
        else:
            this_level = selector(liste[start_index])
            for this_level_item in this_level:
                result.append(this_level_item)
        return result

    def get_slots(self):
        if not self.__slots_cache is None:
            return self.__slots_cache

        reversed_rings = list(reversed(self.__rings))
        temp = self.traverse(reversed_rings, 0, len(
            reversed_rings), lambda ring_model: ring_model.get_slots())
        self.__slots_cache = temp
        return temp

    def reset(self):
        self.__slots_cache = None

    def introspect(self):
        content = ", ".join(map(lambda s: str(s), self.get_slots()))
        rings = ", ".join(map(lambda rm: rm.introspect(), self.__rings))
        return f"PrioritizedRingMerger, ({content}), based on rings ({rings})"
