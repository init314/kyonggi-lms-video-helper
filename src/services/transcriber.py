from pathlib import Path
from functools import lru_cache

from services.cancellation import check_cancelled


REQUIRED_MODEL_FILES = ("config.json", "model.bin")
HF_WHISPER_MODELS = {
    "tiny": "openai/whisper-tiny",
    "base": "openai/whisper-base",
    "small": "openai/whisper-small",
    "medium": "openai/whisper-medium",
    "large": "openai/whisper-large-v3",
    "large-v3": "openai/whisper-large-v3",
    "large-v3-turbo": "openai/whisper-large-v3-turbo",
}





def transcribe_audio(
    file_path: str | Path,
    model_ref: str | Path,
    language: str = "ko",
    cancelled=None,
    logger=None,
) -> str:
    """Convert a local audio file into timestamped transcript text."""
    model_ref = resolve_model_ref(model_ref)
    check_cancelled(cancelled)
    if logger:
        logger(f"STT 모델 준비: {model_ref} (처음 사용하면 다운로드합니다)")
    if is_amd_rocm_available():
        if logger:
            logger("AMD ROCm GPU 감지: RX 9070 XT에서 PyTorch FP16으로 전사합니다.")
        transcript = transcribe_amd_gpu(file_path, model_ref, language, cancelled, logger)
        check_cancelled(cancelled)
        return transcript
    if logger:
        logger("AMD ROCm GPU를 사용할 수 없어 기존 CPU 전사로 진행합니다.")
    model = load_model(model_ref)
    check_cancelled(cancelled)

    segments, _ = model.transcribe(str(file_path), language=language, vad_filter=False)
    lines = []
    for segment in segments:
        check_cancelled(cancelled)
        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = segment.text.strip()
        if text:
            lines.append(f"[{start} - {end}] {text}")
        if logger:
            logger(f"전사 진행: {end}")
    return "\n".join(lines)


def is_amd_rocm_available() -> bool:
    """PyTorch ROCm exposes supported Radeon devices through its CUDA API."""
    try:
        import torch
        return bool(torch.version.hip and torch.cuda.is_available())
    except (ImportError, AttributeError, OSError):
        return False


def transcribe_amd_gpu(file_path, model_ref, language, cancelled=None, logger=None):
    try:
        import torch
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    except ImportError as exc:
        raise RuntimeError(
            "AMD GPU 전사에는 AMD ROCm용 PyTorch와 transformers가 필요합니다. "
            "README의 'RX 9070 XT GPU 설정'을 따라 설치한 뒤 다시 실행하세요."
        ) from exc

    model_id = HF_WHISPER_MODELS.get(model_ref.casefold(), model_ref)
    if Path(model_id).expanduser().is_dir():
        raise ValueError("AMD GPU 모드에는 CTranslate2 폴더 대신 Hugging Face Whisper 모델명을 입력하세요.")
    if logger:
        logger(f"AMD GPU 모델 로딩: {model_id} (첫 실행 시 모델을 다운로드합니다)")
    model = load_amd_model(model_id)
    check_cancelled(cancelled)
    language_names = {"ko": "korean", "en": "english", "ja": "japanese", "zh": "chinese"}
    lines = []
    total_chunks = 0
    for offset, audio_chunk in iter_audio_chunks(file_path, cancelled):
        check_cancelled(cancelled)
        result = model({"raw": audio_chunk, "sampling_rate": 16000}, return_timestamps=True,
                       generate_kwargs={
                           "language": language_names.get(language.casefold(), language),
                           "task": "transcribe",
                           "num_beams": 5,
                       })
        for chunk in result.get("chunks", []):
            check_cancelled(cancelled)
            text = chunk.get("text", "").strip()
            timestamps = chunk.get("timestamp")
            if text:
                if timestamps and timestamps[0] is not None and timestamps[1] is not None:
                    start = format_timestamp(offset + timestamps[0])
                    end = format_timestamp(offset + timestamps[1])
                    lines.append(f"[{start} - {end}] {text}")
                else:
                    lines.append(text)
        if not result.get("chunks") and result.get("text", "").strip():
            lines.append(result["text"].strip())
        total_chunks += 1
        if logger:
            logger(f"AMD GPU 전사 진행: {format_timestamp(offset + len(audio_chunk) / 16000)}")
    if logger:
        logger(f"AMD GPU 전사 완료: 오디오 {total_chunks}개 구간 처리, 문장 {len(lines)}개")
    return "\n".join(lines)


