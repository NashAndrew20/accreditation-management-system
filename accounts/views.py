import secrets
from hmac import compare_digest
from urllib.parse import urlencode

from django.contrib.auth import login as auth_login
from django.contrib.auth.views import LoginView
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import TemplateView, View

from core.access import approved_assignments, can_approve_accounts, is_admin_user
from core.mixins import AccountApprovalMixin, ApprovedUserRequiredMixin
from core.models import AuditLog, Notification, Policy, RoleAssignment, UserProfile
from core.rate_limit import LOGIN_ATTEMPT_WINDOW, allow_login_attempt

from .forms import (
    PortalAuthenticationForm,
    ProfileSettingsForm,
    RegistrationForm,
    RoleAssignmentForm,
    RoleSelectionForm,
)
from . import google_oauth
from .querysets import visible_user_accounts


def _safe_next_url(request, candidate):
    """Return a same-host redirect target, or the dashboard by default."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return reverse('dashboard:index')


class PortalLoginView(LoginView):
    authentication_form = PortalAuthenticationForm
    template_name = 'accounts/login.html'
    # Allow an authenticated development user to return to the account picker
    # and switch between the three development personas.
    redirect_authenticated_user = False
    extra_context = {'page_title': 'Sign in'}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_policies = {p.policy_type: p for p in Policy.active_required()}
        context.update({
            'privacy_policy': active_policies.get(Policy.PRIVACY),
            'terms_policy': active_policies.get(Policy.TERMS),
        })
        return context

    def get_success_url(self):
        return self.get_redirect_url() or reverse('dashboard:index')

    def post(self, request, *args, **kwargs):
        if not allow_login_attempt(request):
            context = self.get_context_data(
                form=self.authentication_form(request=request),
                rate_limited=True,
            )
            response = self.render_to_response(context)
            response.status_code = 429
            response['Retry-After'] = str(LOGIN_ATTEMPT_WINDOW)
            return response
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get('remember_me'):
            self.request.session.set_expiry(None)
        else:
            self.request.session.set_expiry(0)
        profile = getattr(self.request.user, 'profile', None)
        if profile and not profile.active_assignment_id and approved_assignments(self.request.user).count() > 1:
            query = urlencode({'next': self.get_success_url()})
            return redirect(f'{reverse("accounts:select_role")}?{query}')
        return response


def _google_redirect_uri(request):
    configured_uri = settings.GOOGLE_OAUTH_REDIRECT_URI.strip()
    return configured_uri or request.build_absolute_uri(reverse('google_login_callback'))


class GoogleLoginStartView(View):
    """Start Google's server-side OAuth/OpenID Connect sign-in flow."""

    def get(self, request, *args, **kwargs):
        if not settings.GOOGLE_OAUTH_ENABLED:
            messages.error(request, 'Google sign-in is not configured for this environment.')
            return redirect('login')

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        request.session['google_oauth_state'] = state
        request.session['google_oauth_nonce'] = nonce
        request.session['google_oauth_next'] = _safe_next_url(request, request.GET.get('next'))
        return redirect(google_oauth.build_authorization_url(state, nonce, _google_redirect_uri(request)))


