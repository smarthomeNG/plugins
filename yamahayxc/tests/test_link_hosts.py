"""link_hosts lists every configured host and follows live item removal."""

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin


def make_two_host_plugin():
    network = FakeNetwork({'127.0.0.1': FakeDevice(), '127.0.0.2': FakeDevice()})
    plugin, sh = make_plugin('items_two_hosts.yaml', network)
    return plugin, sh


def test_each_host_lists_all_configured_hosts():
    plugin, sh = make_two_host_plugin()

    assert sh.return_item('yamaha.one.available_devices')() == ['127.0.0.1', '127.0.0.2']
    assert sh.return_item('yamaha.two.available_devices')() == ['127.0.0.1', '127.0.0.2']


def test_removing_a_host_updates_the_remaining_lists():
    plugin, sh = make_two_host_plugin()

    for path in ('yamaha.two.available_devices', 'yamaha.two.volume'):
        plugin.remove_item(sh.return_item(path))

    assert sh.return_item('yamaha.one.available_devices')() == ['127.0.0.1']
