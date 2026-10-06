# mangementlogistics/users/api/urls.py
from django.urls import path

from mangementlogistics.users.api.views import UserDetailApi, UserListCreateApi

app_name = "users_api"

urlpatterns = [
    path("", UserListCreateApi.as_view(), name="user-list-create"),
    path("<int:user_id>/", UserDetailApi.as_view(), name="user-detail"),
]
