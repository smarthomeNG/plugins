"""."""
from .exceptions import TR064UnknownServiceIndexException


class ServiceList(list):
    """Service list."""

    def __getattr__(self, name):
        """Direct access to first list entry if brackets omit."""
        return self[0].__getattr__(name)

    def __getitem__(self, index):
        """Overriden bracket operator to return TR-064 exception."""
        if len(self) > index:
            return super().__getitem__(index)

        raise TR064UnknownServiceIndexException("Exception in ServiceListIndex")