class GoogleLoginCallbackView(View):
    """Validate Google's callback and establish the normal Django session."""

    def get(self, request, *args, **kwargs):
        expected_state = request.session.pop('google_oauth_state', '')
        expected_nonce = request.session.pop('google_oauth_nonce', '')
        next_url = request.session.pop('google_oauth_next', reverse('dashboard:index'))
        received_state = request.GET.get('state', '')

        if not expected_state or not expected_nonce or not compare_digest(expected_state, received_state):
            return self._fail(request, 'Google sign-in could not be verified. Please try again.')
        if request.GET.get('error'):
            return self._fail(request, 'Google sign-in was cancelled.')

        code = request.GET.get('code', '').strip()
        if not code:
            return self._fail(request, 'Google did not return an authorization code.')

        try:
            token_data = google_oauth.exchange_code(code, _google_redirect_uri(request))
            identity = google_oauth.verify_id_token(token_data['id_token'], expected_nonce)
            user = self._approved_user(identity)
        except google_oauth.GoogleOAuthError:
            return self._fail(request, 'Google sign-in could not be completed. Please use an approved account.')

        auth_login(request, user)
        safe_next_url = _safe_next_url(request, next_url)
        profile = getattr(user, 'profile', None)
        if profile and not profile.active_assignment_id and approved_assignments(user).count() > 1:
            query = urlencode({'next': safe_next_url})
            return redirect(f'{reverse("accounts:select_role")}?{query}')
        return redirect(safe_next_url)

    @staticmethod
    def _approved_user(identity):
        user_model = get_user_model()
        user = user_model.objects.select_related('profile').filter(
            profile__google_subject=identity['sub'],
        ).first()
        if user is None:
            user = user_model.objects.select_related('profile').filter(
                email__iexact=identity['email'],
            ).first()

        profile = getattr(user, 'profile', None) if user else None
        if (
            user is None
            or profile is None
            or not user.is_active
            or not profile.is_approved
            or (
                profile.google_subject
                and profile.google_subject != identity['sub']
            )
            or not RoleAssignment.objects.filter(
                user=user,
                is_approved=True,
                role__is_active=True,
            ).exists()
        ):
            raise google_oauth.GoogleOAuthError('Google account is not approved.')

        if not profile.google_subject:
            profile.google_subject = identity['sub']
            profile.save(update_fields=['google_subject', 'updated_at'])
        return user

    @staticmethod
    def _fail(request, message):
        messages.error(request, message)
        return redirect('login')


class RegisterView(TemplateView):
    template_name = 'accounts/register.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, {'form': RegistrationForm(), 'page_title': 'Request an account'})

    def post(self, request, *args, **kwargs):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return render(request, 'accounts/registration_pending.html', {'page_title': 'Account pending approval'})
        return render(request, self.template_name, {'form': form, 'page_title': 'Request an account'})


class SelectRoleView(LoginRequiredMixin, TemplateView):
    login_url = reverse_lazy('login')
    template_name = 'accounts/select_role.html'

    def get(self, request, *args, **kwargs):
        form = RoleSelectionForm(request.user)
        return render(request, self.template_name, {
            'form': form,
            'assignments': form.fields['assignment'].queryset,
            'next_url': _safe_next_url(request, request.GET.get('next')),
        })

    def post(self, request, *args, **kwargs):
        form = RoleSelectionForm(request.user, request.POST)
        if form.is_valid():
            profile = request.user.profile
            profile.active_assignment = form.cleaned_data['assignment']
            profile.save(update_fields=['active_assignment', 'updated_at'])
            return redirect(_safe_next_url(request, request.POST.get('next')))
        return render(request, self.template_name, {
            'form': form,
            'assignments': form.fields['assignment'].queryset,
            'next_url': _safe_next_url(request, request.POST.get('next')),
        })


class ChangePasswordView(LoginRequiredMixin, PasswordChangeView):
    login_url = reverse_lazy('login')
    template_name = 'accounts/change_password.html'
    form_class = PasswordChangeForm
    success_url = reverse_lazy('dashboard:index')

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = getattr(self.request.user, 'profile', None)
        if profile:
            profile.must_change_password = False
            profile.save(update_fields=['must_change_password', 'updated_at'])
        update_session_auth_hash(self.request, form.user)
        messages.success(self.request, 'Your password was updated.')
        return response


ROLE_TONES = {
    'Superadmin': 'maroon',
    'Admin': 'maroon',
    'QA': 'green',
    'Accreditation Head': 'maroon',
    'Program Head': 'blue',
    'Dean': 'rose',
    'Area Chair': 'gold',
    'Student': 'slate',
}


