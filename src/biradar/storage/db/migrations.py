"""Schema migrations: ordered DDL applied by the migration runner.

The SQL literals are frozen — AGENTS.md forbids modifying an existing
migration; add a new entry to ``MIGRATIONS`` instead. The DDL text is
preserved byte-identically (including indentation) from the original
``storage/db.py``.
"""

from collections.abc import Callable

import duckdb

MigrationFn = Callable[[duckdb.DuckDBPyConnection], None]


def create_core_tables(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the ten core pipeline tables in one DDL batch."""
    conn.execute("""
            CREATE TABLE IF NOT EXISTS source_providers (
                source_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                kind VARCHAR NOT NULL,
                trust_level VARCHAR NOT NULL,
                enabled BOOLEAN DEFAULT true,
                config_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS source_runs (
                source_run_id VARCHAR PRIMARY KEY,
                source_id VARCHAR NOT NULL,
                run_type VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                params_json VARCHAR,
                records_seen INTEGER DEFAULT 0,
                records_imported INTEGER DEFAULT 0,
                duplicates INTEGER DEFAULT 0,
                rejected INTEGER DEFAULT 0,
                error_json VARCHAR
            );

            CREATE TABLE IF NOT EXISTS raw_records (
                raw_record_id VARCHAR PRIMARY KEY,
                source_run_id VARCHAR NOT NULL,
                source_id VARCHAR NOT NULL,
                external_id VARCHAR,
                retrieved_at TIMESTAMP NOT NULL,
                source_url VARCHAR,
                raw_text VARCHAR,
                raw_json VARCHAR,
                content_hash VARCHAR NOT NULL,
                parser_version VARCHAR
            );

            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id VARCHAR PRIMARY KEY,
                canonical_company_name VARCHAR NOT NULL,
                legal_form VARCHAR,
                court VARCHAR,
                case_number VARCHAR,
                register_number VARCHAR,
                publication_date DATE,
                publication_type VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'raw_candidate',
                source_quality VARCHAR,
                risk_flags_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS candidate_sources (
                candidate_id VARCHAR NOT NULL,
                raw_record_id VARCHAR NOT NULL,
                match_confidence FLOAT,
                match_reason VARCHAR,
                PRIMARY KEY (candidate_id, raw_record_id)
            );

            CREATE TABLE IF NOT EXISTS evidence_items (
                evidence_id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                source_provider VARCHAR NOT NULL,
                source_url VARCHAR,
                retrieved_at TIMESTAMP NOT NULL,
                field VARCHAR NOT NULL,
                value VARCHAR NOT NULL,
                confidence VARCHAR,
                trust_level VARCHAR,
                snippet VARCHAR,
                content_hash VARCHAR
            );

            CREATE TABLE IF NOT EXISTS scores (
                score_id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                score_version VARCHAR NOT NULL,
                company_value INTEGER,
                asset_quality INTEGER,
                sector_attractiveness INTEGER,
                speed_of_action INTEGER,
                legal_risk INTEGER,
                computed_score FLOAT NOT NULL,
                category VARCHAR,
                rationale_json VARCHAR,
                status VARCHAR NOT NULL DEFAULT 'proposed',
                reviewer VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                approved_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reviews (
                review_id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                reviewer VARCHAR NOT NULL,
                decision VARCHAR NOT NULL,
                from_status VARCHAR,
                to_status VARCHAR NOT NULL,
                note VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS issues (
                issue_id VARCHAR PRIMARY KEY,
                week VARCHAR NOT NULL,
                tier VARCHAR NOT NULL,
                status VARCHAR NOT NULL DEFAULT 'draft',
                title VARCHAR,
                draft_markdown VARCHAR,
                created_by VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exported_at TIMESTAMP,
                export_path VARCHAR
            );

            CREATE TABLE IF NOT EXISTS issue_candidates (
                issue_id VARCHAR NOT NULL,
                candidate_id VARCHAR NOT NULL,
                rank INTEGER,
                section VARCHAR,
                included_score_id VARCHAR,
                PRIMARY KEY (issue_id, candidate_id)
            );
        """)


def create_audit_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the audit event log table."""
    conn.execute("""
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_id VARCHAR PRIMARY KEY,
                actor VARCHAR NOT NULL,
                action VARCHAR NOT NULL,
                entity_type VARCHAR NOT NULL,
                entity_id VARCHAR NOT NULL,
                request_json VARCHAR,
                result_json VARCHAR,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)


def create_enrichments_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the enrichment results table."""
    conn.execute("""
            CREATE TABLE IF NOT EXISTS enrichments (
                id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                sector VARCHAR,
                employee_count_range VARCHAR,
                funding_info VARCHAR,
                tech_stack VARCHAR,
                website_url VARCHAR,
                website_status VARCHAR,
                github_org VARCHAR,
                patent_count INTEGER DEFAULT 0,
                enriched_at VARCHAR NOT NULL,
                FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
            );
        """)


def create_enrichment_claims_table(conn: duckdb.DuckDBPyConnection) -> None:
    """Create the enrichment claims table."""
    conn.execute("""
            CREATE TABLE IF NOT EXISTS enrichment_claims (
                claim_id VARCHAR PRIMARY KEY,
                candidate_id VARCHAR NOT NULL,
                source_provider VARCHAR NOT NULL,
                source_url VARCHAR,
                retrieved_at VARCHAR NOT NULL,
                field VARCHAR NOT NULL,
                value VARCHAR NOT NULL,
                classification VARCHAR,
                note VARCHAR,
                content_hash VARCHAR NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (candidate_id) REFERENCES candidates(candidate_id)
            );
        """)


MIGRATIONS: tuple[tuple[str, MigrationFn], ...] = (
    ("001_core_tables", create_core_tables),
    ("002_audit_table", create_audit_table),
    ("003_enrichments", create_enrichments_table),
    ("004_enrichment_claims", create_enrichment_claims_table),
)

MIGRATION_SEQUENCE: tuple[str, ...] = tuple(name for name, _fn in MIGRATIONS)
LATEST_SCHEMA_VERSION = MIGRATION_SEQUENCE[-1]
