from django.db import models


class AccreditationCycle(models.Model):
    DRAFT = 'DRAFT'
    ACTIVE = 'ACTIVE'
    CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (DRAFT, 'Draft'),
        (ACTIVE, 'Active'),
        (CLOSED, 'Closed'),
    )

    name = models.CharField(max_length=180)
    academic_year = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-is_active', '-created_at')

    def __str__(self):
        return f'{self.name} · {self.academic_year}'


class AccreditationLevel(models.Model):
    cycle = models.ForeignKey(AccreditationCycle, on_delete=models.CASCADE, related_name='levels')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    status_label = models.CharField(max_length=100, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order',)
        constraints = [
            models.UniqueConstraint(fields=('cycle', 'code'), name='unique_cycle_level_code'),
        ]

    def __str__(self):
        return self.name


class AccreditationArea(models.Model):
    level = models.ForeignKey(AccreditationLevel, on_delete=models.CASCADE, related_name='areas')
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=80)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order',)
        constraints = [
            models.UniqueConstraint(fields=('level', 'code'), name='unique_level_area_code'),
            models.UniqueConstraint(fields=('level', 'slug'), name='unique_level_area_slug'),
        ]

    def __str__(self):
        return f'{self.code} · {self.name}'


class AccreditationSubArea(models.Model):
    area = models.ForeignKey(AccreditationArea, on_delete=models.CASCADE, related_name='subareas')
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=240)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order',)
        constraints = [
            models.UniqueConstraint(fields=('area', 'code'), name='unique_area_subarea_code'),
        ]

    def __str__(self):
        return f'{self.code} · {self.title}'


class EvidenceRequirement(models.Model):
    area = models.ForeignKey(AccreditationArea, on_delete=models.CASCADE, related_name='evidence_requirements')
    subarea = models.ForeignKey(
        AccreditationSubArea,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='evidence_requirements',
    )
    code = models.CharField(max_length=30)
    title = models.CharField(max_length=300)
    required_description = models.TextField(blank=True)
    deadline = models.DateField(null=True, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_required = models.BooleanField(default=True)

    class Meta:
        ordering = ('sort_order',)
        constraints = [
            models.UniqueConstraint(fields=('area', 'code'), name='unique_area_evidence_code'),
        ]

    def __str__(self):
        return f'{self.code} · {self.title}'


class AreaAssignment(models.Model):
    """Record which department or program owns an area's evidence work."""

    area = models.ForeignKey(AccreditationArea, on_delete=models.CASCADE, related_name='assignments')
    department = models.ForeignKey(
        'core.Department',
        on_delete=models.PROTECT,
        related_name='accreditation_area_assignments',
    )
    assigned_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        related_name='created_area_assignments',
    )
    deadline = models.DateField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('deadline', 'department__name')
        constraints = [
            models.UniqueConstraint(
                fields=('area', 'department'),
                name='unique_area_assignment_department',
            ),
        ]

    def __str__(self):
        return f'{self.area.code} · {self.department.name}'


