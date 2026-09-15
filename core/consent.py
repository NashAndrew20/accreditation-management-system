from django.conf import settings

from .models import Policy, PolicyConsent


def consent_enabled():
    """Master switch for policy-consent enforcement (test-friendly)."""
    return getattr(settings, 'POLICY_CONSENT_ENABLED', True)


def acknowledged_versions(user):
    """Return {policy: version} for consent a user already gave."""
    if not user or not user.is_authenticated:
        return {}
    return {
        pc.policy_id: pc.version
        for pc in PolicyConsent.objects.filter(user=user)
    }


def missing_policy_consents(user):
    """Active required policies the user has not acknowledged at the current version."""
    if not user or not user.is_authenticated:
        return list(Policy.active_required())
    ack = acknowledged_versions(user)
    return [p for p in Policy.active_required() if ack.get(p.id) != p.version]


def has_current_consent(user):
    return not missing_policy_consents(user)


def acknowledge(user, policy, version):
    """Record an explicit, versioned consent for one policy."""
    from .models import AuditLog

    consent, created = PolicyConsent.objects.update_or_create(
        user=user,
        policy=policy,
        defaults={'version': version},
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