from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import TemplateView, View

from core.access import (
    accessible_submissions,
    active_assignment,
    assignment_for_reviewer,
    can_assign_areas,
    department_scope_ids,
    has_role,
    is_admin_user,
    reviewer_department_ids,
)
from core.mixins import ApprovedUserRequiredMixin
from core.models import AuditLog, Notification, RoleAssignment

from .constants import ACTIVE_REVIEW_STATUSES, COMPLETED_STATUSES
from .forms import AreaAssignmentForm, EvidenceSubmissionForm, ReviewActionForm
from .models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationSubArea,
    AreaAssignment,
    EvidenceRequirement,
    EvidenceReview,
    EvidenceSubmission,
)
from .workflow import (
    WorkflowError,
    approve_submission,
    mark_non_complied,
    request_revision,
    save_draft,
    submit_submission,
)


STATUS_LABELS = dict(EvidenceSubmission.STATUS_CHOICES)


def status_label(status):
    return STATUS_LABELS.get(status, 'Not Started')


def status_tone(status):
    if status in COMPLETED_STATUSES:
        return 'green'
    if status == EvidenceSubmission.NEEDS_REVISION:
        return 'rose'
    if status == EvidenceSubmission.NON_COMPLIED:
        return 'red'
    if status in ACTIVE_REVIEW_STATUSES or status == EvidenceSubmission.SUBMITTED:
        return 'gold'
    return 'slate'


def _current_cycle():
    return AccreditationCycle.objects.filter(is_active=True).prefetch_related('levels__areas').first()


def _scoped_submissions(user):
    return accessible_submissions(user).select_related(
        'requirement',
        'requirement__area',
        'requirement__subarea',
        'department',
        'program_head',
        'current_reviewer',
        'current_review_role',
    )


def _progress(submissions, requirement_count):
    if not requirement_count:
        return 0
    completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
    return round(completed * 100 / requirement_count)


def _subarea_context(subarea, scoped_submissions):
    requirements = list(subarea.evidence_requirements.all())
    requirement_ids = [item.id for item in requirements]
    submissions = scoped_submissions.filter(requirement_id__in=requirement_ids)
    by_requirement = {item.requirement_id: item for item in submissions}
    status_values = [item.status for item in submissions]
    if not status_values:
        aggregate_status = EvidenceSubmission.DRAFT
    elif all(status in COMPLETED_STATUSES for status in status_values) and len(status_values) == len(requirements):
        aggregate_status = EvidenceSubmission.CLOSED
    elif EvidenceSubmission.NEEDS_REVISION in status_values:
        aggregate_status = EvidenceSubmission.NEEDS_REVISION
    elif any(status in ACTIVE_REVIEW_STATUSES for status in status_values):
        aggregate_status = EvidenceSubmission.SUBMITTED
    else:
        aggregate_status = EvidenceSubmission.DRAFT
    return {
        'code': subarea.code,
        'title': subarea.title,
        'slug': subarea.code.replace('.', '-'),
        'progress': _progress(submissions, len(requirements)),
        'status': status_label(aggregate_status),
        'tone': status_tone(aggregate_status),
        'active': False,
        'requirements': requirements,
        'submissions': by_requirement,
    }


def _area_context(area, scoped_submissions):
    requirements = EvidenceRequirement.objects.filter(area=area)
    submissions = scoped_submissions.filter(requirement__area=area)
    completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
    revision = submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count()
    pending = submissions.exclude(status__in=COMPLETED_STATUSES | {EvidenceSubmission.DRAFT}).count()
    return {
        'code': area.code,
        'name': area.name,
        'workspace_key': area.slug,
        'progress': _progress(submissions, requirements.count()),
        'tone': 'green' if _progress(submissions, requirements.count()) >= 80 else 'gold',
        'compiled': completed,
        'pending': pending,
        'revision': revision,
        'missing': max(requirements.count() - submissions.count(), 0),
        'model': area,
    }


