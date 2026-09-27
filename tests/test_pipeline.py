from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, get_ident
import time
from unittest import TestCase
from unittest.mock import patch

from application.pipeline import download_and_transcribe
from domain.models import ConversionOptions, ConversionResult
from services.cancellation import JobCancelled, check_cancelled
from services.lms_downloader import Lecture


class PipelineTest(TestCase):
    def run_batch(self, root, fail_first=False, cancel_first=False, fail_download=False):
        events = []
        lectures = [Lecture(1, "첫 강의", "https://example.test/1"), Lecture(2, "둘째 강의", "https://example.test/2")]
        def download(item):
            events.append(("download", item.index))
            if item.index == 1 and cancel_first:
                raise JobCancelled()
            if item.index == 1 and fail_download:
                raise RuntimeError("download unavailable")
            return root / f"{item.index}.mp4"
        def convert(video, options, logger, cancelled):
            index = int(video.stem)
            events.append(("transcribe", index))
            if index == 1 and fail_first:
                raise RuntimeError("unreadable audio")
            folder = options.output_dir / "run"
            folder.mkdir(parents=True)
            return ConversionResult(folder, folder / "transcript.txt", folder / "cleaned.txt", (), (), "now")
        with patch("application.pipeline.LmsDownloader") as downloader, patch("application.pipeline.convert_audio_to_prompts", side_effect=convert):
            downloader.return_value.list_lectures.return_value = lectures
            downloader.return_value.download.side_effect = download
            result = download_and_transcribe("과목", 4, root / "downloads", ConversionOptions(output_dir=root / "output"), lambda _: None)
        return events, result

    def test_next_download_overlaps_transcription_with_only_one_video_ahead(self):
        transcribing_first = Event()
        second_downloaded = Event()
        first_finished = Event()
        events, browser_threads = [], []
        lectures = [Lecture(i, f"Lecture {i}", f"https://example.test/{i}") for i in (1, 2, 3)]
        with TemporaryDirectory() as folder:
            root = Path(folder)

            def download(item):
                browser_threads.append(get_ident())
                if item.index == 2:
                    self.assertTrue(transcribing_first.wait(3), "STT did not overlap download")
                if item.index == 3:
                    self.assertTrue(first_finished.is_set(), "more than one lecture was prefetched")
                events.append(("download", item.index))
                if item.index == 2:
                    second_downloaded.set()
                return root / f"{item.index}.mp4"

            def convert(video, options, logger, cancelled):
                index = int(video.stem)
                events.append(("transcribe", index))
                if index == 1:
                    transcribing_first.set()
                    self.assertTrue(second_downloaded.wait(3), "next download waited for STT to finish")
                    self.assertNotIn(("download", 3), events)
                    first_finished.set()
                path = options.output_dir / "run"
                path.mkdir(parents=True)
                return ConversionResult(path, path / "transcript.txt", path / "cleaned.txt", (), (), "now")

            def list_lectures():
                browser_threads.append(get_ident())
                return lectures

            with patch("application.pipeline.LmsDownloader") as downloader, patch("application.pipeline.convert_audio_to_prompts", side_effect=convert):
                downloader.return_value.list_lectures.side_effect = list_lectures
                downloader.return_value.download.side_effect = download
                result = download_and_transcribe("과목", 4, root / "downloads", ConversionOptions(output_dir=root / "output"), lambda _: None)
            self.assertEqual(result.failures, ())
            self.assertEqual(len(result.completed), 3)
            self.assertEqual([index for stage, index in events if stage == "transcribe"], [1, 2, 3])
            self.assertEqual(len(set(browser_threads)), 1)
            self.assertNotEqual(browser_threads[0], get_ident())
            self.assertTrue((result.completed[0].output_dir / "source.json").is_file())

    def test_failed_transcription_keeps_going_and_reports_partial_result(self):
        with TemporaryDirectory() as folder:
            _, result = self.run_batch(Path(folder), fail_first=True)
            self.assertEqual(len(result.completed), 1)
            self.assertEqual(len(result.failures), 1)

    def test_cancellation_is_not_swallowed_as_a_failed_lecture(self):
        with TemporaryDirectory() as folder, self.assertRaises(JobCancelled):
            self.run_batch(Path(folder), cancel_first=True)

    def test_failed_download_is_not_transcribed_and_next_video_continues(self):
        with TemporaryDirectory() as folder:
            events, result = self.run_batch(Path(folder), fail_download=True)
            self.assertEqual(len(result.completed), 1)
            self.assertEqual(len(result.failures), 1)
            self.assertNotIn(("transcribe", 1), events)
            self.assertIn(("transcribe", 2), events)

    def test_stopping_transcription_stops_inflight_download_before_return(self):
        started = Event()
        closed = Event()
        downloaded = []
        callback = None
        lectures = [Lecture(i, f"Lecture {i}", f"https://example.test/{i}") for i in (1, 2, 3)]
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with patch("application.pipeline.LmsDownloader") as factory:
                downloader = factory.return_value

                def create(course, week, download_dir, logger, cancelled):
                    nonlocal callback
                    callback = cancelled
                    return downloader

                def download(lecture):
                    downloaded.append(lecture.index)
                    if lecture.index == 1:
                        return root / "1.mp4"
                    started.set()
                    deadline = time.monotonic() + 3
                    try:
                        while time.monotonic() < deadline:
                            check_cancelled(callback)
                            Event().wait(0.01)
                        raise AssertionError("in-flight download did not receive cancellation")
                    except JobCancelled:
                        closed.set()
                        raise

                def convert(*args):
                    self.assertTrue(started.wait(3))
                    raise JobCancelled("stop")

                factory.side_effect = create
                downloader.list_lectures.return_value = lectures
                downloader.download.side_effect = download
                with patch("application.pipeline.convert_audio_to_prompts", side_effect=convert), self.assertRaises(JobCancelled):
                    download_and_transcribe("과목", 4, root / "downloads", ConversionOptions(output_dir=root / "output"), lambda _: None)
            self.assertTrue(closed.is_set())
            self.assertEqual(downloaded, [1, 2])
