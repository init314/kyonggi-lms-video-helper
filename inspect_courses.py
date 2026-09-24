"""Log in using Windows Keyring and inspect LMS course navigation DOM."""
import json
import re
from urllib.parse import urlsplit, parse_qs

import keyring
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
ROOT = "https://lms.kyonggi.ac.kr/"


def clean_url(url):
    p = urlsplit(url)
    qs = parse_qs(p.query)
    safe = [(k, v[0]) for k, v in qs.items() if k in {"id", "categoryid", "section"} and v]
    query = "&".join(f"{k}={v}" for k, v in safe)
    return f"{p.scheme}://{p.netloc}{p.path}" + (f"?{query}" if query else "")


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
        try:
            page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)
        except PlaywrightTimeoutError:
            print("LOGIN_FAILED", ascii(page.locator("body").inner_text()[:800]))
            browser.close()
            raise SystemExit(1)

    page.goto(ROOT, wait_until="domcontentloaded")
    page.wait_for_timeout(1800)
    print("HOME", clean_url(page.url))
    print("TITLE", ascii(page.title()))

    course_links = page.locator("a[href*='/course/view.php']")
    print("COURSE_LINK_COUNT", course_links.count())
    for i in range(course_links.count()):
        a = course_links.nth(i)
        title = re.sub(r"\s+", " ", a.inner_text()).strip()
        parent = a.locator("xpath=..").first
        grandparent = parent.locator("xpath=..").first
        print("COURSE", ascii(title), clean_url(a.get_attribute("href") or ""),
              "A_CLASS", ascii(a.get_attribute("class") or ""),
              "PARENT", ascii(parent.evaluate("e => e.tagName.toLowerCase() + '.' + e.className")),
              "GRANDPARENT", ascii(grandparent.evaluate("e => e.tagName.toLowerCase() + '.' + e.className")))

    print("NAV_LINKS")
    links = page.locator("a")
    for i in range(links.count()):
        a = links.nth(i)
        text = re.sub(r"\s+", " ", a.inner_text()).strip()
        href = a.get_attribute("href") or ""
        if re.search(r"강의|강좌|과목|course|dashboard|my/", text + " " + href, re.I):
            print("NAV", ascii(text[:100]), clean_url(href))

    print("COURSE_CONTAINERS")
    for selector in [".coursebox", ".course-list", ".courses", "[data-region='course-content']", "[data-region='course-info-container']", "#frontpage-course-list"]:
        loc = page.locator(selector)
        print("SELECTOR", selector, "COUNT", loc.count())
        for j in range(min(loc.count(), 5)):
            text = re.sub(r"\s+", " ", loc.nth(j).inner_text()).strip()
            print("CONTAINER", ascii(text[:300]))

    management_link = page.locator("a.course_link").filter(has_text="관리회계")
    if management_link.count():
        course_href = management_link.first.evaluate("e => e.href")
        page.goto(course_href, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        print("MANAGEMENT_COURSE", clean_url(page.url))
        for selector in ["li.section", "li.course-section", ".course-section", ".section.main"]:
            loc = page.locator(selector)
            print("WEEK_SELECTOR", selector, "COUNT", loc.count())
            for j in range(min(loc.count(), 20)):
                node = loc.nth(j)
                text = re.sub(r"\s+", " ", node.inner_text()).strip()
                if re.search(r"\d+\s*주차|\d+-\d+", text):
                    h = node.locator(".sectionname, h2, h3, h4").first
                    title = h.inner_text().strip() if h.count() else ""
                    print("WEEK", ascii(title), "CLASS", ascii(node.get_attribute("class") or ""), "TEXT", ascii(text[:500]))
        print("WEEKLY_VIDEO_LINKS")
        links = page.locator("a")
        for j in range(links.count()):
            a = links.nth(j)
            text = re.sub(r"\s+", " ", a.inner_text()).strip()
            if re.match(r"^[1-9]-[1-9](?:\s|$)", text):
                parent = a.locator("xpath=..").first
                print("VIDEO", ascii(text[:160]), clean_url(a.get_attribute("href") or ""),
                      "A_CLASS", ascii(a.get_attribute("class") or ""),
                      "PARENT", ascii(parent.evaluate("e => e.tagName.toLowerCase() + '.' + e.className")))
        for selector in [".activity", "li.activity", ".activityinstance", ".course-content", ".weeks", ".attendance"]:
            print("COURSE_SELECTOR", selector, page.locator(selector).count())
        attendance = page.locator(".attendance")
        for j in range(min(attendance.count(), 5)):
            node = attendance.nth(j)
            print("ATTENDANCE_BLOCK", ascii(re.sub(r"\s+", " ", node.inner_text()).strip()[:1000]),
                  "CLASS", ascii(node.get_attribute("class") or ""))
    browser.close()
