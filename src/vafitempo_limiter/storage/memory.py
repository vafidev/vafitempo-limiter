import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from ..models import RateLimitResult


@dataclass(slots=True)
class _Bucket:
    """Internal state of a single token bucket."""

    tokens: float
    last_update: float


class InMemoryStorage:
    """Thread-safe (asyncio) in-memory storage backend using the Token Bucket algorithm.

    Suitable for single-process applications and testing. State is stored in local
    memory and is not shared across multiple worker processes.
    """

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        cleanup_interval: int = 1000,
    ) -> None:
        """Initialize the in-memory storage.

        Args:
            clock: Monotonic time provider returning seconds as a float.
                Defaults to ``time.monotonic``. Useful for injecting a fake clock in tests.
            cleanup_interval: Number of ``acquire`` calls between background sweeps
                of expired buckets to prevent unbounded memory growth.
        """

        self._clock = clock
        self._cleanup_interval = cleanup_interval
        self._buckets: dict[str, _Bucket] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._ops_count = 0

    async def acquire(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        cost: int = 1,
    ) -> RateLimitResult:
        """Attempt to consume tokens from the bucket identified by ``key``.

        Args:
            key: Unique identifier for the rate-limited entity (e.g., user ID or IP).
            capacity: Maximum number of tokens the bucket can hold (burst size).
            refill_rate: Number of tokens added to the bucket per second.
            cost: Number of tokens required for this request. Defaults to 1.

        Returns:
            A ``RateLimitResult`` indicating whether the request is allowed and
            providing metadata for rate-limit headers.

        Raises:
            ValueError: If ``capacity``, ``refill_rate``, or ``cost`` are non-positive,
                or if ``cost`` exceeds ``capacity``.
        """

        if cost <= 0:
            raise ValueError("Cost must be positive")
        if cost > capacity:
            raise ValueError(f"Cost ({cost}) cannot exceed bucket capacity ({capacity})")
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("Refill rate must be positive")

        self._ops_count += 1
        if self._ops_count >= self._cleanup_interval:
            self._ops_count = 0
            self._cleanup(capacity=capacity, refill_rate=refill_rate)

        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        async with lock:
            now = self._clock()
            bucket = self._buckets.get(key)

            if bucket is None:
                bucket = _Bucket(
                    tokens=float(capacity),
                    last_update=now,
                )
                self._buckets[key] = bucket

            elapsed = max(0.0, now - bucket.last_update)
            bucket.tokens = min(float(capacity), bucket.tokens + elapsed * refill_rate)
            bucket.last_update = now

            if bucket.tokens >= cost:
                bucket.tokens -= cost
                remaining = math.floor(bucket.tokens)
                reset_after = (capacity - bucket.tokens) / refill_rate
                return RateLimitResult(
                    allowed=True,
                    limit=capacity,
                    remaining=remaining,
                    reset_after=reset_after,
                    retry_after=0.0,
                )

            missing = cost - bucket.tokens
            retry_after = missing / refill_rate
            reset_after = (capacity - bucket.tokens) / refill_rate
            return RateLimitResult(
                allowed=False,
                limit=capacity,
                remaining=math.floor(bucket.tokens),
                reset_after=reset_after,
                retry_after=retry_after,
            )

    def _cleanup(self, capacity: int, refill_rate: float) -> None:
        """Evict idle buckets that have already refilled to full capacity."""

        now = self._clock()
        ttl = (capacity / refill_rate) * 2
        expired_keys = [
            k
            for k, b in self._buckets.items()
            if (now - b.last_update) > ttl and not self._locks.get(k, asyncio.Lock()).locked()
        ]

        for k in expired_keys:
            self._buckets.pop(k, None)
            self._locks.pop(k, None)
