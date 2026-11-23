"""Local speech-to-text with faster-whisper. Audio never leaves the machine.

The model downloads once on first use (~460 MB for 'small') and is then cached.
"""
import os
import tempfile

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
SAMPLE_RATE = 16000  # Whisper expects 16 kHz mono
_model = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    return _model


def _decode(path: str):
    """Decode any audio file (m4a, mp3, wav…) to 16 kHz mono float32.

    We decode ourselves instead of letting faster-whisper do it, because
    faster-whisper 1.2.x passes an option (metadata_errors) that newer PyAV
    versions (15+) removed, which breaks opening the file.
    """
    import av
    import numpy as np

    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
    chunks = []
    with av.open(path, mode="r") as container:
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                chunks.append(out.to_ndarray())
        for out in resampler.resample(None):  # flush
            chunks.append(out.to_ndarray())
    if not chunks:
        raise ValueError("No audio found in the file.")
    return np.concatenate(chunks, axis=1).flatten().astype(np.float32) / 32768.0


def transcribe(audio_bytes: bytes, filename: str) -> str:
    suffix = os.path.splitext(filename or "")[1] or ".m4a"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        audio = _decode(path)
        # A hint about the domain helps with names, rand amounts and fund jargon.
        prompt = ("Portfolio manager voice note about a client investment proposal. "
                  "Rand, offshore, Reg 28, discretionary, adviser fee, CPI plus.")
        segments, _info = _get_model().transcribe(audio, language="en", initial_prompt=prompt,
                                                  vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        os.unlink(path)
