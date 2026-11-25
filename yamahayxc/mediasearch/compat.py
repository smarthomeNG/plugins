"""Python version compatibility shims for the media search package."""

from enum import Enum

try:
    from enum import StrEnum
except ImportError:

    class StrEnum(str, Enum):
        """Python 3.10 stand-in for enum.StrEnum (3.11+): str-valued members whose str() is their value"""

        def __str__(self) -> str:
            return str(self.value)


__all__ = ['StrEnum']
