from django.db.models import Case, IntegerField, Q, Value, When

from .models import Department, ROLE_CODES, RoleAssignment


# Keep access checks aligned with the role catalog used by seed data and forms.
INTERNAL_ROLE_CODES = frozenset(ROLE_CODES)


def approved_assignments(user):
    if not user or not user.is_authenticated:
        return RoleAssignment.objects.none()
    return RoleAssignment.objects.filter(
        user=user,
        is_approved=True,
        role__is_active=True,
        role__is_internal=True,
        department__is_active=True,
    ).select_related('role', 'department')


def active_assignment(user):
    if not user or not user.is_authenticated:
        return None
    profile = getattr(user, 'profile', None)
    if profile and profile.active_assignment_id:
        assignment = (
            approved_assignments(user)
            .filter(pk=profile.active_assignment_id)
            .first()
        )
        if assignment:
            return assignment
    return approved_assignments(user).first()


def role_codes(user):
    return set(approved_assignments(user).values_list('role__code', flat=True))


def has_role(user, *codes):
    return bool(role_codes(user).intersection(codes))


def is_admin_user(user):
    return bool(user and user.is_authenticated and (user.is_superuser or has_role(user, 'SUPERADMIN', 'ADMIN')))


def can_approve_accounts(user):
    return bool(user and user.is_authenticated and (is_admin_user(user) or has_role(user, 'QA')))


def can_assign_areas(user):
    """QA and administrators may assign an area's evidence work."""
    return bool(user and user.is_authenticated and (is_admin_user(user) or has_role(user, 'QA')))


def is_approved_user(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_approved and approved_assignments(user).exists())


def department_scope_ids(department):
    if not department:
        return []
    ids = [department.id]
    pending = list(department.children.filter(is_active=True).values_list('id', flat=True))
    while pending:
        child_id = pending.pop()
        if child_id in ids:
            continue
        ids.append(child_id)
        pending.extend(
            Department.objects.filter(parent_id=child_id, is_active=True).values_list('id', flat=True)
        )
    return ids


def reviewer_department_ids(department):
    """Return the submission department and its active parent departments."""
    if not department:
        return []
    ids = []
    current_id = department.id
    while current_id and current_id not in ids:
        ids.append(current_id)
        current = department if current_id == department.id else Department.objects.filter(pk=current_id).first()
        current_id = current.parent_id if current and current.parent_id else None
    return ids


def reviewer_assignments(role_code, submission):
    """Return approved internal reviewers eligible for this submission."""
    from core.models import RoleAssignment

    query = RoleAssignment.objects.filter(
        role__code=role_code,
        role__is_active=True,
        role__is_internal=True,
        is_approved=True,
        user__is_active=True,
        user__profile__approval_status='APPROVED',
    ).select_related('user', 'role', 'department')

    if role_code in {'DEAN', 'AREA_CHAIR'}:
        query = query.filter(department_id__in=reviewer_department_ids(submission.department))
    if role_code == 'AREA_CHAIR':
        query = query.filter(assigned_areas=submission.requirement.area_id)
    return query.order_by(
        Case(
            When(user__username='approver', then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        'user_id',
    )


def assignment_for_reviewer(user, submission, role_code=None):
    selected = active_assignment(user)
    expected_role = role_code or (submission.current_review_role.code if submission.current_review_role_id else None)
    if not selected or not expected_role or selected.role.code != expected_role:
        return None
    assignments = approved_assignments(user)
    if role_code:
        assignments = assignments.filter(role__code=role_code)
    else:
        assignments = assignments.filter(role__code=submission.current_review_role.code)

    if not assignments.exists():
        return None

    if role_code in {'DEAN', 'AREA_CHAIR'} or (not role_code and submission.current_review_role.code in {'DEAN', 'AREA_CHAIR'}):
        assignments = assignments.filter(department_id__in=reviewer_department_ids(submission.department))
    if role_code == 'AREA_CHAIR' or (not role_code and submission.current_review_role.code == 'AREA_CHAIR'):
        assignments = assignments.filter(assigned_areas=submission.requirement.area_id)
    return assignments.first()


def accessible_submissions(user):
    """Return evidence submissions the active user may view."""
    from accreditation.models import EvidenceSubmission

    if not user or not user.is_authenticated:
        return EvidenceSubmission.objects.none()
    if is_admin_user(user) or has_role(user, 'QA', 'ACCREDITATION_HEAD'):
        return EvidenceSubmission.objects.all()

    selected_assignment = active_assignment(user)
    assignments = [selected_assignment] if selected_assignment else list(approved_assignments(user))
    assignments = [item for item in assignments if item]
    query = Q(pk__in=[])
    for assignment in assignments:
        role_code = assignment.role.code
        if role_code == 'PROGRAM_HEAD':
            query |= Q(program_head=user, department_id=assignment.department_id)
        elif role_code in {'DEAN', 'STUDENT'}:
            query |= Q(department_id__in=department_scope_ids(assignment.department))
        elif role_code == 'AREA_CHAIR':
            area_ids = assignment.assigned_areas.values_list('id', flat=True)
            query |= Q(
                department_id__in=department_scope_ids(assignment.department),
                requirement__area_id__in=area_ids,
            )
    return EvidenceSubmission.objects.filter(query).distinct()


def accessible_repository_submissions(user):
    """Return repository submissions limited to the user's active department."""
    submissions = accessible_submissions(user)
    if not user or not user.is_authenticated:
        return submissions
    if is_admin_user(user) or has_role(user, 'QA'):
        return submissions

    assignment = active_assignment(user)
    if not assignment:
        return submissions.none()
    return submissions.filter(
        department_id__in=department_scope_ids(assignment.department),
    )
