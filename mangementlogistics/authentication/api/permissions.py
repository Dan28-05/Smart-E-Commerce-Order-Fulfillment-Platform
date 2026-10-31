# mangementlogistics/authentication/api/permissions.py
from rest_framework.permissions import BasePermission

from mangementlogistics.users.constants import UserRole


class IsAdminUserRole(BasePermission):
    """
    Allows access only to authenticated users who have ADMIN role or is superuser.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (getattr(request.user, "role", None) == UserRole.ADMIN or request.user.is_superuser)
        )


class IsDriverUserRole(BasePermission):
    """
    Allows access only to authenticated users who have DRIVER role.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRole.DRIVER
        )


class IsCustomerUserRole(BasePermission):
    """
    Allows access only to authenticated users who have CUSTOMER role.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == UserRole.CUSTOMER
        )
