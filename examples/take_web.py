"""Example take: a short Wikipedia search filmed with Screen Studio.

    python take_web.py --dry     # rehearse: same moves, nothing recorded
    python take_web.py           # record, export, write marks for assemble.py

Copy this file for a new product: change URL, the window rect and scenario(). Keep scenario() free of
Screen Studio calls so the dry run and the take do exactly the same thing.
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from playwright.sync_api import sync_playwright  # noqa: E402

import screen_studio as ss  # noqa: E402
from browser import Browser, Marks  # noqa: E402

OUT = pathlib.Path(__file__).parent / "out"
URL = "https://en.wikipedia.org/wiki/Main_Page"
WINDOW = (4, 60, 1440, 838)  # x, y, w, h in points; stays left of a right-side Dock and above the picker


def scenario(b: Browser, mark: Marks) -> None:
    mark("cap", "Search any topic")
    x, y = b.box("input[name=search]")
    b.click(x, y)
    b.wait(0.4)
    b.type("Screen recording")
    b.wait(1.2)
    b.page.keyboard.press("Enter")  # keys don't need the cursor; only pointer actions must be real
    b.page.wait_for_load_state()
    b.wait(1.5)
    mark("cap", "Read without leaving the flow")
    b.move(700, 500, 1.0)
    b.scroll(600, 1.6)
    b.wait(1.5)
    b.scroll(-300, 1.0)
    b.wait(1.0)
    mark("end")


def main(dry: bool) -> None:
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as pw:
        b = Browser(pw, URL, *WINDOW)
        b.wait(2)
        mark = Marks()
        if dry:
            scenario(b, mark)
            return
        ss.close_widget(keep=False)  # a leftover widget from the last take would eat clicks
        ss.start_area(*b.content_rect())  # the page only: no title bar in the video
        started = time.time()
        b.wait(0.8)  # a still beat before the first move gives the edit a clean in-point
        scenario(b, mark)
        b.wait(1.0)
        ss.stop_recording()
        time.sleep(4)
        mark.save(str(OUT / "web_marks.json"))
        project = ss.latest_project(started - 10)
        print("project", project, "t0", ss.recording_start(project))
        print("export", ss.quick_export(str(OUT), "web"))
        ss.close_widget(keep=True)
        b.ctx.close()


if __name__ == "__main__":
    main("--dry" in sys.argv)
