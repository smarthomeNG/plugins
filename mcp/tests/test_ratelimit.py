from plugins.mcp.ratelimit import SlidingWindowLimiter


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_hits_up_to_the_limit_pass_and_the_next_one_reports_a_retry_time():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    assert limiter.acquire('k', 2) is None
    clock.now += 10
    assert limiter.acquire('k', 2) is None
    clock.now += 10
    retry_after = limiter.acquire('k', 2)
    assert retry_after == 40.0


def test_the_window_slides():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    limiter.acquire('k', 1)
    clock.now += 59
    assert limiter.acquire('k', 1) == 1.0
    clock.now += 1
    assert limiter.acquire('k', 1) is None


def test_a_rejected_hit_does_not_extend_the_wait():
    clock = FakeClock()
    limiter = SlidingWindowLimiter(clock)
    limiter.acquire('k', 1)
    clock.now += 30
    limiter.acquire('k', 1)
    clock.now += 30
    assert limiter.acquire('k', 1) is None


def test_keys_are_counted_separately():
    limiter = SlidingWindowLimiter(FakeClock())
    assert limiter.acquire('a', 1) is None
    assert limiter.acquire('b', 1) is None
    assert limiter.acquire('a', 1) is not None


def test_a_limit_of_zero_disables_limiting():
    limiter = SlidingWindowLimiter(FakeClock())
    assert all(limiter.acquire('k', 0) is None for _ in range(100))
