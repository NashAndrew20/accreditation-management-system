from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.demo_accounts import DEMO_ACCOUNT_DEFINITIONS, DEMO_PASSWORD
from accreditation.cache import clear_active_structure_cache
from accreditation.evidence_data import EVIDENCE_ITEMS
from accreditation.models import (
    AccreditationArea,
    AccreditationCycle,
    AccreditationLevel,
    AccreditationSubArea,
    EvidenceComment,
    EvidenceFile,
    EvidenceRequirement,
    EvidenceReview,
    EvidenceSubmission,
    EvidenceVersion,
)
from accreditation.views import AREA_SUBAREAS
from core.models import AuditLog, Department, Notification, Role, RoleAssignment, UserProfile


ROLE_DEFINITIONS = [
    ('SUPERADMIN', 'Superadmin'),
    ('ADMIN', 'Admin'),
    ('QA', 'QA'),
    ('ACCREDITATION_HEAD', 'Accreditation Head'),
    ('PROGRAM_HEAD', 'Program Head'),
    ('DEAN', 'Dean'),
    ('AREA_CHAIR', 'Area Chair'),
    ('STUDENT', 'Student'),
]


DEPARTMENT_DEFINITIONS = [
    ('QA', 'QA Office', Department.OFFICE, None),
    ('CITE', 'CITE', Department.DEPARTMENT, None),
    ('ENG', 'College of Engineering', Department.DEPARTMENT, None),
    ('ENG-BSCIV', 'Bachelor of Science in Civil Engineering', Department.PROGRAM, 'ENG'),
    ('BUS', 'College of Business', Department.DEPARTMENT, None),
    ('EDU', 'College of Education', Department.DEPARTMENT, None),
    ('NURS', 'College of Nursing', Department.DEPARTMENT, None),
]


DEMO_USERS = tuple(
    (
        account['username'],
        account['email'],
        account['first_name'],
        account['last_name'],
        account['role_code'],
        account['department_code'],
    )
    for account in DEMO_ACCOUNT_DEFINITIONS
)

# Older demo usernames are migrated to the three canonical personas when the
# seeder runs. Their records are retained so evidence history is not lost.
LEGACY_DEMO_ALIASES = {
    'phead': ('uploader', 'program-head'),
    'dean': ('approver',),
}


