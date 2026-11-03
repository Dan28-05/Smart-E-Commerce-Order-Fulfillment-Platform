# mangementlogistics/orders/api/urls.py
from django.urls import path

from mangementlogistics.orders.api.views import (
    OrderCancelApi,
    OrderCheckpointApi,
    OrderDetailApi,
    OrderListCreateApi,
    OrderStatusUpdateApi,
    OrderTrackPublicApi,
)

app_name = "orders_api"

urlpatterns = [
    path("", OrderListCreateApi.as_view(), name="order-list-create"),
    path("<int:order_id>/", OrderDetailApi.as_view(), name="order-detail"),
    path("<int:order_id>/status/", OrderStatusUpdateApi.as_view(), name="order-status-update"),
    path("<int:order_id>/checkpoint/", OrderCheckpointApi.as_view(), name="order-checkpoint"),
    path("<int:order_id>/cancel/", OrderCancelApi.as_view(), name="order-cancel"),
    path("track/<str:tracking_number>/", OrderTrackPublicApi.as_view(), name="order-track"),
]
