"""Multi-source company enrichment using free public APIs.

Sources (all free / public):
  1. Bundesanzeiger    — annual reports / balance sheets via web scraping
  2. GitHub API        — organisation lookup
  3. Company Website   — homepage fetch (title, meta description, tech signals)
  4. Handelsregister   — public register portal

Rate limiting: 0.3 s pause between source calls.
Error handling: each source is wrapped; failures are logged, never crash.

Gating: controlled by `config/sources.yaml` enrichment settings.
"""

from __future__ import annotations

import json
import logging
import re
import socket
import ssl
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from biradar.config.settings import get_settings, load_config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT: str = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
MAX_RETRIES: int = 3
# Sources that returned terminal errors (400, 403, Cloudflare) —
# skipped for the remainder of the pipeline run to avoid wasting time.
_disabled_sources: set[str] = set()

WEBSITE_TLDS: list[str] = [".de", ".com", ".eu"]

TECH_SIGNALS: list[tuple[str, re.Pattern]] = [
    ("React", re.compile(r"react\.js|react\.min\.js|__REACT_", re.I)),
    ("Vue.js", re.compile(r"vue\.js|vue\.min\.js|__VUE_", re.I)),
    ("Angular", re.compile(r"angular\.js|angular\.min\.js|ng-app|ng-version", re.I)),
    ("Next.js", re.compile(r"next\.js|__NEXT_DATA__", re.I)),
    ("Node.js", re.compile(r"node\.js|express|socket\.io", re.I)),
    ("Python", re.compile(r"django|flask|fastapi|python", re.I)),
    ("Shopify", re.compile(r"shopify\.com|myshopify\.com", re.I)),
    ("WordPress", re.compile(r"wp-content|wp-includes|wordpress", re.I)),
    ("jQuery", re.compile(r"jquery\.js|jquery\.min\.js", re.I)),
    ("Docker", re.compile(r"docker|container", re.I)),
    ("AWS", re.compile(r"aws\.amazon|amazonaws\.com|s3\.amazonaws", re.I)),
    ("Azure", re.compile(r"azure\.com|azurestatic|azureedge", re.I)),
]

BUNDESANZEIGER_SEARCH_URL = "https://www.bundesanzeiger.de/pub/de/suchergebnis"
GITHUB_API_BASE = "https://api.github.com"
HANDELSREGISTER_SEARCH_URL = "https://www.handelsregister.de/rp_web/search.do"
NORTH_DATA_BASE_URL = "https://www.northdata.de"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class EnrichmentResult(BaseModel):
    """Aggregated result from all enrichment sources."""

    company_name: str
    sources: list[dict[str, Any]] = []
    errors: list[str] = []
    enriched: bool = False
    sector: str | None = None
    tech_stack: str | None = None
    website_url: str | None = None
    website_status: int | None = None
    github_org: str | None = None
    funding_info: str | None = None
    legal_form: str | None = None
    registry_court: str | None = None
    registry_number: str | None = None
    company_status: str | None = None


EnrichmentLookupFn = Callable[[str], dict[str, Any] | None]


@dataclass(frozen=True)
class EnrichmentSourceDefinition:
    """Registered enrichment source metadata."""

    name: str
    lookup_fn: EnrichmentLookupFn


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_http_client: httpx.Client | None = None
_enrichment_source_registry: dict[str, EnrichmentSourceDefinition] = {}


def _reset_disabled_sources() -> None:
    """Clear the disabled-sources set (for test resets)."""
    _disabled_sources.clear()


def register_enrichment_source(
    name: str, lookup_fn: EnrichmentLookupFn
) -> EnrichmentSourceDefinition:
    """Register an enrichment lookup in execution order."""
    source = EnrichmentSourceDefinition(name=name, lookup_fn=lookup_fn)
    _enrichment_source_registry[name] = source
    return source


def get_registered_enrichment_sources() -> list[EnrichmentSourceDefinition]:
    """Return the registered enrichment sources in execution order."""
    return list(_enrichment_source_registry.values())


