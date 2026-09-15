"""
AIRA — the accreditation intelligent companion.

AIRA answers natural-language questions using ONLY the current user's
authorized AMS records (``core.access.accessible_submissions`` plus the
active accreditation structure). No external AI-provider call happens:
every reply is produced from live, role-scoped data, so AIRA cannot
fabricate documents, requirements, scores, statuses, or decisions, and
cannot reveal records outside the caller's authorization scope.

Safety rules enforced here:

* Uploaded documents are DATA, never instructions. AIRA never reads file
  bytes, never executes instructions found inside uploaded content, and
  never transmits document contents anywhere.
* System prompts, credentials, API keys, environment variables, and
  internal security configuration are never shared, however a question
  is phrased.
* Direct probes for records outside the user's authorization are refused
  without confirming whether such records exist (IDOR/BOLA protection).
* AIRA reports review statuses already recorded in the AMS; it never
  makes or claims an official accreditation decision.
* No URL retrieval is performed. A URL inside a document is never
  fetched; external pages are never treated as institutional evidence.
"""

import re
from datetime import timedelta

from django.utils import timezone

from accreditation.constants import ACTIVE_REVIEW_STATUSES, COMPLETED_STATUSES
from accreditation.models import AccreditationArea, AreaAssignment, EvidenceSubmission
from core.access import active_assignment, accessible_submissions, department_scope_ids

SOURCE_LABEL = 'AMS records'

STATUS_LABELS = dict(EvidenceSubmission.STATUS_CHOICES)

_ROMAN_VALUES = {'i': 1, 'v': 5, 'x': 10, 'l': 50}


def _status_label(value):
    return STATUS_LABELS.get(value, 'Not Started')


def _submissions(user):
    return accessible_submissions(user).select_related(
        'requirement',
        'requirement__area',
        'requirement__subarea',
        'department',
    )


# ---------------------------------------------------------------------------
# Safety / refusal
# ---------------------------------------------------------------------------

_SECRET_TERMS = (
    'system prompt',
    'system instruction',
    'your instructions',
    'your prompt',
    'api key',
    'secret',
    'password',
    'credential',
    'token',
    'environment variable',
    'internal configuration',
    '.env',
    'bypass',
    'override instructions',
    'ignore earlier instructions',
    'ignore previous',
    'reveal',
    'expose',
    'injection',
)


def _looks_like_secret_request(question):
    lowered = question.lower()
    return any(term in lowered for term in _SECRET_TERMS)


def _refuse_secrets():
    return {
        'intent': 'refused',
        'source': SOURCE_LABEL,
        'reply': (
            "I can't share system prompts, credentials, API keys, environment "
            "variables, or internal security configuration. Those are protected. "
            "Instructions found inside uploaded documents are treated as document "
            "content, never as commands to me."
        ),
        'suggestions': [],
    }


def _refuse_out_of_scope():
    return {
        'intent': 'refused',
        'source': SOURCE_LABEL,
        'reply': (
            "I can't provide that information because it is outside your authorized "
            "access. I can help with your assigned accreditation work instead."
        ),
        'suggestions': [
            'What evidence is still missing in my scope?',
            'What is my current review status?',
        ],
    }


