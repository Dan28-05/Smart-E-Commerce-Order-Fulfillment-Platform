# mangementlogistics/users/urls.py
from django.urls import path

from mangementlogistics.users.views import (
    password_change_view,
    password_reset_confirm_view,
    password_reset_request_view,
    user_create_view,
    user_list_view,
    user_login_view,
    user_logout_view,
    user_profile_view,
)

app_name = "users"

urlpatterns = [
    path("", user_list_view, name="user-list"),
    path("profile/", user_profile_view, name="profile"),
    path("login/", user_login_view, name="login"),
    path("logout/", user_logout_view, name="logout"),
    path("create/", user_create_view, name="user-create"),
    path("password/change/", password_change_view, name="password-change"),
    path("password/reset/", password_reset_request_view, name="password-reset-request"),
    path(
        "password/reset/confirm/<str:uidb64>/<str:token>/",
        password_reset_confirm_view,
        name="password-reset-confirm",
    ),
]
