# mangementlogistics/orders/urls.py
from django.urls import path

from mangementlogistics.orders.views import (
    order_add_checkpoint_view,
    order_cancel_view,
    order_create_view,
    order_delete_view,
    order_detail_view,
    order_export_csv_view,
    order_list_view,
    order_print_view,
    order_status_update_view,
    order_track_view,
    order_update_view,
)

app_name = "orders"

urlpatterns = [
    path("", order_list_view, name="order-list"),
    path("create/", order_create_view, name="order-create"),
    path("export/csv/", order_export_csv_view, name="order-export-csv"),
    path("track/", order_track_view, name="order-track"),
    path("<int:order_id>/", order_detail_view, name="order-detail"),
    path("<int:order_id>/edit/", order_update_view, name="order-update"),
    path("<int:order_id>/status/", order_status_update_view, name="order-status-update"),
    path("<int:order_id>/checkpoint/", order_add_checkpoint_view, name="order-checkpoint"),
    path("<int:order_id>/print/", order_print_view, name="order-print"),
    path("<int:order_id>/cancel/", order_cancel_view, name="order-cancel"),
    path("<int:order_id>/delete/", order_delete_view, name="order-delete"),
]
