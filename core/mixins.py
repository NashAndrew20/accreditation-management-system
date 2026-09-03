from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .access import can_approve_accounts, is_admin_user, is_approved_user


class ApprovedUserRequiredMixin(LoginRequiredMixin):
    login_url = '/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('hide_topbar_title', True)
        return context

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_approved_user(request.user):
            return redirect('login')
        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(ApprovedUserRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not is_admin_user(request.user):
            raise PermissionDenied('Only administrators can access this page.')
        return super().dispatch(request, *args, **kwargs)


class AccountApprovalMixin(ApprovedUserRequiredMixin):
    """Allow QA to approve accounts while keeping configuration admin-only."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not can_approve_accounts(request.user):
            raise PermissionDenied('Only QA or administrators can approve accounts.')
        return super().dispatch(request, *args, **kwargs)
