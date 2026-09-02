"""Demucs v4 音源分离策略实现"""
import os
import logging
import tempfile
import subprocess
from pathlib import Path

from src.config import settings
from src.pipeline.strategies.separation.base import SeparationStrategy, SeparationResult

logger = logging.getLogger(__name__)


class DemucsStrategy(SeparationStrategy):
    """基于 Demucs v4 的人声/伴奏分离策略（模型与内存参数可配置）"""

    def _build_command(self, audio_path: str, output_dir: str, model: str) -> list[str]:
        cmd = [
            "python", "-m", "demucs",
            "--two-stems=vocals",
            "-n", model,
            "-o", output_dir,
        ]
        # --segment bounds peak memory regardless of track length (the main OOM guard on
        # CPU workers); jobs=1 avoids loading the model in several parallel processes.
        if settings.PCT_DEMUCS_SEGMENT_SECONDS > 0:
            cmd += ["--segment", str(settings.PCT_DEMUCS_SEGMENT_SECONDS)]
        if settings.PCT_DEMUCS_JOBS > 0:
            cmd += ["-j", str(settings.PCT_DEMUCS_JOBS)]
        if settings.PCT_DEMUCS_DEVICE:
            cmd += ["-d", settings.PCT_DEMUCS_DEVICE]
        cmd.append(audio_path)
        return cmd

    async def separate(self, audio_path: str) -> SeparationResult:
        """
        使用 demucs CLI 进行音源分离，提取 vocals 和 no_vocals（other+drums+bass）
        """
        model = settings.PCT_DEMUCS_MODEL
        with tempfile.TemporaryDirectory() as temp_dir:
            cmd = self._build_command(audio_path, temp_dir, model)
            logger.info(f"DemucsStrategy: Running separation: {' '.join(cmd)}")

            try:
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                logger.error(f"Demucs separation failed: {e.stderr.decode('utf-8', errors='ignore')}")
                raise RuntimeError("Audio source separation failed via Demucs.") from e

            # Demucs 输出目录结构: {temp_dir}/{model}/{stem_name}/vocals.wav, no_vocals.wav
            stem_name = Path(audio_path).stem
            output_dir = Path(temp_dir) / model / stem_name

            vocal_path = str(output_dir / "vocals.wav")
            bg_path = str(output_dir / "no_vocals.wav")

            if not os.path.exists(vocal_path):
                raise FileNotFoundError(f"Expected vocal track not found: {vocal_path}")

            return SeparationResult(
                vocal_track=vocal_path,
                background_track=bg_path if os.path.exists(bg_path) else "",
            )
