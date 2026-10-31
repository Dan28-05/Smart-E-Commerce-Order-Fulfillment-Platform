# mangementlogistics/authentication/api/urls.py
from django.urls import path

from mangementlogistics.authentication.api.views import (
    LoginApi,
    LogoutApi,
    TokenRefreshApi,
    TokenVerifyApi,
)

app_name = "auth_api"

urlpatterns = [
    path("login/", LoginApi.as_view(), name="login"),
    path("token/refresh/", TokenRefreshApi.as_view(), name="token-refresh"),
    path("token/verify/", TokenVerifyApi.as_view(), name="token-verify"),
    path("logout/", LogoutApi.as_view(), name="logout"),
]
