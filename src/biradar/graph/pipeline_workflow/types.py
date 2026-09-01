"""Injectable callable shapes for the pipeline's external actors."""

from collections.abc import Callable, Mapping
from typing import Any

ExtractorFn = Callable[[str, str], Any]
RiskReviewerFn = Callable[
    [Mapping[str, Any], Mapping[str, Any], Mapping[str, Any], str], Any
]
EnricherFn = Callable[[str], Any]
