from django.urls import path

from mangementlogistics.users.views import user_create_view, user_list_view

app_name = "users"

urlpatterns = [
    path("", user_list_view, name="user-list"),
    path("create/", user_create_view, name="user-create"),
]
