from .models import RateLimitResult


class RateLimitExceeded(Exception):
    """Raised when a client exceeds the configured rate limit.

    Attributes:
        result: Detailed rate limit check metadata (limits, remaining tokens, retry delay).
    """

    def __init__(self, result: RateLimitResult) -> None:
        self.result = result
        super().__init__(f"Rate limit exceeded. Retry after {result.retry_after:.2f}s")
