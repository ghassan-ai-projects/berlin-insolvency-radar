"""Checkpointing for LangGraph workflows."""

from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver

from biradar.config.settings import get_settings
from biradar.observability.logging import get_logger

logger = get_logger(__name__)

try:
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - depends on installed extras
    sqlite3 = None
    SqliteSaver = None

class CheckpointManager:
    """Manage checkpointing with a SQLite saver when available, else memory saver."""

    def __init__(self, db_path: str | Path):
        self._conn = None
        self.db_path = None if db_path == ":memory:" else Path(db_path)

        if SqliteSaver is not None and sqlite3 is not None and self.db_path is not None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL;")
            self.db_path.chmod(0o600)
            self.saver = SqliteSaver(self._conn)
            logger.info("Using SQLite LangGraph checkpoint saver", extra={"path": str(self.db_path)})
        else:
            self.saver = MemorySaver()
            logger.warning("SQLite LangGraph checkpoint saver unavailable; using in-memory saver")

    @property
    def saver_instance(self):
        """Return the configured saver instance."""
        return self.saver

    def close(self) -> None:
        """Close the underlying database connection."""
        if self._conn is not None:
            self._conn.close()
            logger.info("Checkpoint manager connection closed")

    def clear_thread(self, thread_id: str) -> None:
        """Clear checkpoint history for a specific thread."""
        if self.db_path is None or sqlite3 is None:
            logger.info(
                "Checkpoint clear requested with in-memory saver; nothing persisted",
                extra={"thread_id": thread_id},
            )
            return
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
            conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
        logger.info("Cleared checkpoint history for thread", extra={"thread_id": thread_id})
