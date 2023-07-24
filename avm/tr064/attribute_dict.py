"""TR-064 attribute dict."""


class AttributeDict(dict):
    """Direct access dict entries like attributes."""

    def __getattr__(self, name):
        return self[name]
