from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1400, "height": 1000})
    page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
    page.click("#viewCalendarBtn")
    page.wait_for_timeout(1000)
    page.screenshot(path="_screenshot_calendar.png", full_page=False)

    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.wait_for_timeout(500)
    print("Console errors:", errors)

    browser.close()
