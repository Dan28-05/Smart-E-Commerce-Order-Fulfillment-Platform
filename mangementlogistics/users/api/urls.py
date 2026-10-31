# mangementlogistics/users/api/urls.py
from django.urls import path

from mangementlogistics.users.api.views import (
    UserChangePasswordApi,
    UserDetailApi,
    UserListCreateApi,
    UserMeApi,
)

app_name = "users_api"

urlpatterns = [
    path("", UserListCreateApi.as_view(), name="user-list-create"),
    path("me/", UserMeApi.as_view(), name="user-me"),
    path("<int:user_id>/", UserDetailApi.as_view(), name="user-detail"),
    path("<int:user_id>/change-password/", UserChangePasswordApi.as_view(), name="user-change-password"),
]