def iter_audio_chunks(file_path, cancelled=None, chunk_seconds=30):
    """Decode long recordings in bounded-memory 30-second mono chunks."""
    import av
    import numpy as np

    sample_rate = 16000
    chunk_samples = chunk_seconds * sample_rate
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sample_rate)
    pieces = []
    buffered_samples = 0
    offset = 0

    def push(samples):
        nonlocal pieces, buffered_samples
        if len(samples):
            pieces.append(samples)
            buffered_samples += len(samples)

    def drain():
        nonlocal pieces, buffered_samples, offset
        if buffered_samples < chunk_samples:
            return None
        buffered = np.concatenate(pieces)
        complete = buffered[:chunk_samples]
        remaining = buffered[chunk_samples:]
        pieces = [remaining] if len(remaining) else []
        buffered_samples = len(remaining)
        current_offset = offset
        offset += chunk_seconds
        return current_offset, complete

    with av.open(str(file_path)) as container:
        if not container.streams.audio:
            raise RuntimeError("입력 파일에 오디오 트랙이 없습니다.")
        for frame in container.decode(audio=0):
            check_cancelled(cancelled)
            converted = resampler.resample(frame) or []
            for output in converted:
                samples = output.to_ndarray().reshape(-1).astype(np.float32, copy=False)
                push(samples)
                chunk = drain()
                if chunk is not None:
                    yield chunk
        for output in resampler.resample(None) or []:
            push(output.to_ndarray().reshape(-1).astype(np.float32, copy=False))
            chunk = drain()
            if chunk is not None:
                yield chunk
    if buffered_samples:
        check_cancelled(cancelled)
        yield offset, np.concatenate(pieces)


@lru_cache(maxsize=1)
def load_amd_model(model_id: str):
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    device = "cuda:0"  # ROCm-enabled PyTorch presents Radeon devices here.
    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        model_id,
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    ).to(device)
    processor = AutoProcessor.from_pretrained(model_id)
    return pipeline(
        "automatic-speech-recognition",
        model=model,
        tokenizer=processor.tokenizer,
        feature_extractor=processor.feature_extractor,
        torch_dtype=torch.float16,
        device=device,
    )


@lru_cache(maxsize=1)
def load_model(model_ref: str):
    """Reuse the model across sequential lectures."""


    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "faster-whisper가 설치되어 있지 않습니다. "
            "`pip install -e .` 또는 `pip install faster-whisper`로 설치하세요."
        ) from exc


    return WhisperModel(
        model_ref,
        device="cpu",
        compute_type="int8",
        local_files_only=False,
    )





def resolve_model_ref(model_ref: str | Path) -> str:
    raw_model_ref = str(model_ref).strip()


    if not raw_model_ref:
        raise ValueError("STT 모델 폴더 또는 캐시 모델명을 입력하세요.")


    candidate_path = Path(raw_model_ref).expanduser()


    if candidate_path.exists():
        return str(validate_model_dir(candidate_path))


    return raw_model_ref





def validate_model_dir(model_dir: str | Path) -> Path:
    local_model_dir = Path(model_dir).expanduser()


    if not local_model_dir.exists():
        raise FileNotFoundError(f"STT 모델 폴더를 찾을 수 없습니다: {local_model_dir}")


    if not local_model_dir.is_dir():
        raise NotADirectoryError(f"STT 모델 경로가 폴더가 아닙니다: {local_model_dir}")


    missing_files = [
        file_name
        for file_name in REQUIRED_MODEL_FILES
        if not (local_model_dir / file_name).exists()
    ]


    if missing_files:
        missing = ", ".join(missing_files)
        raise FileNotFoundError(
            f"STT 모델 폴더에 필요한 파일이 없습니다: {missing}"
        )


    return local_model_dir





def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60


    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


    return f"{minutes:02d}:{secs:02d}"
