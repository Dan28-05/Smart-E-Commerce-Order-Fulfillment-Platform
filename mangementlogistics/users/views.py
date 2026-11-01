# mangementlogistics/users/views.py
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from mangementlogistics.authentication.exceptions import InvalidTokenError
from mangementlogistics.authentication.services import (
    auth_password_reset_confirm,
    auth_password_reset_request,
    auth_password_reset_validate_token,
)
from mangementlogistics.users.exceptions import InvalidPasswordError
from mangementlogistics.users.forms import (
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    UserCreateForm,
    UserPasswordChangeForm,
)
from mangementlogistics.users.selectors import user_list


def user_list_view(request):
    """
    Renders the HTML page displaying all users in the system.
    """
    role = request.GET.get("role") or None
    users = user_list(role=role)
    return render(
        request,
        "users/user_list.html",
        {
            "users": users,
            "selected_role": role,
        },
    )


def user_create_view(request):
    """
    Renders and processes the HTML form for creating a new user.
    """
    if request.method == "POST":
        form = UserCreateForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                messages.success(request, f"Tạo tài khoản '{user.email}' thành công!")
                return redirect("users:user-list")
            except Exception as exc:
                messages.error(request, f"Lỗi tạo tài khoản: {exc}")
    else:
        form = UserCreateForm()

    return render(
        request,
        "users/user_form.html",
        {"form": form},
    )


def password_change_view(request):
    """
    View for logged-in users to change their password with complexity validation.
    """
    if not request.user.is_authenticated:
        messages.error(request, "Vui lòng đăng nhập để đổi mật khẩu.")
        return redirect("home")

    if request.method == "POST":
        form = UserPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # Giữ nguyên trạng thái đăng nhập của user sau khi đổi password
                update_session_auth_hash(request, user)
                messages.success(request, "Đổi mật khẩu thành công!")
                return redirect("users:user-list")
            except InvalidPasswordError as exc:
                messages.error(request, str(exc))
    else:
        form = UserPasswordChangeForm(user=request.user)

    return render(
        request,
        "users/password_change.html",
        {"form": form},
    )


def password_reset_request_view(request):
    """
    View to request password reset link via email.
    """
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            base_url = request.build_absolute_uri("/")
            _, message = auth_password_reset_request(email=email, base_url=base_url)
            messages.success(request, message)
            return render(
                request,
                "users/password_reset_done.html",
                {"email": email},
            )
    else:
        form = PasswordResetRequestForm()

    return render(
        request,
        "users/password_reset_request.html",
        {"form": form},
    )


def password_reset_confirm_view(request, uidb64: str, token: str):
    """
    View to set a new password using email reset link.
    """
    # Kiểm tra tính hợp lệ của token trước khi hiển thị form
    try:
        user = auth_password_reset_validate_token(uidb64=uidb64, token=token)
    except InvalidTokenError as exc:
        return render(
            request,
            "users/password_reset_invalid.html",
            {"error": str(exc)},
        )

    if request.method == "POST":
        form = PasswordResetConfirmForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            new_password_confirm = form.cleaned_data["new_password_confirm"]
            try:
                auth_password_reset_confirm(
                    uidb64=uidb64,
                    token=token,
                    new_password=new_password,
                    new_password_confirm=new_password_confirm,
                )
                messages.success(request, "Đặt lại mật khẩu thành công! Bạn có thể sử dụng mật khẩu mới ngay bây giờ.")
                return render(request, "users/password_reset_complete.html")
            except (InvalidTokenError, InvalidPasswordError) as exc:
                messages.error(request, str(exc))
    else:
        form = PasswordResetConfirmForm()

    return render(
        request,
        "users/password_reset_confirm.html",
        {"form": form, "user": user},
    )
