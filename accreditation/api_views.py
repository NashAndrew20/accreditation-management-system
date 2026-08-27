from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.access import accessible_submissions

from .models import EvidenceSubmission
from .api_serializers import EvidenceSubmissionSerializer


class EvidenceSubmissionListAPIView(generics.ListAPIView):
    """List evidence submissions visible to the authenticated user's role."""

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)
    serializer_class = EvidenceSubmissionSerializer

    def get_queryset(self):
        queryset = accessible_submissions(self.request.user).select_related(
            'requirement',
            'requirement__area',
            'requirement__area__level',
            'requirement__area__level__cycle',
            'requirement__subarea',
            'department',
            'current_reviewer',
            'current_review_role',
        ).prefetch_related(
            'versions__submitted_by',
            'versions__files__uploaded_by',
            'reviews__reviewer',
            'reviews__reviewer_role',
        )

        status = self.request.query_params.get('status')
        if status:
            valid_statuses = {value for value, _ in EvidenceSubmission.STATUS_CHOICES}
            if status not in valid_statuses:
                raise ValidationError({
                    'status': f'Use one of: {", ".join(sorted(valid_statuses))}.',
                })
            queryset = queryset.filter(status=status)

        area = self.request.query_params.get('area')
        if area:
            queryset = queryset.filter(requirement__area__slug=area)

        return queryset
