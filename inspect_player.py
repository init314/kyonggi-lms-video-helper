"""Inspect the visible play control on one authenticated lecture page."""
import keyring
from playwright.sync_api import sync_playwright

SERVICE = "Kyonggi LMS login"
USERNAME_KEY = "saved-username"
LOGIN = "https://lms.kyonggi.ac.kr/"
LECTURE = "https://lms.kyonggi.ac.kr/mod/xncommons/view.php?id=1106000"

username = keyring.get_password(SERVICE, USERNAME_KEY)
password = keyring.get_password(SERVICE, username) if username else None
if not username or not password:
    raise SystemExit("Keyring에 저장된 LMS 계정을 찾을 수 없습니다.")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(LOGIN, wait_until="domcontentloaded")
    if page.locator("#username").count():
        page.locator("#username").fill(username)
        page.locator("#password").fill(password)
        page.locator("form.loginform button[type=submit]").click()
        page.wait_for_url(lambda url: "login.php" not in url, timeout=20000)
    page.goto(LECTURE, wait_until="domcontentloaded")
    page.wait_for_timeout(3500)
    print("PAGE", page.url.split("?")[0], "TITLE", ascii(page.title()))
    view = page.get_by_text("콘텐츠 보기", exact=True)
    print("CONTENT_VIEW_COUNT", view.count())
    if view.count():
        print("CONTENT_VIEW_NODE", ascii(view.first.evaluate("e => e.outerHTML + ' PARENT ' + e.parentElement.outerHTML.slice(0,1000)")))
        try:
            with page.expect_popup(timeout=2500) as popup:
                view.first.click()
            player_page = popup.value
        except Exception:
            player_page = page
            page.wait_for_timeout(2500)
        page = player_page
        page.wait_for_timeout(3000)
        print("AFTER_CONTENT_VIEW", page.url.split("?")[0], "TITLE", ascii(page.title()))
    result = page.evaluate("""() => {
      const visible = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e); return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
      const els = [...document.querySelectorAll('button, [role=button], video, iframe, .vjs-big-play-button, .play-button, .play')].filter(visible);
      return els.map(e => { const r=e.getBoundingClientRect(); return {
        tag:e.tagName.toLowerCase(), id:e.id, cls:typeof e.className==='string'?e.className:'',
        role:e.getAttribute('role'), aria:e.getAttribute('aria-label'), title:e.getAttribute('title'),
        text:(e.innerText||'').trim().slice(0,100), x:Math.round(r.x), y:Math.round(r.y),
        width:Math.round(r.width), height:Math.round(r.height), centerX:Math.round(r.x+r.width/2), centerY:Math.round(r.y+r.height/2),
        src:e.currentSrc||e.src||''
      }; });
    }""")
    for item in result:
        item["src"] = "present" if item.get("src") else ""
        print("PLAYER_ELEMENT", ascii(item))
    for index, frame in enumerate(page.frames):
        print("FRAME", index, frame.url.split("?")[0])
        try:
            frame_controls = frame.evaluate("""() => {
              const visible = e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e); return r.width>0 && r.height>0 && s.visibility!=='hidden' && s.display!=='none'; };
              return [...document.querySelectorAll('button, [role=button], video, [class*=play]')].filter(visible).map(e => {
                const r=e.getBoundingClientRect();
                return {tag:e.tagName.toLowerCase(), id:e.id, cls:typeof e.className==='string'?e.className:'',
                  text:(e.innerText||'').trim().slice(0,60), aria:e.getAttribute('aria-label'), title:e.getAttribute('title'),
                  x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height),
                  cx:Math.round(r.x+r.width/2), cy:Math.round(r.y+r.height/2)};
              });
            }""")
            for control in frame_controls:
                print("FRAME_CONTROL", ascii(control))
        except Exception as exc:
            print("FRAME_INSPECT_ERROR", type(exc).__name__)
    cms_frame = next((f for f in page.frames if "cms.kyonggi.ac.kr" in f.url), None)
    if cms_frame:
        play = cms_frame.locator(".vc-front-screen-play-btn")
        print("CENTER_PLAY_COUNT", play.count())
        if play.count():
            details = play.evaluate("""e => { const r=e.getBoundingClientRect(), s=getComputedStyle(e); return {
              outerHTML:e.outerHTML, title:e.title, cls:e.className, display:s.display, visibility:s.visibility,
              x:Math.round(r.x), y:Math.round(r.y), width:Math.round(r.width), height:Math.round(r.height),
              centerX:Math.round(r.x+r.width/2), centerY:Math.round(r.y+r.height/2),
              scripts:[...document.scripts].map(s=>s.src).filter(Boolean).map(u=>new URL(u).pathname.split('/').pop())
            }; }""")
            print("CENTER_PLAY_DETAILS", ascii(details))
            play.click()
            page.wait_for_timeout(5000)
            playback = cms_frame.evaluate("""() => [...document.querySelectorAll('video')].map(v => ({
              paused:v.paused, currentTime:Math.round(v.currentTime*10)/10, duration:Number.isFinite(v.duration)?Math.round(v.duration*10)/10:null,
              readyState:v.readyState, networkState:v.networkState, sourcePresent:!!(v.currentSrc||v.src), error:v.error?.code||null
            }))""")
            print("PLAYBACK_STATE", ascii(playback))
            media_types = cms_frame.evaluate("""() => {
              const urls=[...document.querySelectorAll('video')].map(v=>v.currentSrc||v.src).filter(Boolean);
              return urls.map(raw=>{const u=new URL(raw); return {host:u.hostname, extension:u.pathname.split('.').pop().toLowerCase()};});
            }""")
            print("MEDIA_TYPES", ascii(media_types))
            for frame in page.frames:
                try:
                    info = frame.evaluate("""() => ({
                      url: location.href.split('?')[0],
                      mediaFiles: [...document.querySelectorAll('[id*="media_file"], [name*="media_file"], [data-media-file]')].map(e=>({tag:e.tagName,id:e.id,name:e.getAttribute('name'),data:e.getAttribute('data-media-file')})),
                      videos: [...document.querySelectorAll('video,source')].map(e=>({tag:e.tagName,src:e.currentSrc||e.src||e.getAttribute('src')})),
                      mediaText: document.documentElement.innerHTML.match(/.{0,80}media_file.{0,200}/ig)?.slice(0,5)||[]
                    })""")
                    for video in info.get("videos", []):
                        video["src"] = "present" if video.get("src") else ""
                    info["mediaText"] = ["media_file reference present" for x in info.get("mediaText", [])]
                    print("AFTER_PLAY_FRAME", ascii(info))
                except Exception as exc:
                    print("AFTER_PLAY_FRAME_ERROR", type(exc).__name__)
    print("BODY_TAIL", ascii(page.locator("body").inner_text()[-700:]))
    browser.close()