class UserManagementView(AccountApprovalMixin, TemplateView):
    template_name = 'accounts/user_management.html'

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        user = get_object_or_404(get_user_model(), pk=request.POST.get('user_id'))
        profile = getattr(user, 'profile', None)

        if action in {'approve', 'reject'}:
            if not can_approve_accounts(request.user) or not profile:
                raise PermissionDenied('You cannot approve this account.')
            with transaction.atomic():
                if action == 'approve':
                    now = timezone.now()
                    profile.approval_status = UserProfile.APPROVED
                    profile.approved_by = request.user
                    profile.approved_at = now
                    profile.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
                    user.is_active = True
                    user.save(update_fields=['is_active'])
                    RoleAssignment.objects.filter(user=user).update(
                        is_approved=True,
                        approved_by=request.user,
                        approved_at=now,
                    )
                    Notification.objects.create(
                        user=user,
                        kind='account',
                        title='Account approved',
                        message='Your JMCFI AMS account is approved. You can now sign in and select your active role.',
                    )
                    AuditLog.objects.create(
                        actor=request.user,
                        action='ACCOUNT_APPROVED',
                        object_type='User',
                        object_id=str(user.pk),
                        details={'username': user.username},
                    )
                    messages.success(request, f'{user.get_full_name() or user.username} was approved.')
                else:
                    profile.approval_status = UserProfile.REJECTED
                    profile.approved_by = request.user
                    profile.approved_at = timezone.now()
                    profile.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'updated_at'])
                    user.is_active = False
                    user.save(update_fields=['is_active'])
                    RoleAssignment.objects.filter(user=user).update(is_approved=False)
                    AuditLog.objects.create(
                        actor=request.user,
                        action='ACCOUNT_REJECTED',
                        object_type='User',
                        object_id=str(user.pk),
                        details={'username': user.username},
                    )
                    messages.success(request, f'{user.get_full_name() or user.username} was rejected.')
        elif action in {'activate', 'deactivate'}:
            if not is_admin_user(request.user) or not profile:
                raise PermissionDenied('Only administrators can change account status.')
            if action == 'activate' and profile.approval_status != UserProfile.APPROVED:
                messages.error(request, 'Approve the account before activating it.')
            else:
                user.is_active = action == 'activate'
                user.save(update_fields=['is_active'])
                messages.success(request, f'{user.get_full_name() or user.username} was {action}d.')
        elif action == 'assign':
            if not is_admin_user(request.user):
                raise PermissionDenied('Only administrators can manage role assignments.')
            assignment_form = RoleAssignmentForm(request.POST)
            if assignment_form.is_valid():
                target_user = assignment_form.cleaned_data['user']
                role = assignment_form.cleaned_data['role']
                department = assignment_form.cleaned_data['department']
                assignment, created = RoleAssignment.objects.get_or_create(
                    user=target_user,
                    role=role,
                    department=department,
                    defaults={
                        'is_approved': bool(
                            getattr(target_user, 'profile', None)
                            and target_user.profile.approval_status == UserProfile.APPROVED
                        ),
                        'approved_by': request.user,
                        'approved_at': timezone.now(),
                    },
                )
                if not created and target_user.profile.approval_status == UserProfile.APPROVED:
                    assignment.is_approved = True
                    assignment.approved_by = request.user
                    assignment.approved_at = timezone.now()
                    assignment.save(update_fields=['is_approved', 'approved_by', 'approved_at'])
                target_user.profile.department = department
                target_user.profile.save(update_fields=['department', 'updated_at'])
                AuditLog.objects.create(
                    actor=request.user,
                    action='ROLE_ASSIGNED',
                    object_type='RoleAssignment',
                    object_id=str(assignment.pk),
                    details={'user': target_user.username, 'role': role.code, 'department': department.code},
                )
                messages.success(request, 'Role assignment saved.')
            else:
                messages.error(request, 'Choose a valid user, internal role, and department.')
        elif action == 'remove_assignment':
            if not is_admin_user(request.user):
                raise PermissionDenied('Only administrators can manage role assignments.')
            assignment = get_object_or_404(RoleAssignment, pk=request.POST.get('assignment_id'))
            profile = getattr(assignment.user, 'profile', None)
            if profile and profile.active_assignment_id == assignment.id:
                profile.active_assignment = None
                profile.save(update_fields=['active_assignment', 'updated_at'])
            assignment.delete()
            messages.success(request, 'Role assignment removed.')
        else:
            messages.error(request, 'Unknown user management action.')
        return redirect('accounts:user_management')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_queryset = visible_user_accounts().select_related('profile', 'profile__department').prefetch_related(
            'role_assignments__role', 'role_assignments__department'
        ).order_by('last_name', 'first_name', 'username')
        users = []
        for user in user_queryset:
            profile = getattr(user, 'profile', None)
            assignments = list(user.role_assignments.all())
            role_names = list(dict.fromkeys(item.role.name for item in assignments))
            department_names = list(dict.fromkeys(item.department.name for item in assignments))
            name = user.get_full_name().strip() or user.username
            initials = ''.join(part[0] for part in name.split()[:2]).upper() or 'U'
            approval = profile.get_approval_status_display() if profile else 'No profile'
            users.append({
                'id': user.id,
                'initials': initials,
                'name': name,
                'email': user.email or 'No email address',
                'role': ', '.join(role_names) or 'Unassigned',
                'role_tone': ROLE_TONES.get(role_names[0] if role_names else '', 'slate'),
                'department': ', '.join(department_names) or (profile.department.name if profile and profile.department else 'Unassigned'),
                'auth': 'Password',
                'status': 'Active' if user.is_active else 'Inactive',
                'status_tone': 'green' if user.is_active else 'slate',
                'approval': approval,
                'approval_tone': {'Approved': 'green', 'Pending Approval': 'gold', 'Rejected': 'rose'}.get(approval, 'slate'),
                'is_pending': bool(profile and profile.approval_status == UserProfile.PENDING),
                'is_demo': bool(profile and profile.is_demo_account),
                'assignments': assignments,
            })
        visible_users = visible_user_accounts()
        assignment_form = RoleAssignmentForm()
        context.update({
            'page_title': 'User Management',
            'users': users,
            'user_stats': [
                {'label': 'Total Users', 'value': visible_users.count(), 'tone': 'rose'},
                {'label': 'Active', 'value': visible_users.filter(is_active=True).count(), 'tone': 'green'},
                {'label': 'Pending Approval', 'value': visible_users.filter(profile__approval_status=UserProfile.PENDING).count(), 'tone': 'gold'},
                {'label': 'Inactive', 'value': visible_users.filter(is_active=False).count(), 'tone': 'slate'},
            ],
            'assignment_form': assignment_form,
            'can_manage_assignments': is_admin_user(self.request.user),
        })
        return context


