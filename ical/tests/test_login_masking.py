"""
Calendar URLs with embedded login data are logged according to ``handle_login``.
"""

import datetime
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
import tests.common as common

common.register_shng_log_levels()

from plugins.ical import iCal

PASSWORD = 's3cr3t-app-pw'
URL = f'https://user:{PASSWORD}@cal.example.org/remote.php/dav/calendars/user/ferien/?export'


class _FailingDownload:
    def download(self, **kwargs):
        return False


class _Clock:
    def now(self):
        return datetime.datetime(2026, 10, 13, 12, 0, tzinfo=datetime.timezone.utc)


def _plugin(tmp_path, handle_login='mask'):
    plugin = iCal.__new__(iCal)
    plugin.logger = logging.getLogger('test.ical')
    plugin.handle_login = handle_login
    plugin.dl = _FailingDownload()
    plugin.shtime = _Clock()
    plugin._directory = str(tmp_path)
    plugin._ical_aliases = {'ferien': URL}
    plugin._icals = {URL: {}}
    return plugin


def test_failed_download_logs_masked_url(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger='test.ical'):
        _plugin(tmp_path)._read_events(URL)

    assert 'Could not download online ics file https://***:***@cal.example.org' in caplog.text
    assert PASSWORD not in caplog.text


def test_retrieval_by_alias_and_by_url_logs_masked_url(tmp_path, caplog):
    plugin = _plugin(tmp_path)
    with caplog.at_level(logging.DEBUG, logger='test.ical'):
        plugin('ferien')
        plugin(URL)
        plugin(URL.replace('ferien', 'other'))

    assert caplog.text.count('https://***:***@cal.example.org') == 4
    assert PASSWORD not in caplog.text


def test_show_mode_keeps_login_data(tmp_path, caplog):
    with caplog.at_level(logging.DEBUG, logger='test.ical'):
        _plugin(tmp_path, handle_login='show')._read_events(URL)

    assert PASSWORD in caplog.text
