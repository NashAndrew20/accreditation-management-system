"""Shared evidence status groups used by dashboards and views.

Keeping these groups in one module prevents reporting and workflow screens
from drifting apart when a status is added or renamed.
"""

from .models import EvidenceSubmission


COMPLETED_STATUSES = frozenset({
    EvidenceSubmission.COMPLIED,
    EvidenceSubmission.CLOSED,
})

ACTIVE_REVIEW_STATUSES = frozenset({
    EvidenceSubmission.UNDER_DEAN_REVIEW,
    EvidenceSubmission.UNDER_AREA_CHAIR_REVIEW,
    EvidenceSubmission.UNDER_QA_REVIEW,
})

PENDING_STATUSES = ACTIVE_REVIEW_STATUSES | frozenset({
    EvidenceSubmission.NEEDS_REVISION,
})
