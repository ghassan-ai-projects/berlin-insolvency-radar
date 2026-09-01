"""Issue service for generating and exporting newsletter drafts.

The public surface is re-exported so consumers keep importing from
``biradar.services.issues``. Tests patch repositories on the service
instance (``service.candidate_repo.get_by_id``), so no module-level
monkeypatch anchors are needed here.
"""

from biradar.services.issues.service import IssueService

__all__ = ["IssueService"]
