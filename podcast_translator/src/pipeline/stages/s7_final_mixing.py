import tempfile
import logging
from pathlib import Path
from pydub import AudioSegment

from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.services.storage_service import StorageService
from src.pipeline.utils import run_sync

logger = logging.getLogger(__name__)

class FinalMixingStage(StageProcessor):
    def __init__(self, next_processor: 'StageProcessor' = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()

    @property
    def stage(self) -> TaskStage:
        return TaskStage.MIXING

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        final_obj_name = f"{ctx.task_id}/output/final_podcast.mp3"
        if ctx.output_audio_url != final_obj_name:
            return False

        try:
            if not run_sync(self.storage_service.object_exists(final_obj_name)):
                return False
        except Exception:
            logger.warning("Task %s: failed to check final mix artifact.", ctx.task_id, exc_info=True)
            return False

        ctx.output_audio_url = final_obj_name
        logger.info("Task %s: reusing existing final mix.", ctx.task_id)
        return True

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        最终混音操作：
        1. 下载背景纯音乐和全部新配音段落
        2. 背景循环填充与音量衰减
        3. 对齐合成配音贴片
        4. 压制最终作品 mp3 并上传
        """
        if not ctx.synth_segments:
            raise RuntimeError("Final mixing cannot run because no synthesized audio clips were generated.")
            
        bg_url = ctx.background_track_url
        if not bg_url:
            logger.warning(f"Task {ctx.task_id}: No background track provided. Mixing dry vocals only.")

        logger.info(f"Task {ctx.task_id}: Starting Final Mixing Stage...")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            
            # 1. 尝试拉取伴奏大轨
            bg_audio = None
            if bg_url:
                local_bg_path = temp_dir_path / "background.wav"
                try:
                    logger.info(f"Task {ctx.task_id}: Downloading background track...")
                    # 避免有些背景音乐未提供原始扩展名的情况，由 pydub 自适应解析
                    run_sync(self.storage_service.download_file(bg_url, str(local_bg_path)))
                    bg_audio = AudioSegment.from_file(str(local_bg_path))
                    # 【核心保护机制】：纯背景音自动降噪压限 -8 分贝，以免听不到新配音人声
                    bg_audio = bg_audio - 8
                except Exception as e:
                    logger.error(f"Failed to load background track {bg_url}: {e}")
                    bg_audio = None
            
            # 2. 定位最终母带所需的绝对长度 (毫秒)
            #    BUG-13 修复：始终以最后一个 vocal segment 的结束时间为基准
            #    背景音乐不应决定最终成品长度（原来会导致大段空白尾部）
            max_vocal_end_sec = 0.0
            for synth in ctx.synth_segments:
                if synth.get("aligned_end", 0) > max_vocal_end_sec:
                    max_vocal_end_sec = synth["aligned_end"]
            
            # 尾部给予 2秒 优雅静音白场收尾
            required_dur_ms = int(max_vocal_end_sec * 1000) + 2000
            
            # 产生绝对空白静音层（画布主轨）
            canvas = AudioSegment.silent(duration=required_dur_ms)
            
            # 3. 铺设伴奏大轨 (带有 loop=True 机制填满推移引起的留白)
            if bg_audio:
                logger.info(f"Task {ctx.task_id}: Overlaying localized background track with ducking and looping limit.")
                canvas = canvas.overlay(bg_audio, position=0, loop=True)
                
            # 4. 下载并依循时间线贴图拼贴人声片段
            logger.info(f"Task {ctx.task_id}: Downloading and assembling {len(ctx.synth_segments)} vocal overlays...")
            
            for synth in ctx.synth_segments:
                audio_url = synth.get("audio_url")
                aligned_start = synth.get("aligned_start", 0.0)
                seg_id = synth.get("segment_id", "unk")
                
                if not audio_url:
                    continue
                    
                synth_ext = Path(audio_url).suffix or ".mp3"
                local_synth_path = temp_dir_path / f"synth_{seg_id}{synth_ext}"
                try:
                    run_sync(self.storage_service.download_file(audio_url, str(local_synth_path)))
                    vocal_audio = AudioSegment.from_file(str(local_synth_path))
                    
                    # 按时间坐标转为毫秒并将其钉在主环境音轨上
                    pos_ms = int(aligned_start * 1000)
                    canvas = canvas.overlay(vocal_audio, position=pos_ms)
                except Exception as e:
                    logger.error(f"Task {ctx.task_id}: Failed to overlay segment {seg_id}: {e}")
                    
            # 5. 母带压制并导出
            final_mp3_path = temp_dir_path / "final_podcast.mp3"
            logger.info(f"Task {ctx.task_id}: Compressing and exporting final MP3 Master (192kbps)...")
            canvas.export(str(final_mp3_path), format="mp3", bitrate="192k")
            
            final_obj_name = f"{ctx.task_id}/output/final_podcast.mp3"
            run_sync(self.storage_service.upload_file(
                local_path=str(final_mp3_path),
                object_name=final_obj_name,
                content_type="audio/mpeg"
            ))
            
            ctx.output_audio_url = final_obj_name
            logger.info(f"Task {ctx.task_id}: Final mixing successful! Pipeline completely finished. Product: {ctx.output_audio_url}")

        return ctx
