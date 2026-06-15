"""Generate the legacy fixture DuckDB from JSON for Phase 1 tests."""

import json
from pathlib import Path

import duckdb


def build_legacy_fixture(fixture_json_path: str, output_db_path: str) -> None:
    """Read fixture JSON and write to a temporary DuckDB file."""
    with open(fixture_json_path, encoding="utf-8") as f:
        rows = json.load(f)

    # Connect to the output DB
    import os

    if os.path.exists(output_db_path):
        os.remove(output_db_path)
    conn = duckdb.connect(output_db_path)

    # Create the minimal filings table expected by the legacy adapter
    conn.execute(
        """
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
        """
    )

    # Insert rows
    for row in rows:
        conn.execute(
            """
            INSERT INTO filings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row.get("filing_id"),
                row.get("company_name"),
                row.get("legal_form"),
                row.get("court"),
                row.get("case_number"),
                row.get("register_number"),
                row.get("publication_date"),
                row.get("publication_type"),
                row.get("source_url"),
                row.get("raw_text"),
                row.get("scraped_at"),
            ],
        )

    conn.close()
    print(f"Generated legacy fixture at: {output_db_path}")


if __name__ == "__main__":
    base_dir = Path(__file__).parent
    build_legacy_fixture(
        str(base_dir / "fixture_rows.json"), str(base_dir / "legacy_fixture.duckdb")
    )
