from email.message import Message
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from services.displays import Display, choose_virtual_display
from services.lms_downloader import safe_path_component, save_video


class DownloadTest(TestCase):
    def response(self, payload, content_type="video/mp4", length=None):
        result = BytesIO(payload)
        result.headers = Message()
        result.headers["Content-Type"] = content_type
        result.headers["Content-Length"] = str(len(payload) if length is None else length)
        return result

    def test_complete_download_is_published_without_part_suffix(self):
        with TemporaryDirectory() as folder, patch("urllib.request.urlopen", return_value=self.response(b"video")):
            path = save_video("https://example.test/video.mp4", Mock(cookies=lambda _: []), Path(folder) / "lecture", lambda _: None)
            self.assertEqual(path.read_bytes(), b"video")
            self.assertFalse(path.with_suffix(".mp4.part").exists())

    def test_truncated_download_does_not_replace_previous_file(self):
        with TemporaryDirectory() as folder, patch("urllib.request.urlopen", return_value=self.response(b"short", length=100)):
            original = Path(folder) / "lecture.mp4"
            original.write_bytes(b"previous complete video")
            with self.assertRaises(RuntimeError):
                save_video("https://example.test/video.mp4", Mock(cookies=lambda _: []), Path(folder) / "lecture", lambda _: None)
            self.assertEqual(original.read_bytes(), b"previous complete video")

    def test_login_html_is_not_saved_as_video(self):
        with TemporaryDirectory() as folder, patch("urllib.request.urlopen", return_value=self.response(b"login", "text/html")):
            with self.assertRaises(RuntimeError):
                save_video("https://example.test/video.mp4", Mock(cookies=lambda _: []), Path(folder) / "lecture", lambda _: None)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_safe_names_cannot_escape_destination(self):
        self.assertNotIn("/", safe_path_component("../../lecture"))
        self.assertEqual(safe_path_component("CON"), "_CON")


class DisplayTest(TestCase):
    def setUp(self):
        self.real = [Display("DISPLAY1", "AMD", 0, 0, 2560, 1440, True), Display("DISPLAY2", "AMD", 2560, 0, 2560, 1440)]

    def test_virtual_screen_is_selected_by_driver_not_display_number(self):
        virtual = Display("DISPLAY11", "Virtual Display Driver", 5120, 0, 800, 600)
        self.assertEqual(choose_virtual_display([virtual, *self.real]), virtual)

    def test_missing_virtual_display_never_falls_back_to_main(self):
        with self.assertRaises(RuntimeError):
            choose_virtual_display(self.real)
