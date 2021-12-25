from .DelayModel import DelayModel
from .BlinkModel import BlinkModel


class TimmyModel():

    def __init__(self):
        self._items_with_delay = {}
        self._blink_models = {}

    """
    Public interface to Plugin
    """

    def append_delay_item(self, item_path, target_item, on_seconds, off_seconds):
        item_model = DelayModel(target_item, on_seconds, off_seconds)
        self._items_with_delay[item_path] = item_model
    
    def append_blink_item(self, item_path, target_item, blink_pattern, blink_cycles, blink_loops):
        item_model = BlinkModel(target_item, blink_pattern, blink_cycles, blink_loops)
        self._blink_models[item_path] = item_model

    def get_pending_intents(self):
        for delay_model_key in self._items_with_delay:
            dm = self.get_delay_for_item(delay_model_key)
            if dm.intent_pending:
                yield dm

    def get_delay_for_item(self, item_path) -> DelayModel:
        return self._items_with_delay[item_path]

    def get_blink_model_for_item(self, item_path) -> BlinkModel:
        return self._blink_models[item_path]
    
    """
    Interface to WebIF
    """

    def get_item_count(self) -> int:
        """
        Returns number of added items
        """
        return len(self._items_with_delay)
