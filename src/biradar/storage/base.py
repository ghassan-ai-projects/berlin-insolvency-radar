"""Shared base class for the repository modules."""

from biradar.storage.db import Database


class BaseRepository:
    """Common constructor wiring for repositories backed by one DuckDB database."""

    def __init__(self, db: Database):
        self.db = db
