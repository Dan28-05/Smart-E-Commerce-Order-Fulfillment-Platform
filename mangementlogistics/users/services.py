from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.exceptions import DuplicateEmailError, InvalidPasswordError
from mangementlogistics.users.models import User


def user_create(
    *,
    name: str = "",
    email: str,
    password: str,
    role: str = UserRole.CUSTOMER,
    phone_number: str | None = None,
    address: str | None = None,
) -> User:
    """
    Creates a new user with hashed password.
    Raises DuplicateEmailError if the email already exists.
    """
    if User.objects.filter(email__iexact=email).exists():
        raise DuplicateEmailError(f"Email '{email}' đã được sử dụng.")

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        name=name,
        role=role,
        phone_number=phone_number,
        address=address,
    )
    return user


def user_update(*, user: User, **data) -> User:
    """
    Updates user personal details.
    Password changes are excluded and must use user_change_password instead.
    """
    # Không cho đổi mật khẩu qua hàm update thông thường
    data.pop("password", None)

    # Nếu có cập nhật email, kiểm tra xem email mới có bị trùng với người khác không
    new_email = data.get("email")
    if new_email and new_email.lower() != user.email.lower():
        if User.objects.filter(email__iexact=new_email).exclude(id=user.id).exists():
            raise DuplicateEmailError(f"Email '{new_email}' đã được sử dụng.")
        user.username = new_email

    for field, value in data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    user.save()
    return user


def user_change_password(*, user: User, old_password: str, new_password: str) -> User:
    """
    Changes user password after verifying the old password.
    Raises InvalidPasswordError if verification fails.
    """
    if not user.check_password(old_password):
        raise InvalidPasswordError("Mật khẩu cũ không chính xác!")

    if old_password == new_password:
        raise InvalidPasswordError("Mật khẩu mới không được trùng với mật khẩu cũ!")

    user.set_password(new_password)
    user.save()
    return user


def user_delete(*, user: User) -> None:
    """
    Soft-deletes a user by deactivating their account.
    """
    user.is_active = False
    user.save(update_fields=["is_active"])