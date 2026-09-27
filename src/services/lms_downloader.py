"""Kyonggi LMS downloader, adapted from this repository's download_lms_video.py."""
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from email.message import Message
import html
import os
from pathlib import Path
import re
import time
import unicodedata
import urllib.parse
import urllib.request
import sys

# Frozen Playwright otherwise searches for browsers inside the EXE bundle.
if getattr(sys, "frozen", False) and os.environ.get("LOCALAPPDATA"):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(os.environ["LOCALAPPDATA"]) / "ms-playwright"))

import keyring
from playwright.sync_api import sync_playwright

from services.cancellation import check_cancelled
from services.displays import Display, ensure_display_connected, get_virtual_display

SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
ROOT = "https://lms.kyonggi.ac.kr/"
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}

# All lecture players share the existing window on the virtual display.
# LMS popup position hints therefore cannot create a window on a real monitor.
SAME_WINDOW_SCRIPT = """(() => {
    window.open = function(url) {
        if (url) window.location.assign(new URL(url, location.href).href);
        return window;
    };
    document.addEventListener('click', event => {
        const anchor = event.target.closest?.('a[target]');
        if (anchor) anchor.target = '_self';
    }, true);
})();"""


@dataclass(frozen=True)
class Lecture:
    index: int
    title: str
    url: str


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def safe_path_component(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" .")[:100]
    if value.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(10)], *[f"LPT{i}" for i in range(10)]}:
        value = "_" + value
    return value or "미분류"


def is_direct_file(url: str) -> bool:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"https", "http"}:
        return False
    probes = [parsed.path, *(v for _, v in urllib.parse.parse_qsl(parsed.query))]
    return any(Path(urllib.parse.urlsplit(p).path.lower()).suffix in VIDEO_EXTENSIONS for p in probes)


def discover_media_url(page) -> str | None:
    candidates = []
    for frame in page.frames:
        try:
            values = frame.evaluate("""() => [...document.querySelectorAll(
              'video, video source, a[href], iframe, [data-media-file], [id*="media_file"], [name*="media_file"]'
            )].flatMap(e => [e.currentSrc, e.src, e.href, e.getAttribute('data-media-file'),
              e.getAttribute('media_file'), e.getAttribute('href')].filter(Boolean))""")
            candidates.extend(urllib.parse.urljoin(frame.url, html.unescape(v)) for v in values)
            source = frame.content()
            for match in re.finditer("media_file", source, re.IGNORECASE):
                fragment = source[max(0, match.start() - 250):match.start() + 1200]
                for value in re.findall(r'''["']([^"']+)["']''', fragment):
                    value = html.unescape(value).replace("\\/", "/")
                    if value.startswith(("/", "http")):
                        candidates.append(urllib.parse.urljoin(frame.url, value))
        except Exception:
            continue
    return next((url for url in candidates if is_direct_file(url)), None)


def save_video(url, context, target_stem: Path, logger, cancelled=None, guard=lambda: None) -> Path:
    """Publish only fully downloaded files. Interrupted downloads stay as .part."""
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": ROOT})
    cookies = context.cookies(url)
    if cookies:
        request.add_header("Cookie", "; ".join(f"{c['name']}={c['value']}" for c in cookies))
    check_cancelled(cancelled)
    guard()
    with urllib.request.urlopen(request, timeout=30) as response:
        content_type = response.headers.get_content_type().lower()
        disposition = Message()
        disposition["content-disposition"] = response.headers.get("Content-Disposition", "")
        extension = Path(disposition.get_filename() or urllib.parse.urlsplit(url).path).suffix.lower()
        if content_type in {"text/html", "application/json"}:
            raise RuntimeError("영상 대신 로그인 페이지 또는 오류 응답이 도착했습니다.")
        if extension not in VIDEO_EXTENSIONS:
            if content_type == "video/webm":
                extension = ".webm"
            elif content_type.startswith("video/"):
                extension = ".mp4"
            else:
                raise RuntimeError(f"지원하지 않는 영상 응답입니다: {content_type}")
        destination = target_stem.with_name(target_stem.name + extension)
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_suffix(destination.suffix + ".part")
        expected = int(response.headers.get("Content-Length") or 0)
        received = 0
        last_report = 0.0
        with partial.open("wb") as output:
            while True:
                check_cancelled(cancelled)
                guard()
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
                received += len(block)
                now = time.monotonic()
                if now - last_report >= 2:
                    progress = f"{received / expected:.0%}" if expected else f"{received / 1024**2:.1f} MB"
                    logger(f"다운로드 중: {progress}")
                    last_report = now
        if not received or (expected and received != expected):
            raise RuntimeError("영상 다운로드가 불완전합니다. 다시 실행해 주세요.")
        check_cancelled(cancelled)
        os.replace(partial, destination)
    return destination.resolve()


