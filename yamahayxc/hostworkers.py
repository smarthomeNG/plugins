"""One single-thread executor per device host."""

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any


class HostWorkers:
    """
    Per-host single-thread executors, created on first use.

    Work submitted for one host runs in submission order on that host's thread;
    a slow or dead device only stalls its own queue.
    """

    def __init__(self, name: str):
        self._name = name
        self._workers: dict[str, ThreadPoolExecutor] = {}
        self._lock = threading.Lock()

    def submit(self, host: str, fn: Callable[..., Any], *args: Any) -> Future:
        """queue fn(*args) on host's worker; raises RuntimeError if that worker was shut down meanwhile"""
        with self._lock:
            worker = self._workers.get(host)
            if worker is None:
                worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f'{self._name}-{host}')
                self._workers[host] = worker
        return worker.submit(fn, *args)

    def stop(self, keep_hosts=()) -> None:
        """shut down the workers of all hosts not in keep_hosts, dropping their queued work"""
        with self._lock:
            stopped = [self._workers.pop(host) for host in list(self._workers) if host not in keep_hosts]
        for worker in stopped:
            worker.shutdown(wait=False, cancel_futures=True)