def _get_client() -> httpx.Client:
    """Return a shared httpx Client (lazy-init)."""
    global _http_client
    if _http_client is None:
        config = _get_enrichment_config()
        _http_client = httpx.Client(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
    return _http_client


def _close_client() -> None:
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None


def _http_get(url: str) -> httpx.Response | None:
    """GET with retries. Returns response or None on final failure.

    SSL errors, connection errors, and anti-bot blocks (403) are skipped
    immediately without retry.
    """
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()
            resp = client.get(url)
            if resp.status_code == 403:
                text_lower = (resp.text or "")[:2000].lower()
                if any(
                    marker in text_lower
                    for marker in (
                        "cloudflare",
                        "cf-challenge",
                        "captcha",
                        "access denied",
                    )
                ):
                    logger.debug("Anti-bot block fetching %s (skipping)", url)
                    return None
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException as exc:
            logger.debug(
                "Timeout fetching %s (attempt %d/%d)", url, attempt, MAX_RETRIES
            )
            last_error = exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.debug(
                "HTTP %s fetching %s (attempt %d/%d)",
                status,
                url,
                attempt,
                MAX_RETRIES,
            )
            if status in (403, 400):
                break
            last_error = exc
        except ssl.SSLError as exc:
            logger.debug("SSL error fetching %s (skipping): %s", url, exc)
            last_error = exc
            break
        except (httpx.ConnectError, ConnectionError, OSError) as exc:
            logger.debug(
                "Connection/network error fetching %s (skipping): %s", url, exc
            )
            last_error = exc
            break
        except httpx.RequestError as exc:
            logger.debug(
                "Request error fetching %s (attempt %d/%d): %s",
                url,
                attempt,
                MAX_RETRIES,
                exc,
            )
            last_error = exc

        if attempt < MAX_RETRIES:
            time.sleep(1.0)

    logger.warning("All %d retries exhausted for %s: %s", MAX_RETRIES, url, last_error)
    return None


# ---------------------------------------------------------------------------
# Source: Bundesanzeiger
# ---------------------------------------------------------------------------


def lookup_bundesanzeiger(company_name: str) -> dict[str, Any] | None:
    """Search Bundesanzeiger for annual reports / balance sheets."""
    try:
        client = _get_client()
        params: dict[str, Any] = {
            "suchbegriff": company_name,
            "suchbereich": "alle",
        }
        resp = client.get(BUNDESANZEIGER_SEARCH_URL, params=params)
        resp.raise_for_status()
        html = resp.text

        annual_reports: list[str] = []
        balance_summary: str | None = None
        revenue_estimate: str | None = None

        if "Jahresabschluss" in html or "Jahresbericht" in html:
            years = re.findall(r"\b(20[1-2]\d)\b", html)
            unique_years = sorted(set(years))[:5]
            annual_reports = [f"Jahresabschluss {y}" for y in unique_years]

        if "Bilanz" in html:
            balance_summary = "Balance sheet data available"

        revenue_matches = re.findall(
            r"(?:Umsatz|Umsatzerlöse|Gesamtleistung)[^\d]*"
            r"([\d\s.,]+(?:Mio\.|Millionen|Mrd\.|Milliarden)?\s*(?:EUR|€))",
            html,
            re.I,
        )
        if revenue_matches:
            revenue_estimate = revenue_matches[0].strip()

        return {
            "annual_reports": annual_reports,
            "balance_summary": balance_summary,
            "revenue_estimate": revenue_estimate,
            "source": "bundesanzeiger",
        }
    except Exception as exc:
        logger.warning("Bundesanzeiger lookup failed for '%s': %s", company_name, exc)
        return None


# ---------------------------------------------------------------------------
# Source: GitHub API
# ---------------------------------------------------------------------------


def lookup_github(company_name: str) -> dict[str, Any] | None:
    """Search GitHub for an organisation matching the company name.

    Uses the public GitHub REST API (no auth required for basic search).
    """
    try:
        client = _get_client()

        search_url = f"{GITHUB_API_BASE}/search/users"
        params = {"q": f"{company_name} type:org"}
        resp = client.get(search_url, params=params)

        if resp.status_code == 403 and "rate limit" in (resp.text or "").lower():
            logger.debug("GitHub rate limited, waiting 60s...")
            time.sleep(60)
            resp = client.get(search_url, params=params)

        resp.raise_for_status()
        data = resp.json()

        items = data.get("items", [])
        if not items:
            return None

        org_login = items[0].get("login", "")
        if not org_login:
            return None

        org_url = f"{GITHUB_API_BASE}/orgs/{org_login}"
        org_resp = client.get(org_url)
        org_resp.raise_for_status()
        org_data = org_resp.json()

        repos_url = f"{GITHUB_API_BASE}/orgs/{org_login}/repos"
        repos_resp = client.get(repos_url, params={"per_page": 10, "sort": "updated"})
        repos_resp.raise_for_status()
        repos_data = repos_resp.json()

        total_stars = sum(r.get("stargazers_count", 0) for r in repos_data)
        latest_push: str | None = None
        languages: set[str] = set()

        for repo in repos_data:
            pushed = repo.get("pushed_at")
            if pushed and (latest_push is None or pushed > latest_push):
                latest_push = pushed
            lang = repo.get("language")
            if lang:
                languages.add(lang)

        return {
            "org_name": org_login,
            "org_description": org_data.get("description"),
            "public_repos": org_data.get("public_repos", 0),
            "stars": total_stars,
            "last_push": latest_push,
            "language": list(languages)[:3] if languages else None,
            "source": "github",
        }
    except Exception as exc:
        logger.warning("GitHub lookup failed for '%s': %s", company_name, exc)
        return None


# ---------------------------------------------------------------------------
# Source: Company Website
# ---------------------------------------------------------------------------


def _dns_resolves(hostname: str) -> bool:
    """Check if a hostname has a resolvable DNS entry."""
    try:
        socket.getaddrinfo(hostname, 443, socket.AF_INET, socket.SOCK_STREAM)
        return True
    except socket.gaierror:
        return False


def _build_company_slug(company_name: str) -> str:
    """Build a domain slug from a company name."""
    slug = company_name.lower().strip()
    suffixes = [
        " gmbh",
        " ag",
        " ug",
        " se",
        " gmbh & co. kg",
        " kg",
        " ohg",
        " e.v.",
        " e.g.",
    ]
    for suffix in suffixes:
        slug = re.sub(rf"\s*{re.escape(suffix.strip())}\s*$", "", slug)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    if not slug:
        slug = company_name.lower().replace(" ", "-")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug


def lookup_website(company_name: str) -> dict[str, Any] | None:
    """Try to locate and scrape the company website.

    Uses a short timeout (5s) and single attempt per URL — DNS pre-filters
    dead domains, so retries add overhead without benefit.
    """
    slug = _build_company_slug(company_name)

    candidates = [f"https://{slug}{tld}" for tld in WEBSITE_TLDS]
    candidates = [
        url for url in candidates if _dns_resolves(urlparse(url).hostname or "")
    ]

    client = _get_client()
    website_timeout = httpx.Timeout(3.0)

    for url in candidates:
        try:
            resp = client.get(url, timeout=website_timeout)
            if resp.status_code == 403:
                text_lower = (resp.text or "")[:2000].lower()
                if any(
                    marker in text_lower
                    for marker in (
                        "cloudflare",
                        "cf-challenge",
                        "captcha",
                        "access denied",
                    )
                ):
                    logger.debug("Anti-bot block on %s (skipping)", url)
                    continue
            resp.raise_for_status()
        except httpx.TimeoutException:
            logger.debug("Website timeout for %s (skipping)", url)
            continue
        except (httpx.HTTPStatusError, httpx.ConnectError, ssl.SSLError, OSError):
            continue
        except httpx.RequestError:
            continue

        try:
            html = resp.text
            title: str = ""
            description: str = ""
            tech_signals: list[str] = []

            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
            if title_match:
                title = title_match.group(1).strip()

            desc_match = re.search(
                r'<meta\s+[^>]*name\s*=\s*["\']description["\'][^>]*'
                r'content\s*=\s*["\']([^"\']+)["\']',
                html,
                re.I,
            )
            if not desc_match:
                desc_match = re.search(
                    r'<meta\s+[^>]*content\s*=\s*["\']([^"\']+)["\'][^>]*'
                    r'name\s*=\s*["\']description["\']',
                    html,
                    re.I,
                )
            if desc_match:
                description = desc_match.group(1).strip()

            for signal_name, pattern in TECH_SIGNALS:
                if pattern.search(html):
                    tech_signals.append(signal_name)

            return {
                "url": url,
                "title": title,
                "description": description,
                "tech_signals": tech_signals,
                "status_code": resp.status_code,
                "source": "website",
            }
        except Exception as exc:
            logger.debug("Error parsing website %s: %s", url, exc)
            continue

    return None


# ---------------------------------------------------------------------------
# Source: Handelsregister (public portal)
# ---------------------------------------------------------------------------


def lookup_handelsregister(company_name: str) -> dict[str, Any] | None:
    """Search the public Handelsregister portal for company registration data."""
    try:
        client = _get_client()
        params: dict[str, Any] = {
            "suchbegriff": company_name,
            "registerArt": "alle",
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = client.get(HANDELSREGISTER_SEARCH_URL, params=params, headers=headers)
        if resp.status_code in (400, 403):
            _disabled_sources.add("handelsregister")
            logger.warning(
                "Handelsregister returned %d — disabling for remainder of run",
                resp.status_code,
            )
            return None
        resp.raise_for_status()
        html = resp.text

        legal_form: str | None = None
        registry_court: str | None = None
        registry_number: str | None = None
        status: str | None = None

        for form in [
            "GmbH & Co. KG",
            "GmbH",
            "AG",
            "UG",
            "SE",
            "e.V.",
            "KG",
            "OHG",
        ]:
            if re.search(rf"\b{re.escape(form)}\b", html):
                legal_form = form
                break

        court_match = re.search(
            r"(?:Amtsgericht|AG)\s+([A-ZÄÖÜ][a-zäöü]+(?:\s+[A-ZÄÖÜ][a-zäöü]+)*)",
            html,
        )
        if court_match:
            registry_court = court_match.group(0)

        reg_match = re.search(r"(HR[AB]\s*\d+\s*(?:[A-Z][a-z]+)?)", html)
        if reg_match:
            registry_number = reg_match.group(1)

        if "aktiv" in html.lower() or "active" in html.lower():
            status = "active"
        elif "gelöscht" in html.lower() or "löschung" in html.lower():
            status = "deleted"
        elif "aufgelöst" in html.lower():
            status = "dissolved"

        if not any([legal_form, registry_court, registry_number, status]):
            return None

        return {
            "legal_form": legal_form,
            "registry_court": registry_court,
            "registry_number": registry_number,
            "status": status,
            "source": "handelsregister",
        }
    except Exception as exc:
        logger.warning("Handelsregister lookup failed for '%s': %s", company_name, exc)
        return None


def lookup_north_data(company_name: str) -> dict[str, Any] | None:
    """Search North Data for public registry and sector metadata."""
    try:
        client = _get_client()
        search_resp = client.get(NORTH_DATA_BASE_URL, params={"query": company_name})
        search_resp.raise_for_status()
        search_soup = BeautifulSoup(search_resp.text, "html.parser")

        detail_href = None
        for link in search_soup.find_all("a", href=True):
            href = link.get("href")
            if href is None:
                continue
            if not href.startswith("/") or href.startswith("/_"):
                continue
            if href.count("/") < 2:
                continue
            detail_href = href
            break

        if not detail_href:
            return None

        detail_url = f"{NORTH_DATA_BASE_URL}{detail_href}"
        detail_resp = client.get(detail_url)
        detail_resp.raise_for_status()
        detail_soup = BeautifulSoup(detail_resp.text, "html.parser")

        registry_number = None
        title = detail_soup.title.get_text(strip=True) if detail_soup.title else ""
        registry_match = re.search(r"(HR[AB]\s*\d+\s*[A-Z]?)", title)
        if registry_match:
            registry_number = registry_match.group(1)

        sector = None
        for script in detail_soup.find_all("script", type="application/ld+json"):
            try:
                structured = json.loads(script.get_text())
            except json.JSONDecodeError:
                continue
            if structured.get("@type") == "BreadcrumbList":
                for item in structured.get("itemListElement", []):
                    name = item.get("item", {}).get("name")
                    if name and name != "Firmen":
                        sector = name
                        break
            if sector:
                break

        if not registry_number and not sector:
            return None

        return {
            "registry_number": registry_number,
            "sector": sector,
            "source": "north_data",
            "source_url": detail_url,
        }
    except Exception as exc:
        logger.warning("North Data lookup failed for '%s': %s", company_name, exc)
        return None


def _resolve_wikidata_entity_label(entity_id: str) -> str | None:
    """Resolve a Wikidata entity label in German or English."""
    client = _get_client()
    resp = client.get(
        WIKIDATA_API_URL,
        params={
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "labels",
            "languages": "de|en",
            "format": "json",
        },
    )
    resp.raise_for_status()
    entity = resp.json().get("entities", {}).get(entity_id, {})
    labels = entity.get("labels", {})
    return labels.get("de", {}).get("value") or labels.get("en", {}).get("value")


def lookup_wikidata(company_name: str) -> dict[str, Any] | None:
    """Search Wikidata for public website and industry metadata."""
    try:
        client = _get_client()
        search_resp = client.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbsearchentities",
                "search": company_name,
                "language": "de",
                "type": "item",
                "limit": 1,
                "format": "json",
            },
        )
        search_resp.raise_for_status()
        search_results = search_resp.json().get("search", [])
        if not search_results:
            return None

        entity_id = search_results[0].get("id")
        if not entity_id:
            return None

        entity_resp = client.get(
            WIKIDATA_API_URL,
            params={
                "action": "wbgetentities",
                "ids": entity_id,
                "props": "claims",
                "format": "json",
            },
        )
        entity_resp.raise_for_status()
        claims = (
            entity_resp.json().get("entities", {}).get(entity_id, {}).get("claims", {})
        )

        website_url = None
        if "P856" in claims:
            website_claim = claims["P856"][0]
            website_url = (
                website_claim.get("mainsnak", {}).get("datavalue", {}).get("value")
            )

        sector = None
        if "P452" in claims:
            industry_claim = claims["P452"][0]
            industry_value = (
                industry_claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
            )
            industry_entity_id = industry_value.get("id")
            if industry_entity_id:
                sector = _resolve_wikidata_entity_label(industry_entity_id)

        if not website_url and not sector:
            return None

        return {
            "website_url": website_url,
            "sector": sector,
            "source": "wikidata",
            "source_url": f"https://www.wikidata.org/wiki/{entity_id}",
        }
    except Exception as exc:
        logger.warning("Wikidata lookup failed for '%s': %s", company_name, exc)
        return None