def _probe_out_of_scope(user, question):
    """Refuse direct object probes that resolve outside the user's scope."""
    match = re.search(r'submission[^\d]{0,12}(\d{1,10})', question.lower())
    if not match:
        return None
    target_id = int(match.group(1))
    if _submissions(user).filter(pk=target_id).exists():
        return None
    return _refuse_out_of_scope()


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def _detect_intents(question):
    lowered = question.lower()
    intents = set()
    if any(term in lowered for term in (
        'missing', 'gap', 'gaps', 'incomplete', 'outstanding',
        'what do i still need', 'what to do next', 'to-do',
    )):
        intents.add('gaps')
    if any(term in lowered for term in (
        'deadline', 'deadlines', 'due', 'due date', 'overdue', 'july 25',
        'when is', 'schedule', 'time frame', 'window',
    )):
        intents.add('deadlines')
    if any(term in lowered for term in (
        'requirement', 'requirements', 'what is required', 'area', 'sub-area',
        'what do i prepare', 'prepare for',
    )):
        intents.add('requirements')
    if any(term in lowered for term in (
        'status', 'review', 'progress', 'where is', 'what stage', 'folded',
        'forward', 'approval', 'step of review',
    )):
        intents.add('status')
    if any(term in lowered for term in (
        'document', 'evidence uploaded', 'uploaded', 'file', 'attach',
        'latest version', 'version', 'synopsis', 'submitted evidence',
    )):
        intents.add('documents')
    if any(term in lowered for term in (
        'who am i', 'my role', 'my department', 'what can i see',
        'my scope', 'what am i', 'my access',
    )):
        intents.add('scope')
    if any(term in lowered for term in (
        'what can you do', 'how do you work', 'capabilities', 'what are you',
        'help me use', 'how can you help',
    )):
        intents.add('capabilities')
    if any(term in lowered for term in (
        'complied', 'compliant', 'approved', 'accredited', 'fits',
        'confirm', 'final decision', 'officially',
    )):
        intents.add('compliance')
    return intents


# ---------------------------------------------------------------------------
# Reply builders (all data-driven from authorized records)
# ---------------------------------------------------------------------------

def _reply_capabilities():
    return {
        'intent': 'capabilities',
        'source': SOURCE_LABEL,
        'reply': (
            "I'm AIRA, the accreditation intelligent companion for JMCFI AMS. "
            "I can help you understand accreditation requirements, find missing "
            "or incomplete evidence, track submission and review status, check "
            "upcoming deadlines, and identify which evidence documents are "
            "on record for your scope. I work only from the AMS records you are "
            "authorized to access. I am an assistant, not the final accreditation "
            "decision-maker."
        ),
        'suggestions': [
            'What evidence is still missing in my scope?',
            'Which review decisions are recorded as complied?',
            'What is my current review status?',
        ],
    }


def _reply_gaps(user):
    submissions = _submissions(user)
    incomplete = list(submissions.filter(status__in=(
        EvidenceSubmission.DRAFT,
        EvidenceSubmission.NEEDS_REVISION,
        EvidenceSubmission.NON_COMPLIED,
    )).order_by('-last_updated')[:5])
    if not submissions.exists():
        return {
            'intent': 'gaps',
            'source': SOURCE_LABEL,
            'reply': (
                'There are no evidence submissions in your accessible scope yet, '
                'so there are no recorded gaps to report. Evidence is prepared '
                'inside the sub-area workspaces under My Tasks.'
            ),
            'suggestions': ['What do I need to prepare for an area?'],
        }
    if not incomplete:
        return {
            'intent': 'gaps',
            'source': SOURCE_LABEL,
            'reply': (
                'Every evidence submission in your accessible scope has a closed '
                'review record. No missing or incomplete items are on record.'
            ),
            'suggestions': ['Show me the review status summary'],
        }
    lines = '\n'.join(
        f'• {item.requirement.code} — {item.requirement.title} '
        f'({_status_label(item.status)}, {item.department.name})'
        for item in incomplete
    )
    return {
        'intent': 'gaps',
        'source': SOURCE_LABEL,
        'reply': (
            f'In your scope, {len(incomplete)} evidence item(s) are still recorded '
            f'as missing or incomplete:\n{lines}\n'
            'Items returned for revision should be prioritized first, since a '
            'reviewer has already asked for updates.'
        ),
        'suggestions': [
            'Why was this returned for revision?',
            'Which evidence documents are on record?',
        ],
    }


