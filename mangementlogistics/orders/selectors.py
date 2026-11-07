# mangementlogistics/orders/selectors.py
from decimal import Decimal

from django.db.models import Q, QuerySet, Sum

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderStatus,
)
from mangementlogistics.orders.models import (
    CODReconciliation,
    Order,
    OrderTrackingHistory,
)
from mangementlogistics.users.constants import UserRole
from mangementlogistics.users.models import User


def order_list(
    *,
    user: User | None = None,
    status: str | None = None,
    search: str | None = None,
) -> QuerySet[Order]:
    """
    Returns filtered queryset of orders based on user role and query parameters.
    - Customer only sees orders they created.
    - Driver only sees orders assigned to them.
    - Admin / Superuser sees all orders.
    """
    qs = Order.objects.select_related("customer", "driver").all()

    if user and not user.is_superuser:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.CUSTOMER:
            qs = qs.filter(customer=user)
        elif user_role == UserRole.DRIVER:
            qs = qs.filter(driver=user)

    if status:
        qs = qs.filter(status=status)

    if search:
        search_query = search.strip()
        qs = qs.filter(
            Q(tracking_number__icontains=search_query)
            | Q(sender_name__icontains=search_query)
            | Q(sender_phone__icontains=search_query)
            | Q(receiver_name__icontains=search_query)
            | Q(receiver_phone__icontains=search_query)
            | Q(customer__email__icontains=search_query)
        )

    return qs.order_by("-created_at")


def order_get_by_id(*, order_id: int, user: User | None = None) -> Order | None:
    """
    Retrieves an order by its ID with permission verification.
    """
    try:
        order = Order.objects.select_related("customer", "driver").get(id=order_id)
    except Order.DoesNotExist:
        return None

    if user and not user.is_superuser:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.CUSTOMER and order.customer_id != user.id:
            return None
        if user_role == UserRole.DRIVER and order.driver_id != user.id:
            return None

    return order


def order_get_by_tracking_number(*, tracking_number: str) -> Order | None:
    """
    Public lookup for tracking parcel by tracking code.
    """
    return Order.objects.select_related("customer", "driver").filter(
        tracking_number__iexact=tracking_number.strip()
    ).first()


def order_get_tracking_history(*, order: Order) -> QuerySet[OrderTrackingHistory]:
    """
    Returns chronological tracking milestones for the given order.
    """
    return order.tracking_history.select_related("actor").order_by("created_at")


def cod_reconciliation_list(
    *,
    user: User,
    status: str | None = None,
    customer_id: int | None = None,
) -> QuerySet[CODReconciliation]:
    """
    Returns filtered queryset of COD reconciliations based on user role and query parameters.
    """
    qs = CODReconciliation.objects.select_related("customer", "processed_by").all()

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        qs = qs.filter(customer=user)
    elif customer_id:
        qs = qs.filter(customer_id=customer_id)

    if status:
        qs = qs.filter(status=status)

    return qs.order_by("-created_at")


def cod_reconciliation_get_by_id(
    *,
    reconciliation_id: int,
    user: User,
) -> CODReconciliation | None:
    """
    Retrieves a COD reconciliation statement by its ID with permission verification.
    """
    try:
        rec = (
            CODReconciliation.objects.select_related("customer", "processed_by")
            .prefetch_related("orders")
            .get(id=reconciliation_id)
        )
    except CODReconciliation.DoesNotExist:
        return None

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        if rec.customer_id != user.id:
            return None

    return rec


def cod_reconciliation_get_eligible_orders(
    *,
    customer: User,
) -> QuerySet[Order]:
    """
    Retrieves delivered COD orders waiting to be reconciled into a statement.
    """
    return Order.objects.filter(
        customer=customer,
        status=OrderStatus.DELIVERED,
        payment_method=OrderPaymentMethod.COD,
        reconciliation__isnull=True,
    ).order_by("-delivered_at", "-created_at")


def cod_reconciliation_get_summary_stats(
    *,
    user: User,
) -> dict:
    """
    Computes key financial summary indicators for COD settlements.
    """
    reconciliations = cod_reconciliation_list(user=user)

    total_statements = reconciliations.count()
    pending_payout = reconciliations.filter(
        status__in=[CODReconciliationStatus.PENDING, CODReconciliationStatus.CONFIRMED]
    ).aggregate(total=Sum("net_payout_amount"))["total"] or Decimal("0.00")

    paid_payout = reconciliations.filter(
        status=CODReconciliationStatus.PAID
    ).aggregate(total=Sum("net_payout_amount"))["total"] or Decimal("0.00")

    # Unreconciled delivered COD orders
    if user.is_superuser or getattr(user, "role", None) == UserRole.ADMIN:
        unreconciled_qs = Order.objects.filter(
            status=OrderStatus.DELIVERED,
            payment_method=OrderPaymentMethod.COD,
            reconciliation__isnull=True,
        )
    else:
        unreconciled_qs = Order.objects.filter(
            customer=user,
            status=OrderStatus.DELIVERED,
            payment_method=OrderPaymentMethod.COD,
            reconciliation__isnull=True,
        )

    unreconciled_orders_count = unreconciled_qs.count()
    unreconciled_cod_total = unreconciled_qs.aggregate(total=Sum("cod_amount"))["total"] or Decimal("0.00")

    return {
        "total_statements": total_statements,
        "pending_payout": pending_payout,
        "paid_payout": paid_payout,
        "unreconciled_orders_count": unreconciled_orders_count,
        "unreconciled_cod_total": unreconciled_cod_total,
    }


