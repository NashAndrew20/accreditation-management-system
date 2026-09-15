from django.conf import settings
from django.utils import timezone

from .models import Policy, PolicyConsent


def consent_enabled():
    """Master switch for policy-consent enforcement (test-friendly)."""
    return getattr(settings, 'POLICY_CONSENT_ENABLED', True)


def _accepted_records(user):
    """Return {policy_id: consent} for consents the user currently accepts."""
    if not user or not user.is_authenticated:
        return {}
    return {
        pc.policy_id: pc
        for pc in PolicyConsent.objects.filter(
            user=user,
            status=PolicyConsent.ACCEPTED,
        )
    }


def acknowledged_versions(user):
    """Return {policy_id: version} for consent a user currently accepts."""
    return {pid: pc.version for pid, pc in _accepted_records(user).items()}


def missing_policy_consents(user):
    """Active required policies the user has not acknowledged at the current version."""
    accepted = _accepted_records(user)
    return [
        policy
        for policy in Policy.active_required()
        if not accepted.get(policy.id) or accepted[policy.id].version != policy.version
    ]


def has_current_consent(user):
    return not missing_policy_consents(user)


def acknowledge(user, policy, version):
    """Record an explicit, versioned consent for one policy.

    Re-acknowledging the same policy (for example after a version bump, or
    after a withdrawal) updates the single current record in place, so there
    is never more than one active consent per user/policy. Prior versions are
    preserved in the audit trail.
    """
    from .models import AuditLog

    consent, created = PolicyConsent.objects.update_or_create(
        user=user,
        policy=policy,
        defaults={
            'version': version,
            'status': PolicyConsent.ACCEPTED,
            'accepted_at': timezone.now(),
            'withdrawn_at': None,
            'updated_at': timezone.now(),
        },
    )
    AuditLog.objects.create(
        actor=user,
        action='POLICY_ACCEPTED' if created else 'POLICY_REACCEPTED',
        object_type='Policy',
        object_id=str(policy.pk),
        details={
            'policy_type': policy.policy_type,
            'policy_title': policy.title,
            'version': version,
        },
    )
    return consent


def withdraw(user, policy):
    """Revoke an accepted consent for a policy.

    Once withdrawn the user no longer has current consent for the policy:
    required policies re-trigger the consent gate until the new version is
    acknowledged again. Returns the updated consent, or None if there was no
    active consent to revoke.
    """
    from .models import AuditLog

    consent = PolicyConsent.objects.filter(
        user=user,
        policy=policy,
        status=PolicyConsent.ACCEPTED,
    ).first()
    if not consent:
        return None
    consent.status = PolicyConsent.REVOKED
    consent.withdrawn_at = timezone.now()
    consent.updated_at = timezone.now()
    consent.save(update_fields=['status', 'withdrawn_at', 'updated_at'])
    AuditLog.objects.create(
        actor=user,
        action='POLICY_WITHDRAWN',
        object_type='Policy',
        object_id=str(policy.pk),
        details={
            'policy_type': policy.policy_type,
            'policy_title': policy.title,
            'version': consent.version,
        },
    )
    return consent


def consent_summary(user):
    """Per-policy status rows for the login/consent/settings UI.

    Each row exposes the policy, whether the current active version is
    acknowledged, the version/date acknowledged, and a human label. No other
    user's records are ever included (the query is scoped to ``user``).
    """
    policies = list(Policy.active_required())
    accepted = _accepted_records(user)
    rows = []
    for policy in policies:
        record = accepted.get(policy.id)
        current = bool(record and record.version == policy.version)
        if current:
            label = 'Acknowledged'
            status_class = 'current'
        elif record:
            label = 'Needs review'
            status_class = 'outdated'
        else:
            label = 'Not acknowledged'
            status_class = 'missing'
        rows.append({
            'policy': policy,
            'acknowledged': current,
            'outdated': bool(record and not current),
            'status_class': status_class,
            'version_acknowledged': record.version if record else '',
            'acknowledged_at': record.accepted_at if record else None,
            'status_label': label,
        })
    return rows


def last_acknowledged_at(user):
    """Most recent accepted-at timestamp across the user's consents."""
    if not user or not user.is_authenticated:
        return None
    return (
        PolicyConsent.objects
        .filter(user=user, status=PolicyConsent.ACCEPTED)
        .values_list('accepted_at', flat=True)
        .order_by('-accepted_at')
        .first()
    )