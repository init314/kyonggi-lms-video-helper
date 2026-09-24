"""Save directly exposed MP4/WebM lecture files from one LMS course week.

Run with: py download_lms_video.py
Credentials are read from Windows Keyring. The script never prints them.
"""

import html
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from email.message import Message

import keyring
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
ROOT = "https://lms.kyonggi.ac.kr/"
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".m4v"}


def normalize_label(value):
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def ask_selection():
    course = input("과목명 (예: 관리회계): ").strip()
    try:
        week = int(input("주차 (예: 4): ").strip())
    except ValueError as exc:
        raise ValueError("주차는 숫자로 입력하세요.") from exc
    if not course or week < 1:
        raise ValueError("과목명과 주차를 입력해야 합니다.")
    return course, week


def is_direct_file(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"https", "http"}:
        return False
    probes = [parsed.path]
    probes.extend(urllib.parse.unquote(v) for _, v in urllib.parse.parse_qsl(parsed.query))
    return any(os.path.splitext(urllib.parse.urlsplit(p).path.lower())[1] in VIDEO_EXTENSIONS for p in probes)


def discover_media_url(page):
    candidates = []
    for frame in page.frames:
        try:
            dom_values = frame.evaluate("""() => {
              const nodes = [...document.querySelectorAll(
                'video, video source, a[href], iframe, [data-media-file], [id*="media_file"], [name*="media_file"]'
              )];
              return nodes.flatMap(e => [e.currentSrc, e.src, e.href, e.getAttribute('data-media-file'),
                e.getAttribute('media_file'), e.getAttribute('href')].filter(Boolean));
            }""")
            candidates.extend(urllib.parse.urljoin(frame.url, html.unescape(v)) for v in dom_values)

            source = frame.content()
            for match in re.finditer(r"media_file", source, re.IGNORECASE):
                fragment = source[max(0, match.start() - 250):match.start() + 1200]
                for raw_url in re.findall(r"https?://[^\s\"'<>\\]+", fragment):
                    candidates.append(html.unescape(raw_url).replace("\\/", "/"))
                for value in re.findall(r"[\"']([^\"']+)[\"']", fragment):
                    value = html.unescape(value).replace("\\/", "/")
                    if value.startswith("/") or value.startswith("http"):
                        candidates.append(urllib.parse.urljoin(frame.url, value))
        except Exception:
            continue

    # Keep only direct video files; HLS/DASH playlists and other streams are not downloaded.
    seen = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if candidate not in seen and is_direct_file(candidate):
            seen.add(candidate)
            return candidate
    return None


