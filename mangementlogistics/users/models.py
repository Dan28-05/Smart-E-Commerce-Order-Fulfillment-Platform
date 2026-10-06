from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from mangementlogistics.users.constants import UserRole


class User(AbstractUser):
    name = models.CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    email = models.EmailField(_("email address"), unique=True)

    role = models.CharField(
        max_length=255,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        verbose_name="Role",
    )

    phone_number = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Phone Number",
        unique=True,
    )

    address = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Address",
    )

    def __str__(self):
        return f"{self.email} ({self.role})"

