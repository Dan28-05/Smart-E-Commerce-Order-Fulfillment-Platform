# mangementlogistics/orders/selectors.py
from decimal import Decimal

from django.db.models import Q, QuerySet, Sum

from mangementlogistics.orders.constants import (
    CODReconciliationStatus,
    OrderPaymentMethod,
    OrderStatus,
    ReturnStatus,
    TripStatus,
)
from mangementlogistics.orders.models import (
    CODReconciliation,
    DeliveryTrip,
    Order,
    OrderReturn,
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


def order_return_list(
    *,
    user: User,
    status: str | None = None,
    search: str | None = None,
) -> QuerySet[OrderReturn]:
    """
    Returns filtered queryset of order return requests based on user role and search parameters.
    """
    qs = OrderReturn.objects.select_related("order", "requested_by", "assigned_driver", "order__customer").all()

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.DRIVER:
            qs = qs.filter(assigned_driver=user)
        else:
            qs = qs.filter(Q(requested_by=user) | Q(order__customer=user))

    if status:
        qs = qs.filter(status=status)

    if search:
        query = search.strip()
        qs = qs.filter(
            Q(return_code__icontains=query)
            | Q(order__tracking_number__icontains=query)
            | Q(order__receiver_name__icontains=query)
            | Q(order__sender_name__icontains=query)
            | Q(requested_by__email__icontains=query)
            | Q(reason_detail__icontains=query)
        )

    return qs.order_by("-created_at")


def order_return_get_by_id(
    *,
    return_id: int,
    user: User,
) -> OrderReturn | None:
    """
    Retrieves an order return by ID with role-based permission verification.
    """
    try:
        ret = (
            OrderReturn.objects.select_related("order", "requested_by", "assigned_driver", "order__customer")
            .get(id=return_id)
        )
    except OrderReturn.DoesNotExist:
        return None

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.DRIVER and ret.assigned_driver_id != user.id:
            return None
        if user_role != UserRole.DRIVER and ret.requested_by_id != user.id and ret.order.customer_id != user.id:
            return None

    return ret


def order_return_get_by_code(
    *,
    return_code: str,
) -> OrderReturn | None:
    """
    Lookup order return by unique return code.
    """
    return (
        OrderReturn.objects.select_related("order", "requested_by", "assigned_driver", "order__customer")
        .filter(return_code__iexact=return_code.strip())
        .first()
    )


def order_return_get_summary_stats(
    *,
    user: User,
) -> dict:
    """
    Computes key reverse logistics KPIs and refund totals.
    """
    qs = order_return_list(user=user)

    total_returns = qs.count()
    pending_requested = qs.filter(status=ReturnStatus.REQUESTED).count()
    in_transit_returns = qs.filter(
        status__in=[ReturnStatus.APPROVED, ReturnStatus.PICKING_UP, ReturnStatus.IN_RETURN_TRANSIT]
    ).count()
    completed_returns = qs.filter(status=ReturnStatus.RETURNED_TO_SENDER).count()

    total_refund_amount = qs.filter(
        status__in=[ReturnStatus.APPROVED, ReturnStatus.PICKING_UP, ReturnStatus.IN_RETURN_TRANSIT, ReturnStatus.RETURNED_TO_SENDER]
    ).aggregate(total=Sum("refund_amount"))["total"] or Decimal("0.00")

    return {
        "total_returns": total_returns,
        "pending_requested": pending_requested,
        "in_transit_returns": in_transit_returns,
        "completed_returns": completed_returns,
        "total_refund_amount": total_refund_amount,
    }


# ==============================================================================
# Delivery Trip & Manifest Selectors
# ==============================================================================

def delivery_trip_list(
    *,
    user: User,
    status: str | None = None,
    search: str | None = None,
) -> QuerySet[DeliveryTrip]:
    """
    Returns filtered queryset of delivery trips based on user role and query parameters.
    - Admin sees all delivery trips.
    - Driver sees trips assigned to them.
    - Customer sees trips containing any of their orders.
    """
    qs = (
        DeliveryTrip.objects.select_related("driver", "created_by")
        .prefetch_related("trip_orders")
        .all()
    )

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.DRIVER:
            qs = qs.filter(driver=user)
        else:
            qs = qs.filter(trip_orders__customer=user).distinct()

    if status:
        qs = qs.filter(status=status)

    if search:
        query = search.strip()
        qs = qs.filter(
            Q(trip_code__icontains=query)
            | Q(route_name__icontains=query)
            | Q(driver__email__icontains=query)
            | Q(driver__name__icontains=query)
            | Q(license_plate__icontains=query)
            | Q(departure_hub__icontains=query)
        )

    return qs.order_by("-created_at")


def delivery_trip_get_by_id(
    *,
    trip_id: int,
    user: User,
) -> DeliveryTrip | None:
    """
    Retrieves a delivery trip by ID with role-based access verification.
    """
    try:
        trip = (
            DeliveryTrip.objects.select_related("driver", "created_by")
            .prefetch_related("trip_orders")
            .get(id=trip_id)
        )
    except DeliveryTrip.DoesNotExist:
        return None

    if not user.is_superuser and getattr(user, "role", None) != UserRole.ADMIN:
        user_role = getattr(user, "role", None)
        if user_role == UserRole.DRIVER and trip.driver_id != user.id:
            return None
        if user_role != UserRole.DRIVER and not trip.trip_orders.filter(customer=user).exists():
            return None

    return trip


def delivery_trip_get_by_code(
    *,
    trip_code: str,
) -> DeliveryTrip | None:
    """
    Look up a delivery trip by unique trip code.
    """
    return (
        DeliveryTrip.objects.select_related("driver", "created_by")
        .prefetch_related("trip_orders")
        .filter(trip_code__iexact=trip_code.strip())
        .first()
    )


def delivery_trip_get_eligible_orders(
    *,
    trip: DeliveryTrip,
    search: str | None = None,
) -> QuerySet[Order]:
    """
    Returns unassigned or compatible orders available to be added to this trip.
    """
    qs = Order.objects.filter(
        Q(delivery_trip__isnull=True) | Q(delivery_trip=trip),
        status__in=[OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PICKED_UP],
    ).filter(Q(driver__isnull=True) | Q(driver=trip.driver))

    if search:
        query = search.strip()
        qs = qs.filter(
            Q(tracking_number__icontains=query)
            | Q(receiver_name__icontains=query)
            | Q(receiver_phone__icontains=query)
            | Q(receiver_address__icontains=query)
            | Q(sender_name__icontains=query)
        )

    return qs.order_by("-created_at")


def delivery_trip_get_summary_stats(
    *,
    user: User,
) -> dict:
    """
    Computes key performance indicators and metrics for delivery trips.
    """
    qs = delivery_trip_list(user=user)

    total_trips = qs.count()
    active_trips = qs.filter(status__in=[TripStatus.LOADING, TripStatus.IN_TRANSIT]).count()
    completed_trips = qs.filter(status=TripStatus.COMPLETED).count()
    planned_trips = qs.filter(status=TripStatus.PLANNED).count()

    trip_orders = Order.objects.filter(delivery_trip__in=qs)
    total_orders_dispatched = trip_orders.count()
    total_cod_in_trips = trip_orders.aggregate(total=Sum("cod_amount"))["total"] or Decimal("0.00")

    return {
        "total_trips": total_trips,
        "active_trips": active_trips,
        "completed_trips": completed_trips,
        "planned_trips": planned_trips,
        "total_orders_dispatched": total_orders_dispatched,
        "total_cod_in_trips": total_cod_in_trips,
    }




