"""Official portal source adapter for neu.insolvenzbekanntmachungen.de.

This adapter implements JSF session management against the current live portal
markup, including extracting and replaying the active `jakarta.faces.ViewState`
and submitting the real `frm_suche` search form.

The adapter lives in per-concern modules inside this package and is
re-exported here, so ``biradar.sources.official_portal`` stays the single
import surface for the pipeline, the utils, and the tests.

``import asyncio`` / ``import httpx`` below are monkeypatch anchors: the unit
tests patch ``biradar.sources.official_portal.httpx.AsyncClient`` and
``biradar.sources.official_portal.asyncio.sleep``, which resolve through this
module's namespace.
"""

import asyncio  # noqa: F401  (monkeypatch anchor, see module docstring)

import httpx  # noqa: F401  (monkeypatch anchor, see module docstring)

from biradar.sources.official_portal.adapter import OfficialPortalAdapter
from biradar.sources.official_portal.constants import PORTAL_URL, USER_AGENT
from biradar.sources.official_portal.jsf_session import JSFSession
from biradar.sources.official_portal.models import ParsedPortalResponse
from biradar.sources.official_portal.value_normalization import (
    _infer_legal_form,
    _normalize_publication_date,
)

__all__ = [
    "PORTAL_URL",
    "USER_AGENT",
    "JSFSession",
    "OfficialPortalAdapter",
    "ParsedPortalResponse",
    "_infer_legal_form",
    "_normalize_publication_date",
]
