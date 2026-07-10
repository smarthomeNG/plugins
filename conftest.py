"""
Restrict pytest collection to the project's actual test convention: unit tests live in
a 'tests' subdirectory of a plugin (plugins/<plugin>/tests/), never loose alongside
plugin source. The filename convention (test_*.py) is layered on top via pyproject.toml's
[tool.pytest.ini_options] python_files setting - this hook enforces the directory part.

Without this, pytest's default discovery also tries to import any stray *_test.py- or
test_*.py-named file anywhere in a plugin (e.g. internal dev scripts like
smartmeter/dlms_test.py), which can fail to import if its dependencies aren't installed,
even though it was never meant to run under pytest.
"""

import pathlib


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
        explicitly_requested = any(
            _is_priv(arg.parts) and (arg == collection_path or arg in collection_path.parents) for arg in requested
        )
        return None if explicitly_requested else True

    if collection_path.is_file() and 'tests' not in parts:
        return True

    return None