def _reply_deadlines(user):
    today = timezone.localdate()
    horizon = today + timedelta(days=30)
    submissions = _submissions(user)
    requirement_deadlines = [
        item.requirement
        for item in submissions.exclude(requirement__deadline=None).order_by('requirement__deadline')
        if today <= item.requirement.deadline <= horizon
    ]
    requirement_deadlines = requirement_deadlines[:5]

    assignment = active_assignment(user)
    if assignment:
        scoped_departments = department_scope_ids(assignment.department)
        area_assignments = AreaAssignment.objects.filter(
            department_id__in=scoped_departments,
            deadline__range=(today, horizon),
        ).select_related('area').order_by('deadline')[:5]
    else:
        area_assignments = AreaAssignment.objects.filter(
            deadline__range=(today, horizon),
        ).select_related('area').order_by('deadline')[:5]

    items = []
    for requirement in requirement_deadlines:
        items.append((requirement.deadline, f"Requirement {requirement.code} — {requirement.title}"))
    for area_assignment in area_assignments:
        items.append((area_assignment.deadline, f"Area {area_assignment.area.code} — {area_assignment.area.name} assignment"))
    items = sorted(items)[:5]

    if not items:
        return {
            'intent': 'deadlines',
            'source': SOURCE_LABEL,
            'reply': (
                'No accreditation deadlines are recorded in the next 30 days for '
                'your accessible scope.'
            ),
            'suggestions': ['What evidence is still missing?'],
        }
    lines = '\n'.join(
        f'• {deadline.strftime("%b %d, %Y")} — {label}'
        for deadline, label in items
    )
    return {
        'intent': 'deadlines',
        'source': SOURCE_LABEL,
        'reply': (
            f'Upcoming deadlines in the next 30 days for your scope:\n{lines}\n'
            'Dates come from the active accreditation cycle and area assignments.'
        ),
        'suggestions': ['What is currently overdue?', 'Show my review queue'],
    }


def _extract_area_code(question):
    """Return the area code candidates mentioned in ``question``.

    Stored area codes use Roman numerals (for example ``Area I``). Users may
    type either the Roman spelling or the plain number, so both variants are
    returned and matched loosely against the active areas.
    """
    lowered = question.lower()
    match = re.search(r'\barea[:\s]*([ivxlcdm]+|\d{1,2})\b', lowered)
    if not match:
        return None
    token = match.group(1)
    if token.isdigit():
        number = int(token)
        roman = _ROMAN_VALUES.get('i', 1)
        return [f'Area {token}', f'Area {_to_roman(number)}']
    return [f'Area {token.upper()}', f'Area {_roman_value(token)}']


