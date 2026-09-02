import tempfile
import logging
import subprocess
from pathlib import Path

from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.services.storage_service import StorageService
from src.pipeline.utils import run_sync

logger = logging.getLogger(__name__)

class TemporalAlignmentStage(StageProcessor):
    def __init__(self, next_processor: 'StageProcessor' = None):
        super().__init__(next_processor)
        self.storage_service = StorageService()

    @property
    def stage(self) -> TaskStage:
        return TaskStage.ALIGNING

    def _time_stretch_audio(self, input_path: str, output_path: str, ratio: float):
        """
        使用 FFmpeg (atempo 滤波器) 对音频进行无变调变速
        ratio > 1.0 表示加速（时间变短）
        
        BUG-10 修复：
        - atempo 单个滤波器有效范围是 [0.5, 100.0]
        - 当 ratio > 2.0 时，使用链式 atempo 滤波器（每段最大 2.0x）
        - 在边界情况下强制 clamp，防止 FFmpeg 崩溃
        """
        # 安全 clamp：最终比值限制在 [0.5, 100.0]
        ratio = max(0.5, min(ratio, 100.0))
        
        # 构建链式 atempo 滤波器（FFmpeg 单个 atempo 推荐 <= 2.0）
        atempo_filters = []
        remaining = ratio
        while remaining > 2.0:
            atempo_filters.append("atempo=2.0")
            remaining /= 2.0
        if remaining < 0.5:
            remaining = 0.5
        atempo_filters.append(f"atempo={remaining:.3f}")
        
        filter_chain = ",".join(atempo_filters)
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:a", filter_chain,
            output_path
        ]
        logger.debug(f"Running ffmpeg stretch: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg time-stretch failed: {e.stderr.decode('utf-8')}")
            raise RuntimeError("Audio temporal acceleration failed via FFmpeg.") from e

    def process(self, ctx: PipelineContext) -> PipelineContext:
        """
        时间轴对齐核心逻辑：
        1. 遍历所有的 synth_segments (合成音频切片)
        2. 基于 orig_start 与 游标 cursor 计算推移和加速补偿
        3. 对超长句子（<=1.3倍）进行 FFmpeg 物理加速
        4. 记录绝对对齐时间 start/end 给下一步混音使用
        """
        if not ctx.synth_segments or not ctx.segments:
            raise RuntimeError("Temporal alignment cannot run because segments or synthesized audio clips are missing.")

        logger.info(f"Task {ctx.task_id}: Starting Temporal Alignment Stage...")

        # 用于映射原生时间参考的字典
        orig_segments_map = { i: seg for i, seg in enumerate(ctx.segments) }
        
        current_end_cursor = 0.0

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)

            for synth in ctx.synth_segments:
                seg_id = synth.get("segment_id")
                orig_url = synth.get("audio_url")
                synth_dur = synth.get("duration", 0.0)

                orig_seg = orig_segments_map.get(seg_id)
                if not orig_seg or not orig_url:
                    continue

                orig_start = orig_seg.get("start", 0.0)
                orig_end = orig_seg.get("end", 0.0)
                orig_dur = orig_end - orig_start
                # BUG-10 修复：防止除零或极短片段导致 ratio 爆炸
                orig_dur = max(orig_dur, 0.1)

                # 我们保证这段新声音绝对不会和上一句声音打架交叠，
                # 也绝不会比原来该说话的人的启动时间更早
                aligned_start = max(orig_start, current_end_cursor)
                
                final_dur = synth_dur
                final_audio_url = orig_url

                # 时长超标处理
                if synth_dur > orig_dur:
                    ratio = synth_dur / orig_dur
                    
                    if ratio <= 1.3:
                        # 启动加速挤压逻辑：下载 -> FFmpeg 加速 -> 顶替源文件
                        logger.info(f"Task {ctx.task_id}: Segment {seg_id} is slightly long (ratio {ratio:.2f}). Compressing.")
                        
                        synth_ext = Path(orig_url).suffix or ".mp3"
                        local_orig_path = temp_dir_path / f"orig_synth_{seg_id}{synth_ext}"
                        local_stretched_path = temp_dir_path / f"stretched_synth_{seg_id}{synth_ext}"
                        
                        run_sync(self.storage_service.download_file(orig_url, str(local_orig_path)))
                        
                        # atempo 的倍率计算：要让时间变短（即 synth_dur 压缩到 orig_dur），倍率应 > 1
                        atempo_val = synth_dur / orig_dur
                        self._time_stretch_audio(str(local_orig_path), str(local_stretched_path), atempo_val)
                        
                        updated_object_name = f"{ctx.task_id}/synths/seg_{seg_id}_stretched{synth_ext}"
                        run_sync(self.storage_service.upload_file(
                            local_path=str(local_stretched_path),
                            object_name=updated_object_name,
                            content_type="audio/mpeg" if synth_ext.lower() == ".mp3" else "audio/wav"
                        ))
                        
                        final_audio_url = updated_object_name
                        final_dur = orig_dur  # 它现在完美适配了原本期待的时间大小
                    else:
                        # 对于极其长的情况：保留原速，这会导致 current_end_cursor 大幅延后
                        logger.warning(f"Task {ctx.task_id}: Segment {seg_id} is extremely long (ratio {ratio:.2f}). Triggering Timeline Shift.")
                        final_dur = synth_dur

                aligned_end = aligned_start + final_dur
                current_end_cursor = aligned_end

                # 保存黄金参数
                synth["aligned_start"] = aligned_start
                synth["aligned_end"] = aligned_end
                synth["audio_url"] = final_audio_url
                synth["duration"] = final_dur
                
                logger.debug(f"Segment {seg_id}: Aligned [{aligned_start:.2f} -> {aligned_end:.2f}] (Original [{orig_start:.2f} -> {orig_end:.2f}])")

        logger.info(f"Task {ctx.task_id}: Temporal Alignment completed.")
        return ctx
