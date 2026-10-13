#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/matter/role.py - Backoff and registration merging."""

import unittest

from plugins.matter.role import (
    RESTART_BACKOFF_SECONDS,
    STABLE_RUN_SECONDS,
    Backoff,
    ItemRegistration,
    merge_registrations,
)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class TestBackoff(unittest.TestCase):
    def test_repeated_failures_escalate_and_cap(self):
        backoff = Backoff(clock=_Clock())

        delays = [backoff.next_delay() for _ in range(len(RESTART_BACKOFF_SECONDS) + 2)]

        self.assertEqual(delays[: len(RESTART_BACKOFF_SECONDS)], list(RESTART_BACKOFF_SECONDS))
        self.assertEqual(delays[-1], RESTART_BACKOFF_SECONDS[-1])

    def test_immediate_crash_after_start_keeps_escalating(self):
        clock = _Clock()
        backoff = Backoff(clock=clock)
        backoff.next_delay()
        backoff.started()
        clock.now += 1

        self.assertEqual(backoff.next_delay(), RESTART_BACKOFF_SECONDS[1])

    def test_stable_run_resets_the_schedule(self):
        clock = _Clock()
        backoff = Backoff(clock=clock)
        backoff.next_delay()
        backoff.next_delay()
        backoff.started()
        clock.now += STABLE_RUN_SECONDS

        self.assertEqual(backoff.next_delay(), RESTART_BACKOFF_SECONDS[0])

    def test_reset(self):
        backoff = Backoff(clock=_Clock())
        backoff.next_delay()
        backoff.reset()

        self.assertEqual(backoff.next_delay(), RESTART_BACKOFF_SECONDS[0])


class TestMergeRegistrations(unittest.TestCase):
    def test_no_registration_is_none(self):
        self.assertIsNone(merge_registrations([None, None]))

    def test_configs_are_merged_and_updating_is_any(self):
        merged = merge_registrations(
            [ItemRegistration({'a': 1}, updating=False), None, ItemRegistration({'b': 2}, updating=True)]
        )

        self.assertEqual(dict(merged.config), {'a': 1, 'b': 2})
        self.assertTrue(merged.updating)

    def test_read_only_only(self):
        merged = merge_registrations([ItemRegistration({'a': 1}, updating=False)])

        self.assertFalse(merged.updating)


if __name__ == '__main__':
    unittest.main()
