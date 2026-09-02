"""Independent task heartbeat process.

This process is intentionally separate from the Celery prefork child so native CPU/GPU calls
cannot starve the liveness heartbeat by holding the Python GIL.
"""

import argparse
import os
import signal
import threading

from src.workers.task_liveness import refresh_task_ownership


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--parent-pid", required=True, type=int)
    parser.add_argument("--interval", required=True, type=int)
    parser.add_argument("--lock-ttl", required=True, type=int)
    parser.add_argument("--heartbeat-ttl", required=True, type=int)
    args = parser.parse_args()

    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())

    while not stopped.is_set():
        if os.getppid() != args.parent_pid:
            return 0
        renewed = refresh_task_ownership(
            args.task_id,
            args.owner,
            args.lock_ttl,
            args.heartbeat_ttl,
        )
        if renewed is False:
            return 2
        stopped.wait(max(5, args.interval))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
