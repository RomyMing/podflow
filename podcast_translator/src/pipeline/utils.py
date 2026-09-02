"""
Pipeline 公共工具模块。

提供统一的同步 -> 异步桥接能力，避免在 Celery worker 的同步执行路径里
反复创建和销毁 event loop，导致数据库连接池或异步客户端跨 loop 复用。
"""

import asyncio
import atexit
import logging
import threading
from collections.abc import Coroutine
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_background_loop: asyncio.AbstractEventLoop | None = None
_background_thread: threading.Thread | None = None
_background_loop_ready = threading.Event()
_background_loop_lock = threading.Lock()


def _background_loop_worker() -> None:
    global _background_loop

    loop = asyncio.new_event_loop()
    _background_loop = loop
    asyncio.set_event_loop(loop)
    loop.call_soon(_background_loop_ready.set)

    try:
        loop.run_forever()
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        asyncio.set_event_loop(None)
        loop.close()
        _background_loop = None


def _ensure_background_loop() -> asyncio.AbstractEventLoop:
    global _background_thread

    with _background_loop_lock:
        if _background_loop is not None and _background_loop.is_running():
            return _background_loop

        _background_loop_ready.clear()
        _background_thread = threading.Thread(
            target=_background_loop_worker,
            name="podcast-translator-asyncio",
            daemon=True,
        )
        _background_thread.start()

    _background_loop_ready.wait()

    if _background_loop is None:
        raise RuntimeError("Failed to initialize the shared background event loop.")

    return _background_loop


def _close_coro_safely(coro: Coroutine[Any, Any, T]) -> None:
    try:
        coro.close()
    except RuntimeError:
        # 部分已开始执行的协程可能无法再次关闭，直接忽略即可。
        pass


def _shutdown_background_loop() -> None:
    loop = _background_loop
    thread = _background_thread

    if loop is None or not loop.is_running():
        return

    loop.call_soon_threadsafe(loop.stop)
    if thread is not None and thread.is_alive():
        thread.join(timeout=1)


atexit.register(_shutdown_background_loop)


def run_sync(coro: Coroutine[Any, Any, T]) -> T:
    """
    在同步上下文中安全地执行单个异步协程。

    这里统一复用进程级后台 event loop，而不是为每次调用单独执行
    `asyncio.run()`。这样可以避免 asyncpg / aioboto3 等异步资源在多个
    event loop 之间来回切换，引发 "attached to a different loop" 异常。
    """
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    loop = _ensure_background_loop()

    if current_loop is loop:
        _close_coro_safely(coro)
        raise RuntimeError("run_sync() cannot be called from within its managed event loop.")

    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()
