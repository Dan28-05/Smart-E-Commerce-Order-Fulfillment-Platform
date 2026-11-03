# mangementlogistics/orders/selectors.py
from django.db.models import Q, QuerySet

from mangementlogistics.orders.models import Order, OrderTrackingHistory
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

