from rest_framework import serializers

from .models import EvidenceFile, EvidenceReview, EvidenceSubmission, EvidenceVersion


class EvidenceFileSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.CharField(source='uploaded_by.username', read_only=True)
    url = serializers.SerializerMethodField()

    class Meta:
        model = EvidenceFile
        fields = ('id', 'original_name', 'content_type', 'size', 'url', 'uploaded_by', 'created_at')
        read_only_fields = fields

    def get_url(self, obj):
        if obj.link_url:
            return obj.link_url
        if not obj.file:
            return None
        request = self.context.get('request')
        file_url = obj.file.url
        return request.build_absolute_uri(file_url) if request else file_url


class EvidenceVersionSerializer(serializers.ModelSerializer):
    submitted_by = serializers.CharField(source='submitted_by.username', read_only=True)
    submitted_at = serializers.DateTimeField(source='created_at', read_only=True)
    files = EvidenceFileSerializer(many=True, read_only=True)

    class Meta:
        model = EvidenceVersion
        fields = (
            'id',
            'version_number',
            'self_evaluation',
            'actual_situation',
            'submitted_by',
            'submitted_at',
            'notes',
            'files',
        )
        read_only_fields = fields


class EvidenceReviewSerializer(serializers.ModelSerializer):
    reviewer = serializers.CharField(source='reviewer.username', read_only=True)
    reviewer_role = serializers.CharField(source='reviewer_role.name', read_only=True)
    from_status = serializers.CharField(source='get_from_status_display', read_only=True)
    to_status = serializers.CharField(source='get_to_status_display', read_only=True)
    decision = serializers.CharField(source='get_decision_display', read_only=True)
    reviewed_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = EvidenceReview
        fields = (
            'id',
            'reviewer',
            'reviewer_role',
            'from_status',
            'to_status',
            'decision',
            'remarks',
            'reviewed_at',
        )
        read_only_fields = fields


class EvidenceSubmissionSerializer(serializers.ModelSerializer):
    evidence_code = serializers.CharField(source='requirement.code', read_only=True)
    evidence_title = serializers.CharField(source='requirement.title', read_only=True)
    level = serializers.CharField(source='requirement.area.level.name', read_only=True)
    level_code = serializers.CharField(source='requirement.area.level.code', read_only=True)
    area = serializers.CharField(source='requirement.area.name', read_only=True)
    area_code = serializers.CharField(source='requirement.area.code', read_only=True)
    sub_area = serializers.CharField(source='requirement.subarea.title', allow_null=True, read_only=True)
    sub_area_code = serializers.CharField(source='requirement.subarea.code', allow_null=True, read_only=True)
    department = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    required_evidence_description = serializers.CharField(source='requirement.required_description', read_only=True)
    status_code = serializers.CharField(source='status', read_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)
    current_reviewer = serializers.SerializerMethodField()
    submission_date = serializers.DateTimeField(source='submitted_at', read_only=True)
    versions = EvidenceVersionSerializer(many=True, read_only=True)
    review_history = EvidenceReviewSerializer(source='reviews', many=True, read_only=True)

    class Meta:
        model = EvidenceSubmission
        fields = (
            'id',
            'evidence_code',
            'evidence_title',
            'level',
            'level_code',
            'area',
            'area_code',
            'sub_area',
            'sub_area_code',
            'department',
            'department_code',
            'required_evidence_description',
            'self_evaluation',
            'actual_situation',
            'current_reviewer',
            'status_code',
            'status',
            'submission_date',
            'last_updated',
            'versions',
            'review_history',
        )
        read_only_fields = fields

    def get_current_reviewer(self, obj):
        if not obj.current_reviewer:
            return None
        return {
            'username': obj.current_reviewer.username,
            'name': obj.current_reviewer.get_full_name().strip() or obj.current_reviewer.username,
            'role': obj.current_review_role.name if obj.current_review_role else '',
        }
