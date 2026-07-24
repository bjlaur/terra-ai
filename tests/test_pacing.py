"""Deterministic tests for provider request pacing."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from terra_ai.providers.pacing import RequestPacer


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_pacer(*, rpm=0, minimum=0):
    fake = FakeTime()
    pacer = RequestPacer(
        requests_per_minute=rpm,
        min_interval=minimum,
        clock=fake.clock,
        sleep=fake.sleep,
    )
    return pacer, fake


def test_disabled_pacer_never_sleeps():
    pacer, fake = make_pacer()

    assert pacer.enabled is False
    assert pacer.wait() == 0
    assert pacer.wait() == 0
    assert fake.sleeps == []


def test_first_request_proceeds_immediately():
    pacer, fake = make_pacer(rpm=20)

    assert pacer.wait() == 0
    assert fake.sleeps == []


def test_rpm_converts_to_request_interval():
    pacer, fake = make_pacer(rpm=20)

    assert pacer.interval == pytest.approx(3.0)
    pacer.wait()
    assert pacer.wait() == pytest.approx(3.0)
    assert fake.sleeps == pytest.approx([3.0])


def test_minimum_interval_works_without_rpm():
    pacer, _ = make_pacer(minimum=2.5)

    assert pacer.interval == pytest.approx(2.5)


def test_stricter_constraint_wins():
    assert make_pacer(rpm=20, minimum=4)[0].interval == pytest.approx(4.0)
    assert make_pacer(rpm=10, minimum=4)[0].interval == pytest.approx(6.0)


@pytest.mark.parametrize(
    ("kwargs", "name"),
    [
        ({"requests_per_minute": -1}, "requests_per_minute"),
        ({"requests_per_minute": True}, "requests_per_minute"),
        ({"requests_per_minute": float("nan")}, "requests_per_minute"),
        ({"requests_per_minute": float("inf")}, "requests_per_minute"),
        ({"min_interval": -1}, "min_interval"),
        ({"min_interval": False}, "min_interval"),
        ({"min_interval": float("nan")}, "min_interval"),
        ({"min_interval": float("inf")}, "min_interval"),
    ],
)
def test_invalid_values_are_rejected(kwargs, name):
    with pytest.raises(ValueError, match=name):
        RequestPacer(**kwargs)


def test_explicit_cooldown_blocks_next_request():
    pacer, fake = make_pacer(rpm=20)
    pacer.wait()

    fake.now = 1.0
    pacer.defer_for(3.0)

    assert pacer.wait() == pytest.approx(3.0)
    assert fake.now == pytest.approx(4.0)


def test_concurrent_callers_are_serialized_without_real_sleep():
    pacer, fake = make_pacer(rpm=20)

    with ThreadPoolExecutor(max_workers=3) as executor:
        waits = list(executor.map(lambda _: pacer.wait(), range(3)))

    assert sorted(waits) == pytest.approx([0.0, 3.0, 3.0])
    assert fake.now == pytest.approx(6.0)
    assert fake.sleeps == pytest.approx([3.0, 3.0])


def test_configured_values_are_retained():
    pacer, _ = make_pacer(rpm=20, minimum=4)

    assert pacer.requests_per_minute == pytest.approx(20.0)
    assert pacer.min_interval == pytest.approx(4.0)
