"""TR-064 exceptions."""

__all__ = [
    'TR064UnknownDeviceException',
    'TR064UnknownServiceException',
    'TR064UnknownServiceIndexException',
    'TR064UnknownActionException',
    'TR064UnknownArgumentException',
    'TR064MissingArgumentException'
]


class TR064Exception(Exception):
    """TR-064 base exception."""


class TR064UnknownDeviceException(Exception):
    """TR-064 unknown device exception."""


class TR064UnknownServiceException(Exception):
    """TR-064 unknown service exception."""


class TR064UnknownServiceIndexException(Exception):
    """TR-064 unknown service index exception."""


class TR064UnknownActionException(Exception):
    """TR-064 unknown action exception."""


class TR064UnknownArgumentException(Exception):
    """TR-064 unknown argument exception."""


class TR064MissingArgumentException(Exception):
    """TR-064 missing argument exception."""