# Default registry order. New sources should be added here or via register_enrichment_source.
register_enrichment_source("bundesanzeiger", lookup_bundesanzeiger)
register_enrichment_source("github", lookup_github)
register_enrichment_source("website", lookup_website)
register_enrichment_source("handelsregister", lookup_handelsregister)
register_enrichment_source("north_data", lookup_north_data)
register_enrichment_source("wikidata", lookup_wikidata)


# ---------------------------------------------------------------------------
# Main enricher
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _get_enrichment_config():
    settings = get_settings()
    return load_config(settings.project_root / "config").enrichment


def _is_source_enabled(source_name: str, enrichment_config: Any) -> bool:
    """Resolve whether a registered source is enabled in config."""
    source_flags = getattr(enrichment_config, "sources", {}) or {}
    return bool(source_flags.get(source_name, True))


def _resolve_enrichment_sources() -> list[EnrichmentSourceDefinition]:
    """Resolve registered sources after applying config-based enablement."""
    enrichment_config = _get_enrichment_config()
    return [
        source
        for source in get_registered_enrichment_sources()
        if _is_source_enabled(source.name, enrichment_config)
    ]


def _aggregate_result(sources_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate flat fields from source results for DB persistence."""
    sector: str | None = None
    tech_stack: str | None = None
    website_url: str | None = None
    website_status: int | None = None
    github_org: str | None = None
    funding_info: str | None = None
    legal_form: str | None = None
    registry_court: str | None = None
    registry_number: str | None = None
    company_status: str | None = None

    for src in sources_results:
        src_name = src.get("source", "")

        if src_name == "handelsregister":
            lf = src.get("legal_form")
            if lf:
                legal_form = lf
                sector = f"Legal form: {lf}"
            registry_court = src.get("registry_court") or registry_court
            registry_number = src.get("registry_number") or registry_number
            company_status = src.get("status") or company_status

        if src_name == "website":
            website_url = src.get("url")
            website_status = src.get("status_code")
            ts = src.get("tech_signals")
            if ts:
                tech_stack = ", ".join(ts)

        if src_name == "wikidata":
            website_url = src.get("website_url") or website_url
            sector = src.get("sector") or sector

        if src_name == "github":
            github_org = src.get("org_name")
            ts = src.get("language")
            if ts and not tech_stack:
                tech_stack = ", ".join(ts) if isinstance(ts, list) else str(ts)

        if src_name == "bundesanzeiger":
            rev = src.get("revenue_estimate")
            if rev:
                funding_info = f"Revenue: {rev}"
            reports = src.get("annual_reports")
            if reports and not funding_info:
                funding_info = f"Reports: {', '.join(reports)}"

        if src_name == "north_data":
            sector = src.get("sector") or sector
            registry_number = src.get("registry_number") or registry_number

    return {
        "sector": sector,
        "tech_stack": tech_stack,
        "website_url": website_url,
        "website_status": website_status,
        "github_org": github_org,
        "funding_info": funding_info,
        "legal_form": legal_form,
        "registry_court": registry_court,
        "registry_number": registry_number,
        "company_status": company_status,
    }


def enrich_candidate(company_name: str) -> EnrichmentResult:
    """Run enrichment from all free sources for a candidate company.

    Each source is isolated — a single failure does not abort the pipeline.
    """
    if not company_name:
        return EnrichmentResult(
            company_name=company_name or "",
            errors=["Missing company_name"],
            enriched=False,
        )

    enrichment_config = _get_enrichment_config()
    if not enrichment_config.enabled:
        return EnrichmentResult(
            company_name=company_name,
            errors=["Enrichment is disabled in config/sources.yaml"],
            enriched=False,
        )

    errors: list[str] = []
    sources_results: list[dict[str, Any]] = []

    source_defs = _resolve_enrichment_sources()
    if not source_defs:
        return EnrichmentResult(
            company_name=company_name,
            errors=["No enrichment sources are enabled"],
            enriched=False,
        )

    for idx, source in enumerate(source_defs):
        source_name = source.name
        if source_name in _disabled_sources:
            errors.append(f"{source_name}: skipped (disabled after terminal error)")
            continue

        if idx > 0:
            time.sleep(enrichment_config.delay_between_sources)

        try:
            logger.debug("Enriching '%s' via %s ...", company_name, source_name)
            result = source.lookup_fn(company_name)
            if result is not None:
                sources_results.append(result)
            else:
                errors.append(f"{source_name}: no data returned")
        except Exception as exc:
            msg = f"{source_name}: unexpected error: {exc}"
            logger.warning(
                "Enrichment error for '%s' via %s: %s",
                company_name,
                source_name,
                exc,
            )
            errors.append(msg)

    aggregated = _aggregate_result(sources_results)

    logger.info(
        "Enrichment complete for '%s': %d sources, %d errors",
        company_name,
        len(sources_results),
        len(errors),
    )

    return EnrichmentResult(
        company_name=company_name,
        sources=sources_results,
        errors=errors,
        enriched=bool(sources_results),
        **aggregated,
    )
