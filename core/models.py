from django.db import models


ROLE_CODES = (
    'SUPERADMIN',
    'ADMIN',
    'QA',
    'ACCREDITATION_HEAD',
    'PROGRAM_HEAD',
    'DEAN',
    'AREA_CHAIR',
    'STUDENT',
)


class Role(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    is_internal = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('sort_order', 'name')

    def __str__(self):
        return self.name


class Department(models.Model):
    DEPARTMENT = 'DEPARTMENT'
    PROGRAM = 'PROGRAM'
    OFFICE = 'OFFICE'
    KIND_CHOICES = (
        (DEPARTMENT, 'Department'),
        (PROGRAM, 'Program'),
        (OFFICE, 'Office'),
    )

    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=160)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=DEPARTMENT)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='children',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ('kind', 'name')

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    PENDING = 'PENDING'
    APPROVED = 'APPROVED'
    REJECTED = 'REJECTED'
    APPROVAL_CHOICES = (
        (PENDING, 'Pending Approval'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    )

    user = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='profile')
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='profiles',
    )
    active_assignment = models.ForeignKey(
        'RoleAssignment',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='active_profiles',
    )
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default=PENDING)
    approved_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_profiles',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    photo = models.FileField(upload_to='profiles/', blank=True)
    google_subject = models.CharField(max_length=255, unique=True, null=True, blank=True)
    is_demo_account = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def is_approved(self):
        return self.approval_status == self.APPROVED and self.user.is_active


class RoleAssignment(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='role_assignments')
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='assignments')
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='role_assignments')
    assigned_areas = models.ManyToManyField(
        'accreditation.AccreditationArea',
        blank=True,
        related_name='role_assignments',
    )
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_role_assignments',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('role__sort_order', 'department__name', 'user__username')
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'role', 'department'),
                name='unique_user_role_department',
            ),
        ]

    def __str__(self):
        return f'{self.user} · {self.role} · {self.department}'


class Notification(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='notifications')
    submission = models.ForeignKey(
        'accreditation.EvidenceSubmission',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    kind = models.CharField(max_length=40, default='workflow')
    title = models.CharField(max_length=180)
    message = models.TextField()
    target_url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('is_read', '-created_at')


class AuditLog(models.Model):
    actor = models.ForeignKey(
        'auth.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    submission = models.ForeignKey(
        'accreditation.EvidenceSubmission',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_events',
    )
    action = models.CharField(max_length=80)
    object_type = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=64, blank=True)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)


class Policy(models.Model):
    PRIVACY = 'PRIVACY'
    TERMS = 'TERMS'
    POLICY_TYPE_CHOICES = (
        (PRIVACY, 'Privacy Policy'),
        (TERMS, 'Terms of Use'),
    )

    DRAFT = 'DRAFT'
    ACTIVE = 'ACTIVE'
    STATUS_CHOICES = (
        (DRAFT, 'Draft'),
        (ACTIVE, 'Active'),
    )

    policy_type = models.CharField(max_length=20, choices=POLICY_TYPE_CHOICES)
    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=160)
    version = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=DRAFT)
    is_required = models.BooleanField(default=True)
    effective_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-status', 'policy_type', '-version')
        constraints = [
            models.UniqueConstraint(
                fields=('policy_type', 'version'),
                name='unique_policy_type_version',
            ),
        ]

    def __str__(self):
        return f'{self.get_policy_type_display()} v{self.version}'

    @staticmethod
    def active_required():
        """Active policies that require explicit user acknowledgment."""
        return Policy.objects.filter(status=Policy.ACTIVE, is_required=True).order_by(
            'policy_type', '-version'
        )


class PolicyConsent(models.Model):
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='policy_consents',
    )
    policy = models.ForeignKey(
        Policy,
        on_delete=models.CASCADE,
        related_name='consents',
    )
    version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('policy__policy_type',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'policy'),
                name='unique_user_policy_consent',
            ),
        ]

    def __str__(self):
        return f'{self.user} · {self.policy} · {self.version}'
