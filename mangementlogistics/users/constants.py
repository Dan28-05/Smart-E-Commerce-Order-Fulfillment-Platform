from typing import cast

from django.db import models


class UserRole(models.TextChoices):
    ADMIN = cast(str, ("Admin", "Quan tri vien"))
    DRIVER = cast(str, ("Driver", "Tai xe"))
    CUSTOMER = cast(str, ("Customer", "Khach hang"))
    