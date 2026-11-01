# mangementlogistics/authentication/api/urls.py
from django.urls import path

from mangementlogistics.authentication.api.views import (
    ChangePasswordApi,
    LoginApi,
    LogoutApi,
    PasswordResetConfirmApi,
    PasswordResetRequestApi,
    PasswordResetValidateTokenApi,
    TokenRefreshApi,
    TokenVerifyApi,
)

app_name = "auth_api"

urlpatterns = [
    path("login/", LoginApi.as_view(), name="login"),
    path("token/refresh/", TokenRefreshApi.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyApi.as_view(), name="token-verify"),
    path("logout/", LogoutApi.as_view(), name="logout"),
    path("change-password/", ChangePasswordApi.as_view(), name="change-password"),
    path("password-reset/", PasswordResetRequestApi.as_view(), name="password-reset-request"),
    path(
        "password-reset/validate-token/",
        PasswordResetValidateTokenApi.as_view(),
        name="password-reset-validate-token",
    ),
    path("password-reset/confirm/", PasswordResetConfirmApi.as_view(), name="password-reset-confirm"),
]
