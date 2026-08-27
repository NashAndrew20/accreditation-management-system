from django import forms

from core.models import Department

from .models import EvidenceSubmission


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [super().clean(item, initial) for item in data]
        return [super().clean(data, initial)]


class EvidenceSubmissionForm(forms.ModelForm):
    files = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={'multiple': True, 'accept': '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.jpg,.jpeg,.png'}),
    )
    link_url = forms.URLField(required=False, label='Supporting link')

    class Meta:
        model = EvidenceSubmission
        fields = ('self_evaluation', 'actual_situation')
        widgets = {
            'self_evaluation': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Explain how the program meets this requirement and cite the evidence.',
            }),
            'actual_situation': forms.Textarea(attrs={
                'rows': 6,
                'placeholder': 'Describe the current situation, implementation, and any gaps.',
            }),
        }


class ReviewActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=(
            ('approve', 'Approve and forward'),
            ('revision', 'Request revision'),
            ('non_complied', 'Mark non-complied'),
        ),
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Add reviewer remarks...'}),
    )

    def __init__(
        self,
        *args,
        allow_non_complied=True,
        approve_label='Approve and forward',
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        approve_choice = ('approve', approve_label)
        if not allow_non_complied:
            self.fields['action'].choices = (
                approve_choice,
                ('revision', 'Request revision'),
            )
        else:
            self.fields['action'].choices = (
                approve_choice,
                ('revision', 'Request revision'),
                ('non_complied', 'Mark non-complied'),
            )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('action') == 'revision' and not cleaned.get('remarks', '').strip():
            self.add_error('remarks', 'Remarks are required when requesting a revision.')
        return cleaned


class AreaAssignmentForm(forms.Form):
    department_scope = forms.ChoiceField(
        label='Assignment scope',
        choices=(
            ('all', 'All departments / programs'),
            ('specific', 'Specific departments / programs'),
        ),
        initial='all',
        widget=forms.RadioSelect,
    )
    departments = forms.ModelMultipleChoiceField(
        label='Departments / programs',
        queryset=Department.objects.none(),
        required=False,
        help_text='Choose one or more departments when using the specific option.',
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'assignment-checkbox-list'}),
    )
    deadline = forms.DateField(
        label='Deadline',
        widget=forms.DateInput(attrs={'class': 'assignment-input', 'type': 'date'}),
    )
    instructions = forms.CharField(
        label='Instructions (optional)',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'assignment-input',
            'rows': 4,
            'placeholder': 'Add guidance for the assigned Program Head(s).',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        departments = Department.objects.filter(
            is_active=True,
            kind__in=(Department.DEPARTMENT, Department.PROGRAM),
        ).order_by('kind', 'name')
        self.fields['departments'].queryset = departments
        self.fields['departments'].label_from_instance = (
            lambda department: f'{department.name} · {department.get_kind_display()}'
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('department_scope') == 'specific' and not cleaned.get('departments'):
            self.add_error('departments', 'Select at least one department or program.')
        if cleaned.get('department_scope') == 'all':
            cleaned['departments'] = self.fields['departments'].queryset
        return cleaned
