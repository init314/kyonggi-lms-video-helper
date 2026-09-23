"""Open and play a selected LMS lecture using the normal course interface.

This script does not inspect hidden media URLs or download course media.
Run with: py watch_lms_lecture.py
"""

import re
import sys

import keyring
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
ROOT = "https://lms.kyonggi.ac.kr/"


def read_selection():
    course_name = input("과목명 (예: 관리회계): ").strip()
    try:
        week = int(input("주차 번호 (예: 4): ").strip())
        video_number = int(input("해당 주차의 영상 순번 (예: 1): ").strip())
    except ValueError as exc:
        raise ValueError("주차와 영상 순번은 숫자로 입력하세요.") from exc
    if not course_name or week < 1 or video_number < 1:
        raise ValueError("과목명, 주차, 영상 순번을 올바르게 입력하세요.")
    return course_name, week, video_number


def main():
    try:
        course_name, week, video_number = read_selection()
        username = keyring.get_password(SERVICE, USERNAME_KEY)
        password = keyring.get_password(SERVICE, username) if username else None
        if not username or not password:
            raise RuntimeError("Windows Keyring에 저장된 LMS 계정을 찾을 수 없습니다.")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(ROOT, wait_until="domcontentloaded")
            if page.locator("#username").count():
                page.locator("#username").fill(username)
                page.locator("#password").fill(password)
                page.locator("form.loginform button[type=submit]").click()
                try:
                    page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)
                except PlaywrightTimeoutError as exc:
                    raise RuntimeError("로그인되지 않았습니다. LMS 로그인 화면을 확인하세요.") from exc

            course = page.locator("a.course_link").filter(has_text=course_name)
            if course.count() == 0:
                raise RuntimeError(f"홈 과목 목록에서 '{course_name}'을 찾지 못했습니다.")
            if course.count() > 1:
                raise RuntimeError(f"'{course_name}'에 해당하는 과목이 여러 개입니다. 과목명을 더 구체적으로 입력하세요.")
            page.goto(course.first.evaluate("e => e.href"), wait_until="domcontentloaded")
            page.wait_for_timeout(800)

            section_pattern = re.compile(rf"^\s*{week}\s*주차\b")
            sections = page.locator("li.section.main").filter(has_text=section_pattern)
            label_pattern = re.compile(rf"^\s*{week}-{video_number}\b")
            activity = None
            for i in range(sections.count()):
                candidate = sections.nth(i).locator("a[href*='/mod/xncommons/view.php']").filter(has_text=label_pattern)
                if candidate.count():
                    activity = candidate.first
                    break
            if activity is None:
                raise RuntimeError(f"{week}주차의 {week}-{video_number} 영상 링크를 찾지 못했습니다.")

            activity.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1200)

            play_button = page.locator("button.vjs-big-play-button")
            if play_button.count() and play_button.first.is_visible():
                play_button.first.click()
            else:
                video = page.locator("video").first
                if video.count() and video.is_visible():
                    video.click()
                else:
                    print("강의 페이지는 열렸지만 재생 버튼을 자동으로 찾지 못했습니다. 브라우저에서 직접 재생하세요.")

            page.wait_for_timeout(10000)
            print(f"{course_name} {week}주차 {week}-{video_number} 강의를 열고 10초 기다렸습니다.")
            print("브라우저에서 계속 시청할 수 있습니다. 종료하려면 이 창에서 Enter를 누르세요.")
            input()
            browser.close()
    except Exception as exc:
        print(f"문제: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
