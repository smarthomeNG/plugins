from typing import KeysView
from .MessageRingModel import MessageRingModel
from .MessageSourceModel import MessageSourceModel
from .MessageSinkModel import MessageSinkModel
from .PrioritizedRingMerger import PrioritizedRingMerger
from .SerializedRingMerger import SerializedRingMerger
from .OverrulingMergerMerger import OverrulingMergerMerger
from .RingReader import RingReader


class TextDisplayModel():

    def __init__(self):
        self._items_with_delay = {}
        self._message_rings = {}
        self._items_with_message_sink = {}
        self._source_to_ring = {}
        self._ring_to_readers = {}
        self._rings_to_sink_item_path = {}

    """
    Public interface to Plugin
    """

    def append_message_source_to_ring(self, ring, content_source_path, content_source, is_relevant_path, is_relevant):
        message_source = MessageSourceModel(
            content_source_path, content_source, is_relevant_path, is_relevant)

        self.__prepare_ring_model(ring)

        self._message_rings[ring].append_message_source(message_source)
        self._source_to_ring[is_relevant_path] = ring

    def __store_ring_to_sink_item_path(self, ring, sink_item_path):
        if ring not in self._rings_to_sink_item_path:
            self._rings_to_sink_item_path[ring] = []
        if sink_item_path not in self._rings_to_sink_item_path[ring]:
            self._rings_to_sink_item_path[ring].append(sink_item_path)

    def get_ring_for_relevance_item(self, is_relevant_path):
        return self._source_to_ring[is_relevant_path]

    def get_sink_item_paths_for_ring(self, ring):
        return self._rings_to_sink_item_path[ring]

    def append_message_sink_to_rings(self, item_path, source_rings, default_value=None, prioritized_mode=True, tick_time_hint=3):
        for ring in source_rings:
            self.__prepare_ring_model(ring)
            self.__store_ring_to_sink_item_path(ring, item_path)

        if(prioritized_mode):
            reader = self.__read_prioritized(source_rings)
        else:
            reader = self.__read_serialized(source_rings)
        sink_model = MessageSinkModel(default_value, reader, tick_time_hint)
        self._items_with_message_sink[item_path] = sink_model

    def append_message_sink_to_overruling_rings(self, item_path, overruling_rings):
        overruling_merger = SerializedRingMerger()
        for ring_name in overruling_rings:
            self.__prepare_ring_model(ring_name)
            overruling_merger.append_ring_model(self.get_ring_model(ring_name))
            self.__store_ring_to_sink_item_path(ring_name, item_path)

        sink_model = self._items_with_message_sink[item_path]
        base_merger = sink_model.reader.merger

        def overruler():
            if self.__any_relevant_message_in(overruling_rings):
                return False

        sink_model.reader.merger = OverrulingMergerMerger(
            base_merger, overruling_merger, overruler)
        self.__register_reader_to_rings(sink_model.reader, overruling_rings)

    def update_source_relevance(self, source_is_relevant_path):
        ring_name = self._source_to_ring[source_is_relevant_path]
        readers = self._ring_to_readers[ring_name]
        for reader in readers:
            reader.reset()

    def tick_sink(self, sink_key):
        sink_model = self._items_with_message_sink[sink_key]
        return sink_model.tick()

    def sink_has_messages_present(self, sink_key):
        sink_model = self._items_with_message_sink[sink_key]
        return sink_model.has_relevant_messages()

    def dump_sink(self, sink_key):
        sink_model = self._items_with_message_sink[sink_key]
        return sink_model.dump()

    def get_pending_intents(self):
        for delay_model_key in self._items_with_delay:
            dm = self.get_delay_for_item(delay_model_key)
            if dm.intent_pending:
                yield dm
    
    def introspect_sink(self, sink_key):
        sink_model = self._items_with_message_sink[sink_key]
        return sink_model.introspect()

    def reset_sinks(self):
        for sink_key in self._items_with_message_sink:
            self._items_with_message_sink[sink_key].reset()

    """
    Interface to WebIF
    """

    def get_ring_model(self, ring) -> MessageRingModel:
        return self._message_rings[ring]

    def get_rings(self) -> KeysView:
        return self._message_rings.keys()

    def get_sinks(self) -> KeysView:
        return self._items_with_message_sink.keys()

    def get_sink_model(self, sink) -> MessageSinkModel:
        return self._items_with_message_sink[sink]

    def get_item_count(self) -> int:
        """
        Returns number of added items
        """
        return len(self._items_with_delay)

    """
    Private helper methods
    """

    def __prepare_ring_model(self, ring):
        if not ring in self._message_rings:
            self._message_rings[ring] = MessageRingModel(ring)
        return self._message_rings[ring]

    def __register_reader_to_rings(self, reader, ring_names):
        for ring_name in ring_names:
            if not ring_name in self._ring_to_readers:
                self._ring_to_readers[ring_name] = []
            self._ring_to_readers[ring_name].append(reader)

    def __any_relevant_message_in(self, source_rings):
        for ring_name in source_rings:
            ring_model = self.get_ring_model(ring_name)
            if ring_model.contains_relevant_message():
                return True
        return False

    def __read_prioritized(self, ringnames_ordered):
        merger = PrioritizedRingMerger()
        for ring_name in ringnames_ordered:
            merger.append_ring_model(self.get_ring_model(ring_name))

        reader = RingReader(merger)
        self.__register_reader_to_rings(reader, ringnames_ordered)
        return reader

    def __read_serialized(self, ringnames_ordered):
        merger = SerializedRingMerger()
        for ring_name in ringnames_ordered:
            merger.append_ring_model(self.get_ring_model(ring_name))

        reader = RingReader(merger)
        self.__register_reader_to_rings(reader, ringnames_ordered)
        return reader
