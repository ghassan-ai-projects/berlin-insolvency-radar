"""Unit tests for BeautifulSoup attribute reading helpers."""

from bs4 import BeautifulSoup

from biradar.utils.html import attr_str


def _tag(html: str):
    return BeautifulSoup(html, "html.parser").find(True)


def test_attr_str_reads_single_valued_attribute():
    assert attr_str(_tag('<a href="/x">t</a>'), "href") == "/x"


def test_attr_str_returns_default_for_missing_attribute():
    assert attr_str(_tag("<a>t</a>"), "href") is None
    assert attr_str(_tag("<a>t</a>"), "href", "") == ""


def test_attr_str_returns_default_for_none_tag():
    assert attr_str(None, "href") is None
    assert attr_str(None, "href", "fallback") == "fallback"


def test_attr_str_joins_multi_valued_attribute():
    """`class` parses to a list; callers expecting a string must not get one."""
    assert attr_str(_tag('<div class="a b">t</div>'), "class") == "a b"


def test_attr_str_stringifies_unexpected_attribute_types():
    """Non-string, non-list values (e.g. numeric attrs) still become text."""
    assert attr_str(_tag('<div data-count="5">t</div>'), "data-count") == "5"


def test_attr_str_result_supports_string_operations():
    """The whole point: the return value is safe to call str methods on."""
    value = attr_str(_tag('<div class="a b">t</div>'), "class")
    assert value is not None
    assert value.startswith("a")
