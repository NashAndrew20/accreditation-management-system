from django.contrib.auth import get_user_model
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.access import active_assignment, is_approved_user


class PortalTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Issue tokens only to approved users with an internal role assignment."""

    def validate(self, attrs):
        username = attrs.get(self.username_field)
        if username and '@' in username:
            user = get_user_model().objects.filter(email__iexact=username).first()
            if user:
                attrs[self.username_field] = user.get_username()

        data = super().validate(attrs)
        if not self.user.is_superuser and not is_approved_user(self.user):
            raise serializers.ValidationError({
                'detail': 'Your account must be approved and assigned an internal role before using the API.',
            })

        assignment = active_assignment(self.user)
        data['user'] = {
            'id': self.user.pk,
            'username': self.user.get_username(),
            'email': self.user.email,
            'name': self.user.get_full_name().strip() or self.user.get_username(),
            'active_role': assignment.role.name if assignment else '',
            'active_department': assignment.department.name if assignment else '',
        }
        return data
