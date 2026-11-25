"""The web interface lists the registers read and written, with their last values, and SunSpec devices."""

import pathlib

import jinja2
import pytest

from plugins.modbus import webif
from plugins.modbus.tests.sunspec_rig import image, model
from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until
from tests.sdp_harness import load_plugin

BASE = jinja2.DictLoader(
    {
        'base_plugin.html': '{% block headtable %}{% endblock %}'
        '{{ tab1title }}{% block bodytab1 %}{% endblock %}'
        '{{ tab2title }}{% block bodytab2 %}{% endblock %}'
        '{{ tab3title }}{% block bodytab3 %}{% endblock %}'
    }
)


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


def render(plugin, **params) -> str:
    templates = pathlib.Path(webif.__file__).parent / 'templates'
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader([BASE, jinja2.FileSystemLoader(templates)]), extensions=['jinja2.ext.i18n']
    )
    env.install_null_translations()
    interface = webif.WebInterface.__new__(webif.WebInterface)
    interface.plugin = plugin
    interface.logger = plugin.logger
    interface.tplenv = env
    interface.items = plugin._sh.items
    return interface.index(**params)


def test_index_shows_read_and_written_registers(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        assert 'registers to read</strong> (4)' in render(plugin)

        plugin._trigger_async_read()
        wait_until(lambda: rig.item('dev.value')() == 123.4)
        rig.item('dev.value')(43.2, 'test')
        wait_until(lambda: simulator.registers[0] == 432)

        html = render(plugin)
    finally:
        plugin.stop()

    assert 'registers to write</strong> (2)' in html
    assert 'HoldingRegister' in html
    assert 'InputRegister' in html
    assert 'dev.value' in html
    assert 'uint16' in html
    assert '123.4' in html
    assert '432' in html


def test_sunspec_scan_lists_the_points_of_the_device(tmp_path, modbus_server):
    body = [0] * 50
    body[12], body[13] = 1234, 0xFFFF
    registers = image(40000, model(1, [0x4163, 0x6D65] + [0] * 64), model(103, body))
    server = modbus_server(1, {40000: [registers[a] for a in sorted(registers)]})
    rig = load_plugin(
        str(tmp_path),
        'plugins.modbus',
        'Modbus',
        'dev:\n    poll:\n        type: bool\n        modbusPoll: true\n',
        params={'host': server.host, 'port': server.port, 'cycle': 0, 'slaveUnit': 1},
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        assert '103.W' not in render(plugin)

        html = render(plugin, sunspec_unit='1')
    finally:
        plugin.stop()

    assert 'inverter_three_phase' in html
    assert '103.W' in html
    assert '123.4' in html
    assert '1.Mn' in html and 'Acme' in html


def test_sunspec_scan_reports_devices_without_sunspec(tmp_path, simulator):
    rig = rig_for(tmp_path, simulator, cycle=0)
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        html = render(plugin, sunspec_unit='7')
    finally:
        plugin.stop()

    assert 'no SunSpec marker' in html