class LevelsAreasView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/levels_areas.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cycle = _current_cycle()
        if not cycle:
            context.update({'page_title': 'Levels & Areas', 'levels': [], 'areas': [], 'overview': {}})
            return context
        scoped = _scoped_submissions(self.request.user)
        levels = []
        active_level = None
        for level in cycle.levels.all():
            level_submissions = scoped.filter(requirement__area__level=level)
            compiled = level_submissions.filter(status__in=COMPLETED_STATUSES).count()
            revision = level_submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count()
            pending = level_submissions.exclude(status__in=COMPLETED_STATUSES | {EvidenceSubmission.DRAFT}).count()
            level_data = {
                'name': level.name,
                'status': level.status_label,
                'compiled': compiled,
                'pending': pending,
                'revision': revision,
                'active': level.code == 'I',
                'model': level,
            }
            levels.append(level_data)
            if level_data['active']:
                active_level = level
        active_level = active_level or cycle.levels.first()
        area_models = list(active_level.areas.all()) if active_level else []
        areas = [_area_context(area, scoped) for area in area_models]
        active_submissions = scoped.filter(requirement__area__level=active_level) if active_level else scoped.none()
        context.update({
            'page_title': 'Levels & Areas',
            'levels': levels,
            'areas': areas,
            'active_level': next((item for item in levels if item['model'] == active_level), None),
            'overview': {
                'compiled': active_submissions.filter(status__in=COMPLETED_STATUSES).count(),
                'pending': active_submissions.exclude(status__in=COMPLETED_STATUSES | {EvidenceSubmission.DRAFT}).count(),
                'revision': active_submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count(),
            },
        })
        return context


