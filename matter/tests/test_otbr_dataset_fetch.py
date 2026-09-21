#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for server/__init__.py's fetch_thread_dataset_from_otbr() - the
GET /node/dataset/active round trip against OTBR's own REST API, mocked at
urllib.request.urlopen so no real HTTP call happens.
"""

import urllib.error
from unittest.mock import MagicMock, patch

from plugins.matter.server import fetch_thread_dataset_from_otbr

HEX_DATASET = '0e080000000000010000000300001035060004001fffe0'


def _plugin(**overrides):
    plugin = MagicMock()
    plugin.server_otbr_rest_url = overrides.get('server_otbr_rest_url', 'http://localhost:8081')
    plugin.run_asyncio_coro = MagicMock(return_value=None)
    return plugin


def _mock_response(body: bytes):
    response = MagicMock()
    response.read.return_value = body
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


@patch('plugins.matter.server.urllib.request.urlopen')
def test_fetch_returns_dataset_and_registers_it(mock_urlopen):
    mock_urlopen.return_value = _mock_response(HEX_DATASET.encode('utf-8'))
    plugin = _plugin()

    result = fetch_thread_dataset_from_otbr(plugin)

    assert result == HEX_DATASET
    plugin.server_client.set_thread_dataset.assert_called_once_with(HEX_DATASET)
    plugin.run_asyncio_coro.assert_called_once()


@patch('plugins.matter.server.urllib.request.urlopen')
def test_fetch_requests_text_plain(mock_urlopen):
    mock_urlopen.return_value = _mock_response(HEX_DATASET.encode('utf-8'))
    fetch_thread_dataset_from_otbr(_plugin())

    request = mock_urlopen.call_args[0][0]
    assert request.full_url == 'http://localhost:8081/node/dataset/active'
    assert request.get_header('Accept') == 'text/plain'


@patch('plugins.matter.server.urllib.request.urlopen')
def test_fetch_strips_trailing_slash_from_base_url(mock_urlopen):
    mock_urlopen.return_value = _mock_response(HEX_DATASET.encode('utf-8'))
    fetch_thread_dataset_from_otbr(_plugin(server_otbr_rest_url='http://otbr.local:8081/'))

    request = mock_urlopen.call_args[0][0]
    assert request.full_url == 'http://otbr.local:8081/node/dataset/active'


@patch('plugins.matter.server.urllib.request.urlopen')
def test_fetch_empty_response_raises(mock_urlopen):
    mock_urlopen.return_value = _mock_response(b'')
    plugin = _plugin()

    try:
        fetch_thread_dataset_from_otbr(plugin)
        assert False, 'expected ValueError'
    except ValueError as ex:
        assert 'no active Thread dataset' in str(ex)
    plugin.server_client.set_thread_dataset.assert_not_called()


@patch('plugins.matter.server.urllib.request.urlopen')
def test_fetch_unreachable_border_router_raises(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError('connection refused')
    plugin = _plugin()

    try:
        fetch_thread_dataset_from_otbr(plugin)
        assert False, 'expected ValueError'
    except ValueError as ex:
        assert 'could not reach' in str(ex)
    plugin.server_client.set_thread_dataset.assert_not_called()
