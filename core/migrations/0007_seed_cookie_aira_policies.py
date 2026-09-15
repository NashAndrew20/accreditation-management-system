from django.db import migrations


def seed_policies(apps, schema_editor):
    Policy = apps.get_model('core', 'Policy')
    Policy.objects.update_or_create(
        policy_type='COOKIE',
        version='1.0',
        defaults={
            'slug': 'cookie-policy',
            'title': 'Cookie Policy',
            'status': 'ACTIVE',
            'is_required': True,
            'effective_date': '2026-09-15',
        },
    )
    Policy.objects.update_or_create(
        policy_type='AIRA',
        version='1.0',
        defaults={
            'slug': 'aira-data-notice',
            'title': 'AIRA & AI Data-Use Notice',
            'status': 'ACTIVE',
            'is_required': False,
            'effective_date': '2026-09-15',
        },
    )


def remove_policies(apps, schema_editor):
    Policy = apps.get_model('core', 'Policy')
    Policy.objects.filter(policy_type__in=('COOKIE', 'AIRA'), version='1.0').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_consent_preferences'),
    ]

    operations = [
        migrations.RunPython(seed_policies, remove_policies),
    ]