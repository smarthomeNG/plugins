# ruff: noqa: F821  (sh and logger are injected by the logic loader)
# Counts up every cycle (for wait_for_change) and writes log lines with secrets and a traceback (for get_logs)
counter = sh.mcpdemo.counter
counter(counter() + 1)
logger.info(f'mcp_ticker: run {counter()}')
logger.warning('mcp_ticker: login with password=hunter2 on device SN-4711, Authorization: Bearer abcdef0123456789')
if counter() % 4 == 0:
    try:
        raise ValueError('mcp_ticker: deliberate error')
    except ValueError:
        logger.exception('mcp_ticker: caught')
