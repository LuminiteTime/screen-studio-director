"""A real Chrome window you can film: Playwright opens and inspects it, desktop.py moves the real cursor.

Playwright is used for what it is good at (navigation, waiting, finding elements and their boxes).
Every visible pointer action goes through desktop.py, because Screen Studio only sees the system cursor.
Keyboard text can go through Playwright: typing does not need the cursor.
"""
import json
import time

from playwright.sync_api import sync_playwright

import desktop

FLUTTER_FIND = """([label, nth, contains]) => {
  const hits = [...document.querySelectorAll('flt-semantics')].map(e => {
    const l = (e.getAttribute('aria-label') || e.innerText || '').trim(); const r = e.getBoundingClientRect();
    return {l, x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width};
  }).filter(h => h.w > 0 && (contains ? h.l.includes(label) : h.l.startsWith(label)));
  const seen = new Set(), uniq = hits.filter(h => { const k = Math.round(h.x) + ':' + Math.round(h.y);
    return seen.has(k) ? false : seen.add(k); });  // Flutter nests several nodes with one label
  uniq.sort((a, b) => a.y - b.y || a.x - b.x);
  return uniq[nth] ? [uniq[nth].x, uniq[nth].y] : null;
}"""


class Browser:
    """Chrome in --app mode (no tabs, no address bar) at a fixed window rect.

    Keep the window off the Dock and away from Screen Studio's floating widgets: anything drawn over
    the recorded rectangle ends up in the video, and anything under the cursor eats the clicks.
    """

    def __init__(self, pw, url: str, x: int, y: int, w: int, h: int, init_script: str | None = None):
        self.url = url
        self.ctx = pw.chromium.launch_persistent_context(
            "",
            channel="chrome",
            headless=False,
            no_viewport=True,  # real window size = real layout; viewport emulation breaks screen mapping
            args=[f"--app={url}", f"--window-position={x},{y}", f"--window-size={w},{h}",
                  "--hide-crash-restore-bubble"],
            ignore_default_args=["--enable-automation", "--no-sandbox"],  # both draw infobars on the page
        )
        if init_script:
            self.ctx.add_init_script(init_script)
        self.page = self.ctx.pages[0]
        self.page.wait_for_load_state()
        if not self.page.url.startswith("http"):  # --app needs an ASCII URL; percent-encode the rest
            self.page.goto(url)
        self._origin = None

    # ---------- coordinates ----------
    def origin(self) -> tuple[float, float]:
        """Screen point of the page's (0, 0). Assumes no viewport emulation (or call freeze_origin first)."""
        if self._origin:
            return self._origin
        sx, sy, ow, oh, iw, ih = self.page.evaluate(
            "[screenX, screenY, outerWidth, outerHeight, innerWidth, innerHeight]"
        )
        return sx + (ow - iw) / 2, sy + (oh - ih)

    def freeze_origin(self) -> None:
        self._origin = self.origin()

    def screen(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.origin()
        return ox + x, oy + y

    def content_rect(self) -> tuple[float, float, float, float]:
        ox, oy = self.origin()
        w, h = self.page.evaluate("[innerWidth, innerHeight]")
        return ox, oy, w, h

    def emulate_phone(self, w: int = 390, h: int = 844, dpr: int = 2) -> tuple[float, float, float, float]:
        """Render a phone-sized viewport in the window's top-left corner and return its screen rect for
        Area recording. Chrome windows cannot be narrower than ~500 pt, so this replaces a narrow window.
        Input stays 1:1 because nothing is scaled."""
        self.freeze_origin()
        cdp = self.ctx.new_cdp_session(self.page)
        cdp.send("Emulation.setDeviceMetricsOverride",
                 {"width": w, "height": h, "deviceScaleFactor": dpr, "mobile": False})
        ox, oy = self._origin
        return ox, oy, w, h

    # ---------- finding things ----------
    def box(self, selector: str, nth: int = 0, timeout: float = 8.0) -> tuple[float, float]:
        """Centre of a Playwright locator (CSS, text=..., role=...) in page coordinates."""
        loc = self.page.locator(selector).nth(nth)
        loc.wait_for(state="visible", timeout=timeout * 1000)
        b = loc.bounding_box()
        return b["x"] + b["width"] / 2, b["y"] + b["height"] / 2

    def flutter_enable(self) -> None:
        """Flutter web draws to a canvas; its accessibility tree appears only after this placeholder click."""
        self.page.evaluate("document.querySelector('flt-semantics-placeholder')?.click()")
        self.page.wait_for_timeout(800)

    def flutter(self, label: str, nth: int = 0, contains: bool = False, timeout: float = 8.0):
        """Centre of the nth (top-to-bottom) Flutter semantics node whose label starts with / contains label."""
        end = time.time() + timeout
        while True:
            r = self.page.evaluate(FLUTTER_FIND, [label, nth, contains])
            if r:
                return r[0], r[1]
            if time.time() > end:
                raise RuntimeError(f"no Flutter node {label!r} #{nth}")
            self.page.wait_for_timeout(200)

    # ---------- filmed actions (page coordinates in, real cursor out) ----------
    def move(self, x: float, y: float, dur: float = 0.8) -> None:
        desktop.move(*self.screen(x, y), dur)

    def click(self, x: float, y: float, dur: float = 0.8) -> None:
        desktop.click(*self.screen(x, y), dur)

    def scroll(self, dy: float, dur: float = 1.2) -> None:
        desktop.scroll(dy, dur)

    def scroll_to(self, find, y_target: float, tries: int = 2) -> None:
        """Scroll until find() returns a point near y_target. Wheel distance per pixel differs between
        apps and pixel ratios, so measure and correct instead of guessing."""
        for dur in (1.6, 0.6)[:tries]:
            _, y = find()
            if abs(y - y_target) < 24:
                return
            self.scroll(y - y_target, dur)
            self.page.wait_for_timeout(500)

    def type(self, text: str, delay_ms: int = 55) -> None:
        self.page.keyboard.type(text, delay=delay_ms)

    def go(self, url_or_hash: str) -> None:
        if url_or_hash.startswith("#"):
            self.page.evaluate(f"location.hash = {json.dumps(url_or_hash[1:])}")
        else:
            self.page.goto(url_or_hash)

    def wait(self, s: float) -> None:
        self.page.wait_for_timeout(int(s * 1000))


class Marks:
    """Scenario timeline in unix seconds. Captions and cuts are placed from these after export."""

    def __init__(self):
        self.items: list[tuple[float, str, str | None]] = []

    def __call__(self, kind: str, text: str | None = None) -> None:
        self.items.append((time.time(), kind, text))

    def save(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=0)


def check_mapping(url: str = "https://example.com") -> None:
    """Self-check: the page must see the real cursor exactly where Browser.screen() says it is."""
    with sync_playwright() as pw:
        b = Browser(pw, url, 40, 60, 1280, 800)
        b.page.evaluate("document.addEventListener('pointermove', e => window._m = [e.clientX, e.clientY], true)")
        for x, y in [(200, 150), (900, 500)]:
            b.move(x, y, 0.4)
            b.wait(0.3)
            seen = b.page.evaluate("window._m")
            assert seen and abs(seen[0] - x) < 2 and abs(seen[1] - y) < 2, (x, y, seen)
        print("mapping ok, page origin", b.origin())
        b.ctx.close()


if __name__ == "__main__":
    check_mapping()
