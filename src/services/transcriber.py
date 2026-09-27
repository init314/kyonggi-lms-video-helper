from pathlib import Path
from functools import lru_cache

from services.cancellation import check_cancelled


REQUIRED_MODEL_FILES = ("config.json", "model.bin")





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
