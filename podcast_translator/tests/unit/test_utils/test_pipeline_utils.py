import asyncio

import pytest

from src.pipeline.utils import run_sync


class _LoopBoundFutureHolder:
    def __init__(self) -> None:
        self.future: asyncio.Future[str] | None = None

    async def create_future(self) -> None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        future.set_result("ok")
        self.future = future

    async def await_future(self) -> str:
        if self.future is None:
            raise AssertionError("future not initialized")
        return await self.future


def test_run_sync_reuses_the_same_background_loop_across_calls() -> None:
    holder = _LoopBoundFutureHolder()

    run_sync(holder.create_future())

    assert run_sync(holder.await_future()) == "ok"


@pytest.mark.asyncio
async def test_run_sync_uses_dedicated_loop_when_caller_already_has_running_loop() -> None:
    caller_loop_id = id(asyncio.get_running_loop())

    async def get_loop_id() -> int:
        return id(asyncio.get_running_loop())

    managed_loop_id = run_sync(get_loop_id())

    assert managed_loop_id != caller_loop_id
