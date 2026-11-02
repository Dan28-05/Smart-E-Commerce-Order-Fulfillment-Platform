# mangementlogistics/common/views.py
from django.db.models import Sum
from django.shortcuts import render

from mangementlogistics.orders.constants import OrderPaymentStatus, OrderStatus
from mangementlogistics.orders.models import Order
from mangementlogistics.orders.selectors import order_list
from mangementlogistics.users.constants import UserRole


def home_view(request):
    """
    Renders the main home page / dashboard:
    - If user is authenticated: Displays a personalized operational dashboard with real-time stats and recent orders.
    - If user is guest/visitor: Displays a modern, high-converting landing page with quick parcel tracking, platform features, and services.
    """
    context = {}

    if request.user.is_authenticated:
        # Retrieve orders visible to current user based on HackSoftware selector
        user_orders = order_list(user=request.user)

        total_orders = user_orders.count()
        pending_orders = user_orders.filter(status=OrderStatus.PENDING).count()
        delivering_orders = user_orders.filter(
            status__in=[OrderStatus.CONFIRMED, OrderStatus.PICKED_UP, OrderStatus.IN_TRANSIT]
        ).count()
        delivered_orders = user_orders.filter(status=OrderStatus.DELIVERED).count()
        cancelled_orders = user_orders.filter(status=OrderStatus.CANCELLED).count()

        # Total COD collected/held for delivered or paid orders
        total_cod = (
            user_orders.filter(payment_status=OrderPaymentStatus.PAID).aggregate(Sum("cod_amount"))[
                "cod_amount__sum"
            ]
            or 0
        )

        recent_orders = user_orders[:6]

        context.update(
            {
                "is_dashboard": True,
                "total_orders": total_orders,
                "pending_orders": pending_orders,
                "delivering_orders": delivering_orders,
                "delivered_orders": delivered_orders,
                "cancelled_orders": cancelled_orders,
                "total_cod": total_cod,
                "recent_orders": recent_orders,
                "UserRole": UserRole,
            }
        )
    else:
        # High-level statistics for guest landing page
        total_system_orders = Order.objects.count()
        delivered_count = Order.objects.filter(status=OrderStatus.DELIVERED).count()

        context.update(
            {
                "is_dashboard": False,
                "total_system_orders": total_system_orders,
                "delivered_count": delivered_count,
            }
        )

    return render(request, "pages/home.html", context)

