from enum import Enum


class UserRole(str, Enum):
    """Values verified against the live Kullanicilar.rol column."""

    ADMIN = "admin"
    WAITER = "garson"
    CASHIER = "kasa"
    KITCHEN = "mutfak"


class TableStatus(str, Enum):
    EMPTY = "bos"
    OCCUPIED = "dolu"
    BILL_REQUESTED = "hesap_istendi"


class PaymentMethod(str, Enum):
    POS = "pos"
    CASH = "nakit"
    WAITER_AT_CASHIER = "garson_kasada"


class PaymentStatus(str, Enum):
    PENDING = "bekliyor"
    PAID = "odendi"


class OrderStatus(str, Enum):
    PAYMENT_PENDING = "odeme_bekliyor"
    PAID_IN_KITCHEN = "odendi_mutfakta"
    WAITER_APPROVAL_PENDING = "garson_onayi_bekliyor"
    CASH_PENDING = "nakit_bekliyor"
    WAITER_APPROVED_IN_KITCHEN = "garson_onayladi_mutfakta"
    PREPARING = "hazirlaniyor"
    READY = "hazir"
    DELIVERED = "teslim_edildi"
    CANCELLED = "iptal"
    PAID_CLOSED = "odendi_kapatildi"


class OrderAction(str, Enum):
    """Commands accepted by the legacy status endpoint but not persisted as-is."""

    CASH_COLLECTED = "nakit_tahsil_edildi"


class TokenType(str, Enum):
    STAFF = "STAFF"
    CUSTOMER_SESSION = "CUSTOMER_SESSION"
