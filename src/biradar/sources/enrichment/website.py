"""Website enrichment adapter and helpers."""

from __future__ import annotations

import logging
import re
import socket
import ssl
from urllib.parse import urlparse

import httpx

from biradar.sources.enrichment.registry import register_enrichment_source
from biradar.sources.enrichment.runtime import _get_client

logger = logging.getLogger(__name__)

WEBSITE_TLDS: list[str] = [".de", ".com", ".eu"]

TECH_SIGNALS: list[tuple[str, re.Pattern[str]]] = [
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


def lookup_website(company_name: str) -> dict[str, object] | None:
    """Try to locate and scrape the company website."""
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
            title = ""
            description = ""
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


register_enrichment_source("website", lookup_website)