class LmsDownloader:
    def __init__(self, course: str, week: int, folder: Path, logger=print, cancelled=None):
        self.course = course.strip()
        self.week = week
        self.folder = Path(folder)
        self.logger = logger
        self.cancelled = cancelled
        self.display = get_virtual_display()
        self.storage_state = None
        if not self.course or self.week < 1:
            raise ValueError("과목명과 1 이상의 주차를 입력하세요.")

    def guard(self):
        check_cancelled(self.cancelled)
        ensure_display_connected(self.display)

    @contextmanager
    def session(self):
        self.guard()
        username = keyring.get_password(SERVICE, USERNAME_KEY)
        password = keyring.get_password(SERVICE, username) if username else None
        if not username or not password:
            raise RuntimeError("저장된 LMS 계정이 없습니다. 앱의 'LMS 계정 설정'에서 등록하세요.")
        with sync_playwright() as playwright:
            browser = launch_on_display(playwright, self.display)
            try:
                context = browser.new_context(storage_state=self.storage_state, no_viewport=True)
                context.add_init_script(SAME_WINDOW_SCRIPT)
                page = context.new_page()
                place_page(context, page, self.display)
                # Unexpected popup windows are closed rather than used on another screen.
                context.on("page", lambda popup: popup.close())
                page.set_default_timeout(20000)
                page.goto(ROOT, wait_until="domcontentloaded")
                if page.locator("#username").count():
                    try:
                        page.locator("#username").fill(username)
                        page.locator("#password").fill(password)
                        page.locator("form.loginform button[type=submit]").click()
                        page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)
                        page.locator("a.course_link").first.wait_for()
                    except Exception:
                        raise RuntimeError("LMS 로그인 실패: 저장된 계정이나 추가 인증 여부를 확인하세요.") from None
                self.guard()
                self.storage_state = context.storage_state()
                yield context, page
            finally:
                browser.close()

    def list_lectures(self) -> list[Lecture]:
        self.logger(f"다운로드 화면: {self.display.name} ({self.display.description})")
        with self.session() as (_, page):
            links = page.locator("a.course_link")
            matching = [link for link in links.all()
                        if normalize_label(self.course) in normalize_label(link.inner_text())]
            if len(matching) != 1:
                raise RuntimeError(f"'{self.course}' 과목을 하나로 특정할 수 없습니다. 정확한 과목명을 입력하세요.")
            page.goto(matching[0].evaluate("e => e.href"), wait_until="domcontentloaded")
            page.locator("li.section.main").first.wait_for()
            pattern = re.compile(rf"^\s*{self.week}\s*주차\b")
            result, seen = [], set()
            for section in page.locator("li.section.main").all():
                heading = section.locator(".sectionname").first
                if not heading.count() or not pattern.search(heading.inner_text().strip()):
                    continue
                for link in section.locator("a[href*='/mod/xncommons/view.php']").all():
                    href = link.evaluate("e => e.href")
                    if href not in seen:
                        seen.add(href)
                        result.append(Lecture(len(result) + 1, re.sub(r"\s+", " ", link.inner_text()).strip(), href))
            if not result:
                raise RuntimeError(f"{self.week}주차에 다운로드 가능한 영상이 없습니다.")
            return result

    def download(self, lecture: Lecture) -> Path:
        stem = self.folder / safe_path_component(self.course) / f"{self.week}주차" / f"{lecture.index:03d}_{safe_path_component(lecture.title)}"
        with self.session() as (context, page):
            page.goto(lecture.url, wait_until="domcontentloaded")
            self.wait(page, 1200)
            content_view = page.locator("a.btn.btn-default[onclick*='XinicsContentWindow']")
            if content_view.count():
                content_view.first.click()
                self.wait(page, 1200)
                page.wait_for_load_state("domcontentloaded")
            media_url = discover_media_url(page)
            if not media_url:
                for frame in page.frames:
                    button = frame.locator(".vc-front-screen-play-btn")
                    if button.count():
                        button.first.click()
                        break
                for _ in range(20):
                    self.wait(page, 500)
                    media_url = discover_media_url(page)
                    if media_url:
                        break
            if not media_url:
                raise RuntimeError("직접 다운로드 가능한 MP4/WebM 링크를 찾지 못했습니다. 스트리밍 전용 영상은 지원하지 않습니다.")
            # Stop playback while copying the file; browser sound is also muted.
            for frame in page.frames:
                try:
                    frame.evaluate("() => document.querySelectorAll('video,audio').forEach(v => v.pause())")
                except Exception:
                    pass
            return save_video(media_url, context, stem, self.logger, self.cancelled, self.guard)

    def wait(self, page, milliseconds):
        for _ in range(max(1, milliseconds // 100)):
            self.guard()
            page.wait_for_timeout(100)


def launch_on_display(playwright, display: Display):
    ensure_display_connected(display)
    if not Path(playwright.chromium.executable_path).is_file():
        raise RuntimeError("다운로드용 Chromium이 없습니다. 프로젝트에서 .venv\\Scripts\\python.exe -m playwright install chromium 명령을 실행하세요.")
    return playwright.chromium.launch(headless=False, args=[
        f"--window-position={display.x},{display.y}",
        f"--window-size={display.width},{display.height}",
        "--force-device-scale-factor=1", "--mute-audio",
        "--disable-backgrounding-occluded-windows", "--disable-renderer-backgrounding",
    ])


def place_page(context, page, display: Display):
    ensure_display_connected(display)
    session = context.new_cdp_session(page)
    try:
        window_id = session.send("Browser.getWindowForTarget")["windowId"]
        session.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": {
            "left": display.x, "top": display.y, "width": display.width,
            "height": display.height, "windowState": "normal"}})
        bounds = session.send("Browser.getWindowBounds", {"windowId": window_id})["bounds"]
        if not display.contains(bounds):
            raise RuntimeError("브라우저를 가상 디스플레이 안에 배치하지 못해 중단했습니다.")
    finally:
        session.detach()
