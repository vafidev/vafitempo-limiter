from typing import Protocol

from ..models import RateLimitResult


class BaseStorage(Protocol):
    """Protocol defining the interface for rate limiter storage backends."""

    async def acquire(
        self,
        key: str,
        capacity: int,
        refill_rate: float,
        cost: int = 1,
    ) -> RateLimitResult:
        """Attempt to consume tokens for the given key using the token bucket algorithm.

        Args:
            key: Unique identifier for the rate limit bucket (e.g., client IP or user ID).
            capacity: Maximum number of tokens the bucket can hold.
            refill_rate: Token replenishment rate in tokens per second.
            cost: Number of tokens to consume for this request. Defaults to 1.

        Returns:
            A RateLimitResult indicating whether the request is allowed and current quota state.
        """
        ...