class AreaDetailsView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/area_details.html'

    def _get_area(self, area_key):
        return get_object_or_404(
            AccreditationArea.objects.select_related('level', 'level__cycle').prefetch_related(
                'subareas__evidence_requirements',
            ),
            slug=area_key,
            level__cycle__is_active=True,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area = self._get_area(kwargs['area_key'])
        scoped = _scoped_submissions(self.request.user)
        sub_areas = []
        for subarea in area.subareas.all():
            item = _subarea_context(subarea, scoped)
            item.pop('requirements', None)
            item.pop('submissions', None)
            sub_areas.append(item)
        context.update({
            'page_title': f'{area.code} · {area.name}',
            'area': area,
            'area_key': area.slug,
            'sub_areas': sub_areas,
            'area_count': area.level.areas.count(),
            'total_subarea_count': sum(item.subareas.count() for item in area.level.areas.all()),
            'can_assign_area': can_assign_areas(self.request.user),
            'assignment_form': getattr(self, 'assignment_form', None),
            'area_assignments': [],
        })
        if can_assign_areas(self.request.user):
            context['assignment_form'] = context['assignment_form'] or AreaAssignmentForm()
            context['area_assignments'] = AreaAssignment.objects.filter(area=area).select_related(
                'department',
                'assigned_by',
            )
        return context

    def post(self, request, *args, **kwargs):
        if not can_assign_areas(request.user):
            raise PermissionDenied('Only QA or administrators can assign area evidence.')

        area = self._get_area(kwargs['area_key'])
        self.assignment_form = AreaAssignmentForm(request.POST)
        if not self.assignment_form.is_valid():
            return self.render_to_response(self.get_context_data(area_key=area.slug))

        requirements_exist = area.evidence_requirements.exists()
        if not requirements_exist:
            self.assignment_form.add_error(
                None,
                'This area has no evidence requirements to assign yet.',
            )
            return self.render_to_response(self.get_context_data(area_key=area.slug))

        departments = list(self.assignment_form.cleaned_data['departments'])
        deadline = self.assignment_form.cleaned_data['deadline']
        instructions = self.assignment_form.cleaned_data['instructions'].strip()
        recipients = {}
        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for department in departments:
                assignment, created = AreaAssignment.objects.get_or_create(
                    area=area,
                    department=department,
                    defaults={
                        'assigned_by': request.user,
                        'deadline': deadline,
                        'instructions': instructions,
                    },
                )
                changed = created
                if created:
                    created_count += 1
                else:
                    changed = (
                        assignment.deadline != deadline
                        or assignment.instructions != instructions
                        or assignment.assigned_by_id != request.user.id
                    )
                    if changed:
                        assignment.deadline = deadline
                        assignment.instructions = instructions
                        assignment.assigned_by = request.user
                        assignment.save(update_fields=(
                            'deadline',
                            'instructions',
                            'assigned_by',
                            'updated_at',
                        ))
                        updated_count += 1

                if not changed:
                    continue

                AuditLog.objects.create(
                    actor=request.user,
                    action='AREA_ASSIGNMENT_UPDATED' if not created else 'AREA_ASSIGNED',
                    object_type='AreaAssignment',
                    object_id=str(assignment.pk),
                    details={
                        'area': area.code,
                        'department': department.name,
                        'deadline': deadline.isoformat(),
                        'instructions': instructions,
                    },
                )
                program_head_assignments = RoleAssignment.objects.filter(
                    role__code='PROGRAM_HEAD',
                    role__is_active=True,
                    role__is_internal=True,
                    is_approved=True,
                    user__is_active=True,
                    user__profile__approval_status='APPROVED',
                    department__is_active=True,
                    department_id__in=department_scope_ids(department),
                ).select_related('user')
                for program_head_assignment in program_head_assignments:
                    recipients[program_head_assignment.user_id] = program_head_assignment.user

            for recipient in recipients.values():
                Notification.objects.create(
                    user=recipient,
                    kind='assignment',
                    title='New area assignment',
                    message=(
                        f'{area.code} — {area.name} is assigned to your department. '
                        f'Deadline: {deadline:%b %d, %Y}.'
                    ),
                )

        if created_count or updated_count:
            messages.success(
                request,
                f'{area.code} assigned to {len(departments)} department(s) or program(s). '
                f'{len(recipients)} Program Head(s) notified.',
            )
        else:
            messages.info(request, 'The selected area assignments are already up to date.')
        return redirect('accreditation:area_details', area_key=area.slug)


class SubmissionWorkspaceView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/submission_workspace.html'

    def _department_for_program_head(self):
        assignment = active_assignment(self.request.user)
        return assignment.department if assignment and assignment.role.code == 'PROGRAM_HEAD' else None

    def _ensure_program_submissions(self, requirements):
        department = self._department_for_program_head()
        if not department:
            return {}
        result = {}
        for requirement in requirements:
            submission, _ = EvidenceSubmission.objects.get_or_create(
                requirement=requirement,
                department=department,
                defaults={'program_head': self.request.user, 'created_by': self.request.user},
            )
            result[requirement.id] = submission
        return result

    def _get_task_workspace(self):
        cycle = _current_cycle()
        assignment = active_assignment(self.request.user)
        department = assignment.department if assignment else None
        empty_workspace = {
            'is_task_landing': True,
            'department': department.name if department else 'No active department',
            'assigned_tasks': [],
            'missing_tasks': [],
            'assigned_count': 0,
            'missing_count': 0,
        }
        if not cycle:
            return empty_workspace

        submissions = _scoped_submissions(self.request.user).filter(
            requirement__area__level__cycle=cycle,
        )
        if not is_admin_user(self.request.user):
            if not assignment:
                return empty_workspace
            submissions = submissions.filter(
                department_id__in=department_scope_ids(assignment.department),
            )

        requirements_query = EvidenceRequirement.objects.filter(area__level__cycle=cycle)
        area_assignment_deadlines = {}
        area_assignment_instructions = {}
        if assignment and assignment.role.code == 'PROGRAM_HEAD':
            target_department_ids = reviewer_department_ids(assignment.department)
            assigned_area_ids = set(
                AreaAssignment.objects.filter(
                    area__level__cycle=cycle,
                    department_id__in=target_department_ids,
                ).values_list('area_id', flat=True)
            )
            if AreaAssignment.objects.filter(area__level__cycle=cycle).exists():
                requirements_query = requirements_query.filter(area_id__in=assigned_area_ids)

            # A direct program assignment takes precedence over an assignment
            # made to one of its parent departments.
            for department_id in reversed(target_department_ids):
                for area_assignment in AreaAssignment.objects.filter(
                    area__level__cycle=cycle,
                    department_id=department_id,
                ).values('area_id', 'deadline', 'instructions'):
                    area_assignment_deadlines[area_assignment['area_id']] = area_assignment['deadline']
                    area_assignment_instructions[area_assignment['area_id']] = area_assignment['instructions']

        requirements = list(
            requirements_query
            .select_related('area', 'subarea')
            .order_by('area__sort_order', 'subarea__sort_order', 'sort_order', 'code')
        )

        requirement_ids = {requirement.id for requirement in requirements}
        submissions = submissions.filter(requirement_id__in=requirement_ids)
        groups = {}
        for requirement in requirements:
            subarea = requirement.subarea
            group_key = ('subarea', subarea.id) if subarea else ('area', requirement.area.id)
            group = groups.setdefault(group_key, {
                'code': subarea.code if subarea else requirement.area.code,
                'title': subarea.title if subarea else requirement.area.name,
                'area_code': requirement.area.code,
                'area_name': requirement.area.name,
                'area_key': requirement.area.slug,
                'subarea_code': subarea.code if subarea else '',
                'subarea_title': subarea.title if subarea else '',
                'subarea_key': subarea.code.replace('.', '-') if subarea else '',
                'requirement_ids': set(),
                'submitted_requirement_ids': set(),
                'action_statuses': set(),
                'deadline_values': [],
                'instructions': area_assignment_instructions.get(requirement.area_id, ''),
            })
            group['requirement_ids'].add(requirement.id)
            deadline = area_assignment_deadlines.get(requirement.area_id, requirement.deadline)
            if deadline:
                group['deadline_values'].append(deadline)

        for submission in submissions:
            subarea = submission.requirement.subarea
            group_key = ('subarea', subarea.id) if subarea else ('area', submission.requirement.area.id)
            group = groups.get(group_key)
            if not group:
                continue
            group['submitted_requirement_ids'].add(submission.requirement_id)
            if submission.status in {EvidenceSubmission.DRAFT, EvidenceSubmission.NEEDS_REVISION}:
                group['action_statuses'].add(submission.status)

        def finalize_group(group, missing=False):
            if missing:
                status = 'Missing'
                tone = 'rose'
            elif EvidenceSubmission.NEEDS_REVISION in group['action_statuses']:
                status = status_label(EvidenceSubmission.NEEDS_REVISION)
                tone = status_tone(EvidenceSubmission.NEEDS_REVISION)
            else:
                status = status_label(EvidenceSubmission.DRAFT)
                tone = status_tone(EvidenceSubmission.DRAFT)
            return {
                key: value
                for key, value in group.items()
                if key not in {
                    'requirement_ids',
                    'submitted_requirement_ids',
                    'action_statuses',
                    'deadline_values',
                }
            } | {
                'requirement_count': len(group['requirement_ids']),
                'submitted_count': len(group['submitted_requirement_ids']),
                'missing_count': len(group['requirement_ids'] - group['submitted_requirement_ids']),
                'deadline': min(group['deadline_values']) if group['deadline_values'] else None,
                'deadline_overdue': bool(
                    group['deadline_values'] and min(group['deadline_values']) < timezone.localdate()
                ),
                'status': status,
                'tone': tone,
            }

        assigned_tasks = [
            finalize_group(group)
            for group in groups.values()
            if group['action_statuses']
        ]
        missing_tasks = [
            finalize_group(group, missing=True)
            for group in groups.values()
            if group['requirement_ids'] - group['submitted_requirement_ids']
        ]
        assigned_tasks.sort(key=lambda item: (item['area_code'], item['subarea_code'], item['code']))
        missing_tasks.sort(key=lambda item: (item['area_code'], item['subarea_code'], item['code']))
        return {
            **empty_workspace,
            'assigned_tasks': assigned_tasks,
            'missing_tasks': missing_tasks,
            'assigned_count': len(assigned_tasks),
            'missing_count': len(missing_tasks),
        }

    def _get_workspace(self, area_key, subarea_key=None):
        area = get_object_or_404(
            AccreditationArea.objects.select_related('level', 'level__cycle').prefetch_related('subareas__evidence_requirements'),
            slug=area_key,
            level__cycle__is_active=True,
        )
        scoped = _scoped_submissions(self.request.user)
        current_assignment = active_assignment(self.request.user)
        subarea = None
        if subarea_key:
            subarea = get_object_or_404(area.subareas, code=subarea_key.replace('-', '.'))
            requirements = list(subarea.evidence_requirements.all())
            submissions = self._ensure_program_submissions(requirements)
            if not submissions:
                submissions = {item.requirement_id: item for item in scoped.filter(requirement_id__in=[item.id for item in requirements])}
            evidence_items = []
            for requirement in requirements:
                submission = submissions.get(requirement.id)
                evidence_items.append({
                    'code': requirement.code,
                    'title': requirement.title,
                    'description': requirement.required_description,
                    'status': status_label(submission.status) if submission else 'Not Started',
                    'tone': status_tone(submission.status) if submission else 'slate',
                    'submission_id': submission.id if submission else None,
                })
            active_subarea = {
                'code': subarea.code,
                'title': subarea.title,
                'slug': subarea.code.replace('.', '-'),
            }
        else:
            evidence_items = []
            active_subarea = None

        sub_areas = []
        for item in area.subareas.all():
            data = _subarea_context(item, scoped)
            data.pop('requirements', None)
            data.pop('submissions', None)
            data['active'] = bool(subarea and item.id == subarea.id)
            sub_areas.append(data)

        submission_values = list(submissions.values()) if subarea_key and submissions else []
        latest_documents = []
        remarks = []
        is_qa_browse = has_role(self.request.user, 'QA')
        show_workspace_feedback = not is_qa_browse
        if submission_values:
            for submission in submission_values:
                version = submission.latest_version
                if version:
                    for evidence_file in version.files.all():
                        name = evidence_file.original_name or evidence_file.file.name or evidence_file.link_url
                        latest_documents.append({
                            'name': name,
                            'meta': f'Version {version.version_number} · {evidence_file.created_at:%b %d, %Y}',
                            'version': f'v{version.version_number}',
                        })
                if show_workspace_feedback:
                    for review in submission.reviews.select_related('reviewer').all()[:3]:
                        remarks.append({
                            'author': review.reviewer.get_full_name() or review.reviewer.username,
                            'date': review.created_at.strftime('%b %d, %Y'),
                            'message': review.remarks or review.get_decision_display(),
                            'tone': 'rose' if review.decision == EvidenceReview.REQUEST_REVISION else 'green',
                        })
        first_submission = submission_values[0] if submission_values else None
        status = first_submission.status if first_submission else EvidenceSubmission.DRAFT
        return {
            'area_key': area.slug,
            'subarea_key': active_subarea['slug'] if active_subarea else '',
            'area_code': area.code,
            'area_name': area.name,
            'department': first_submission.department.name if first_submission else (current_assignment.department.name if current_assignment else 'No active department'),
            'program_head': first_submission.program_head.get_full_name() if first_submission else (self.request.user.get_full_name() or self.request.user.username),
            'active_subarea': f"{active_subarea['code']} — {active_subarea['title']}" if active_subarea else area.name,
            'subarea_code': active_subarea['code'] if active_subarea else '',
            'requirements_count': len(evidence_items),
            'status': status_label(status),
            'tone': status_tone(status),
            'score': '',
            'score_label': 'Not Evaluated',
            'actual_situation': first_submission.actual_situation if first_submission else 'Open a sub-area to prepare its evidence requirements.',
            'instructions': evidence_items,
            'sub_areas': sub_areas,
            'documents': latest_documents,
            'remarks': remarks,
            'show_feedback': show_workspace_feedback,
            'is_qa_browse': is_qa_browse,
            'can_manage_submission': bool(current_assignment and current_assignment.role.code == 'PROGRAM_HEAD'),
            'missing_requirements': [item['title'] for item in evidence_items if item['status'] in {'Draft', 'Needs Revision', 'Not Started'}],
            'can_submit': any(item['status'] == status_label(EvidenceSubmission.DRAFT) for item in evidence_items),
            'can_resubmit': any(item['status'] == status_label(EvidenceSubmission.NEEDS_REVISION) for item in evidence_items),
        }

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        area_key = kwargs.get('area_key') or 'area-i'
        subarea_key = kwargs.get('subarea_key')
        if action == 'cancel' or not subarea_key:
            return redirect('accreditation:area_details', area_key=area_key)
        department = self._department_for_program_head()
        if not department:
            raise PermissionDenied('Only an assigned Program Head can submit program evidence.')
        area = get_object_or_404(AccreditationArea, slug=area_key, level__cycle__is_active=True)
        subarea = get_object_or_404(area.subareas, code=subarea_key.replace('-', '.'))
        requirement_ids = subarea.evidence_requirements.values_list('id', flat=True)
        submissions = EvidenceSubmission.objects.filter(
            requirement_id__in=requirement_ids,
            department=department,
            program_head=request.user,
            status__in={EvidenceSubmission.DRAFT, EvidenceSubmission.NEEDS_REVISION},
        ).select_related('requirement')
        try:
            with transaction.atomic():
                for submission in submissions:
                    submit_submission(
                        submission,
                        request.user,
                        submission.self_evaluation,
                        submission.actual_situation,
                    )
            messages.success(request, 'Evidence items submitted for internal review.')
        except (PermissionDenied, WorkflowError) as error:
            messages.error(request, str(error))
        return redirect('accreditation:submission_workspace_subarea', area_key, subarea_key)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        area_key = kwargs.get('area_key')
        workspace = (
            self._get_task_workspace()
            if not area_key
            else self._get_workspace(area_key, kwargs.get('subarea_key'))
        )
        context.update({
            'page_title': 'My Tasks',
            'workspace': workspace,
            'sub_areas': workspace.get('sub_areas', []),
            'documents': workspace.get('documents', []),
            'remarks': workspace.get('remarks', []),
            'show_workspace_feedback': workspace.get('show_feedback', True),
            'can_manage_submission': workspace.get('can_manage_submission', False),
            'missing_requirements': workspace.get('missing_requirements', []),
            'evidence_items': workspace.get('instructions', []),
            'can_submit': workspace.get('can_submit', False),
            'can_resubmit': workspace.get('can_resubmit', False),
            'is_qa_browse': workspace.get('is_qa_browse', False),
        })
        return context


class EvidenceDetailView(ApprovedUserRequiredMixin, View):
    template_name = 'accreditation/evidence_detail.html'

    def get_submission(self, request, submission_id):
        return get_object_or_404(_scoped_submissions(request.user), pk=submission_id)

    def get_context(self, request, submission, form=None):
        latest = submission.latest_version
        is_current_qa_review = (
            has_role(request.user, 'QA')
            and submission.current_reviewer_id == request.user.id
            and assignment_for_reviewer(request.user, submission)
        )
        show_review_history = not has_role(request.user, 'QA') or is_current_qa_review
        return {
            'page_title': 'My Tasks',
            'hide_topbar_title': True,
            'submission': submission,
            'requirement': submission.requirement,
            'area': submission.requirement.area,
            'subarea': submission.requirement.subarea,
            'latest_version': latest,
            'versions': submission.versions.prefetch_related('files', 'reviews__reviewer').all(),
            'reviews': submission.reviews.select_related('reviewer', 'reviewer_role').all() if show_review_history else [],
            'comments': submission.comments.select_related('author').all() if show_review_history else [],
            'show_review_history': show_review_history,
            'form': form or EvidenceSubmissionForm(instance=submission),
            'can_edit': has_role(request.user, 'PROGRAM_HEAD') and submission.program_head_id == request.user.id and submission.status in {EvidenceSubmission.DRAFT, EvidenceSubmission.NEEDS_REVISION},
            'status_label': status_label(submission.status),
            'status_tone': status_tone(submission.status),
        }

    def get(self, request, submission_id):
        submission = self.get_submission(request, submission_id)
        return render(request, self.template_name, self.get_context(request, submission))

    @transaction.atomic
    def post(self, request, submission_id):
        submission = self.get_submission(request, submission_id)
        if not (has_role(request.user, 'PROGRAM_HEAD') and submission.program_head_id == request.user.id):
            raise PermissionDenied('Only the assigned Program Head can edit this evidence.')
        form = EvidenceSubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            try:
                if request.POST.get('action') == 'save_draft':
                    save_draft(submission, request.user, form.cleaned_data['self_evaluation'], form.cleaned_data['actual_situation'])
                    messages.success(request, 'Draft saved.')
                else:
                    submit_submission(
                        submission,
                        request.user,
                        form.cleaned_data['self_evaluation'],
                        form.cleaned_data['actual_situation'],
                        files=form.cleaned_data.get('files'),
                        link_url=form.cleaned_data.get('link_url', ''),
                    )
                    messages.success(request, 'Evidence submitted for review.')
                return redirect('accreditation:evidence_detail', submission_id=submission.id)
            except (PermissionDenied, WorkflowError) as error:
                form.add_error(None, str(error))
        return render(request, self.template_name, self.get_context(request, submission, form))


class EvidenceReviewView(ApprovedUserRequiredMixin, View):
    template_name = 'accreditation/evidence_review.html'

    def get_submission(self, request, submission_id):
        submission = get_object_or_404(_scoped_submissions(request.user), pk=submission_id)
        if submission.current_reviewer_id != request.user.id or not assignment_for_reviewer(request.user, submission):
            raise PermissionDenied('This submission is not assigned to you.')
        return submission

    def get(self, request, submission_id):
        submission = self.get_submission(request, submission_id)
        can_mark_non_complied = has_role(request.user, 'QA', 'ACCREDITATION_HEAD')
        return render(request, self.template_name, {
            'page_title': 'Review Workflow',
            'hide_topbar_title': True,
            'submission': submission,
            'requirement': submission.requirement,
            'latest_version': submission.latest_version,
            'reviews': submission.reviews.select_related('reviewer', 'reviewer_role').all(),
            'comments': submission.comments.select_related('author').all(),
            'form': ReviewActionForm(allow_non_complied=can_mark_non_complied),
            'can_mark_non_complied': can_mark_non_complied,
            'status_label': status_label(submission.status),
            'status_tone': status_tone(submission.status),
        })

    def post(self, request, submission_id):
        submission = self.get_submission(request, submission_id)
        can_mark_non_complied = has_role(request.user, 'QA', 'ACCREDITATION_HEAD')
        form = ReviewActionForm(request.POST, allow_non_complied=can_mark_non_complied)
        if form.is_valid():
            try:
                action = form.cleaned_data['action']
                remarks = form.cleaned_data.get('remarks', '')
                if action == 'approve':
                    approve_submission(submission, request.user, remarks)
                    messages.success(request, 'Evidence approved and forwarded.')
                elif action == 'revision':
                    request_revision(submission, request.user, remarks)
                    messages.success(request, 'Revision requested and returned to the Program Head.')
                else:
                    mark_non_complied(submission, request.user, remarks)
                    messages.success(request, 'Evidence marked non-complied.')
                return redirect('accreditation:review_workflow')
            except (PermissionDenied, WorkflowError) as error:
                form.add_error(None, str(error))
        return render(request, self.template_name, {
            'page_title': 'Review Workflow',
            'hide_topbar_title': True,
            'submission': submission,
            'requirement': submission.requirement,
            'latest_version': submission.latest_version,
            'reviews': submission.reviews.select_related('reviewer', 'reviewer_role').all(),
            'comments': submission.comments.select_related('author').all(),
            'form': form,
            'can_mark_non_complied': can_mark_non_complied,
            'status_label': status_label(submission.status),
            'status_tone': status_tone(submission.status),
        })


class ReviewWorkflowView(ApprovedUserRequiredMixin, TemplateView):
    template_name = 'accreditation/review_workflow.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        submissions = _scoped_submissions(self.request.user)
        if has_role(self.request.user, 'DEAN', 'AREA_CHAIR', 'QA', 'ACCREDITATION_HEAD'):
            submissions = submissions.filter(current_reviewer=self.request.user, status__in=ACTIVE_REVIEW_STATUSES)
        elif is_admin_user(self.request.user):
            submissions = submissions.filter(status__in=ACTIVE_REVIEW_STATUSES)
        else:
            submissions = submissions.none()
        rows = []
        for submission in submissions:
            rows.append({
                'evidence': submission.requirement.title,
                'code': submission.requirement.code,
                'department': submission.department.name,
                'area': submission.requirement.area.code,
                'submitted_by': submission.program_head.get_full_name() or submission.program_head.username,
                'status': status_label(submission.status),
                'tone': status_tone(submission.status),
                'reviewer': submission.current_reviewer.get_full_name() if submission.current_reviewer else 'Unassigned',
                'date': submission.submitted_at or submission.last_updated,
                'review_url': f'/accreditation/review/{submission.id}/',
            })
        context.update({
            'page_title': 'Review Workflow',
            'review_stats': [
                {'label': 'Pending Review', 'value': submissions.filter(status__in=ACTIVE_REVIEW_STATUSES).count(), 'tone': 'gold'},
                {'label': 'Needs Revision', 'value': _scoped_submissions(self.request.user).filter(status=EvidenceSubmission.NEEDS_REVISION).count(), 'tone': 'rose'},
                {'label': 'Closed', 'value': _scoped_submissions(self.request.user).filter(status=EvidenceSubmission.CLOSED).count(), 'tone': 'green'},
            ],
            'submissions': rows,
            'submission_count': len(rows),
        })
        return context
