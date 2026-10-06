# mangementlogistics/users/selectors.py
from django.db.models import QuerySet

from mangementlogistics.users.models import User


def user_list(*, role: str | None = None, is_active: bool | None = None) -> QuerySet[User]:
    """
    Get a queryset of users, optionally filtered by role and active status.
    Ordered by most recent joined date.
    """
    qs = User.objects.all().order_by("-date_joined")
    if role is not None:
        qs = qs.filter(role=role)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    return qs


def user_get_by_id(*, user_id: int) -> User | None:
    """
    Fetch a single user by primary key ID.
    Returns None if not found.
    """
    return User.objects.filter(id=user_id).first()


def user_get_by_email(*, email: str) -> User | None:
    """
    Fetch a single user by email address (case-insensitive).
    Returns None if not found.
    """
    return User.objects.filter(email__iexact=email).first()
