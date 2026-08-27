from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from core.access import active_assignment, approved_assignments


class CurrentUserAPIView(APIView):
    """Return the authenticated user's current role and department context."""

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        assignment = active_assignment(request.user)
        assignments = approved_assignments(request.user).select_related('role', 'department')

        return Response({
            'id': request.user.pk,
            'username': request.user.get_username(),
            'email': request.user.email,
            'name': request.user.get_full_name().strip() or request.user.get_username(),
            'is_superuser': request.user.is_superuser,
            'profile_department': profile.department.name if profile and profile.department else '',
            'active_role': assignment.role.name if assignment else '',
            'active_department': assignment.department.name if assignment else '',
            'roles': [
                {
                    'code': item.role.code,
                    'name': item.role.name,
                    'department': item.department.name,
                    'department_code': item.department.code,
                }
                for item in assignments
            ],
        })
