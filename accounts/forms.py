from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction

from core.models import AuditLog, Department, Notification, Role, RoleAssignment, UserProfile

from .querysets import visible_user_accounts


class PortalAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label='Email or username',
        widget=forms.TextInput(
            attrs={
                'class': 'login-input',
                'autocomplete': 'username',
                'placeholder': 'name@jmc.edu.ph',
                'autofocus': True,
            }
        ),
    )
    password = forms.CharField(
        label='Password',
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                'class': 'login-input',
                'autocomplete': 'current-password',
                'placeholder': 'Enter your password',
            }
        ),
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            login_identifier = username
            if '@' in username:
                user = get_user_model()._default_manager.filter(email__iexact=username).first()
                if user:
                    login_identifier = user.get_username()

            self.user_cache = authenticate(
                self.request,
                username=login_identifier,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        profile = getattr(user, 'profile', None)
        if profile and profile.is_demo_account and not settings.DEMO_MODE:
            if user.is_active:
                user.is_active = False
                user.save(update_fields=['is_active'])
            raise ValidationError('This development account is disabled in production.')
        if not profile or not profile.is_approved:
            raise ValidationError('Your account is still waiting for approval.')
        if not RoleAssignment.objects.filter(user=user, is_approved=True, role__is_active=True).exists():
            raise ValidationError('Your account has no active role assignment yet.')
        super().confirm_login_allowed(user)


class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150, label='Username')
    email = forms.EmailField(label='Email address')
    first_name = forms.CharField(max_length=80, label='First name')
    last_name = forms.CharField(max_length=80, label='Last name')
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_internal=True, is_active=True).exclude(code__in={'SUPERADMIN', 'ADMIN'}),
        empty_label='Select a role',
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        empty_label='Select a department or program',
    )
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)
    data_use_acknowledged = forms.BooleanField(
        required=False,
        label='I have read and understand this notice.',
        widget=forms.CheckboxInput(attrs={'class': 'data-use-checkbox'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'login-input')

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('That username is already in use.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('That email address is already registered.')
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The passwords do not match.')
        if password1:
            try:
                validate_password(password1)
            except ValidationError as error:
                self.add_error('password1', error)
        notice_config = getattr(settings, 'DATA_USE_NOTICES', {}).get('registration', {})
        if notice_config.get('required', True) and not cleaned.get('data_use_acknowledged'):
            self.add_error(
                'data_use_acknowledged',
                'Please confirm that you have read and understood the Data Use Notice.',
            )
        return cleaned

    @transaction.atomic
    def save(self):
        User = get_user_model()
        user = User.objects.create_user(
            username=self.cleaned_data['username'],
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            password=self.cleaned_data['password1'],
            is_active=False,
        )
        profile = UserProfile.objects.create(
            user=user,
            department=self.cleaned_data['department'],
            approval_status=UserProfile.PENDING,
        )
        assignment = RoleAssignment.objects.create(
            user=user,
            role=self.cleaned_data['role'],
            department=self.cleaned_data['department'],
            is_approved=False,
        )
        approver_ids = UserProfile.objects.filter(
            approval_status=UserProfile.APPROVED,
            user__is_active=True,
            user__role_assignments__role__code__in={'SUPERADMIN', 'ADMIN', 'QA'},
            user__role_assignments__is_approved=True,
        ).values_list('user_id', flat=True).distinct()
        Notification.objects.bulk_create([
            Notification(
                user_id=approver_id,
                kind='account',
                title='Account awaiting approval',
                message=f'{user.get_full_name() or user.username} requested a {assignment.role.name} account for {assignment.department.name}.',
            )
            for approver_id in approver_ids
        ])
        AuditLog.objects.create(
            action='ACCOUNT_REGISTERED',
            object_type='User',
            object_id=str(user.pk),
            details={'username': user.username, 'role': assignment.role.code, 'department': assignment.department.code},
        )
        return profile


class RoleSelectionForm(forms.Form):
    assignment = forms.ModelChoiceField(queryset=RoleAssignment.objects.none(), empty_label=None)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assignment'].widget.attrs['class'] = 'login-input'
        self.fields['assignment'].queryset = RoleAssignment.objects.filter(
            user=user,
            is_approved=True,
            role__is_active=True,
            department__is_active=True,
        ).select_related('role', 'department')
        self.fields['assignment'].label_from_instance = lambda assignment: (
            f'{assignment.role.name} · {assignment.department.name}'
        )


class ProfileSettingsForm(forms.Form):
    first_name = forms.CharField(max_length=80, label='First name')
    last_name = forms.CharField(max_length=80, label='Last name')
    email = forms.EmailField(label='Email address')
    photo = forms.FileField(required=False, label='Profile photo')

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['first_name'].initial = user.first_name
        self.fields['last_name'].initial = user.last_name
        self.fields['email'].initial = user.email
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'settings-input')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('That email address is already in use.')
        return email

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            if not getattr(photo, 'content_type', '').startswith('image/'):
                raise forms.ValidationError('Choose an image file.')
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError('The profile photo must be smaller than 5 MB.')
        return photo

    @transaction.atomic
    def save(self):
        self.user.first_name = self.cleaned_data['first_name'].strip()
        self.user.last_name = self.cleaned_data['last_name'].strip()
        self.user.email = self.cleaned_data['email']
        self.user.save(update_fields=['first_name', 'last_name', 'email'])
        profile = self.user.profile
        if self.cleaned_data.get('photo'):
            profile.photo = self.cleaned_data['photo']
            profile.save(update_fields=['photo', 'updated_at'])
        return profile


class RoleAssignmentForm(forms.Form):
    user = forms.ModelChoiceField(queryset=get_user_model().objects.none(), label='User')
    role = forms.ModelChoiceField(
        queryset=Role.objects.filter(is_internal=True, is_active=True),
        label='Role',
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True).order_by('name'),
        label='Department or program',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = visible_user_accounts().filter(is_superuser=False).order_by(
            'last_name', 'first_name', 'username'
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'settings-input')