def save_video(url, context, filename_stem):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    parsed = urllib.parse.urlsplit(url)
    cookies = context.cookies(url)
    cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
    if cookie_header:
        request.add_header("Cookie", cookie_header)

    try:
        response = urllib.request.urlopen(request, timeout=60)
    except urllib.error.URLError as exc:
        raise RuntimeError(f"영상 파일 요청 실패: {exc.reason}") from exc

    with response:
        content_type = response.headers.get_content_type().lower()
        disposition = Message()
        disposition["content-disposition"] = response.headers.get("Content-Disposition", "")
        server_name = disposition.get_filename()
        ext = os.path.splitext(server_name or parsed.path)[1].lower()
        if ext not in VIDEO_EXTENSIONS:
            if content_type == "video/webm":
                ext = ".webm"
            elif content_type.startswith("video/"):
                ext = ".mp4"
            else:
                raise RuntimeError(f"응답이 영상 파일이 아닙니다 (Content-Type: {content_type}).")

        os.makedirs("downloads", exist_ok=True)
        path = os.path.join("downloads", filename_stem + ext)
        with open(path, "wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
    return os.path.abspath(path)


def open_player(page, activity_url):
    """Open one activity and return its player page."""
    page.goto(activity_url, wait_until="domcontentloaded")
    video_page = page
    video_page.wait_for_timeout(1200)

    content_view = video_page.locator("a.btn.btn-default[onclick*='XinicsContentWindow']")
    if content_view.count():
        with video_page.expect_popup(timeout=10000) as content_popup:
            content_view.first.click()
        video_page = content_popup.value
        video_page.wait_for_load_state("domcontentloaded")
        video_page.wait_for_timeout(1000)

    return video_page


def main():
    try:
        course_name, week = ask_selection()
        username = keyring.get_password(SERVICE, USERNAME_KEY)
        password = keyring.get_password(SERVICE, username) if username else None
        if not username or not password:
            raise RuntimeError("Windows Keyring에서 저장된 LMS 계정을 찾을 수 없습니다.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            page.goto(ROOT, wait_until="domcontentloaded")
            if page.locator("#username").count():
                page.locator("#username").fill(username)
                page.locator("#password").fill(password)
                page.locator("form.loginform button[type=submit]").click()
                try:
                    page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError("로그인에 실패했습니다. LMS 로그인 화면을 확인하세요.") from exc

            course_links = page.locator("a.course_link")
            matching_courses = []
            for i in range(course_links.count()):
                link = course_links.nth(i)
                if normalize_label(course_name) in normalize_label(link.inner_text()):
                    matching_courses.append(link)
            if len(matching_courses) != 1:
                raise RuntimeError(f"'{course_name}' 과목을 하나로 특정할 수 없습니다. 홈 화면에 표시된 과목명을 확인하세요.")
            await_course_url = matching_courses[0].evaluate("e => e.href")
            page.goto(await_course_url, wait_until="domcontentloaded")
            page.wait_for_timeout(800)

            all_sections = page.locator("li.section.main")
            sections = []
            week_heading = re.compile(rf"^\s*{week}\s*주차\b")
            for i in range(all_sections.count()):
                section = all_sections.nth(i)
                heading = section.locator(".sectionname").first
                if heading.count() and week_heading.search(heading.inner_text().strip()):
                    sections.append(section)
            ordered_links = []
            seen_hrefs = set()
            for section in sections:
                links = section.locator("a[href*='/mod/xncommons/view.php']")
                for j in range(links.count()):
                    link = links.nth(j)
                    href = link.evaluate("e => e.href")
                    if href not in seen_hrefs:
                        seen_hrefs.add(href)
                        title = re.sub(r"\s+", " ", link.inner_text()).strip()
                        ordered_links.append((href, title))
            if not ordered_links:
                raise RuntimeError(f"{week}주차에서 영상을 찾지 못했습니다.")

            print(f"{week}주차 영상 {len(ordered_links)}개를 순서대로 처리합니다.")
            failures = []
            for index, (activity_url, video_title) in enumerate(ordered_links, start=1):
                player_page = None
                try:
                    print(f"[{index}/{len(ordered_links)}] {video_title} 여는 중...")
                    player_page = open_player(page, activity_url)
                    cms_frame = None
                    for frame in player_page.frames:
                        try:
                            if frame.locator(".vc-front-screen-play-btn").count():
                                cms_frame = frame
                                break
                        except Exception:
                            continue
                    if cms_frame is None:
                        raise RuntimeError("재생 버튼을 찾지 못했습니다.")
                    cms_frame.locator(".vc-front-screen-play-btn").click()
                    player_page.wait_for_timeout(5000)
                    media_url = discover_media_url(player_page)
                    if not media_url:
                        raise RuntimeError("직접 다운로드 가능한 MP4/WebM 링크를 찾지 못했습니다.")

                    filename = re.sub(
                        r"[^\w.-]+", "_",
                        f"{course_name}_{week}week_{index}_{video_title}", flags=re.UNICODE
                    )
                    saved_path = save_video(media_url, context, filename)
                    print(f"저장 완료: {saved_path}")
                except Exception as exc:
                    failures.append((index, video_title, str(exc)))
                    print(f"[{index}/{len(ordered_links)}] 실패: {exc}")
                finally:
                    if player_page is not None and player_page is not page:
                        try:
                            player_page.close()
                        except Exception:
                            pass
                    # Keep the next item on the course page; popup activities do not
                    # disturb it, and current-tab activities are reopened by URL.
                    if page.url != await_course_url:
                        page.goto(await_course_url, wait_until="domcontentloaded")

            if failures:
                print(f"완료: {len(ordered_links) - len(failures)}개 성공, {len(failures)}개 실패")
                for index, title, reason in failures:
                    print(f"  {index}. {title}: {reason}")
            else:
                print(f"주차 영상 {len(ordered_links)}개를 모두 저장했습니다.")
            browser.close()
    except Exception as exc:
        print(f"문제: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
