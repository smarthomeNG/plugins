"""
Restrict pytest collection to the project's actual test convention: unit tests live in
a 'tests' subdirectory of a plugin (plugins/<plugin>/tests/), never loose alongside
plugin source. The filename convention (test_*.py) is layered on top via pyproject.toml's
[tool.pytest.ini_options] python_files setting - this hook enforces the directory part.

Without this, pytest's default discovery also tries to import any stray *_test.py- or
test_*.py-named file anywhere in a plugin (e.g. internal dev scripts like
smartmeter/dlms_test.py), which can fail to import if its dependencies aren't installed,
even though it was never meant to run under pytest.

Also provides fixtures shared by several plugins' tests (``modbus_server``).
"""

import asyncio
import functools
import pathlib
import socket
import threading
from dataclasses import dataclass
from typing import Any

import pytest

PLUGINS_DIR = pathlib.Path(__file__).resolve().parent


def _is_superseded(parts):
    # superseded plugin versions are kept for reference only - same convention as
    # ruff's "*/_pv_*" exclude and lib/shpypi.py's filelist building.
    return any('_pv' in part for part in parts)


def _is_priv(parts):
    # gitignored, locally-only plugin variants (personal dev forks, third-party
    # forks, or long-term production candidates fetched by the github plugin's
    # worktree collector into priv_repos/) - same convention as plugins/.gitignore's
    # "/priv_*" pattern.
    return any(part.startswith('priv_') for part in parts)


@functools.cache
def _requirements_files():
    # imported lazily: core is only importable once pytest has put its root on sys.path
    import bin.shngversion
    from lib.shpypi import Requirements_files

    return Requirements_files(version=bin.shngversion.get_shng_version(), for_tests=True)


def _excluded_by_version_bounds(path):
    """
    Return True if path is a plugin directory whose plugin.yaml sh_/py_ min/max version bounds
    exclude the running SmartHomeNG or Python version.

    Uses the check that tools/build_test_requirements.py applies, so a plugin without installed
    requirements is not collected either. A plugin.yaml that cannot be loaded excludes nothing.
    """
    if not path.is_dir() or path.parent.resolve() != PLUGINS_DIR or not (path / 'plugin.yaml').is_file():
        return False
    use_it, reason = _requirements_files()._test_plugin_versions(str(path / 'requirements.txt'))
    return not use_it and reason != ''


def pytest_ignore_collect(collection_path, config):
    # pytest_ignore_collect is a firstresult hook: returning a definitive True/False
    # here stops pytest from consulting any other hookimpl, including its own builtin
    # handling of --ignore/--ignore-glob. Only return a real opinion (True) for the
    # cases we actually want to force; defer (None) otherwise.
    parts = collection_path.parts

    if _is_superseded(parts):
        # always excluded, no override - nobody legitimately runs tests against a
        # superseded official plugin version
        return True

    if _is_priv(parts):
        # excluded from default discovery (so one developer's unofficial sandbox can't
        # break another's full-suite run), but still runnable on purpose by naming the
        # path explicitly, e.g. `pytest priv_repos/onkelandy/sml`
        requested = []
        for arg in config.invocation_params.args:
            if arg.startswith('-'):
                continue
            try:
                requested.append(pathlib.Path(arg).resolve())
            except OSError:
                continue
        # requested paths are resolved, so compare against the resolved collection path (symlinked plugin dirs)
        resolved = collection_path.resolve()
        explicitly_requested = any(
            _is_priv(arg.parts) and (arg == resolved or arg in resolved.parents) for arg in requested
        )
        return None if explicitly_requested else True

    if _excluded_by_version_bounds(collection_path):
        return True

    if collection_path.is_file() and 'tests' not in parts:
        return True

    return None


@dataclass
class ModbusTestServer:
    """A running loopback Modbus TCP server started by the ``modbus_server`` fixture."""

    host: str
    port: int
    unit: int
    context: Any

    def holding(self, address: int, count: int = 1) -> list[int]:
        """Current values of ``count`` holding registers from 0-based ``address``."""
        return list(self.context[self.unit].getValues(3, address, count))


@pytest.fixture
def modbus_server():
    """
    Start real pymodbus TCP servers on loopback; stopped at teardown.

    Returns a factory ``start(unit, holding, block=None)``: ``holding`` maps a 0-based register
    address to the register values stored from there on (all other holding registers read 0),
    ``unit`` is the device id the server answers as. ``block`` replaces the holding register
    block, for devices that react to writes; it is addressed like the context addresses it
    (request address + 1).
    The factory returns a ``ModbusTestServer``. pymodbus is imported lazily, so plugins without
    it are unaffected.
    """
    from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext
    from pymodbus.server import ModbusTcpServer

    try:
        from pymodbus.datastore import ModbusDeviceContext as _DeviceContext
    except ImportError:
        from pymodbus.datastore import ModbusSlaveContext as _DeviceContext

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    servers = []

    def start(unit: int, holding: dict[int, list[int]], block: Any = None) -> ModbusTestServer:
        if block is None:
            registers = [0] * 65536
            for addr, regs in holding.items():
                registers[addr : addr + len(regs)] = regs
            # the device context adds 1 to every request address before reading the block
            block = ModbusSequentialDataBlock(1, registers)
        # pymodbus 3.9 ignores co/ir/hr unless di is passed as well
        device = _DeviceContext(
            di=ModbusSequentialDataBlock.create(),
            co=ModbusSequentialDataBlock.create(),
            ir=ModbusSequentialDataBlock.create(),
            hr=block,
        )
        context = ModbusServerContext({unit: device}, single=False)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]

        async def create() -> ModbusTcpServer:
            return ModbusTcpServer(context, address=('127.0.0.1', port))

        server = asyncio.run_coroutine_threadsafe(create(), loop).result(timeout=5)
        asyncio.run_coroutine_threadsafe(server.serve_forever(), loop)
        servers.append(server)
        for _ in range(100):
            with socket.socket() as client:
                if client.connect_ex(('127.0.0.1', port)) == 0:
                    break
            threading.Event().wait(0.02)
        return ModbusTestServer('127.0.0.1', port, unit, context)

    yield start

    for server in servers:
        asyncio.run_coroutine_threadsafe(server.shutdown(), loop).result(timeout=5)
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=5)
