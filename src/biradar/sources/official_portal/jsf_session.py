"""JSF session state handling and the date-range search form payload."""

import logging
import re
from typing import Any
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from biradar.sources.official_portal.constants import PORTAL_URL
from biradar.utils.html import attr_str

logger = logging.getLogger(__name__)


class JSFSession:
    """Manages JSF session state, including ViewState and cookies."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.view_state: str | None = None
        self.token: str | None = None
        self.form_action: str = PORTAL_URL
        self.form_id: str = "frm_suche"
        self.view_state_field: str = "jakarta.faces.ViewState"

    async def initialize(self) -> None:
        """Initialize the session by fetching the initial page and extracting JSF state."""
        logger.info("Initializing JSF session for official portal")
        html = await self._fetch_initial_page()
        soup = BeautifulSoup(html, "html.parser")
        self._extract_form_state(soup)
        self._extract_csrf_token(html)

    async def _fetch_initial_page(self) -> str:
        """GET the search page and return its HTML."""
        response = await self.client.get(PORTAL_URL, timeout=15.0)
        response.raise_for_status()
        return response.text

    def _extract_form_state(self, soup: BeautifulSoup) -> None:
        """Extract the form action and ViewState; raise when either is missing."""
        search_form = soup.find("form", {"id": self.form_id})
        if search_form is None:
            raise RuntimeError("Search form frm_suche not found on official portal")

        action = attr_str(search_form, "action")
        if action:
            self.form_action = urljoin(PORTAL_URL, action)

        view_state_input = search_form.find("input", {"name": self.view_state_field})
        if view_state_input and attr_str(view_state_input, "value"):
            self.view_state = attr_str(view_state_input, "value")
            logger.debug("Extracted jakarta.faces.ViewState")
        else:
            raise RuntimeError("Could not extract jakarta.faces.ViewState")

    def _extract_csrf_token(self, html: str) -> None:
        """Extract the CSRF token when present (often named 'token' in JSF)."""
        token_match = re.search(r'<input[^>]*name="token"[^>]*value="([^"]*)"', html)
        if token_match:
            self.token = token_match.group(1)
            logger.debug("Extracted CSRF token")

    def get_payload(self, form_data: dict[str, Any]) -> dict[str, Any]:
        """Build the JSF POST payload with required state fields."""
        payload = {
            self.form_id: self.form_id,
        }
        if self.view_state:
            payload[self.view_state_field] = self.view_state
        if self.token:
            payload["token"] = self.token
        payload.update(form_data)
        return payload


def build_date_range_form_data(start_date, end_date) -> dict[str, str]:
    """Build the frm_suche form fields for a Berlin date-range search."""
    return {
        "frm_suche:ldi_datumVon:datumHtml5": start_date.isoformat(),
        "frm_suche:ldi_datumBis:datumHtml5": end_date.isoformat(),
        "frm_suche:lsom_wildcard:lsom": "0",
        "frm_suche:lsom_gegenstand:codelist:mysom": "NO_CODE",
        "frm_suche:lsom_bundesland:codelist:scl_bundesland:mysom": "BE",
        "frm_suche:lsi_insolvenzgerichte:codelist:scl_insolvenzgericht:mysom": "NO_CODE",
        "frm_suche:litx_firmaNachName:text": "",
        "frm_suche:litx_vorname:text": "",
        "frm_suche:litx_sitzWohnsitz:text": "",
        "frm_suche:iaz_aktenzeichen:itx_abteilung": "",
        "frm_suche:iaz_aktenzeichen:itx_lfdNr": "",
        "frm_suche:iaz_aktenzeichen:itx_jahr": "",
        "frm_suche:iaz_aktenzeichen:ih_aktenzeichen": "true",
        "frm_suche:ir_registereintrag:itx_registernummer": "",
        "frm_suche:ir_registereintrag:ih_registereintrag": "true",
        "frm_suche:cbt_suchen": "Suchen",
    }
