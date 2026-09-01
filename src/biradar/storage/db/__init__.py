"""Database connection and initialization for biradar.

The public surface is re-exported so consumers keep importing from
``biradar.storage.db``. Nothing patches this package at module level; the
frozen anchors are the ``Database.conn`` attribute, the Database method
names, and single-positional-arg construction.
"""

from biradar.storage.db.connection import Database, scalar_count
from biradar.storage.db.hashing import compute_content_hash
from biradar.storage.db.migrations import LATEST_SCHEMA_VERSION, MIGRATION_SEQUENCE

__all__ = [
    "LATEST_SCHEMA_VERSION",
    "MIGRATION_SEQUENCE",
    "Database",
    "compute_content_hash",
    "scalar_count",
]
