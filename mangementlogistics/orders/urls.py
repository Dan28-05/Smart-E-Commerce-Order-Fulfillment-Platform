# mangementlogistics/orders/urls.py
from django.urls import path

from mangementlogistics.orders.views import (
    cod_reconciliation_detail_view,
    cod_reconciliation_export_csv_view,
    cod_reconciliation_generate_view,
    cod_reconciliation_list_view,
    cod_reconciliation_process_view,
    order_add_checkpoint_view,
    order_cancel_view,
    order_create_view,
    order_delete_view,
    order_detail_view,
    order_export_csv_view,
    order_fee_estimator_view,
    order_list_view,
    order_print_view,
    order_return_action_view,
    order_return_create_view,
    order_return_detail_view,
    order_return_list_view,
    order_return_print_view,
    order_status_update_view,
    order_track_view,
    order_update_view,
)

app_name = "orders"

urlpatterns = [
    path("", order_list_view, name="order-list"),
    path("create/", order_create_view, name="order-create"),
    path("calculator/", order_fee_estimator_view, name="fee-estimator"),
    path("export/csv/", order_export_csv_view, name="order-export-csv"),
    path("track/", order_track_view, name="order-track"),
    path("reconciliations/", cod_reconciliation_list_view, name="reconciliation-list"),
    path("reconciliations/create/", cod_reconciliation_generate_view, name="reconciliation-create"),
    path("reconciliations/<int:reconciliation_id>/", cod_reconciliation_detail_view, name="reconciliation-detail"),
    path("reconciliations/<int:reconciliation_id>/export/csv/", cod_reconciliation_export_csv_view, name="reconciliation-export-csv"),
    path("reconciliations/<int:reconciliation_id>/process/", cod_reconciliation_process_view, name="reconciliation-process"),
    path("returns/", order_return_list_view, name="return-list"),
    path("returns/<int:return_id>/", order_return_detail_view, name="return-detail"),
    path("returns/<int:return_id>/action/", order_return_action_view, name="return-action"),
    path("returns/<int:return_id>/print/", order_return_print_view, name="return-print"),
    path("<int:order_id>/", order_detail_view, name="order-detail"),
    path("<int:order_id>/return/", order_return_create_view, name="order-return-create"),
    path("<int:order_id>/edit/", order_update_view, name="order-update"),
    path("<int:order_id>/status/", order_status_update_view, name="order-status-update"),
    path("<int:order_id>/checkpoint/", order_add_checkpoint_view, name="order-checkpoint"),
    path("<int:order_id>/print/", order_print_view, name="order-print"),
    path("<int:order_id>/cancel/", order_cancel_view, name="order-cancel"),
    path("<int:order_id>/delete/", order_delete_view, name="order-delete"),
]
