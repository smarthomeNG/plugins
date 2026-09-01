#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that plugins.kodi's module-level bootstrap does not clobber an
already-True builtins.SDP_standalone.

The real trigger: in standalone mode, __init__.py runs as __main__ and sets
SDP_standalone = True. Later, SDPCommands._read_commands() does
locate('plugins.kodi.commands'), which needs the plugins.kodi package
importable under its real dotted name - re-running this module's top-level
code with __name__ == 'plugins.kodi', hitting the `else` branch. Simulated
here via importlib.reload(), which re-executes the same top-level code path
under the module's real (non-__main__) name.
"""

import builtins
import importlib
import unittest


class TestKodiStandaloneFlagNotClobbered(unittest.TestCase):
    def test_reload_does_not_reset_true_to_false(self):
        import plugins.kodi  # noqa: F401  (else branch runs, sets False - expected for normal import)

        self.addCleanup(setattr, builtins, 'SDP_standalone', builtins.SDP_standalone)
        builtins.SDP_standalone = True  # simulate: we are genuinely running standalone
        importlib.reload(plugins.kodi)

        self.assertTrue(builtins.SDP_standalone)


if __name__ == '__main__':
    unittest.main(verbosity=2)
