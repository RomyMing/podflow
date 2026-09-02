import json
import logging
from typing import List

from src.config import settings
from src.core.provider_errors import TaskPausedError, pause_for_provider_error
from src.pipeline.base_stage import StageProcessor
from src.pipeline.context import PipelineContext, TaskStage
from src.pipeline.utils import run_sync
from src.services.user_api_key_service import resolve_provider_credentials_sync

logger = logging.getLogger(__name__)


class TranslationBatchError(RuntimeError):
    pass


class TranslationStage(StageProcessor):
    LANGUAGE_NAMES = {
        "en": "English",
        "zh": "Chinese (Simplified)",
        "ja": "Japanese",
        "ko": "Korean",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "ru": "Russian",
        "pt": "Portuguese",
        "ar": "Arabic",
    }

    def __init__(self, next_processor: "StageProcessor" = None):
        super().__init__(next_processor)
        self.translation_provider = settings.PCT_TRANSLATION_PROVIDER
        self.openai_client = None
        self.deepseek_client = None
        self.async_openai_cls = None
        self._clients_ready = False

        if settings.PCT_OPENAI_API_KEY or settings.PCT_DEEPSEEK_API_KEY:
            try:
                from openai import AsyncOpenAI

                self.async_openai_cls = AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai package is required for configured translation providers."
                ) from exc

    @property
    def stage(self) -> TaskStage:
        return TaskStage.TRANSLATING

    def restore_from_artifacts(self, ctx: PipelineContext) -> bool:
        if not ctx.segments:
            return False
        if not self._translations_are_complete(ctx):
            return False

        logger.info("Task %s: reusing persisted translations for %s segments.", ctx.task_id, len(ctx.segments))
        return True

    def restored_stage_is_valid(self, ctx: PipelineContext) -> bool:
        return self._translations_are_complete(ctx)

    def _translations_are_complete(self, ctx: PipelineContext) -> bool:
        if not ctx.segments:
            return False

        source_lang = ctx.source_language or "en"
        target_lang = ctx.target_language or "zh"
        for segment in ctx.segments:
            if self._segment_needs_translation(segment, source_lang, target_lang):
                return False
        return True

    def _segment_needs_translation(self, segment: dict, source_lang: str, target_lang: str) -> bool:
        original = str(segment.get("text") or "")
        translation = str(segment.get("translation") or "")
        if original.strip() and not translation.strip():
            return True
        return self._looks_untranslated(original, translation, source_lang, target_lang)

    def _build_system_prompt(self, source_lang: str, target_lang: str) -> str:
        source_name = self.LANGUAGE_NAMES.get(source_lang, source_lang)
        target_name = self.LANGUAGE_NAMES.get(target_lang, target_lang)
        return (
            "You are a professional podcast translator. "
            f"Translate the provided {source_name} dialogue segments into fluent, natural {target_name}. "
            "Preserve conversational tone, emotion, and speaker intent. "
            "The user message is a JSON array of objects with 'id' and 'text'. "
            "Return only a JSON object with exactly one key named 'translations'. "
            "The value must be an array with exactly one item per input object, without merging, splitting, "
            "omitting, summarizing, or reordering any segment. "
            "Each item must be an object with the same 'id' and a 'translation' string. "
            'Example: {"translations": [{"id": 0, "translation": "translated sentence 1"}]}'
        )

    def _resolve_translation_provider(self, ctx: PipelineContext) -> str:
        config = getattr(ctx, "config", None) or {}
        provider = str(config.get("translation_provider") or settings.PCT_TRANSLATION_PROVIDER).strip().lower()
        if provider not in {"openai", "deepseek"}:
            logger.warning(
                "Task %s: unsupported translation provider '%s'; falling back to %s.",
                ctx.task_id,
                provider,
                settings.PCT_TRANSLATION_PROVIDER,
            )
            return settings.PCT_TRANSLATION_PROVIDER
        return provider

    def _configure_clients(self, ctx: PipelineContext) -> None:
        self.translation_provider = self._resolve_translation_provider(ctx)

        if getattr(self, "async_openai_cls", None) is None:
            try:
                from openai import AsyncOpenAI

                self.async_openai_cls = AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai package is required for configured translation providers."
                ) from exc

        translation_provider = getattr(self, "translation_provider", settings.PCT_TRANSLATION_PROVIDER)
        if translation_provider == "deepseek":
            credentials = resolve_provider_credentials_sync(ctx.user_id, "deepseek")
            if credentials is None:
                raise TaskPausedError(
                    "DeepSeek API key is not configured. Add it in Profile > API management.",
                    provider="deepseek",
                    reason_code="provider_credentials_missing",
                    stage=self.stage,
                )
            self.deepseek_client = self.async_openai_cls(
                api_key=credentials.api_key,
                base_url=credentials.base_url or "https://api.deepseek.com",
            )
            return

        credentials = resolve_provider_credentials_sync(ctx.user_id, "openai")
        if credentials is None:
            raise TaskPausedError(
                "OpenAI API key is not configured. Add it in Profile > API management.",
                provider="openai",
                reason_code="provider_credentials_missing",
                stage=self.stage,
            )
        self.openai_client = self.async_openai_cls(
            api_key=credentials.api_key,
            base_url=credentials.base_url,
        )

    def _ensure_clients_configured(self, ctx: PipelineContext) -> None:
        """Resolve provider credentials once per stage instance.

        ``_configure_clients`` issues a (sync) DB lookup and may raise ``TaskPausedError``,
        so it must run exactly once even when the stage translates many slices (the
        long-audio overlap path calls ``translate_segments`` per chunk). Stages built via
        ``object.__new__`` in tests have no ``translation_provider`` attribute and skip
        configuration, matching the historical ``process`` guard.
        """
        if getattr(self, "_clients_ready", False):
            return
        if hasattr(self, "translation_provider"):
            self._configure_clients(ctx)
        self._clients_ready = True

    def _provider_client_and_model(self):
        if getattr(self, "translation_provider", settings.PCT_TRANSLATION_PROVIDER) == "deepseek":
            return "DEEPSEEK", self.deepseek_client, "deepseek-chat"
        return "OPENAI", self.openai_client, "gpt-4o"

    async def _call_llm_for_batch(self, segments_batch: List[str], system_prompt: str) -> List[str] | None:
        user_payload = [{"id": index, "text": text} for index, text in enumerate(segments_batch)]
        user_content = json.dumps(user_payload, ensure_ascii=False)
        provider, client, model = self._provider_client_and_model()

        logger.info("Calling translation provider %s with model %s", provider, model)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        raw_result = response.choices[0].message.content or ""
        logger.info("Translation batch success via %s", provider)

        try:
            return self._parse_translation_response(raw_result, len(segments_batch))
        except TranslationBatchError as exc:
            logger.error("Failed to parse translation output from %s: %s", provider, exc)
            logger.debug("Raw translation output from %s: %s", provider, raw_result)
            return None

    def _parse_translation_response(self, raw_result: str, expected_count: int) -> List[str]:
        try:
            parsed = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise TranslationBatchError(str(exc)) from exc

        translated_arr = parsed.get("translations") if isinstance(parsed, dict) else None
        if not isinstance(translated_arr, list):
            raise TranslationBatchError("Missing translations array")

        if not translated_arr and expected_count:
            raise TranslationBatchError(f"Mismatch array lengths: input {expected_count}, output 0")

        if all(isinstance(item, str) for item in translated_arr):
            if len(translated_arr) != expected_count:
                raise TranslationBatchError(
                    f"Mismatch array lengths: input {expected_count}, output {len(translated_arr)}"
                )
            return [str(item) for item in translated_arr]

        translations_by_id: dict[int, str] = {}
        for item in translated_arr:
            if not isinstance(item, dict):
                raise TranslationBatchError("Translation items must be strings or objects")
            item_id = item.get("id", item.get("index"))
            if isinstance(item_id, str) and item_id.isdigit():
                item_id = int(item_id)
            translation = item.get("translation")
            if translation is None:
                translation = item.get("text")
            if not isinstance(item_id, int) or not isinstance(translation, str):
                raise TranslationBatchError("Translation object must contain integer id and string translation")
            if item_id in translations_by_id:
                raise TranslationBatchError(f"Duplicate translation id: {item_id}")
            translations_by_id[item_id] = translation

        expected_ids = set(range(expected_count))
        actual_ids = set(translations_by_id)
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)
            extra = sorted(actual_ids - expected_ids)
            raise TranslationBatchError(f"Translation id mismatch: missing={missing}, extra={extra}")

        return [translations_by_id[index] for index in range(expected_count)]

    def _looks_untranslated(self, original: str, translation: str, source_lang: str, target_lang: str) -> bool:
        if source_lang == target_lang:
            return False

        original_norm = " ".join(original.split()).strip().lower()
        translation_norm = " ".join(translation.split()).strip().lower()
        if not original_norm or not translation_norm:
            return False

        alpha_count = sum(char.isalpha() for char in original_norm)
        word_count = len(original_norm.split())
        if original_norm == translation_norm and (alpha_count >= 12 or word_count >= 3):
            return True

        if target_lang == "zh":
            has_cjk = any("\u4e00" <= char <= "\u9fff" for char in translation)
            if not has_cjk and alpha_count >= 12 and word_count >= 3:
                return True

        return False

    def _validate_translations(
        self,
        originals: List[str],
        translations: List[str],
        source_lang: str,
        target_lang: str,
    ) -> None:
        if len(translations) != len(originals):
            raise TranslationBatchError(
                f"Mismatch array lengths: input {len(originals)}, output {len(translations)}"
            )

        for index, (original, translation) in enumerate(zip(originals, translations)):
            if original.strip() and not str(translation or "").strip():
                raise TranslationBatchError(f"Empty translation for segment {index}")
            if self._looks_untranslated(original, str(translation or ""), source_lang, target_lang):
                raise TranslationBatchError(f"Segment {index} appears untranslated")

    def _translate_non_empty_texts(
        self,
        texts: List[str],
        system_prompt: str,
        source_lang: str,
        target_lang: str,
        batch_start: int,
        depth: int = 0,
    ) -> List[str]:
        if not texts:
            return []

        max_attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                translations = run_sync(self._call_llm_for_batch(texts, system_prompt))
                if translations is None:
                    raise TranslationBatchError("Provider returned invalid translation payload")
                self._validate_translations(texts, translations, source_lang, target_lang)
                return translations
            except Exception as exc:
                # Permanent provider problems pause now; transient connectivity keeps
                # retrying and pauses only once retries are exhausted (handled below).
                pause_error = pause_for_provider_error(
                    exc,
                    provider=getattr(self, "translation_provider", settings.PCT_TRANSLATION_PROVIDER),
                    stage=self.stage,
                    prefix="Translation provider is unavailable",
                    include_transient=False,
                )
                if pause_error is not None:
                    raise pause_error from exc
                last_error = exc
                logger.warning(
                    "Task translation batch starting at %s failed attempt %s/%s with %s segment(s): %s",
                    batch_start,
                    attempt,
                    max_attempts,
                    len(texts),
                    exc,
                )

        if len(texts) == 1:
            # Retries are exhausted for this segment: pause (resumable) if the failure is a
            # provider problem incl. transient connectivity, instead of hard-failing.
            if last_error is not None:
                pause_error = pause_for_provider_error(
                    last_error,
                    provider=getattr(self, "translation_provider", settings.PCT_TRANSLATION_PROVIDER),
                    stage=self.stage,
                    prefix="Translation provider is unavailable",
                )
                if pause_error is not None:
                    raise pause_error from last_error
            raise RuntimeError(
                f"Translation failed for segment {batch_start}; refusing to fall back to original text."
            ) from last_error

        midpoint = len(texts) // 2
        logger.info(
            "Splitting translation batch starting at %s from %s to %s/%s segment(s).",
            batch_start,
            len(texts),
            midpoint,
            len(texts) - midpoint,
        )
        left = self._translate_non_empty_texts(
            texts[:midpoint],
            system_prompt,
            source_lang,
            target_lang,
            batch_start,
            depth + 1,
        )
        right = self._translate_non_empty_texts(
            texts[midpoint:],
            system_prompt,
            source_lang,
            target_lang,
            batch_start + midpoint,
            depth + 1,
        )
        return left + right

    def _translate_batch(
        self,
        original_texts: List[str],
        system_prompt: str,
        source_lang: str,
        target_lang: str,
        batch_start: int,
    ) -> List[str]:
        translations = [""] * len(original_texts)
        non_empty_positions = [
            index for index, text in enumerate(original_texts) if str(text or "").strip()
        ]
        non_empty_texts = [original_texts[index] for index in non_empty_positions]
        translated_non_empty = self._translate_non_empty_texts(
            non_empty_texts,
            system_prompt,
            source_lang,
            target_lang,
            batch_start,
        )
        for position, translation in zip(non_empty_positions, translated_non_empty):
            translations[position] = translation
        return translations

    def translate_segments(
        self,
        ctx: PipelineContext,
        segments: List[dict],
        *,
        source_lang: str | None = None,
        target_lang: str | None = None,
    ) -> bool:
        """Translate ``segments`` in place, returning whether anything changed.

        Unlike :meth:`process`, this has no context-global side effects (it does not reset
        ``synth_segments`` or invalidate downstream stages) and does not report stage
        progress, so it is safe to call concurrently on per-chunk slices while the
        long-audio front-half is still running (see ``LongAudioPipeline``). The
        ``source_lang``/``target_lang`` overrides let a caller translate a chunk using that
        chunk's detected language before the global majority-vote language is known.
        """
        if not segments:
            return False

        source_lang = source_lang or ctx.source_language or "en"
        target_lang = target_lang or ctx.target_language or "zh"

        if source_lang == target_lang:
            changed = False
            for segment in segments:
                if not str(segment.get("translation") or "").strip():
                    segment["translation"] = segment.get("text", "")
                    changed = True
            return changed

        self._ensure_clients_configured(ctx)
        system_prompt = self._build_system_prompt(source_lang, target_lang)
        return self._translate_segment_list(
            ctx, segments, system_prompt, source_lang, target_lang, report_progress=False
        )

    def _translate_segment_list(
        self,
        ctx: PipelineContext,
        segments: List[dict],
        system_prompt: str,
        source_lang: str,
        target_lang: str,
        *,
        report_progress: bool,
    ) -> bool:
        batch_size = max(1, settings.PCT_TRANSLATION_BATCH_SIZE)
        total_segments = len(segments)
        if report_progress:
            self._report_items_progress(ctx, items_total=total_segments, items_done=0)
        changed_translations = False
        for index in range(0, total_segments, batch_size):
            batch_slice = segments[index:index + batch_size]
            pending_positions = [
                local_index
                for local_index, segment in enumerate(batch_slice)
                if self._segment_needs_translation(segment, source_lang, target_lang)
            ]
            original_texts = [
                str(batch_slice[local_index].get("text") or "")
                for local_index in pending_positions
            ]

            if not any(original_texts):
                continue

            logger.info(
                "Task %s: translating %s segment(s) in batch %s to %s of %s",
                ctx.task_id,
                len(original_texts),
                index,
                min(index + batch_size, total_segments),
                total_segments,
            )

            translations = self._translate_batch(
                original_texts,
                system_prompt,
                source_lang,
                target_lang,
                index,
            )

            for local_index, translation in zip(pending_positions, translations):
                segment = batch_slice[local_index]
                segment["translation"] = translation
                segment.pop("synth_audio_url", None)
                changed_translations = True

            if report_progress:
                self._report_items_progress(
                    ctx, items_total=total_segments, items_done=min(index + batch_size, total_segments)
                )
                self._report_progress(ctx, round(min(index + batch_size, total_segments) * 100 / total_segments))

        return changed_translations

    def process(self, ctx: PipelineContext) -> PipelineContext:
        if not ctx.segments:
            logger.warning("Task %s: segment list is empty. Translation skipped.", ctx.task_id)
            return ctx

        source_lang = ctx.source_language or "en"
        target_lang = ctx.target_language or "zh"

        if source_lang == target_lang:
            logger.info(
                "Task %s: source and target language are both '%s'. Skipping translation.",
                ctx.task_id,
                source_lang,
            )
            for segment in ctx.segments:
                segment["translation"] = segment.get("text", "")
            return ctx

        self._ensure_clients_configured(ctx)

        system_prompt = self._build_system_prompt(source_lang, target_lang)
        logger.info("Task %s: translation direction %s -> %s", ctx.task_id, source_lang, target_lang)

        changed_translations = self._translate_segment_list(
            ctx, ctx.segments, system_prompt, source_lang, target_lang, report_progress=True
        )

        if changed_translations:
            ctx.synth_segments = None
            ctx.output_audio_url = None
            ctx.invalidated_stages.update(
                {
                    TaskStage.SYNTHESIZING.value,
                    TaskStage.ALIGNING.value,
                    TaskStage.MIXING.value,
                }
            )

        logger.info("Task %s: translation stage completed.", ctx.task_id)
        return ctx
