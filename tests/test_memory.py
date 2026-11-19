import asyncio

import pytest

from vafitempo_limiter.storage.memory import InMemoryStorage


class FakeClock:
    def __init__(self, current: float = 100.0) -> None:
        self.current = current

    def __call__(self) -> float:
        return self.current

    def advance(self, seconds: float) -> None:
        self.current += seconds


async def test_basic_token_bucket() -> None:
    clock = FakeClock()
    storage = InMemoryStorage(clock=clock)

    res1 = await storage.acquire("user1", capacity=3, refill_rate=1.0)
    assert res1.allowed is True
    assert res1.remaining == 2

    res2 = await storage.acquire("user1", capacity=3, refill_rate=1.0)
    assert res2.allowed is True
    assert res2.remaining == 1

    res3 = await storage.acquire("user1", capacity=3, refill_rate=1.0)
    assert res3.allowed is True
    assert res3.remaining == 0

    res4 = await storage.acquire("user1", capacity=3, refill_rate=1.0)
    assert res4.allowed is False
    assert res4.retry_after == pytest.approx(1)
    assert res4.reset_after == pytest.approx(3)

    clock.advance(2.0)
    res5 = await storage.acquire("user1", capacity=3, refill_rate=1.0)
    assert res5.allowed is True
    assert res5.remaining == 1
    assert res5.reset_after == pytest.approx(2)


async def test_weighted_cost() -> None:
    clock = FakeClock()
    storage = InMemoryStorage(clock=clock)

    res1 = await storage.acquire("user:1", capacity=5, refill_rate=1.0, cost=4)
    assert res1.allowed is True
    assert res1.remaining == 1

    res2 = await storage.acquire("user:1", capacity=5, refill_rate=1.0, cost=2)
    assert res2.allowed is False
    assert res2.retry_after == pytest.approx(1)


async def test_concurrency_no_race_condition() -> None:
    clock = FakeClock()
    storage = InMemoryStorage(clock=clock)

    results = await asyncio.gather(
        *(storage.acquire("user:1", capacity=10, refill_rate=0.1) for _ in range(30))
    )

    allowed_count = sum(1 for r in results if r.allowed)
    assert allowed_count == 10
