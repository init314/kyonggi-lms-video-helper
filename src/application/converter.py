from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from domain.models import ConversionOptions, ConversionResult
from services.chunker import split_text_into_chunks
from services.prompt_builder import build_lecture_summary_prompt
from services.text_cleaner import clean_transcript
from services.transcriber import transcribe_audio
from services.cancellation import check_cancelled


LogHandler = Callable[[str], None]





def convert_audio_to_prompts(
    audio_path: str | Path,
    options: ConversionOptions | None = None,
    logger: LogHandler | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> ConversionResult:
    """Run the full audio-to-prompt conversion pipeline."""
    options = options or ConversionOptions()
    audio_file = Path(audio_path).expanduser()


    if not audio_file.exists():
        raise FileNotFoundError(f"오디오 파일을 찾을 수 없습니다: {audio_file}")


    emit = logger or (lambda message: None)
    check_cancelled(cancelled)


    emit("STT 진행 중")
    transcript = transcribe_audio(
        audio_file,
        model_ref=options.model_ref,
        language=options.language,
        cancelled=cancelled,
        logger=emit,
    )
    check_cancelled(cancelled)


    emit("텍스트 정제 중")
    cleaned = clean_transcript(transcript)


    emit("텍스트 분할 중")
    chunks = split_text_into_chunks(
        cleaned,
        chunk_size=options.chunk_size,
        overlap=options.overlap,
    )


    emit("프롬프트 생성 중")
    prompts = [build_lecture_summary_prompt(chunk) for chunk in chunks]


    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = Path(options.output_dir).expanduser() / f"lecture_{timestamp}"
    chunks_dir = run_dir / "chunks"
    prompts_dir = run_dir / "prompts"


    chunks_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)


    transcript_path = run_dir / "transcript.txt"
    cleaned_path = run_dir / "cleaned.txt"


    transcript_path.write_text(transcript, encoding="utf-8")
    cleaned_path.write_text(cleaned, encoding="utf-8")


    chunk_paths: list[Path] = []
    prompt_paths: list[Path] = []


    for index, chunk in enumerate(chunks, start=1):
        chunk_path = chunks_dir / f"chunk_{index:03d}.txt"
        chunk_path.write_text(chunk, encoding="utf-8")
        chunk_paths.append(chunk_path)


    for index, prompt in enumerate(prompts, start=1):
        prompt_path = prompts_dir / f"prompt_{index:03d}.md"
        prompt_path.write_text(prompt, encoding="utf-8")
        prompt_paths.append(prompt_path)


    emit(f"완료: 총 {len(prompt_paths)}개 프롬프트 생성")


    return ConversionResult(
        output_dir=run_dir,
        transcript_path=transcript_path,
        cleaned_path=cleaned_path,
        chunk_paths=tuple(chunk_paths),
        prompt_paths=tuple(prompt_paths),
        timestamp=timestamp,
    )
