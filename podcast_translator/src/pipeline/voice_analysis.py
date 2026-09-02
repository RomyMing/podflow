import logging
import statistics

import torch

logger = logging.getLogger(__name__)

MIN_PITCH_HZ = 70
MAX_PITCH_HZ = 350
MALE_PITCH_MAX_HZ = 165
FEMALE_PITCH_MIN_HZ = 185
MIN_AUTOCORRELATION_CONFIDENCE = 0.25


def _next_power_of_two(value: int) -> int:
    return 1 << max(1, value - 1).bit_length()


def _estimate_frame_pitch(frame: torch.Tensor, sample_rate: int) -> float | None:
    frame = frame.float()
    frame = frame - frame.mean()
    if float(frame.abs().mean()) < 0.005:
        return None

    window = torch.hann_window(frame.numel(), dtype=frame.dtype, device=frame.device)
    frame = frame * window
    autocorr_zero = float(frame.pow(2).sum())
    if autocorr_zero <= 1e-8:
        return None

    fft_size = _next_power_of_two(frame.numel() * 2)
    spectrum = torch.fft.rfft(frame, n=fft_size)
    autocorr = torch.fft.irfft(spectrum * spectrum.conj(), n=fft_size)[: frame.numel()]

    lag_min = max(1, int(sample_rate / MAX_PITCH_HZ))
    lag_max = min(frame.numel() - 2, int(sample_rate / MIN_PITCH_HZ))
    if lag_max <= lag_min:
        return None

    search = autocorr[lag_min : lag_max + 1] / max(float(autocorr[0]), 1e-8)
    peak_value, peak_index = torch.max(search, dim=0)
    if float(peak_value) < MIN_AUTOCORRELATION_CONFIDENCE:
        return None

    lag = float(lag_min + int(peak_index.item()))
    lag_int = int(lag)
    if 1 <= lag_int < autocorr.numel() - 1:
        left = float(autocorr[lag_int - 1])
        center = float(autocorr[lag_int])
        right = float(autocorr[lag_int + 1])
        denominator = left - (2 * center) + right
        if abs(denominator) > 1e-8:
            lag += 0.5 * (left - right) / denominator

    if lag <= 0:
        return None
    pitch_hz = sample_rate / lag
    if MIN_PITCH_HZ <= pitch_hz <= MAX_PITCH_HZ:
        return float(pitch_hz)
    return None


def _estimate_pitch_with_torchaudio(mono: torch.Tensor, sample_rate: int) -> float | None:
    try:
        import torchaudio

        pitches = torchaudio.functional.detect_pitch_frequency(
            mono.unsqueeze(0),
            sample_rate,
            frame_time=0.05,
            freq_low=MIN_PITCH_HZ,
            freq_high=MAX_PITCH_HZ,
        ).reshape(-1)
        pitches = pitches[(pitches >= MIN_PITCH_HZ) & (pitches <= MAX_PITCH_HZ)]
        if pitches.numel() == 0:
            return None
        return float(pitches.median())
    except Exception:
        logger.warning("Torchaudio pitch detection failed; falling back to autocorrelation.", exc_info=True)
        return None


def _estimate_pitch_with_autocorrelation(mono: torch.Tensor, sample_rate: int) -> float | None:
    frame_size = max(int(sample_rate * 0.05), 1)
    hop_size = frame_size
    pitches: list[float] = []
    for start in range(0, max(0, mono.numel() - frame_size), hop_size):
        frame = mono[start : start + frame_size]
        if frame.numel() < frame_size:
            continue
        pitch = _estimate_frame_pitch(frame, sample_rate)
        if pitch is not None:
            pitches.append(pitch)

    if not pitches:
        return None
    return float(statistics.median(pitches))


def estimate_speaker_gender(waveform, sample_rate: int) -> tuple[str, float | None]:
    """Estimate speaker gender from local pitch when voice enrollment is unavailable.

    This is a coarse fallback selector, not speaker verification. Autocorrelation
    is intentionally used instead of zero-crossing so noisy male speech is less
    likely to be mistaken for a high-pitch/female preset.
    """
    try:
        if waveform.numel() == 0 or sample_rate <= 0:
            return "unknown", None

        mono = waveform.mean(dim=0) if waveform.ndim > 1 else waveform
        max_samples = min(int(sample_rate * 30), mono.numel())
        mono = mono[:max_samples].float()
        if mono.numel() < sample_rate:
            return "unknown", None

        median_pitch = _estimate_pitch_with_torchaudio(mono, sample_rate)
        if median_pitch is None:
            median_pitch = _estimate_pitch_with_autocorrelation(mono, sample_rate)
        if median_pitch is None:
            return "unknown", None

        if median_pitch <= MALE_PITCH_MAX_HZ:
            return "male", median_pitch
        if median_pitch >= FEMALE_PITCH_MIN_HZ:
            return "female", median_pitch
        return "unknown", median_pitch
    except Exception:
        logger.warning("Failed to estimate speaker gender from reference audio.", exc_info=True)
        return "unknown", None
