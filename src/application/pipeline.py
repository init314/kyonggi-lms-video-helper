"""Transcribe in LMS order while downloading one lecture ahead."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
from pathlib import Path
from collections.abc import Callable
from threading import Event

from application.converter import convert_audio_to_prompts
from domain.models import ConversionOptions, ConversionResult
from services.cancellation import JobCancelled, check_cancelled
from services.lms_downloader import LmsDownloader, safe_path_component


@dataclass(frozen=True)
class BatchResult:
    completed: tuple[ConversionResult, ...]
    failures: tuple[str, ...]
    output_dir: Path


def download_and_transcribe(course: str, week: int, download_dir: Path,
                           options: ConversionOptions, logger: Callable[[str], None] = print,
                           cancelled=None) -> BatchResult:
    destination = Path(options.output_dir) / safe_path_component(course) / f"{week}주차"
    completed, failures = [], []
    stopping = Event()

    def is_cancelled():
        return stopping.is_set() or bool(cancelled and cancelled())

    def prepare():
        # Create and use all Playwright sessions on the same download thread.
        check_cancelled(is_cancelled)
        downloader = LmsDownloader(course, week, download_dir, logger, is_cancelled)
        return downloader, downloader.list_lectures()

    def download_one(lecture):
        check_cancelled(is_cancelled)
        label = f"[{lecture.index}/{len(lectures)}] {lecture.title}"
        downloader.logger = lambda message: logger(f"{label} · {message}")
        logger(f"{label} 다운로드 시작")
        video = downloader.download(lecture)
        logger(f"{label} 다운로드 완료")
        return video

    pending = None
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="lecture-download") as downloads:
        try:
            downloader, lectures = downloads.submit(prepare).result()
            check_cancelled(is_cancelled)
            destination.mkdir(parents=True, exist_ok=True)
            logger(f"영상 {len(lectures)}개: 전사 중 다음 영상을 미리 다운로드합니다. 전사는 순서대로 진행합니다.")
            if lectures:
                pending = downloads.submit(download_one, lectures[0])
            for offset, lecture in enumerate(lectures):
                check_cancelled(is_cancelled)
                label = f"[{lecture.index}/{len(lectures)}] {lecture.title}"
                try:
                    video = pending.result()
                except JobCancelled:
                    raise
                except Exception as exc:
                    message = f"{label} 다운로드 실패: {exc}"
                    failures.append(message)
                    logger(message)
                    video = None

                check_cancelled(is_cancelled)
                # Only one video may be waiting ahead of the current transcription.
                pending = (downloads.submit(download_one, lectures[offset + 1])
                           if offset + 1 < len(lectures) else None)
                if video is None:
                    continue
                try:
                    logger(f"{label} 전사 시작")
                    item_dir = destination / f"{lecture.index:03d}_{safe_path_component(lecture.title)}"
                    item_logger = lambda message, label=label: logger(f"{label} · {message}")
                    result = convert_audio_to_prompts(video, replace(options, output_dir=item_dir), item_logger, is_cancelled)
                    check_cancelled(is_cancelled)
                    (result.output_dir / "source.json").write_text(json.dumps({
                        "course": course, "week": week, "index": lecture.index,
                        "title": lecture.title, "video_path": str(video),
                    }, ensure_ascii=False, indent=2), encoding="utf-8")
                    completed.append(result)
                    logger(f"{label} 전사 완료: {result.output_dir}")
                except JobCancelled:
                    raise
                except Exception as exc:
                    message = f"{label} 전사 실패: {exc}"
                    failures.append(message)
                    logger(message)
        finally:
            # Stop any in-flight download before returning, including on STT errors.
            stopping.set()
            if pending is not None:
                pending.cancel()
    summary = BatchResult(tuple(completed), tuple(failures), destination)
    (destination / "latest_result.json").write_text(json.dumps({
        "completed": [str(item.output_dir) for item in completed], "failures": failures,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary
