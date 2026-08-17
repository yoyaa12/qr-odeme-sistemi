"""Process-local login throttling.

This protects the current single-process internship deployment. It is not a
distributed limit: counters reset on restart and are not shared by workers.
"""

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


@dataclass(slots=True)
class _RateLimitBucket:
    failures: deque[float] = field(default_factory=deque)
    in_flight: int = 0
    last_seen: float = 0.0


class LoginAttemptReservation:
    """One atomically reserved authentication attempt.

    A reservation counts against every supplied key while password verification
    is running. The context-manager fallback releases it after unexpected
    exceptions so an internal error cannot permanently consume capacity.
    """

    __slots__ = ("_limiter", "_keys", "decision", "_active")

    def __init__(
        self,
        limiter: "ProcessLocalLoginRateLimiter",
        keys: tuple[str, ...],
        decision: RateLimitDecision,
        *,
        active: bool,
    ) -> None:
        self._limiter = limiter
        self._keys = keys
        self.decision = decision
        self._active = active

    @property
    def allowed(self) -> bool:
        return self.decision.allowed

    @property
    def retry_after_seconds(self) -> int:
        return self.decision.retry_after_seconds

    def __enter__(self) -> "LoginAttemptReservation":
        if not self.allowed or not self._active:
            raise RuntimeError("Cannot enter an inactive login reservation")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()

    def record_failure(self) -> None:
        if not self._active:
            return
        self._limiter._finish_reservation(self._keys, failed=True)
        self._active = False

    def record_success(self, clear_failure_keys: Iterable[str] = ()) -> None:
        if not self._active:
            return
        clear_keys = tuple(dict.fromkeys(clear_failure_keys))
        if not set(clear_keys).issubset(self._keys):
            raise ValueError("Success keys must belong to the reservation")
        self._limiter._finish_reservation(
            self._keys,
            failed=False,
            clear_failure_keys=clear_keys,
        )
        self._active = False

    def release(self) -> None:
        if not self._active:
            return
        self._limiter._finish_reservation(self._keys, failed=False)
        self._active = False


