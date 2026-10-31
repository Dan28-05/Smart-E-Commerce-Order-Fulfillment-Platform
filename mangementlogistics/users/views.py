from django.contrib import messages
from django.shortcuts import redirect, render

from mangementlogistics.users.forms import UserCreateForm
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
            except Exception:
                pass
    else:
        form = UserCreateForm()

    return render(
        request,
        "users/user_form.html",
        {"form": form},
    )

