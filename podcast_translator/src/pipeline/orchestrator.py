import logging

from src.core.provider_errors import TaskPausedError
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.stages.s1_source_separation import SourceSeparationStage
from src.pipeline.stages.s2_speaker_diarization import SpeakerDiarizationStage
from src.pipeline.stages.s3_asr_transcription import ASRTranscriptionStage
from src.pipeline.stages.s4_translation import TranslationStage
from src.pipeline.stages.s5_voice_clone_tts import CosyVoiceTTSStage
from src.pipeline.stages.s6_temporal_alignment import TemporalAlignmentStage
from src.pipeline.stages.s7_final_mixing import FinalMixingStage

logger = logging.getLogger(__name__)

class PipelineError(Exception):
    """Pipeline 执行全生命周期中发生的严重异常的封装"""
    pass

class PodcastTranslatorPipeline:
    def __init__(self, start_stage: TaskStage = TaskStage.SEPARATING):
        """
        初始化管线统筹编排器
        :param start_stage: 支持指定启动节点，实现由于挂起导致的“断点续装”
        """
        self.start_stage = start_stage
        self.head_processor = self._build_chain()

    def _build_chain(self):
        """利用责任链模式动态倒序组装 Pipeline 的对象模型"""
        
        # 预制完整的流水线节点蓝图（注意：按执行顺序列出）
        blueprint = [
            (TaskStage.SEPARATING, SourceSeparationStage),
            (TaskStage.DIARIZING, SpeakerDiarizationStage),
            (TaskStage.TRANSCRIBING, ASRTranscriptionStage),
            (TaskStage.TRANSLATING, TranslationStage),
            (TaskStage.SYNTHESIZING, CosyVoiceTTSStage),
            (TaskStage.ALIGNING, TemporalAlignmentStage),
            (TaskStage.MIXING, FinalMixingStage),
        ]
        
        # 截断无需执行的早期步骤，保留断点之后的流水线
        active_blueprint = []
        started = False
        for st, PClass in blueprint:
            if st == self.start_stage:
                started = True
            if started:
                active_blueprint.append(PClass)
                
        if not active_blueprint:
            raise ValueError(f"Invalid start_stage [{self.start_stage}]: No stages to execute.")
            
        # 倒序实例化并链接下一节点 (next_processor)
        current_head = None
        for PClass in reversed(active_blueprint):
            # 新实例化出来的节点通过参数吸纳之前构建的 current_head 以此成链
            current_head = PClass(next_processor=current_head)
            
        return current_head

    def execute_task(self, ctx: PipelineContext) -> PipelineContext:
        """
        全生命循环执行器入口
        """
        logger.info(f"=== Starting Podcast Translator Pipeline for Task: {ctx.task_id} ===")
        logger.info(f"Initial Stage: {self.start_stage.name}")
        
        ctx.status = "PROCESSING"
        
        try:
            # 引爆责任链的头部，启动击鼓传花
            final_ctx = self.head_processor.execute(ctx)
            
            final_ctx.status = "COMPLETED"
            logger.info(f"=== Pipeline COMPLETED successfully for Task: {final_ctx.task_id} ===")
            logger.info(f"Final Artifact URL: {final_ctx.output_audio_url}")
            
            return final_ctx
            
        except TaskPausedError:
            ctx.status = "PAUSED"
            logger.warning("=== Pipeline PAUSED for Task: %s ===", ctx.task_id)
            raise
        except Exception as e:
            # 剥离系统错误堆栈并做宏观错误日志收容
            error_msg = f"Fatal system halt during pipeline traversal. Detail: {str(e)}"
            logger.error(f"=== Pipeline FAILED for Task: {ctx.task_id} ===")
            logger.error(error_msg)
            
            ctx.status = "FAILED"
            raise PipelineError(error_msg) from e
