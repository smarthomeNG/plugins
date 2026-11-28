"""Data structures of the bark plugin."""

from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BarkMessage:
    """
    One push notification.

    :ivar body: text of the notification
    :ivar title: headline above the text, None for a notification showing the text only
    :ivar url: URL opened when the notification is tapped
    """

    body: str
    title: str | None = None
    url: str | None = None

    def payload(self, device_key: str) -> dict[str, str]:
        """
        Request body for the push endpoint of a Bark server.

        :param device_key: key of the receiving device
        :return: the payload, without unset optional fields
        """
        payload = {'device_key': device_key, 'body': self.body}
        if self.title:
            payload['title'] = self.title
        if self.url:
            payload['url'] = self.url
        return payload


@dataclass(frozen=True)
class BarkTemplate:
    """
    Notification configured by the ``bark_*`` attributes of an item.

    :ivar values: texts for specific item values
    :ivar text: text for all values without an entry in *values*
    :ivar title: headline of the notification
    :ivar url: URL opened when the notification is tapped
    """

    values: Mapping[Hashable, str] = field(default_factory=dict)
    text: str | None = None
    title: str | None = None
    url: str | None = None

    def message_for(self, value: object) -> BarkMessage | None:
        """
        Build the notification for an item value.

        ``VAL`` in :attr:`text`, :attr:`title` and :attr:`url` is replaced by the value, texts from
        :attr:`values` are used as they are.

        :param value: item value
        :return: the notification, or None if no text is configured for the value
        """
        if isinstance(value, Hashable) and value in self.values:
            body = self.values[value]
        else:
            body = _insert(self.text, value)
        if not body:
            return None
        return BarkMessage(body, _insert(self.title, value), _insert(self.url, value))


def _insert(pattern: str | None, value: object) -> str | None:
    """Replace ``VAL`` in *pattern* by *value*, keeping an unset pattern unset."""
    return None if pattern is None else pattern.replace('VAL', str(value))
