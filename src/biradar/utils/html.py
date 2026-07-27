"""Shared helpers for reading BeautifulSoup parse trees."""

from typing import Any


def attr_str(tag: Any, name: str, default: str | None = None) -> str | None:
    """Read a tag attribute as text.

    BeautifulSoup types attribute access as ``str | AttributeValueList | None``
    because multi-valued attributes (``class``, ``rel``) parse into lists. The
    attributes this codebase reads are single-valued, but a malformed page can
    still yield a list, in which case the parts are joined rather than allowed
    to reach code expecting a string.
    """
    if tag is None:
        return default
    value = tag.get(name)
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(part) for part in value)
    return str(value)
