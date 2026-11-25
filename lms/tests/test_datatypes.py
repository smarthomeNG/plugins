#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Tests for plugins/lms/datatypes.py DT_* classes."""

import unittest

from plugins.lms.datatypes import DT_LMSSyncnames, DT_LMSSyncmembers, DT_LMSAlarms, DT_LMSPlayers


class TestDTLMSSyncnames(unittest.TestCase):
    def test_name_containing_lowercase_s_not_truncated(self):
        # [^s] excludes the literal letter 's' instead of using \S for
        # non-whitespace - any name containing a lowercase 's' truncated
        data = 'sync_member_names:Speakers,Sonos sync_members:11,22'
        result = DT_LMSSyncnames().get_shng_data(data)
        self.assertEqual(result, ['Speakers,Sonos'])


class TestDTLMSSyncmembers(unittest.TestCase):
    def test_value_containing_lowercase_s_not_truncated(self):
        # sync_members values are normally player IDs, but the regex bug is
        # about the character class itself, not this field's real content -
        # any value containing a lowercase 's' demonstrates the truncation
        data = 'sync_members:abcs,def sync_member_names:Living Room'
        result = DT_LMSSyncmembers().get_shng_data(data)
        self.assertEqual(result, ['abcs,def'])


class TestDTLMSAlarms(unittest.TestCase):
    def test_simple_fields_parsed(self):
        data = 'id:0 dow:0 enabled:1'
        result = DT_LMSAlarms().get_shng_data(data)
        self.assertEqual(result, {'0': {'dow': '0', 'enabled': '1'}})

    def test_value_containing_colon_does_not_raise(self):
        # a field value with a colon in it (e.g. a time or URL) must not
        # crash the unconditional 2-way unpack
        data = 'id:0 time:07:30'
        result = DT_LMSAlarms().get_shng_data(data)
        self.assertEqual(result, {'0': {'time': '07:30'}})


class TestDTLMSPlayers(unittest.TestCase):
    def test_sentinel_entry_uses_bare_ip_key(self):
        # real parsed entries use bare 'ip' (from the 'key:value' regex,
        # which never captures the colon) - the '-' sentinel must match
        result = DT_LMSPlayers().get_shng_data('playerindex:0 playerid:aa ip:1.2.3.4')
        self.assertIn('ip', result['-'])
        self.assertNotIn('ip:', result['-'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
