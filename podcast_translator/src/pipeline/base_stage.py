import logging
from abc import ABC, abstractmethod
from typing import Any

from src.core.redis import publish_task_progress_message
from src.pipeline.checkpoint import PipelineCheckpointManager
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.pause import raise_if_user_paused
from src.pipeline.progress import get_overall_progress, get_stage_progress

logger = logging.getLogger(__name__)


class StageProcessor(ABC):
    def __init__(self, next_processor: "StageProcessor" = None):
        self._next = next_processor
        self._checkpoint_manager = PipelineCheckpointManager()

    def execute(self, ctx: PipelineContext) -> PipelineContext:
        raise_if_user_paused(ctx.task_id, self.stage)
        self._update_status(ctx, self.stage)
        try:
            if self._restore_completed_stage(ctx):
                logger.info("[Resume] Task [%s] skipped completed stage %s", ctx.task_id, self.stage.value)
            else:
                ctx = self.process(ctx)
            invalidated_stages = getattr(ctx, "invalidated_stages", None)
            if invalidated_stages is not None:
                invalidated_stages.discard(self.stage.value)
            self._persist_stage_state(ctx)
            self._save_stage_checkpoint(ctx)
            self._report_progress(ctx, 100)
        except Exception as exc:
            self._handle_failure(ctx, exc)
            raise

        if self._next:
            return self._next.execute(ctx)
        return ctx

    @abstractmethod
    def process(self, ctx: PipelineContext) -> PipelineContext:
        pass

    @property
    @abstractmethod
    def stage(self) -> TaskStage:
        pass

    def _get_lifecycle_hooks(self, ctx: PipelineContext) -> Any:
        return getattr(ctx, "lifecycle_hooks", None)

    def _persist_stage_state(self, ctx: PipelineContext) -> None:
        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_stage_completed"):
            hooks.on_stage_completed(self.stage, ctx)

    def _restore_completed_stage(self, ctx: PipelineContext) -> bool:
        invalidated_stages = getattr(ctx, "invalidated_stages", set()) or set()
        if self.stage.value in invalidated_stages:
            logger.info(
                "[Resume] Task [%s] stage %s was invalidated; running stage normally.",
                ctx.task_id,
                self.stage.value,
            )
            return False

        if self._checkpoint_manager.load_stage(ctx, self.stage):
            if self.restored_stage_is_valid(ctx):
                return True
            logger.warning(
                "[Resume] Task [%s] checkpoint for stage %s is invalid; running stage normally.",
                ctx.task_id,
                self.stage.value,
            )
            return False
        return self.restore_from_artifacts(ctx)

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        return False

    def restored_stage_is_valid(self, ctx: PipelineContext) -> bool:
        return True

    def _save_stage_checkpoint(self, ctx: PipelineContext) -> None:
        self._checkpoint_manager.save_stage(ctx, self.stage)

    def _update_status(self, ctx: PipelineContext, stage: TaskStage) -> None:
        logger.info("[Stage] Task [%s] => %s", ctx.task_id, stage.name)

        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_stage_started"):
            hooks.on_stage_started(stage)
            return

        publish_task_progress_message(
            task_id=ctx.task_id,
            stage=stage.value,
            progress_percent=get_stage_progress(stage),
            status="processing",
            event="stage_started",
        )

    def _report_progress(self, ctx: PipelineContext, progress: int) -> None:
        logger.info("[Progress] Task [%s] => %s%%", ctx.task_id, progress)

        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_stage_progress"):
            hooks.on_stage_progress(self.stage, progress)
            return

        publish_task_progress_message(
            task_id=ctx.task_id,
            stage=self.stage.value,
            progress_percent=get_overall_progress(self.stage, progress),
            status="processing",
            event="stage_progress",
        )

    def _report_items_progress(
        self,
        ctx: PipelineContext,
        *,
        items_total: int | None = None,
        items_done: int | None = None,
        cost_estimate: float | None = None,
        processed_seconds: float | None = None,
        total_seconds: float | None = None,
        chunk_index: int | None = None,
        chunk_count: int | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_stage_items_progress"):
            hooks.on_stage_items_progress(
                self.stage,
                items_total=items_total,
                items_done=items_done,
                cost_estimate=cost_estimate,
                processed_seconds=processed_seconds,
                total_seconds=total_seconds,
                chunk_index=chunk_index,
                chunk_count=chunk_count,
                metrics=metrics,
            )

    def _handle_failure(self, ctx: PipelineContext, exc: Exception) -> None:
        logger.error("[FATAL] Task [%s] failed at %s: %s", ctx.task_id, self.stage.name, str(exc))

        hooks = self._get_lifecycle_hooks(ctx)
        if hooks and hasattr(hooks, "on_stage_failed"):
            hooks.on_stage_failed(self.stage, str(exc))
            return

        publish_task_progress_message(
            task_id=ctx.task_id,
            stage=self.stage.value,
            progress_percent=get_stage_progress(self.stage),
            status="failed",
            error_message=str(exc),
            event="stage_failed",
        )
