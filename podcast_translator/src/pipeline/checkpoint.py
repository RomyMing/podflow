import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.utils import run_sync
from src.services.storage_service import StorageService

logger = logging.getLogger(__name__)


CONTEXT_FIELDS = (
    "task_id",
    "source_audio_url",
    "status",
    "error_message",
    "source_language",
    "target_language",
    "config",
    "vocal_track_url",
    "background_track_url",
    "speakers",
    "segments",
    "synth_segments",
    "output_audio_url",
    "invalidated_stages",
)


def checkpoint_object_name(task_id: str, stage: TaskStage) -> str:
    return f"{task_id}/checkpoints/{stage.value}.json"


def context_to_dict(ctx: PipelineContext) -> dict[str, Any]:
    data = {field: getattr(ctx, field) for field in CONTEXT_FIELDS}
    data["invalidated_stages"] = sorted(data.get("invalidated_stages") or [])
    return data


def apply_context_dict(ctx: PipelineContext, data: dict[str, Any]) -> PipelineContext:
    for field in CONTEXT_FIELDS:
        if field in data:
            if field == "invalidated_stages":
                setattr(ctx, field, set(data[field] or []))
            else:
                setattr(ctx, field, data[field])
    return ctx


class PipelineCheckpointManager:
    def __init__(self, storage_service: StorageService | None = None):
        self.storage_service = storage_service or StorageService()

    def load_stage(self, ctx: PipelineContext, stage: TaskStage) -> bool:
        object_name = checkpoint_object_name(ctx.task_id, stage)
        try:
            if not run_sync(self.storage_service.object_exists(object_name)):
                return False

            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = Path(temp_dir) / "checkpoint.json"
                run_sync(self.storage_service.download_file(object_name, str(local_path)))
                data = json.loads(local_path.read_text(encoding="utf-8"))

            apply_context_dict(ctx, data.get("context") or {})
            logger.info(
                "Task %s: restored %s from checkpoint %s.",
                ctx.task_id,
                stage.value,
                object_name,
            )
            return True
        except Exception:
            logger.warning(
                "Task %s: failed to load checkpoint for %s; running stage normally.",
                ctx.task_id,
                stage.value,
                exc_info=True,
            )
            return False

    def save_stage(self, ctx: PipelineContext, stage: TaskStage) -> None:
        object_name = checkpoint_object_name(ctx.task_id, stage)
        payload = {
            "stage": stage.value,
            "context": context_to_dict(ctx),
        }

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                local_path = Path(temp_dir) / "checkpoint.json"
                local_path.write_text(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                run_sync(
                    self.storage_service.upload_file(
                        local_path=str(local_path),
                        object_name=object_name,
                        content_type="application/json",
                    )
                )
            logger.info("Task %s: saved checkpoint for %s.", ctx.task_id, stage.value)
        except Exception:
            logger.warning(
                "Task %s: failed to save checkpoint for %s; continuing.",
                ctx.task_id,
                stage.value,
                exc_info=True,
            )