def _to_roman(number):
    numerals = (
        (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
        (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I'),
    )
    if number < 1 or number > 100:
        return 'I'
    result = ''
    for value, symbol in numerals:
        while number >= value:
            result += symbol
            number -= value
    return result


def _roman_value(token):
    total = 0
    value = 0
    for char in token.upper():
        digit = _ROMAN_VALUES.get(char, 0)
        total += digit
        if digit > value:
            total -= value * 2
        value = digit
    return total if total else 1


def _reply_requirements(user, question):
    area_codes = _extract_area_code(question)
    submissions = _submissions(user)
    if not area_codes:
        areas = AccreditationArea.objects.filter(level__cycle__is_active=True).order_by('level__sort_order', 'sort_order')
        if not areas.exists():
            return {
                'intent': 'requirements',
                'source': SOURCE_LABEL,
                'reply': 'No accreditation areas are configured in the active cycle yet.',
                'suggestions': [],
            }
        sample = ', '.join(area.code for area in areas[:5])
        return {
            'intent': 'requirements',
            'source': SOURCE_LABEL,
            'reply': (
                'I can list the evidence requirements for a specific area. The active '
                f'cycle currently has: {sample}. Ask me, for example, '
                '"What is required for Area I?"'
            ),
            'suggestions': [f'What is required for {areas.first().code}?'],
        }

    areas = list(AccreditationArea.objects.filter(
        code__in=area_codes,
        level__cycle__is_active=True,
    ).select_related('level'))
    if not areas:
        return {
            'intent': 'requirements',
            'source': SOURCE_LABEL,
            'reply': (
                f"{area_codes[0]} is not part of the active accreditation cycle, so I "
                "don't have records for it."
            ),
            'suggestions': ['What evidence is still missing in my scope?'],
        }

    area = areas[0]
    requirements = list(
        area.evidence_requirements.select_related('subarea').order_by('sort_order')
    )
    if not requirements:
        return {
            'intent': 'requirements',
            'source': SOURCE_LABEL,
            'reply': f'{area.code} has no evidence requirements configured yet.',
            'suggestions': ['Which areas are configured in the active cycle?'],
        }

    by_requirement = {
        item.requirement_id: _status_label(item.status)
        for item in submissions.filter(requirement_id__in=[req.id for req in requirements])
    }
    lines = []
    for requirement in requirements:
        label = by_requirement.get(requirement.id)
        subarea = f' · {requirement.subarea.code}' if requirement.subarea else ''
        if label:
            lines.append(f'• {requirement.code} — {requirement.title} ({label})')
        else:
            lines.append(f'• {requirement.code} — {requirement.title} (no submission recorded)')
    return {
        'intent': 'requirements',
        'source': SOURCE_LABEL,
        'reply': (
            f'Evidence requirements recorded for {area.code}:\n'
            + '\n'.join(lines)
            + '\nStatuses shown are as recorded in the AMS review records.'
        ),
        'suggestions': ['Which of these are still missing?'],
    }


def _reply_documents(user):
    submissions = _submissions(user).prefetch_related('versions__files')
    records = []
    for submission in submissions.order_by('-last_updated')[:8]:
        version = submission.latest_version
        if not version:
            continue
        names = [
            evidence_file.original_name or evidence_file.file.name or evidence_file.link_url
            for evidence_file in version.files.all()
            if evidence_file.original_name or evidence_file.file.name or evidence_file.link_url
        ]
        if names:
            records.append({
                'code': submission.requirement.code,
                'title': submission.requirement.title,
                'version': version.version_number,
                'date': version.created_at.date(),
                'names': ', '.join(names[:2]),
                'department': submission.department.name,
            })
    if not records:
        return {
            'intent': 'documents',
            'source': SOURCE_LABEL,
            'reply': (
                'No uploaded evidence documents are recorded in your accessible '
                'scope yet. Evidence is uploaded inside the sub-area workspaces '
                'under My Tasks.'
            ),
            'suggestions': ['What evidence is still missing?'],
        }
    lines = '\n'.join(
        f'• {item["code"]} — {item["title"]} · v{item["version"]} '
        f'({item["date"].strftime("%b %d, %Y")}) · {item["department"]}\n'
        f"    {item['names']}"
        for item in records
    )
    return {
        'intent': 'documents',
        'source': SOURCE_LABEL,
        'reply': (
            'The latest uploaded evidence documents on record for your scope are:\n'
            f'{lines}\n'
            'I report document metadata from the AMS. I do not read file contents, '
            'so I cannot summarize the text inside a document.'
        ),
        'suggestions': [
            'Which versions were returned for revision?',
            'Show my review status',
        ],
    }


def _reply_status(user):
    submissions = _submissions(user)
    draft = submissions.filter(status=EvidenceSubmission.DRAFT).count()
    pending = submissions.filter(status__in=ACTIVE_REVIEW_STATUSES).count()
    revision = submissions.filter(status=EvidenceSubmission.NEEDS_REVISION).count()
    completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
    total = submissions.count()

    lines = []
    if pending:
        lines.append(f'• {pending} item(s) are currently waiting on an assigned reviewer.')
    if revision:
        lines.append(f'• {revision} item(s) were returned for revision and need updates.')
    if draft:
        lines.append(f'• {draft} item(s) are still in draft.')
    if completed:
        lines.append(f'• {completed} item(s) have a recorded complied/closed review.')
    summary = '\n'.join(lines) if lines else '• No submissions are recorded in your scope.'

    return {
        'intent': 'status',
        'source': SOURCE_LABEL,
        'reply': (
            f'Your review picture across {total} recorded submission(s):\n{summary}\n'
            'Review stages are Dean → Area Chair → QA, then a final record of '
            'complied. Statuses shown are as recorded in the AMS.'
        ),
        'suggestions': [
            'Which items are waiting on a reviewer?',
            'What evidence is still missing?',
        ],
    }


def _reply_scope(user):
    assignment = active_assignment(user)
    role_name = assignment.role.name if assignment else 'Pending Approval'
    role_code = assignment.role.code if assignment else ''
    department_name = assignment.department.name if assignment else 'No active department'
    submissions = _submissions(user)
    return {
        'intent': 'scope',
        'source': SOURCE_LABEL,
        'reply': (
            f'AIRA sees you as {role_name}'
            + (f' for {department_name}.' if role_code else '.')
            + f' Your authorized scope currently includes {submissions.count()} evidence '
            'submission record(s). I can only retrieve information inside that scope.'
        ),
        'suggestions': ['What is my current review status?', 'What evidence is still missing?'],
    }


def _reply_compliance(user, question):
    submissions = _submissions(user)
    completed = submissions.filter(status__in=COMPLETED_STATUSES).count()
    total = submissions.count()

    lowered = question.lower()
    found_code = next(
        (
            code for code in (
                submissions.order_by('requirement__code')
                .values_list('requirement__code', flat=True)
                .distinct()
            )
            if code and code.lower() in lowered
        ),
        None,
    )
    if found_code:
        item = submissions.filter(requirement__code=found_code).first()
        label = _status_label(item.status)
        decided = item.status in COMPLETED_STATUSES
        return {
            'intent': 'compliance',
            'source': SOURCE_LABEL,
            'reply': (
                f'{found_code} — {item.requirement.title} is recorded '
                f'with review status "{label}". '
                + ('That is a recorded complied/closed outcome.'
                   if decided else
                   'It is still in progress, so no complied outcome is recorded yet. '
                   'The authorized reviewer makes the final decision.')
            ),
            'suggestions': ['Which items are waiting on a reviewer?'],
        }
    return {
        'intent': 'compliance',
        'source': SOURCE_LABEL,
        'reply': (
            'Compliance decisions belong to the authorized reviewer, not to me. '
            f'Based on the AMS records in your scope, {completed} of {total} '
            'recorded submission(s) show a complied or closed review status. '
            'I can report what is recorded, but I cannot confirm official '
            'compliance or accreditation myself.'
        ),
        'suggestions': ['Show the items currently in review', 'What is my review status?'],
    }


def _reply_guidance(user):
    assignment = active_assignment(user)
    role_code = assignment.role.code if assignment else ''
    if role_code == 'PROGRAM_HEAD':
        prompt = 'I can help you find missing evidence, understand review comments, and track deadlines for your assigned area.'
    elif role_code in {'DEAN', 'AREA_CHAIR', 'QA', 'ACCREDITATION_HEAD'}:
        prompt = 'I can help you track items waiting on a reviewer, understand revision requests, and spot gaps across your review scope.'
    else:
        prompt = 'I can help you understand accreditation requirements, deadlines, and review status across your access scope.'
    return {
        'intent': 'guidance',
        'source': SOURCE_LABEL,
        'reply': prompt,
        'suggestions': [
            'What evidence is still missing in my scope?',
            'What is my current review status?',
            'Which deadlines are coming up?',
        ],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ask(user, question):
    """Return a reply dict for ``user``. Raises nothing for ordinary input."""
    question = (question or '').strip()
    if not question:
        return {
            'intent': 'guidance',
            'source': SOURCE_LABEL,
            'reply': 'Ask me about missing evidence, deadlines, review status, or requirements.',
            'suggestions': [
                'What evidence is still missing in my scope?',
                'What is my current review status?',
                'Which deadlines are coming up?',
            ],
        }
    if _looks_like_secret_request(question):
        return _refuse_secrets()
    probe = _probe_out_of_scope(user, question)
    if probe:
        return probe
    intents = _detect_intents(question)
    if 'capabilities' in intents:
        return _reply_capabilities()
    if 'compliance' in intents:
        return _reply_compliance(user, question)
    if 'gaps' in intents:
        return _reply_gaps(user)
    if 'deadlines' in intents:
        return _reply_deadlines(user)
    if 'documents' in intents:
        return _reply_documents(user)
    if 'requirements' in intents:
        return _reply_requirements(user, question)
    if 'status' in intents:
        return _reply_status(user)
    if 'scope' in intents:
        return _reply_scope(user)
    return _reply_guidance(user)