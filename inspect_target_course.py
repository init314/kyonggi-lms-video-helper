"""Inspect a selected course's week/activity DOM using the saved LMS login."""
import re
import keyring
from playwright.sync_api import sync_playwright

SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
ROOT = "https://lms.kyonggi.ac.kr/"
COURSE_FRAGMENT = "사고와표현"
WEEK = 4

username = keyring.get_password(SERVICE, USERNAME_KEY)
password = keyring.get_password(SERVICE, username) if username else None
if not username or not password:
    raise SystemExit("Keyring에 저장된 LMS 계정을 찾을 수 없습니다.")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(ROOT, wait_until="domcontentloaded")
    if page.locator("#username").count():
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("form.loginform button[type=submit]").click()
        page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)

    courses = page.locator("a.course_link")
    matches = []
    for i in range(courses.count()):
        link = courses.nth(i)
        name = re.sub(r"\s+", "", link.inner_text())
        if COURSE_FRAGMENT in name:
            matches.append((name, link.evaluate("e => e.href")))
    print("COURSE_MATCHES", ascii(matches))
    if not matches:
        raise SystemExit("과목 링크가 없습니다.")

    page.goto(matches[0][1], wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    print("COURSE_URL", page.url.split("?")[0])
    sections = page.locator("li.section")
    print("SECTION_COUNT", sections.count())
    for i in range(sections.count()):
        section = sections.nth(i)
        text = re.sub(r"\s+", " ", section.inner_text()).strip()
        if re.search(rf"^\s*{WEEK}\s*주차\b", text):
            heading = section.locator(".sectionname").first
            print("WEEK_SECTION", ascii(text[:600]), "CLASS", ascii(section.get_attribute("class") or ""),
                  "HEADING", ascii(heading.inner_text() if heading.count() else "NO_HEADING"))
            links = section.locator("a")
            for j in range(links.count()):
                a = links.nth(j)
                label = re.sub(r"\s+", " ", a.inner_text()).strip()
                href = a.get_attribute("href") or ""
                if label or href:
                    print("WEEK_LINK", ascii(label[:120]), ascii(href), "CLASS", ascii(a.get_attribute("class") or ""))
    browser.close()
