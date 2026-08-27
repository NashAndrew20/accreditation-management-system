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
from django.views.generic import TemplateView

from core.access import approved_assignments, can_approve_accounts, is_admin_user
from core.mixins import AccountApprovalMixin, ApprovedUserRequiredMixin
from core.models import AuditLog, Notification, RoleAssignment, UserProfile
from core.rate_limit import LOGIN_ATTEMPT_WINDOW, allow_login_attempt

from .forms import (
    PortalAuthenticationForm,
    ProfileSettingsForm,
    RegistrationForm,
    RoleAssignmentForm,
    RoleSelectionForm,
)


DEMO_LOGIN_OPTIONS = (
    {
        'label': 'Admin',
        'role': 'Full system access',
        'username': 'admin',
        'password': '123',
        'initials': 'AD',
    },
    {
        'label': 'Evidence Uploader',
        'role': 'Prepare and submit evidence',
        'username': 'uploader',
        'password': '123',
        'initials': 'EU',
    },
    {
        'label': 'Approver',
        'role': 'Review and approve evidence',
        'username': 'approver',
        'password': '123',
        'initials': 'AP',
    },
)


class PortalLoginView(LoginView):
    authentication_form = PortalAuthenticationForm
    template_name = 'accounts/login.html'
    # Allow an authenticated development user to return to the account picker
    # and switch between the Admin, Uploader, and Approver demo personas.
    redirect_authenticated_user = False
    extra_context = {'page_title': 'Sign in'}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['demo_login_options'] = DEMO_LOGIN_OPTIONS if settings.DEMO_MODE else ()
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
            return redirect(f'{reverse("accounts:select_role")}?next={self.get_success_url()}')
        return response


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
            'next_url': request.GET.get('next', ''),
        })

    def post(self, request, *args, **kwargs):
        form = RoleSelectionForm(request.user, request.POST)
        if form.is_valid():
            profile = request.user.profile
            profile.active_assignment = form.cleaned_data['assignment']
            profile.save(update_fields=['active_assignment', 'updated_at'])
            return redirect(request.POST.get('next') or 'dashboard:index')
        return render(request, self.template_name, {
            'form': form,
            'assignments': form.fields['assignment'].queryset,
            'next_url': request.POST.get('next', ''),
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
        user_queryset = get_user_model().objects.select_related('profile', 'profile__department').prefetch_related(
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
        user_model = get_user_model()
        assignment_form = RoleAssignmentForm()
        context.update({
            'page_title': 'User Management',
            'users': users,
            'user_stats': [
                {'label': 'Total Users', 'value': user_model.objects.count(), 'tone': 'rose'},
                {'label': 'Active', 'value': user_model.objects.filter(is_active=True).count(), 'tone': 'green'},
                {'label': 'Pending Approval', 'value': UserProfile.objects.filter(approval_status=UserProfile.PENDING).count(), 'tone': 'gold'},
                {'label': 'Inactive', 'value': user_model.objects.filter(is_active=False).count(), 'tone': 'slate'},
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
            ],
            'profile': profile,
            'form': form or ProfileSettingsForm(user),
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(self.get_page_context())
        return context
