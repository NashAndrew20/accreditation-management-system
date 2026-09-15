"""
Site-wide context: the sidebar navigation map and the signed-in user
summary shown in the topbar. Kept in one place so the sidebar template
never hardcodes a link — add a section/item here and it shows up
everywhere automatically.
"""

from django.urls import reverse
from django.utils.timesince import timesince

from .access import active_assignment, can_approve_accounts, is_admin_user
from .models import Notification


_AIRA_DEFAULT_GUIDANCE = {
    'title': 'Your accreditation companion',
    'message': 'I can help you keep evidence work organized, find the next step, and stay on top of review activity.',
}

_AIRA_GUIDANCE = {
    'dashboard:index': {
        'title': 'Your accreditation overview',
        'message': 'I can help you interpret readiness, activity, and deadlines across your current access scope.',
    },
    'accreditation:levels_areas': {
        'title': 'Navigate the accreditation structure',
        'message': 'I can guide you through levels, areas, sub-areas, and the evidence requirements connected to them.',
    },
    'accreditation:area_details': {
        'title': 'Explore this accreditation area',
        'message': 'I can help you understand this area and identify the evidence work that should happen next.',
    },
    'accreditation:submission_workspace': {
        'title': 'Prioritize your evidence tasks',
        'message': 'I can help you focus on missing evidence, deadlines, and items returned for revision.',
    },
    'accreditation:submission_workspace_subarea': {
        'title': 'Prepare this evidence set',
        'message': 'I can help you check the requirement, supporting files, self-evaluation, and actual situation before submitting.',
    },
    'accreditation:evidence_detail': {
        'title': 'Understand this evidence requirement',
        'message': 'I can help you review the current evidence, versions, remarks, and next action.',
    },
    'accreditation:evidence_review': {
        'title': 'Keep the review focused',
        'message': 'I can help you check the evidence against its requirement and prepare clear reviewer remarks.',
    },
    'accreditation:review_workflow': {
        'title': 'Track internal review',
        'message': 'I can help you prioritize assigned reviews, revisions, and evidence moving through the approval stages.',
    },
    'resources:document_repository': {
        'title': 'Find the right evidence file',
        'message': 'I can help you locate documents and keep the latest evidence version easy to verify.',
    },
    'resources:communication': {
        'title': 'Keep accreditation conversations clear',
        'message': 'I can help you keep messages focused on evidence, reviewer remarks, owners, and deadlines.',
    },
    'intelligence:reports_monitoring': {
        'title': 'Read your compliance picture',
        'message': 'I can help you interpret readiness, compliance, department performance, and submission trends.',
    },
    'core:notifications': {
        'title': 'Stay informed on the next action',
        'message': 'I can help you sort new messages, evidence updates, assignments, and review decisions.',
    },
    'core:audit_history': {
        'title': 'Follow the evidence trail',
        'message': 'I can help you understand the recorded actions and decisions behind an evidence submission.',
    },
    'accounts:user_management': {
        'title': 'Keep access assignments accurate',
        'message': 'I can help you check account approvals, internal roles, and department assignments.',
    },
    'accounts:settings_profile': {
        'title': 'Keep your profile ready',
        'message': 'I can help you review your account details and assistant preferences for accreditation work.',
    },
}


def _aira_guidance(request):
    resolver_match = getattr(request, 'resolver_match', None)
    view_name = getattr(resolver_match, 'view_name', '')
    return _AIRA_GUIDANCE.get(view_name, _AIRA_DEFAULT_GUIDANCE)


# Detail/intermediate views that should keep a parent sidebar section
# highlighted when the exact view name has no nav item of its own.
_ACTIVE_NAV_PARENTS = {
    'accreditation:area_details': 'accreditation:levels_areas',
    'accreditation:submission_workspace_subarea': 'accreditation:submission_workspace',
    'accreditation:evidence_review': 'accreditation:review_workflow',
}


def _resolve_active_nav(request):
    resolver_match = getattr(request, 'resolver_match', None)
    if not resolver_match:
        return ''
    current = (
        f'{resolver_match.namespace}:{resolver_match.url_name}'
        if resolver_match.namespace
        else resolver_match.url_name
    )
    if current == 'accreditation:evidence_detail':
        # Evidence details open from "My Tasks" for Program Heads and from
        # the review queue for reviewers, so highlight the matching section.
        assignment = active_assignment(request.user)
        role_code = assignment.role.code if assignment else ''
        if role_code == 'PROGRAM_HEAD':
            return 'accreditation:submission_workspace'
        return 'accreditation:review_workflow'
    return _ACTIVE_NAV_PARENTS.get(current, current)


