from django.db import migrations


def seed_policies(apps, schema_editor):
    Policy = apps.get_model('core', 'Policy')
    Policy.objects.update_or_create(
        policy_type='PRIVACY',
        version='1.0',
        defaults={
            'slug': 'privacy-policy',
            'title': 'Data Privacy Notice & Policy',
            'status': 'ACTIVE',
            'is_required': True,
            'effective_date': '2026-09-14',
        },
    )
    Policy.objects.update_or_create(
        policy_type='TERMS',
        version='1.0',
        defaults={
            'slug': 'terms-of-use',
            'title': 'Terms of Use',
            'status': 'ACTIVE',
            'is_required': True,
            'effective_date': '2026-09-14',
        },
    )


def remove_policies(apps, schema_editor):
    Policy = apps.get_model('core', 'Policy')
    Policy.objects.filter(policy_type__in=('PRIVACY', 'TERMS'), version='1.0').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_policy_policyconsent'),
    ]

    operations = [
        migrations.RunPython(seed_policies, remove_policies),
    ]