class EvidenceSubmission(models.Model):
    DRAFT = 'DRAFT'
    SUBMITTED = 'SUBMITTED'
    UNDER_DEAN_REVIEW = 'UNDER_DEAN_REVIEW'
    UNDER_AREA_CHAIR_REVIEW = 'UNDER_AREA_CHAIR_REVIEW'
    UNDER_QA_REVIEW = 'UNDER_QA_REVIEW'
    NEEDS_REVISION = 'NEEDS_REVISION'
    COMPLIED = 'COMPLIED'
    NON_COMPLIED = 'NON_COMPLIED'
    CLOSED = 'CLOSED'
    STATUS_CHOICES = (
        (DRAFT, 'Draft'),
        (SUBMITTED, 'Submitted'),
        (UNDER_DEAN_REVIEW, 'Under Dean Review'),
        (UNDER_AREA_CHAIR_REVIEW, 'Under Area Chair Review'),
        (UNDER_QA_REVIEW, 'Under QA Review'),
        (NEEDS_REVISION, 'Needs Revision'),
        (COMPLIED, 'Complied'),
        (NON_COMPLIED, 'Non-Complied'),
        (CLOSED, 'Complied'),
    )

    requirement = models.ForeignKey(EvidenceRequirement, on_delete=models.PROTECT, related_name='submissions')
    department = models.ForeignKey(
        'core.Department',
        on_delete=models.PROTECT,
        related_name='evidence_submissions',
    )
    program_head = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        related_name='owned_evidence_submissions',
    )
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.PROTECT,
        related_name='created_evidence_submissions',
    )
    last_updated_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='updated_evidence_submissions',
    )
    current_reviewer = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_evidence_reviews',
    )
    current_review_role = models.ForeignKey(
        'core.Role',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='current_evidence_reviews',
    )
    status = models.CharField(max_length=35, choices=STATUS_CHOICES, default=DRAFT)
    self_evaluation = models.TextField(blank=True)
    actual_situation = models.TextField(blank=True)
    revision_return_status = models.CharField(max_length=35, choices=STATUS_CHOICES, blank=True)
    revision_return_reviewer = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='revision_return_submissions',
    )
    revision_return_role = models.ForeignKey(
        'core.Role',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='revision_return_submissions',
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('requirement__code', 'department__name')
        constraints = [
            models.UniqueConstraint(
                fields=('requirement', 'department'),
                name='unique_requirement_department_submission',
            ),
        ]

    def __str__(self):
        return f'{self.requirement.code} · {self.department.name}'

    @property
    def latest_version(self):
        return self.versions.order_by('-version_number').first()


class EvidenceVersion(models.Model):
    submission = models.ForeignKey(EvidenceSubmission, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    self_evaluation = models.TextField(blank=True)
    actual_situation = models.TextField(blank=True)
    submitted_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='evidence_versions')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-version_number',)
        constraints = [
            models.UniqueConstraint(fields=('submission', 'version_number'), name='unique_submission_version'),
        ]


class EvidenceFile(models.Model):
    version = models.ForeignKey(EvidenceVersion, on_delete=models.CASCADE, related_name='files')
    uploaded_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='evidence_files')
    file = models.FileField(upload_to='evidence/%Y/%m/%d/', blank=True)
    link_url = models.URLField(blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=120, blank=True)
    size = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class EvidenceReview(models.Model):
    APPROVED = 'APPROVED'
    REQUEST_REVISION = 'REQUEST_REVISION'
    COMPLIED_DECISION = 'COMPLIED'
    NON_COMPLIED_DECISION = 'NON_COMPLIED'
    CLOSED_DECISION = 'CLOSED'
    DECISION_CHOICES = (
        (APPROVED, 'Approved'),
        (REQUEST_REVISION, 'Request Revision'),
        (COMPLIED_DECISION, 'Complied'),
        (NON_COMPLIED_DECISION, 'Non-Complied'),
        (CLOSED_DECISION, 'Complied'),
    )

    submission = models.ForeignKey(EvidenceSubmission, on_delete=models.CASCADE, related_name='reviews')
    version = models.ForeignKey(EvidenceVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviews')
    reviewer = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='evidence_reviews')
    reviewer_role = models.ForeignKey('core.Role', on_delete=models.PROTECT, related_name='evidence_reviews')
    from_status = models.CharField(max_length=35, choices=EvidenceSubmission.STATUS_CHOICES)
    to_status = models.CharField(max_length=35, choices=EvidenceSubmission.STATUS_CHOICES)
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class EvidenceComment(models.Model):
    submission = models.ForeignKey(EvidenceSubmission, on_delete=models.CASCADE, related_name='comments')
    version = models.ForeignKey(EvidenceVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name='comments')
    author = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='evidence_comments')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at',)
