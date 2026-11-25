"""walk(): step through all DAB services once and collect them in device order."""

import threading

from plugins.yamahayxc.dabstations import DabService, Settle, WalkState, walk
from plugins.yamahayxc.tests.dab_fake import FakeDabLink

FAST = Settle(poll_interval=0.0, timeout=0.02)
SERVICES = [(7, 'Dlf'), (3, 'RADIO BOB!'), (9, 'WDR 2'), (4, 'SWR3')]


def test_walk_collects_every_service_in_device_order_starting_at_the_current_one():
    link = FakeDabLink(SERVICES, position=1)

    result = walk(link, threading.Event())

    assert result.state is WalkState.DONE
    assert result.total == 4
    assert result.services == (
        DabService(3, 'RADIO BOB!'),
        DabService(9, 'WDR 2'),
        DabService(4, 'SWR3'),
        DabService(7, 'Dlf'),
    )


def test_walk_is_muted_while_stepping_and_unmuted_afterwards():
    muted_during_steps = []
    link = FakeDabLink(SERVICES, on_step=lambda dab: muted_during_steps.append(dab.muted))

    walk(link, threading.Event())

    assert muted_during_steps == [True] * len(SERVICES)
    assert link.muted is False


def test_walk_leaves_an_already_muted_device_muted():
    link = FakeDabLink(SERVICES, muted=True)

    walk(link, threading.Event())

    assert link.muted is True


def test_walk_carries_on_when_the_device_refuses_to_mute():
    link = FakeDabLink(SERVICES, mute_refused=True)

    result = walk(link, threading.Event())

    assert result.state is WalkState.DONE
    assert link.mute_calls == [True]


def test_walk_carries_on_when_the_mute_state_is_unreadable():
    link = FakeDabLink(SERVICES, mute_fails=True)

    result = walk(link, threading.Event())

    assert result.state is WalkState.DONE
    assert link.mute_calls == []


def test_cancel_aborts_the_walk_unmutes_and_publishes_no_services():
    cancel = threading.Event()
    link = FakeDabLink(SERVICES, on_step=lambda dab: cancel.set() if len(dab.steps) == 2 else None)

    result = walk(link, cancel)

    assert result == type(result)(WalkState.ABORTED)
    assert link.steps == ['next', 'next']
    assert link.muted is False


def test_progress_reports_percent_of_the_scanned_service_count():
    percents = []

    walk(FakeDabLink(SERVICES), threading.Event(), percents.append)

    assert percents == [25, 50, 75, 100]


def test_walk_fails_without_stepping_when_the_device_does_not_answer():
    link = FakeDabLink(SERVICES, down=True)

    result = walk(link, threading.Event())

    assert result.state is WalkState.ERROR
    assert link.steps == []


def test_walk_fails_when_no_initial_scan_has_found_services():
    link = FakeDabLink([])

    result = walk(link, threading.Event())

    assert result.state is WalkState.ERROR
    assert link.steps == []


def test_walk_fails_and_unmutes_when_the_tuner_stays_on_the_same_service():
    link = FakeDabLink(SERVICES, stuck=True)

    result = walk(link, threading.Event(), settle=FAST)

    assert result.state is WalkState.ERROR
    assert link.muted is False
