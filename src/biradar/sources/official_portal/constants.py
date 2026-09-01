"""Portal endpoints, client fingerprints, and search request headers."""

PORTAL_URL = "https://neu.insolvenzbekanntmachungen.de/ap/suche.jsf"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def build_search_headers() -> dict[str, str]:
    """Build the browser-like headers the live search POST expects."""
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": PORTAL_URL,
        "Origin": "https://neu.insolvenzbekanntmachungen.de",
    }
