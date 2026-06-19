"""Database connection and initialization for biradar."""

import hashlib
from pathlib import Path

import duckdb

MIGRATION_SEQUENCE = (
    "001_core_tables",
    "002_audit_table",
    "003_enrichments",
    "004_enrichment_claims",
)
LATEST_SCHEMA_VERSION = MIGRATION_SEQUENCE[-1]


class Database:
    """Manages the DuckDB connection and schema initialization."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))

    def close(self) -> None:
        self.conn.close()

    def begin(self) -> None:
        self.conn.execute("BEGIN TRANSACTION")

    def commit(self) -> None:
        self.conn.execute("COMMIT")

    def rollback(self) -> None:
        self.conn.execute("ROLLBACK")

    def run_migrations(self) -> None:
        """Run database schema migrations."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                migration_name VARCHAR PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        migrations = [
            (MIGRATION_SEQUENCE[0], self._create_core_tables),
            (MIGRATION_SEQUENCE[1], self._create_audit_table),
            (MIGRATION_SEQUENCE[2], self._create_enrichments_table),
            (MIGRATION_SEQUENCE[3], self._create_enrichment_claims_table),
        ]

        for name, migration_fn in migrations:
            cursor = self.conn.execute(
                "SELECT 1 FROM schema_migrations WHERE migration_name = ?", [name]
            )
            if cursor.fetchone() is None:
                migration_fn()
                self.conn.execute(
                    "INSERT INTO schema_migrations (migration_name) VALUES (?)", [name]
                )

    def _create_core_tables(self) -> None:
        self.conn.execute("""
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

    def _create_audit_table(self) -> None:
        self.conn.execute("""
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

    def _create_enrichments_table(self) -> None:
        self.conn.execute("""
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

    def _create_enrichment_claims_table(self) -> None:
        self.conn.execute("""
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

    def get_schema_version(self) -> str:
        cursor = self.conn.execute(
            "SELECT migration_name FROM schema_migrations ORDER BY migration_name DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return row[0] if row else "unmigrated"


def compute_content_hash(data: str | bytes) -> str:
    """Compute SHA-256 hash of string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"
