"""Review service for candidate approval, rejection, and scoring.

The public surface is re-exported so consumers keep importing from
``biradar.services.reviews``. Nothing patches this module at module level;
the service exposes its repositories as instance attributes.
"""

from biradar.services.reviews.service import ReviewService

__all__ = ["ReviewService"]
