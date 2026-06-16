"""Bridge: import legacy insolvency_scout.duckdb into biradar."""

import sys
import uuid
import duckdb
from pathlib import Path

# Build a compatible DuckDB from the legacy scout data
scout_db = Path("data") / "insolvency_scout.duckdb"
compat_db = Path("data") / "insolvency_scout_compat.duckdb"

if compat_db.exists():
    compat_db.unlink()

conn = duckdb.connect(str(scout_db))
compat = duckdb.connect(str(compat_db))

# Create compatible filings table
compat.execute("""
    CREATE TABLE filings (
        filing_id VARCHAR,
        company_name VARCHAR,
        legal_form VARCHAR,
        court VARCHAR,
        case_number VARCHAR,
        register_number VARCHAR,
        publication_date VARCHAR,
        publication_type VARCHAR,
        source_url VARCHAR,
        raw_text VARCHAR,
        scraped_at VARCHAR
    )
""")

rows = conn.execute("""
    SELECT id, company_name, court, filing_type, published_at, scraped_at, raw_text, url, status
    FROM filings
""").fetchall()

inserted = 0
for row in rows:
    id_, name, court, filing_type, published_at, scraped_at, raw_text, url, status = row

    if not name:
        continue

    # Parse legal_form from name (GmbH, UG, AG, etc.)
    legal_form = None
    for form in ["GmbH & Co. KG", "UG (haftungsbeschränkt)", "GmbH", "UG", "AG", "SE", "e.K.", "KG", "OHG", "PartG", "GmbH & Co. OHG"]:
        if form in name:
            legal_form = form
            break

    # Parse case_number and register_number from raw_text
    # Format: "Company | Court | CASE_NUMBER | City, REGISTER | ..."
    case_number = None
    register_number = None
    if raw_text:
        parts = [p.strip() for p in raw_text.split("|")]
        if len(parts) >= 3:
            case_number = parts[2]  # e.g. "3602 IN 2175/26"
        if len(parts) >= 4:
            reg_part = parts[3]  # e.g. "Berlin, HRB 184397"
            if "," in reg_part:
                register_number = reg_part.split(",", 1)[1].strip()

    # publication_date from published_at
    pub_date = published_at or ""
    pub_type = filing_type or ""
    source_url = url or ""

    compat.execute("""
        INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        id_ or str(uuid.uuid4()),
        name or "",
        legal_form or "",
        court or "",
        case_number or "",
        register_number or "",
        pub_date,
        pub_type,
        source_url,
        raw_text or "",
        scraped_at or ""
    ])
    inserted += 1

conn.close()
compat.close()
print(f"Built compat DB: {inserted} rows at {compat_db}")
print(f"Now run: uv run biradar legacy-import data/insolvency_scout_compat.duckdb")
