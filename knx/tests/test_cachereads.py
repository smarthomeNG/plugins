"""Tests for plugins.knx.cachereads.CacheReadTracker."""

import unittest

from plugins.knx.cachereads import CacheReadTracker


class TestCacheReadTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = CacheReadTracker(retry_delays=(2.0, 5.0))

    def test_start_returns_unique_gas_in_order(self):
        self.assertEqual(self.tracker.start(['1/1/1', '1/1/2', '1/1/1']), ['1/1/1', '1/1/2'])
        self.assertEqual(self.tracker.pending, ['1/1/1', '1/1/2'])

    def test_answered_removes_from_pending(self):
        self.tracker.start(['1/1/1', '1/1/2'])
        self.tracker.answered('1/1/1')
        self.assertEqual(self.tracker.pending, ['1/1/2'])

    def test_answered_reports_whether_ga_was_pending(self):
        self.tracker.start(['1/1/1'])
        self.assertTrue(self.tracker.answered('1/1/1'))
        self.assertFalse(self.tracker.answered('1/1/1'))
        self.assertFalse(self.tracker.answered('9/9/9'))

    def test_answered_unknown_ga_is_ignored(self):
        self.tracker.start(['1/1/1'])
        self.tracker.answered('9/9/9')
        self.assertEqual(self.tracker.pending, ['1/1/1'])

    def test_no_retry_when_nothing_pending(self):
        self.tracker.start(['1/1/1'])
        self.tracker.answered('1/1/1')
        self.assertIsNone(self.tracker.next_retry_delay())

    def test_retry_rounds_follow_configured_delays(self):
        self.tracker.start(['1/1/1', '1/1/2'])
        self.tracker.answered('1/1/2')

        self.assertEqual(self.tracker.next_retry_delay(), 2.0)
        self.assertEqual(self.tracker.take_retry(), ['1/1/1'])
        self.assertEqual(self.tracker.next_retry_delay(), 5.0)
        self.assertEqual(self.tracker.take_retry(), ['1/1/1'])
        self.assertIsNone(self.tracker.next_retry_delay())

    def test_retry_skips_gas_answered_between_rounds(self):
        self.tracker.start(['1/1/1', '1/1/2'])
        self.tracker.take_retry()
        self.tracker.answered('1/1/1')
        self.assertEqual(self.tracker.take_retry(), ['1/1/2'])

    def test_exhausted_keeps_unanswered_gas_pending(self):
        self.tracker.start(['1/1/1'])
        self.tracker.take_retry()
        self.tracker.take_retry()
        self.assertIsNone(self.tracker.next_retry_delay())
        self.assertEqual(self.tracker.pending, ['1/1/1'])

    def test_start_resets_previous_run(self):
        self.tracker.start(['1/1/1'])
        self.tracker.take_retry()
        self.tracker.start(['2/2/2'])
        self.assertEqual(self.tracker.pending, ['2/2/2'])
        self.assertEqual(self.tracker.next_retry_delay(), 2.0)

    def test_no_delays_means_no_retries(self):
        tracker = CacheReadTracker(retry_delays=())
        tracker.start(['1/1/1'])
        self.assertIsNone(tracker.next_retry_delay())
