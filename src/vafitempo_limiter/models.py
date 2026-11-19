from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Result of a rate limit check returned by a storage backend.

    Attributes:
        allowed: Whether the request is permitted to proceed.
        limit: Maximum token capacity of the bucket.
        remaining: Number of whole tokens left after this check.
        reset_after: Time in seconds until the bucket is completely refilled.
        retry_after: Time in seconds to wait before retrying if rejected (0.0 if allowed).
    """

    allowed: bool
    limit: int
    remaining: int
    reset_after: float
    retry_after: float
