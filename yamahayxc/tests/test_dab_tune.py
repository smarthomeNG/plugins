"""tune(): step to a service of the walked list in the shorter direction."""

import threading

from plugins.yamahayxc.dabstations import DabService, WalkState, tune
from plugins.yamahayxc.tests.dab_fake import FakeDabLink

DEVICE = [(7, 'Dlf'), (3, 'RADIO BOB!'), (9, 'WDR 2'), (4, 'SWR3'), (5, 'NDR 2')]
LIST = tuple(DabService(i, n) for i, n in DEVICE)


def test_tune_steps_forward_when_the_target_is_closer_ahead():
    link = FakeDabLink(DEVICE, position=0)

    state = tune(link, LIST, 2, threading.Event())

    assert state is WalkState.DONE
    assert link.steps == ['next', 'next']
    assert link.position == 2


def test_tune_steps_backward_when_the_target_is_closer_behind():
    link = FakeDabLink(DEVICE, position=0)

    state = tune(link, LIST, 4, threading.Event())

    assert state is WalkState.DONE
    assert link.steps == ['previous']
    assert link.position == 4


def test_tune_to_the_current_service_does_not_step():
    link = FakeDabLink(DEVICE, position=3)

    state = tune(link, LIST, 3, threading.Event())

    assert state is WalkState.DONE
    assert link.steps == []


def test_tune_is_muted_while_stepping_and_unmuted_afterwards():
    muted_during_steps = []
    link = FakeDabLink(DEVICE, on_step=lambda dab: muted_during_steps.append(dab.muted))

    tune(link, LIST, 2, threading.Event())

    assert muted_during_steps == [True, True]
    assert link.muted is False


def test_cancel_stops_tuning_where_it_is_and_unmutes():
    cancel = threading.Event()
    link = FakeDabLink(DEVICE, on_step=lambda dab: cancel.set())

    state = tune(link, LIST, 2, cancel)

    assert state is WalkState.ABORTED
    assert link.position == 1
    assert link.muted is False


def test_tune_fails_without_stepping_when_the_current_service_is_not_in_the_list():
    link = FakeDabLink([(99, 'Unknown')] + DEVICE, position=0)

    state = tune(link, LIST, 2, threading.Event())

    assert state is WalkState.ERROR
    assert link.steps == []


def test_tune_fails_when_it_lands_on_another_service_than_listed():
    stale = LIST[:2] + (DabService(8, 'Other'),) + LIST[3:]
    link = FakeDabLink(DEVICE, position=0)

    state = tune(link, stale, 2, threading.Event())

    assert state is WalkState.ERROR
    assert link.muted is False