class ProcessLocalLoginRateLimiter:
    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 5 * 60,
        max_buckets: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_failures <= 0 or window_seconds <= 0 or max_buckets <= 0:
            raise ValueError("Rate-limit settings must be positive")
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self._clock = clock
        self._buckets: dict[str, _RateLimitBucket] = {}
        self._lock = threading.Lock()

    @property
    def _failures(self) -> dict[str, deque[float]]:
        """Compatibility snapshot for older diagnostics/tests."""
        with self._lock:
            return {
                key: deque(bucket.failures)
                for key, bucket in self._buckets.items()
                if bucket.failures
            }

    @property
    def bucket_count(self) -> int:
        with self._lock:
            return len(self._buckets)

    def _normalize_keys(
        self,
        keys: Iterable[str],
        *,
        allow_empty: bool = False,
    ) -> tuple[str, ...]:
        normalized = tuple(dict.fromkeys(keys))
        if not normalized and not allow_empty:
            raise ValueError("At least one rate-limit key is required")
        if len(normalized) > self.max_buckets:
            raise ValueError("Too many rate-limit keys")
        if any(not isinstance(key, str) or not key for key in normalized):
            raise ValueError("Rate-limit keys must be non-empty text")
        return normalized

    def _purge(self, bucket: _RateLimitBucket, now: float) -> None:
        cutoff = now - self.window_seconds
        while bucket.failures and bucket.failures[0] <= cutoff:
            bucket.failures.popleft()

    def _compact(self, now: float, *, protected_keys: frozenset[str] = frozenset()) -> None:
        for key, bucket in list(self._buckets.items()):
            self._purge(bucket, now)
            if not bucket.failures and bucket.in_flight == 0:
                self._buckets.pop(key, None)

        overflow = len(self._buckets) - self.max_buckets
        if overflow <= 0:
            return
        removable = sorted(
            (
                (key, bucket)
                for key, bucket in self._buckets.items()
                if bucket.in_flight == 0 and key not in protected_keys
            ),
            key=lambda item: item[1].last_seen,
        )
        for key, _bucket in removable[:overflow]:
            self._buckets.pop(key, None)

    def _decision(self, keys: tuple[str, ...], now: float) -> RateLimitDecision:
        retry_after = 0
        for key in keys:
            bucket = self._buckets.get(key)
            if not bucket:
                continue
            self._purge(bucket, now)
            attempts = len(bucket.failures) + bucket.in_flight
            if attempts < self.max_failures:
                continue
            if len(bucket.failures) >= self.max_failures:
                retry_after = max(
                    retry_after,
                    math.ceil(
                        bucket.failures[0] + self.window_seconds - now
                    ),
                )
            else:
                # Capacity is currently held by password checks. A short retry
                # avoids advertising the unrelated historical failure window.
                retry_after = max(retry_after, 1)
        if retry_after > 0:
            return RateLimitDecision(False, retry_after)
        return RateLimitDecision(True)

    def check(self, keys: Iterable[str]) -> RateLimitDecision:
        normalized = self._normalize_keys(keys)
        now = self._clock()
        with self._lock:
            decision = self._decision(normalized, now)
            self._compact(now)
            return decision

    def reserve(self, keys: Iterable[str]) -> LoginAttemptReservation:
        normalized = self._normalize_keys(keys)
        now = self._clock()
        with self._lock:
            decision = self._decision(normalized, now)
            if not decision.allowed:
                self._compact(now)
                return LoginAttemptReservation(
                    self,
                    normalized,
                    decision,
                    active=False,
                )

            protected = frozenset(normalized)
            new_key_count = sum(key not in self._buckets for key in normalized)
            required_capacity = len(self._buckets) + new_key_count - self.max_buckets
            if required_capacity > 0:
                removable = sorted(
                    (
                        (key, bucket)
                        for key, bucket in self._buckets.items()
                        if bucket.in_flight == 0 and key not in protected
                    ),
                    key=lambda item: item[1].last_seen,
                )
                for key, _bucket in removable[:required_capacity]:
                    self._buckets.pop(key, None)

            if len(self._buckets) + new_key_count > self.max_buckets:
                return LoginAttemptReservation(
                    self,
                    normalized,
                    RateLimitDecision(False, 1),
                    active=False,
                )

            for key in normalized:
                bucket = self._buckets.setdefault(key, _RateLimitBucket())
                bucket.in_flight += 1
                bucket.last_seen = now
            return LoginAttemptReservation(
                self,
                normalized,
                RateLimitDecision(True),
                active=True,
            )

    def _finish_reservation(
        self,
        keys: tuple[str, ...],
        *,
        failed: bool,
        clear_failure_keys: tuple[str, ...] = (),
    ) -> None:
        now = self._clock()
        clear = frozenset(clear_failure_keys)
        with self._lock:
            for key in keys:
                bucket = self._buckets.get(key)
                if bucket is None or bucket.in_flight <= 0:
                    raise RuntimeError("Rate-limit reservation is inconsistent")
                bucket.in_flight -= 1
                bucket.last_seen = now
                if failed:
                    self._purge(bucket, now)
                    bucket.failures.append(now)
                elif key in clear:
                    bucket.failures.clear()
            self._compact(now)

    def record_failure(self, keys: Iterable[str]) -> None:
        normalized = self._normalize_keys(keys)
        now = self._clock()
        with self._lock:
            for key in normalized:
                bucket = self._buckets.setdefault(key, _RateLimitBucket())
                self._purge(bucket, now)
                bucket.failures.append(now)
                bucket.last_seen = now
            self._compact(now, protected_keys=frozenset(normalized))

    def record_success(self, keys: Iterable[str]) -> None:
        normalized = self._normalize_keys(keys, allow_empty=True)
        with self._lock:
            now = self._clock()
            for key in normalized:
                bucket = self._buckets.get(key)
                if bucket is not None:
                    bucket.failures.clear()
                    bucket.last_seen = now
            self._compact(now)


staff_login_limiter = ProcessLocalLoginRateLimiter()

# Masa QR/TOTP doğrulaması kimlik istemez ve 6 haneli bir kod kabul eder.
# ±2 pencere toleransı yüzünden aynı anda 5 kod geçerli olduğundan, kısıtlamasız
# bir uç nokta çevrimiçi kaba kuvvete açıktır. Gerçek müşteri en fazla birkaç
# deneme yapar, bu yüzden dakikada 10 başarısız deneme fazlasıyla yeterlidir.
qr_verify_limiter = ProcessLocalLoginRateLimiter(
    max_failures=10,
    window_seconds=60,
)
