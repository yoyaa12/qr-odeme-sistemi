from fastapi import HTTPException, status

from app.enums import OrderAction, OrderStatus, UserRole


_ROLE_STATUS_TARGETS: dict[UserRole, frozenset[OrderStatus | OrderAction]] = {
    UserRole.ADMIN: frozenset((*OrderStatus, *OrderAction)),
    UserRole.WAITER: frozenset(
        {
            OrderStatus.WAITER_APPROVED_IN_KITCHEN,
            OrderAction.CASH_COLLECTED,
            OrderStatus.DELIVERED,
        }
    ),
    UserRole.KITCHEN: frozenset(
        {
            OrderStatus.PREPARING,
            OrderStatus.READY,
        }
    ),
    UserRole.CASHIER: frozenset({OrderAction.CASH_COLLECTED}),
}


def enforce_order_status_role(
    role: UserRole,
    requested_status: OrderStatus | OrderAction,
) -> None:
    """Enforce the staff-role boundary before an order mutation reaches the DB."""
    allowed_targets = _ROLE_STATUS_TARGETS.get(role, frozenset())
    if requested_status not in allowed_targets:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Personel rolünüz bu sipariş durum işlemi için yetkili değil.",
        )


_ALLOWED_STATE_TRANSITIONS: dict[str, set[str]] = {
    # Legacy initial state. No code path produces it today, but historical rows
    # can still carry it, so it must be mapped: an unmapped status would be
    # rejected outright by the fail-closed guard in
    # validate_order_state_transition.
    OrderStatus.PAYMENT_PENDING.value: {
        OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
        OrderStatus.PAID_IN_KITCHEN.value,
        OrderStatus.CANCELLED.value,
        OrderAction.CASH_COLLECTED.value,
    },
    OrderStatus.CASH_PENDING.value: {
        OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
        OrderStatus.DELIVERED.value,
        OrderStatus.CANCELLED.value,
        OrderAction.CASH_COLLECTED.value,
    },
    OrderStatus.WAITER_APPROVAL_PENDING.value: {
        OrderStatus.WAITER_APPROVED_IN_KITCHEN.value,
        OrderStatus.CANCELLED.value,
        OrderAction.CASH_COLLECTED.value,
    },
    OrderStatus.PAID_IN_KITCHEN.value: {
        OrderStatus.PREPARING.value,
        OrderStatus.READY.value,
        OrderStatus.CANCELLED.value,
    },
    OrderStatus.WAITER_APPROVED_IN_KITCHEN.value: {
        OrderStatus.PREPARING.value,
        OrderStatus.READY.value,
        OrderStatus.CANCELLED.value,
    },
    OrderStatus.PREPARING.value: {
        OrderStatus.READY.value,
        OrderStatus.CANCELLED.value,
    },
    OrderStatus.READY.value: {
        OrderStatus.DELIVERED.value,
        OrderStatus.CANCELLED.value,
    },
    OrderStatus.DELIVERED.value: {
        OrderStatus.PAID_CLOSED.value,
        OrderAction.CASH_COLLECTED.value,
    },
    OrderStatus.CANCELLED.value: set(),
    OrderStatus.PAID_CLOSED.value: set(),
}


def validate_order_state_transition(
    current_status: str,
    requested_status: OrderStatus | OrderAction,
) -> None:
    """Validate that moving from current_status to requested_status is a legal transition."""
    curr = current_status.strip().lower()
    req = requested_status.value if isinstance(requested_status, (OrderStatus, OrderAction)) else str(requested_status).strip().lower()

    if curr in (OrderStatus.CANCELLED.value, OrderStatus.PAID_CLOSED.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bu sipariş sonlandırılmış durumdadır (iptal/kapatıldı), durumu değiştirilemez.",
        )

    # Fail-closed: an unrecognised current status must not silently permit every
    # transition. Previously a status missing from the map skipped the check
    # entirely, so a single unmapped value disabled the whole state machine.
    allowed = _ALLOWED_STATE_TRANSITIONS.get(curr)
    if allowed is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Sipariş bilinmeyen bir durumda ('{curr}'), durum değişikliği yapılamaz.",
        )
    if req not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{curr}' durumundaki sipariş '{req}' durumuna geçirilemez.",
        )

