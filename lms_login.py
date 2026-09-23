"""Open the Kyonggi LMS and sign in with credentials stored in Windows."""

from getpass import getpass
import sys
import re

try:
    import keyring
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError as exc:
    print(f"필요한 패키지가 없습니다: {exc.name}")
    print("PowerShell에서 다음을 실행하세요:")
    print("  py -m pip install playwright keyring")
    print("  py -m playwright install chromium")
    raise SystemExit(1)


LOGIN_URL = "https://lms.kyonggi.ac.kr/login.php"
SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"


def get_credentials() -> tuple[str, str]:
    username = keyring.get_password(SERVICE, USERNAME_KEY)
    password = keyring.get_password(SERVICE, username) if username else None
    if username and password:
        return username, password

    print("처음 한 번만 계정을 입력하면 Windows 자격 증명 관리자에 저장됩니다.")
    username = input("경기대학교 LMS 아이디: ").strip()
    password = getpass("비밀번호 (입력 내용은 화면에 표시되지 않습니다): ")
    if not username or not password:
        raise ValueError("아이디와 비밀번호를 모두 입력해야 합니다.")
    keyring.set_password(SERVICE, username, password)
    keyring.set_password(SERVICE, USERNAME_KEY, username)
    return username, password


def open_absent_week_lecture(page) -> None:
    """Open one lecture from the absent weeks visible in the user's screenshot."""
    course_url = "https://lms.kyonggi.ac.kr/course/view.php?id=6305"
    page.goto(course_url, wait_until="domcontentloaded")
    page.wait_for_timeout(1200)

    labels = [f"{week}-{part}" for week in (4, 5, 6) for part in (1, 2, 3)]
    print("출석이 결석으로 표시된 4~6주차 영상입니다:")
    for index, label in enumerate(labels, start=1):
        print(f"  {index}. {label}")
    choice = input("열 영상 번호를 입력하세요 (1-9): ").strip()
    if not choice.isdigit() or not 1 <= int(choice) <= len(labels):
        print("선택이 없어 강의 목록을 열어 두었습니다.")
        return

    label = labels[int(choice) - 1]
    lecture = page.get_by_role("link", name=re.compile(re.escape(label)))
    if lecture.count() == 0:
        lecture = page.get_by_text(re.compile(re.escape(label)))
    if lecture.count() == 0:
        print(f"{label} 항목을 찾지 못했습니다. 강의 목록에서 직접 선택해주세요.")
        return
    lecture.first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1800)

    play_button = page.locator("button.vjs-big-play-button")
    if play_button.count() and play_button.first.is_visible():
        play_button.first.click()
        print(f"{label}을 열고 재생을 눌렀습니다. 영상을 끝까지 시청해 주세요.")
    else:
        print(f"{label} 강의 페이지를 열었습니다. 재생 버튼이 보이면 눌러주세요.")


def main() -> None:
    try:
        if "--reset" in sys.argv:
            try:
                keyring.delete_password(SERVICE, USERNAME_KEY)
            except keyring.errors.PasswordDeleteError:
                pass
            print("저장된 아이디 정보를 초기화했습니다. 새 계정을 입력하세요.")
        username, password = get_credentials()
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
            page.locator("#username").fill(username)
            page.locator("#password").fill(password)
            page.locator("form.loginform button[type=submit]").click()
            try:
                page.wait_for_url(lambda url: "login.php" not in url, timeout=15000)
            except PlaywrightTimeoutError:
                print("로그인이 완료되지 않았습니다. 브라우저에서 오류나 추가 인증을 확인하세요.")
            else:
                print("로그인된 LMS를 열었습니다. 종료하려면 이 창에서 Enter를 누르세요.")
                try:
                    open_absent_week_lecture(page)
                except Exception as exc:
                    print(f"강의 자동 열기에 실패했습니다: {exc}")
                    print("브라우저에서 관리회계 과목과 4-1 강의를 직접 열어주세요.")
            input()
            browser.close()
    except Exception as exc:
        print(f"실행 중 문제가 발생했습니다: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