class Command(BaseCommand):
    help = 'Seed the internal accreditation structure and development demo accounts.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Demo seeding is disabled when DEMO_MODE is false.')
        if not DEMO_PASSWORD:
            raise CommandError('Set DEMO_PASSWORD before seeding development accounts.')

        roles = {}
        for sort_order, (code, name) in enumerate(ROLE_DEFINITIONS):
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={'name': name, 'is_internal': True, 'is_active': True, 'sort_order': sort_order},
            )
            roles[code] = role

        departments = {}
        for code, name, kind, parent_code in DEPARTMENT_DEFINITIONS:
            parent = departments.get(parent_code)
            department, _ = Department.objects.update_or_create(
                code=code,
                defaults={'name': name, 'kind': kind, 'parent': parent, 'is_active': True},
            )
            departments[code] = department

        cycle, _ = AccreditationCycle.objects.update_or_create(
            academic_year='2025-2026',
            defaults={
                'name': 'PACUCOA Accreditation Cycle',
                'status': AccreditationCycle.ACTIVE,
                'is_active': True,
            },
        )
        level_names = [
            ('I', 'Level I', 'Candidate Status'),
            ('II', 'Level II', 'Accredited Status'),
            ('III', 'Level III', 'Accredited Status II'),
            ('IV', 'Level IV', 'Accredited Status III'),
        ]
        levels = {}
        for order, (code, name, status_label) in enumerate(level_names):
            level, _ = AccreditationLevel.objects.update_or_create(
                cycle=cycle,
                code=code,
                defaults={'name': name, 'status_label': status_label, 'sort_order': order},
            )
            levels[code] = level

        areas = []
        for order, (area_key, area_data) in enumerate(AREA_SUBAREAS.items()):
            area_number = area_data['code'].split()[-1]
            area, _ = AccreditationArea.objects.update_or_create(
                level=levels['I'],
                code=area_data['code'],
                defaults={
                    'name': area_data['name'],
                    'slug': area_key,
                    'sort_order': order,
                },
            )
            areas.append(area)
            subareas_by_code = {}
            for sub_order, subarea in enumerate(area_data['subareas']):
                subarea_obj, _ = AccreditationSubArea.objects.update_or_create(
                    area=area,
                    code=subarea['code'],
                    defaults={'title': subarea['title'], 'sort_order': sub_order},
                )
                subareas_by_code[subarea['code']] = subarea_obj
                for evidence_order, (evidence_code, evidence_title) in enumerate(EVIDENCE_ITEMS.get(subarea['code'], ())):
                    EvidenceRequirement.objects.update_or_create(
                        area=area,
                        code=evidence_code,
                        defaults={
                            'subarea': subarea_obj,
                            'title': evidence_title,
                            'required_description': f'Supporting evidence for {evidence_title}.',
                            'deadline': timezone.localdate() + timedelta(days=14 + order * 5 + evidence_order),
                            'sort_order': evidence_order,
                            'is_required': True,
                        },
                    )

        User = get_user_model()
        demo_users = {}
        for username, email, first_name, last_name, role_code, department_code in DEMO_USERS:
            user = User.objects.filter(username=username).first()
            if user is None:
                user = self._take_over_legacy_demo_user(User, username)
            if user is None:
                user = User.objects.create_user(username=username, email=email)
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.is_staff = role_code in {'SUPERADMIN', 'ADMIN'}
            user.is_superuser = role_code == 'SUPERADMIN'
            user.set_password(DEMO_PASSWORD)
            user.save()

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.department = departments[department_code]
            profile.approval_status = UserProfile.APPROVED
            profile.is_demo_account = True
            profile.must_change_password = False
            profile.save()

            assignment, _ = RoleAssignment.objects.update_or_create(
                user=user,
                role=roles[role_code],
                department=departments[department_code],
                defaults={
                    'is_approved': True,
                    'approved_by': None,
                },
            )
            # A canonical demo user should have one active role/department so
            # switching between the three personas remains predictable.
            RoleAssignment.objects.filter(user=user).exclude(pk=assignment.pk).update(is_approved=False)
            assignment.assigned_areas.clear()
            demo_users[username] = user
            profile.active_assignment = assignment
            profile.save(update_fields=['active_assignment', 'updated_at'])

        self._migrate_legacy_demo_users(User, demo_users)
        self._disable_stale_demo_accounts(User, set(demo_users))

        sample_count = self._seed_demo_submissions(
            areas=areas,
            departments=departments,
            roles=roles,
            users=demo_users,
        )
        clear_active_structure_cache()
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(roles)} internal roles, {len(departments)} departments/programs, '
            f'{len(areas)} areas, {len(DEMO_USERS)} demo accounts, and {sample_count} new sample submissions.'
        ))
        self.stdout.write('Demo accounts use the configured development-only password without forced first-login password changes.')

    @staticmethod
    def _take_over_legacy_demo_user(User, username):
        for legacy_username in LEGACY_DEMO_ALIASES.get(username, ()):
            legacy_user = User.objects.filter(
                username=legacy_username,
                profile__is_demo_account=True,
            ).first()
            if legacy_user:
                legacy_user.username = username
                legacy_user.save(update_fields=['username'])
                return legacy_user
        return None

    @classmethod
    def _migrate_legacy_demo_users(cls, User, demo_users):
        for canonical_username, legacy_usernames in LEGACY_DEMO_ALIASES.items():
            target = demo_users[canonical_username]
            for legacy_username in legacy_usernames:
                legacy = User.objects.filter(
                    username=legacy_username,
                    profile__is_demo_account=True,
                ).exclude(pk=target.pk).first()
                if not legacy:
                    continue
                cls._repoint_user_history(legacy, target)
                cls._disable_demo_account(legacy)

    @staticmethod
    def _repoint_user_history(source, target):
        submission_fields = (
            'program_head',
            'created_by',
            'last_updated_by',
            'current_reviewer',
            'revision_return_reviewer',
        )
        for field in submission_fields:
            EvidenceSubmission.objects.filter(**{f'{field}_id': source.id}).update(
                **{f'{field}_id': target.id},
            )

        for model, field in (
            (EvidenceVersion, 'submitted_by'),
            (EvidenceFile, 'uploaded_by'),
            (EvidenceReview, 'reviewer'),
            (EvidenceComment, 'author'),
            (Notification, 'user'),
            (AuditLog, 'actor'),
            (UserProfile, 'approved_by'),
            (RoleAssignment, 'approved_by'),
        ):
            model.objects.filter(**{f'{field}_id': source.id}).update(
                **{f'{field}_id': target.id},
            )

    @staticmethod
    def _disable_demo_account(user):
        user.is_active = False
        user.is_staff = False
        user.is_superuser = False
        user.save(update_fields=['is_active', 'is_staff', 'is_superuser'])
        RoleAssignment.objects.filter(user=user).update(is_approved=False)
        profile = getattr(user, 'profile', None)
        if profile:
            profile.active_assignment = None
            profile.save(update_fields=['active_assignment', 'updated_at'])

    @classmethod
    def _disable_stale_demo_accounts(cls, User, active_usernames):
        stale_users = User.objects.filter(profile__is_demo_account=True).exclude(username__in=active_usernames)
        for user in stale_users:
            cls._disable_demo_account(user)

    def _seed_demo_submissions(self, areas, departments, roles, users):
        """Create repeatable evidence activity so development dashboards are useful."""
        program_head = users['phead']
        dean = users['dean']
        qa = users['qa']
        sample_departments = [departments['CITE']]
        reviewer_by_stage = {
            EvidenceSubmission.UNDER_DEAN_REVIEW: (dean, roles['DEAN']),
            EvidenceSubmission.UNDER_QA_REVIEW: (qa, roles['QA']),
        }

        def reviewer_for_stage(stage, department):
            if stage == EvidenceSubmission.UNDER_DEAN_REVIEW and department.id != departments['CITE'].id:
                return None, None
            return reviewer_by_stage.get(stage, (None, None))

        status_pattern = [
            EvidenceSubmission.CLOSED,
            EvidenceSubmission.COMPLIED,
            EvidenceSubmission.UNDER_QA_REVIEW,
            EvidenceSubmission.UNDER_DEAN_REVIEW,
            EvidenceSubmission.NEEDS_REVISION,
            EvidenceSubmission.DRAFT,
            EvidenceSubmission.SUBMITTED,
            EvidenceSubmission.NON_COMPLIED,
            EvidenceSubmission.CLOSED,
        ]
        requirements = []
        for area in areas:
            requirements.extend(
                EvidenceRequirement.objects.filter(area=area)
                .select_related('subarea')
                .order_by('subarea__sort_order', 'sort_order', 'code')[:10]
            )

        now = timezone.now()
        created_count = 0
        for index, requirement in enumerate(requirements):
            department = sample_departments[index % len(sample_departments)]
            status = status_pattern[index % len(status_pattern)]
            age_days = (index * 5) % 180
            created_at = now - timedelta(days=age_days + 2, hours=index % 6)
            submitted_at = created_at + timedelta(hours=12)
            current_reviewer = None
            current_review_role = None
            revision_return_status = ''
            revision_return_reviewer = None
            revision_return_role = None

            if status in reviewer_by_stage:
                current_reviewer, current_review_role = reviewer_for_stage(status, department)
            elif status == EvidenceSubmission.SUBMITTED:
                current_reviewer, current_review_role = reviewer_for_stage(
                    EvidenceSubmission.UNDER_DEAN_REVIEW,
                    department,
                )
            elif status == EvidenceSubmission.NEEDS_REVISION:
                revision_return_status = (
                    EvidenceSubmission.UNDER_DEAN_REVIEW,
                    EvidenceSubmission.UNDER_QA_REVIEW,
                )[index % 2]
                revision_return_reviewer, revision_return_role = reviewer_for_stage(
                    revision_return_status,
                    department,
                )
                current_reviewer = program_head
                current_review_role = roles['PROGRAM_HEAD']

            submission, created = EvidenceSubmission.objects.get_or_create(
                requirement=requirement,
                department=department,
                defaults={
                    'program_head': program_head,
                    'created_by': program_head,
                    'last_updated_by': current_reviewer or program_head,
                    'current_reviewer': current_reviewer,
                    'current_review_role': current_review_role,
                    'status': status,
                    'self_evaluation': f'Demo self-evaluation for {requirement.code}.',
                    'actual_situation': (
                        f'Demo actual situation for {requirement.title} in {department.name}.'
                    ),
                    'revision_return_status': revision_return_status,
                    'revision_return_reviewer': revision_return_reviewer,
                    'revision_return_role': revision_return_role,
                    'submitted_at': None if status == EvidenceSubmission.DRAFT else submitted_at,
                    'closed_at': submitted_at + timedelta(days=4) if status == EvidenceSubmission.CLOSED else None,
                },
            )
            if not created:
                demo_version = EvidenceVersion.objects.filter(
                    submission=submission,
                    notes='Seeded development demo evidence.',
                ).first()
                if demo_version:
                    submission.program_head = program_head
                    if status in reviewer_by_stage:
                        submission.current_reviewer, submission.current_review_role = reviewer_for_stage(
                            status,
                            department,
                        )
                    elif status == EvidenceSubmission.SUBMITTED:
                        submission.current_reviewer, submission.current_review_role = reviewer_for_stage(
                            EvidenceSubmission.UNDER_DEAN_REVIEW,
                            department,
                        )
                    elif status == EvidenceSubmission.NEEDS_REVISION:
                        submission.current_reviewer = program_head
                        submission.current_review_role = roles['PROGRAM_HEAD']
                    submission.last_updated_by = submission.current_reviewer or program_head
                    submission.save(update_fields=[
                        'program_head',
                        'current_reviewer',
                        'current_review_role',
                        'last_updated_by',
                        'last_updated',
                    ])
                continue
            created_count += 1

            version = EvidenceVersion.objects.create(
                submission=submission,
                version_number=1,
                self_evaluation=submission.self_evaluation,
                actual_situation=submission.actual_situation,
                submitted_by=program_head,
                notes='Seeded development demo evidence.',
            )
            EvidenceFile.objects.create(
                version=version,
                uploaded_by=program_head,
                link_url=f'https://example.com/jmcfi-ams/{requirement.code.lower()}',
                original_name=f'{requirement.code} supporting evidence link',
                content_type='text/uri-list',
            )
            EvidenceVersion.objects.filter(pk=version.pk).update(created_at=created_at)
            EvidenceFile.objects.filter(version=version).update(created_at=created_at)

            self._stamp_submission(submission, created_at, submitted_at if status != EvidenceSubmission.DRAFT else None)
            self._seed_submission_history(
                submission=submission,
                version=version,
                status=status,
                index=index,
                submitted_at=submitted_at,
                reviewer_by_stage=reviewer_by_stage,
                roles=roles,
                program_head=program_head,
            )

        # Reconcile rows created by earlier demo seeds so their active reviewers
        # use the current canonical accounts where the stage is available.
        demo_submissions = EvidenceSubmission.objects.filter(
            status__in=(
                EvidenceSubmission.SUBMITTED,
                EvidenceSubmission.UNDER_DEAN_REVIEW,
                EvidenceSubmission.UNDER_QA_REVIEW,
            ),
            versions__notes='Seeded development demo evidence.',
        ).select_related('department').distinct()
        for submission in demo_submissions:
            stage = (
                EvidenceSubmission.UNDER_DEAN_REVIEW
                if submission.status == EvidenceSubmission.SUBMITTED
                else submission.status
            )
            reviewer, reviewer_role = reviewer_for_stage(stage, submission.department)
            if (
                submission.current_reviewer_id != getattr(reviewer, 'id', None)
                or submission.current_review_role_id != getattr(reviewer_role, 'id', None)
            ):
                submission.current_reviewer = reviewer
                submission.current_review_role = reviewer_role
                submission.last_updated_by = reviewer or program_head
                submission.save(update_fields=[
                    'current_reviewer',
                    'current_review_role',
                    'last_updated_by',
                    'last_updated',
                ])
        return created_count

    @staticmethod
    def _stamp_submission(submission, created_at, submitted_at):
        EvidenceSubmission.objects.filter(pk=submission.pk).update(
            created_at=created_at,
            last_updated=created_at + timedelta(hours=18),
            submitted_at=submitted_at,
        )

    def _seed_submission_history(
        self,
        submission,
        version,
        status,
        index,
        submitted_at,
        reviewer_by_stage,
        roles,
        program_head,
    ):
        if status == EvidenceSubmission.DRAFT:
            self._create_audit(
                actor=program_head,
                submission=submission,
                action='DRAFT_SAVED',
                details={'demo_seed': True, 'status': EvidenceSubmission.DRAFT},
                created_at=submitted_at - timedelta(hours=10),
            )
            return

        self._create_audit(
            actor=program_head,
            submission=submission,
            action='SUBMITTED',
            details={'demo_seed': True, 'to_status': EvidenceSubmission.UNDER_DEAN_REVIEW},
            created_at=submitted_at,
        )

        # The current demo intentionally has no Area Chair account. Keep the
        # role and workflow available to real users, but seed only the three
        # active demo personas and leave their samples at the Dean/QA stages.
        if status in {
            EvidenceSubmission.COMPLIED,
            EvidenceSubmission.CLOSED,
            EvidenceSubmission.NON_COMPLIED,
        }:
            qa_reviewer, qa_role = reviewer_by_stage[EvidenceSubmission.UNDER_QA_REVIEW]
            qa_time = submitted_at + timedelta(hours=32)
            if status == EvidenceSubmission.NON_COMPLIED:
                self._create_review(
                    submission=submission,
                    version=version,
                    reviewer=qa_reviewer,
                    reviewer_role=qa_role,
                    from_status=EvidenceSubmission.UNDER_QA_REVIEW,
                    to_status=EvidenceSubmission.NON_COMPLIED,
                    decision=EvidenceReview.NON_COMPLIED_DECISION,
                    remarks='Demo evidence requires additional proof before compliance.',
                    created_at=qa_time,
                )
                self._create_audit(
                    actor=qa_reviewer,
                    submission=submission,
                    action='NON_COMPLIED',
                    details={'demo_seed': True, 'from_status': EvidenceSubmission.UNDER_QA_REVIEW},
                    created_at=qa_time,
                )
            else:
                self._create_review(
                    submission=submission,
                    version=version,
                    reviewer=qa_reviewer,
                    reviewer_role=qa_role,
                    from_status=EvidenceSubmission.UNDER_QA_REVIEW,
                    to_status=EvidenceSubmission.COMPLIED,
                    decision=EvidenceReview.COMPLIED_DECISION,
                    remarks='Demo evidence meets the internal compliance check.',
                    created_at=qa_time,
                )
                self._create_audit(
                    actor=qa_reviewer,
                    submission=submission,
                    action='COMPLIED',
                    details={'demo_seed': True, 'from_status': EvidenceSubmission.UNDER_QA_REVIEW},
                    created_at=qa_time,
                )
                if status == EvidenceSubmission.CLOSED:
                    close_time = qa_time + timedelta(hours=8)
                    self._create_review(
                        submission=submission,
                        version=version,
                        reviewer=qa_reviewer,
                        reviewer_role=qa_role,
                        from_status=EvidenceSubmission.COMPLIED,
                        to_status=EvidenceSubmission.CLOSED,
                        decision=EvidenceReview.CLOSED_DECISION,
                        remarks='Demo evidence marked complied after final internal review.',
                        created_at=close_time,
                    )
                    self._create_audit(
                        actor=qa_reviewer,
                        submission=submission,
                        action='CLOSED',
                        details={'demo_seed': True, 'from_status': EvidenceSubmission.COMPLIED},
                        created_at=close_time,
                    )

        if status == EvidenceSubmission.NEEDS_REVISION:
            revision_stage = (
                EvidenceSubmission.UNDER_DEAN_REVIEW,
                EvidenceSubmission.UNDER_QA_REVIEW,
            )[index % 2]
            reviewer, reviewer_role = reviewer_by_stage[revision_stage]
            revision_time = submitted_at + timedelta(hours=10)
            remarks = 'Demo revision requested: attach clearer supporting evidence and update the narrative.'
            self._create_review(
                submission=submission,
                version=version,
                reviewer=reviewer,
                reviewer_role=reviewer_role,
                from_status=revision_stage,
                to_status=EvidenceSubmission.NEEDS_REVISION,
                decision=EvidenceReview.REQUEST_REVISION,
                remarks=remarks,
                created_at=revision_time,
            )
            EvidenceComment.objects.create(
                submission=submission,
                version=version,
                author=reviewer,
                body=remarks,
            )
            self._create_audit(
                actor=reviewer,
                submission=submission,
                action='REQUEST_REVISION',
                details={'demo_seed': True, 'from_status': revision_stage, 'remarks': remarks},
                created_at=revision_time,
            )

    @staticmethod
    def _create_review(
        submission,
        version,
        reviewer,
        reviewer_role,
        from_status,
        to_status,
        decision,
        remarks,
        created_at,
    ):
        review = EvidenceReview.objects.create(
            submission=submission,
            version=version,
            reviewer=reviewer,
            reviewer_role=reviewer_role,
            from_status=from_status,
            to_status=to_status,
            decision=decision,
            remarks=remarks,
        )
        EvidenceReview.objects.filter(pk=review.pk).update(created_at=created_at)
        return review

    @staticmethod
    def _create_audit(actor, submission, action, details, created_at):
        event = AuditLog.objects.create(
            actor=actor,
            submission=submission,
            action=action,
            object_type='EvidenceSubmission',
            object_id=str(submission.pk),
            details=details,
        )
        AuditLog.objects.filter(pk=event.pk).update(created_at=created_at)
        return event