def site_nav(request):
    nav_sections = [
        {
            'label': 'Overview',
            'items': [
                {
                    'label': 'Dashboard',
                    'icon': 'grid',
                    'url_name': 'dashboard:index',
                },
            ],
        },
        {
            'label': 'Accreditation',
            'items': [
                {
                    'label': 'PACUCOA',
                    'icon': 'layers',
                    'url_name': 'accreditation:levels_areas',
                },
                {
                    'label': 'My Tasks',
                    'icon': 'folder',
                    'url_name': 'accreditation:submission_workspace',
                },
                {
                    'label': 'Review Workflow',
                    'icon': 'clipboard',
                    'url_name': 'accreditation:review_workflow',
                },
            ],
        },
        {
            'label': 'Resources',
            'items': [
                {
                    'label': 'Document Repository',
                    'icon': 'cloud',
                    'url_name': 'resources:document_repository',
                },
                {
                    'label': 'Communication',
                    'icon': 'message',
                    'url_name': 'resources:communication',
                },
            ],
        },
        {
            'label': 'Intelligence',
            'items': [
                {
                    'label': 'Reports & Monitoring',
                    'icon': 'chart',
                    'url_name': 'intelligence:reports_monitoring',
                },
                {
                    'label': 'Smart Companion',
                    'icon': 'sparkle',
                    'url_name': 'intelligence:smart_companion',
                },
            ],
        },
        {
            'label': 'Administration',
            'items': [
                {
                    'label': 'User Management',
                    'icon': 'users',
                    'url_name': 'accounts:user_management',
                },
                {
                    'label': 'Settings & Profile',
                    'icon': 'settings',
                    'url_name': 'accounts:settings_profile',
                },
            ],
        },
    ]

    admin_items = [
        {
            'label': 'Settings & Profile',
            'icon': 'settings',
            'url_name': 'accounts:settings_profile',
        },
    ]
    if can_approve_accounts(request.user):
        admin_items.insert(0, {
            'label': 'User Management',
            'icon': 'users',
            'url_name': 'accounts:user_management',
        })
        admin_items.insert(1, {
            'label': 'Audit History',
            'icon': 'clock',
            'url_name': 'core:audit_history',
        })
    nav_sections[-1]['items'] = admin_items

    if request.user.is_authenticated and not is_admin_user(request.user):
        assignment = active_assignment(request.user)
        role_code = assignment.role.code if assignment else ''
        if role_code == 'PROGRAM_HEAD':
            nav_sections[1]['items'] = [
                item for item in nav_sections[1]['items']
                if item['url_name'] != 'accreditation:review_workflow'
            ]
        elif role_code in {'DEAN', 'AREA_CHAIR', 'QA', 'ACCREDITATION_HEAD'}:
            nav_sections[1]['items'] = [
                item for item in nav_sections[1]['items']
                if item['url_name'] != 'accreditation:submission_workspace'
            ]

    current_user_summary = {
        'name': 'Guest',
        'role': 'Sign in required',
        'role_context': 'JMCFI AMS',
        'initials': 'GU',
        'photo_url': '',
    }
    aira_guidance = _aira_guidance(request)
    notification_count = 0
    notification_preview = []
    if request.user.is_authenticated:
        assignment = active_assignment(request.user)
        profile = getattr(request.user, 'profile', None)
        name = request.user.get_full_name().strip() or request.user.username
        initials = ''.join(part[0] for part in name.split()[:2]).upper() or 'U'
        current_user_summary = {
            'name': name,
            'role': assignment.role.name if assignment else 'Pending Approval',
            'role_context': assignment.department.name if assignment else 'Awaiting assignment',
            'initials': initials,
            'photo_url': profile.photo.url if profile and profile.photo else '',
        }
        user_notifications = Notification.objects.filter(user=request.user).select_related('submission')
        notification_count = user_notifications.filter(is_read=False).count()
        for notification in user_notifications[:5]:
            notification_preview.append({
                'title': notification.title,
                'message': notification.message,
                'time_label': f'{timesince(notification.created_at)} ago',
                'unread': not notification.is_read,
                'url': notification.target_url or (
                    reverse('accreditation:evidence_detail', args=[notification.submission_id])
                    if notification.submission_id else reverse('core:notifications')
                ),
            })

    return {
        'nav_sections': nav_sections,
        'current_user_summary': current_user_summary,
        'aira_guidance': aira_guidance,
        'notification_count': notification_count,
        'notification_preview': notification_preview,
        'active_nav': _resolve_active_nav(request),
    }
