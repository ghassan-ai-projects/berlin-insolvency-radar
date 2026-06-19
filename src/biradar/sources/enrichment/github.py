"""GitHub enrichment adapter."""

from __future__ import annotations

import logging
import time

from biradar.sources.enrichment.registry import register_enrichment_source
from biradar.sources.enrichment.runtime import _get_client

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


def lookup_github(company_name: str) -> dict[str, object] | None:
    """Search GitHub for an organisation matching the company name."""
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


register_enrichment_source("github", lookup_github)
