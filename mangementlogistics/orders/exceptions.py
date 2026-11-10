# mangementlogistics/orders/exceptions.py


class OrderNotFoundError(Exception):
    """Raised when the specified order does not exist."""
    pass


class InvalidOrderStatusError(Exception):
    """Raised when an invalid status transition is requested."""
    pass


class OrderPermissionDeniedError(Exception):
    """Raised when user is not authorized to perform the action on the order."""
    pass


class DriverAssignmentError(Exception):
    """Raised when an invalid driver is assigned."""
    pass


class CODReconciliationError(Exception):
    """Raised when COD reconciliation processing fails or validation is violated."""
    pass


class OrderReturnError(Exception):
    """Raised when an order return operation fails or violates validation rules."""
    pass


class DeliveryTripError(Exception):
    """Raised when a delivery trip operation fails or violates validation rules."""
    pass



