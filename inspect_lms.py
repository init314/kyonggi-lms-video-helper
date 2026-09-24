"""Inspect the authenticated LMS course DOM without printing credentials."""
import re
from urllib.parse import urlsplit, parse_qs

import keyring
from playwright.sync_api import sync_playwright

SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
COURSE_URL = "https://lms.kyonggi.ac.kr/course/view.php?id=6305"


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    params = parse_qs(parts.query)
    keep = [(k, v[0]) for k, v in params.items() if k in {"id", "courseid", "section"} and v]
    query = "&".join(f"{k}={v}" for k, v in keep)
    return f"{parts.scheme}://{parts.netloc}{parts.path}" + (f"?{query}" if query else "")


username = keyring.get_password(SERVICE, USERNAME_KEY)
password = keyring.get_password(SERVICE, username) if username else None
if not username or not password:
    raise SystemExit("Keyring에 LMS 로그인 정보가 없습니다. 기존 로그인 스크립트를 먼저 실행해 저장하세요.")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://lms.kyonggi.ac.kr/login.php", wait_until="domcontentloaded")
    page.locator("#username").fill(username)
    page.locator("#password").fill(password)
    page.locator("form.loginform button[type=submit]").click()
    page.wait_for_timeout(2500)
    if "login.php" in page.url:
        print("LOGIN_FAILED", "title=" + page.title())
        print(page.locator("body").inner_text()[:1200])
    else:
        page.goto(COURSE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        print("COURSE_URL", safe_url(page.url))
        print("TITLE", page.title())
        notices = page.locator(".alert, .notification, #notice, .box.errorbox").all_inner_texts()
        print("NOTICES", ascii([re.sub(r"\s+", " ", x).strip() for x in notices]))
        print("SECTIONS")
        sections = page.locator("li.section, section.course-section, .course-section, [data-section]")
        for i in range(min(sections.count(), 30)):
            section = sections.nth(i)
            text = re.sub(r"\s+", " ", section.inner_text()).strip()
            if re.search(r"[1-9]\s*주차|[1-9]-[1-9]", text):
                heading = section.locator(".sectionname, h2, h3, h4").first
                title = heading.inner_text().strip() if heading.count() else "(no heading selector)"
                print("SECTION", title, "CLASS", section.get_attribute("class"), "TEXT", text[:220])
        print("LECTURE_LINKS")
        links = page.locator("a")
        for i in range(links.count()):
            link = links.nth(i)
            text = re.sub(r"\s+", " ", link.inner_text()).strip()
            if re.match(r"^[1-9]-[1-9](?:\s|$)", text):
                parent = link.locator("xpath=..").first
                print("LINK", repr(text[:120]), safe_url(link.get_attribute("href") or ""),
                      "CLASS", link.get_attribute("class"), "PARENT", parent.evaluate("e => e.tagName.toLowerCase() + '.' + e.className"))
        print("PLAYER_SELECTORS")
        for selector in ["video", "iframe", ".activity", "li.activity", ".activityinstance", "[data-region='activity-card']"]:
            locator = page.locator(selector)
            print(selector, locator.count())
    browser.close()