class SettingsProfileView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accounts/settings_profile.html'

    def post(self, request, *args, **kwargs):
        form = ProfileSettingsForm(request.user, request.POST, request.FILES)
        if form.is_valid():
            form.save()
            AuditLog.objects.create(
                actor=request.user,
                action='PROFILE_UPDATED',
                object_type='User',
                object_id=str(request.user.pk),
            )
            messages.success(request, 'Profile changes saved.')
            return redirect('accounts:settings_profile')
        return render(request, self.template_name, self.get_page_context(form))

    def get_page_context(self, form=None):
        user = self.request.user
        profile_model = getattr(user, 'profile', None)
        assignment = approved_assignments(user).filter(pk=getattr(profile_model, 'active_assignment_id', None)).select_related('role', 'department').first() or approved_assignments(user).first()
        name = user.get_full_name().strip() or user.username
        initials = ''.join(part[0] for part in name.split()[:2]).upper() or 'U'
        profile = {
            'initials': initials,
            'name': name,
            'office': profile_model.department.name if profile_model and profile_model.department else 'No department assigned',
            'email': user.email,
            'role': assignment.role.name if assignment else 'Pending assignment',
            'assignment': f'Assigned by an administrator · {assignment.department.name}' if assignment else 'Awaiting approved assignment',
            'photo_url': profile_model.photo.url if profile_model and profile_model.photo else '',
        }
        return {
            'page_title': 'Settings & Profile',
            'settings_tabs': [
                {'key': 'profile', 'label': 'Profile', 'icon': 'users', 'active': True},
                {'key': 'password', 'label': 'Password', 'icon': 'settings', 'active': False},
                {'key': 'notifications', 'label': 'Notifications', 'icon': 'bell', 'active': False},
                {'key': 'assistant', 'label': 'Assistant', 'icon': 'sparkle', 'active': False},
                {'key': 'privacy', 'label': 'Privacy & Legal', 'icon': 'shield', 'active': False},
            ],
            'profile': profile,
            'form': form or ProfileSettingsForm(user),
            'legal_policies': list(Policy.active_required()),
            'legal_consents': list(
                user.policy_consents.select_related('policy').order_by('-accepted_at')
            ),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_page_context())
        return context
