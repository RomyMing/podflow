import subprocess
import tempfile
import logging
from pathlib import Path

from src.config import settings
from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.services.storage_service import StorageService
from src.pipeline.utils import run_sync

logger = logging.getLogger(__name__)

class SourceSeparationStage(StageProcessor):
    def __init__(self, next_processor: 'StageProcessor' = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()

    @property
    def stage(self) -> TaskStage:
        return TaskStage.SEPARATING

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        vocal_object_name = f"{ctx.task_id}/vocals.wav"
        bg_object_name = f"{ctx.task_id}/no_vocals.wav"
        try:
            has_vocals = run_sync(self.storage_service.object_exists(vocal_object_name))
            has_bg = run_sync(self.storage_service.object_exists(bg_object_name))
        except Exception:
            logger.warning("Task %s: failed to check separated track artifacts.", ctx.task_id, exc_info=True)
            return False

        if not (has_vocals and has_bg):
            return False

        ctx.vocal_track_url = vocal_object_name
        ctx.background_track_url = bg_object_name
        logger.info("Task %s: reusing existing separated tracks.", ctx.task_id)
        return True

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        音源分离核心处理逻辑
        1. 下载源音频
        2. 使用 demucs 分离出人声和背景音
        3. 上传分离后的音频到存储服务
        4. 更新并返回上下文
        """
        if not ctx.source_audio_url:
            raise ValueError(f"Task {ctx.task_id}: source_audio_url is missing in context.")

        logger.info(f"Task {ctx.task_id}: Starting source separation (Demucs)...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            source_ext = Path(ctx.source_audio_url).suffix or ".wav"
            local_source_path = temp_dir_path / f"source{source_ext}"

            # 1. 下载源音频
            logger.info(f"Task {ctx.task_id}: Downloading source audio {ctx.source_audio_url}...")
            run_sync(self.storage_service.download_file(
                object_name=ctx.source_audio_url,
                dest_path=str(local_source_path)
            ))

            # 2. 执行 Demucs
            output_dir = temp_dir_path / "demucs_output"
            output_dir.mkdir(exist_ok=True)
            
            logger.info(f"Task {ctx.task_id}: Running Demucs CLI...")
            # demucs -n <model> --two-stems vocals <file> -o <outdir>
            # --segment 限制峰值内存（CPU worker 上避免 OOM 的关键），-j 1 避免并行加载多份模型。
            # 注意：如果环境中没有 GPU，推理可能会耗时较长
            model = settings.PCT_DEMUCS_MODEL
            cmd = [
                "demucs",
                "-n", model,
                "--two-stems", "vocals",
                "-o", str(output_dir),
            ]
            if settings.PCT_DEMUCS_SEGMENT_SECONDS > 0:
                cmd += ["--segment", str(settings.PCT_DEMUCS_SEGMENT_SECONDS)]
            if settings.PCT_DEMUCS_JOBS > 0:
                cmd += ["-j", str(settings.PCT_DEMUCS_JOBS)]
            if settings.PCT_DEMUCS_DEVICE:
                cmd += ["-d", settings.PCT_DEMUCS_DEVICE]
            cmd.append(str(local_source_path))

            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"Task {ctx.task_id}: Demucs execution failed: {e.stderr}")
                raise RuntimeError(f"Demucs processing failed: {e.stderr}") from e

            # Demucs 默认输出结构: <output_dir>/<model>/<filename_without_ext>/{vocals.wav, no_vocals.wav}
            base_name = local_source_path.stem
            demucs_result_dir = output_dir / model / base_name
            
            local_vocals_path = demucs_result_dir / "vocals.wav"
            local_bg_path = demucs_result_dir / "no_vocals.wav"

            if not local_vocals_path.exists() or not local_bg_path.exists():
                raise FileNotFoundError(f"Task {ctx.task_id}: Demucs output files not found at {demucs_result_dir}")

            # 3. 上传分离出来的音频
            vocal_object_name = f"{ctx.task_id}/vocals.wav"
            bg_object_name = f"{ctx.task_id}/no_vocals.wav"

            logger.info(f"Task {ctx.task_id}: Uploading separated tracks...")
            run_sync(self.storage_service.upload_file(
                local_path=str(local_vocals_path),
                object_name=vocal_object_name,
                content_type="audio/wav"
            ))
            
            run_sync(self.storage_service.upload_file(
                local_path=str(local_bg_path),
                object_name=bg_object_name,
                content_type="audio/wav"
            ))

            # 4. 更新上下文属性
            ctx.vocal_track_url = vocal_object_name
            ctx.background_track_url = bg_object_name
            logger.info(f"Task {ctx.task_id}: Source separation completed successfully.")
            
            return ctx
