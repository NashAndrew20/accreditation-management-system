"""Canonical development accounts used by the login shortcuts and demo seeder."""

from django.conf import settings


DEMO_PASSWORD = settings.DEMO_PASSWORD

DEMO_ACCOUNT_DEFINITIONS = (
    {
        'username': 'qa',
        'email': 'qa@jmcfi.edu.ph',
        'first_name': 'Demo',
        'last_name': 'QA',
        'role_code': 'QA',
        'department_code': 'QA',
        'label': 'QA',
        'description': 'Internal review · QA Office',
        'initials': 'QA',
    },
    {
        'username': 'dean',
        'email': 'dean@jmcfi.edu.ph',
        'first_name': 'Demo',
        'last_name': 'Dean',
        'role_code': 'DEAN',
        'department_code': 'CITE',
        'label': 'Dean',
        'description': 'Department approver · CITE',
        'initials': 'DE',
    },
    {
        'username': 'phead',
        'email': 'phead@jmcfi.edu.ph',
        'first_name': 'Demo',
        'last_name': 'Program Head',
        'role_code': 'PROGRAM_HEAD',
        'department_code': 'CITE',
        'label': 'Program Head',
        'description': 'Prepare and submit evidence · CITE',
        'initials': 'PH',
    },
)

DEMO_LOGIN_OPTIONS = (
    tuple(
        {
            'label': account['label'],
            'role': account['description'],
            'username': account['username'],
            'password': DEMO_PASSWORD,
            'initials': account['initials'],
        }
        for account in DEMO_ACCOUNT_DEFINITIONS
    )
    if DEMO_PASSWORD
    else ()
)
