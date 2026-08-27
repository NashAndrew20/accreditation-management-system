from django.contrib.auth import get_user_model


def visible_user_accounts():
    """Return accounts that should be shown in User Management.

    Retired development accounts remain in the database for history, but they
    should not clutter the active account-management view. Pending or
    inactive non-demo accounts remain visible so administrators can manage
    them normally.
    """
    return get_user_model().objects.exclude(
        profile__is_demo_account=True,
        is_active=False,
    )
