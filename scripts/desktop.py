"""Real macOS input and screen capture through Quartz.

Screen Studio follows the system cursor, so every pointer action in a recording must be a real
CGEvent. Synthetic browser input (Playwright, CDP, Selenium) never moves the cursor and Screen Studio
will not see it. All coordinates here are global screen points (top-left origin), not pixels.
"""
import math
import subprocess
import time

import Quartz

LEFT = Quartz.kCGMouseButtonLeft


def screen_size() -> tuple[float, float]:
    b = Quartz.CGDisplayBounds(Quartz.CGMainDisplayID())
    return b.size.width, b.size.height


def check_permissions() -> dict[str, bool]:
    """Both must be True for the terminal app that runs the scripts (System Settings > Privacy & Security)."""
    return {
        "accessibility (post events)": bool(Quartz.CGPreflightPostEventAccess()),
        "screen recording (screencapture)": bool(Quartz.CGPreflightScreenCaptureAccess()),
    }


def cursor() -> tuple[float, float]:
    p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
    return p.x, p.y


def _mouse(kind: int, x: float, y: float) -> None:
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, Quartz.CGEventCreateMouseEvent(None, kind, (x, y), LEFT))


def warp(x: float, y: float) -> None:
    """Jump without a path. Only for setup moments that are not recorded."""
    _mouse(Quartz.kCGEventMouseMoved, x, y)


def _ease_in_out(k: float) -> float:
    return 4 * k**3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def move(x: float, y: float, dur: float = 0.8, arc: float = 0.05, hz: int = 120) -> None:
    """Human-looking path: ease-in-out with a slight arc. Screen Studio smooths further on top."""
    x0, y0 = cursor()
    n = max(2, int(dur * hz))
    for i in range(1, n + 1):
        k = i / n
        e = _ease_in_out(k)
        lift = math.sin(k * math.pi) * arc * abs(x - x0)
        _mouse(Quartz.kCGEventMouseMoved, x0 + (x - x0) * e, y0 + (y - y0) * e - lift)
        time.sleep(dur / n)


def click(x: float, y: float, dur: float = 0.8, settle: float = 0.12, hold: float = 0.07) -> None:
    """Move, pause like a person aiming, press. The pause gives Screen Studio's click zoom a clean anchor."""
    move(x, y, dur)
    _mouse(Quartz.kCGEventMouseMoved, x, y)  # last move exactly on target; coalesced moves can stop short
    time.sleep(settle)
    _mouse(Quartz.kCGEventLeftMouseDown, x, y)
    time.sleep(hold)
    _mouse(Quartz.kCGEventLeftMouseUp, x, y)


def quick_click(x: float, y: float) -> None:
    """Setup click for app chrome (pickers, dialogs) outside the take."""
    warp(x, y)
    time.sleep(0.25)
    _mouse(Quartz.kCGEventLeftMouseDown, x, y)
    time.sleep(0.07)
    _mouse(Quartz.kCGEventLeftMouseUp, x, y)


def drag(x0: float, y0: float, x1: float, y1: float, dur: float = 0.6) -> None:
    warp(x0, y0)
    time.sleep(0.2)
    _mouse(Quartz.kCGEventLeftMouseDown, x0, y0)
    n = max(2, int(dur * 60))
    for i in range(1, n + 1):
        k = i / n
        _mouse(Quartz.kCGEventLeftMouseDragged, x0 + (x1 - x0) * k, y0 + (y1 - y0) * k)
        time.sleep(dur / n)
    _mouse(Quartz.kCGEventLeftMouseUp, x1, y1)


def scroll(dy: float, dur: float = 1.2) -> None:
    """Pixel scroll under the cursor, eased like a trackpad flick. Positive dy reveals content below."""
    n = max(1, int(dur * 60))
    done = 0
    for i in range(1, n + 1):
        target = round(dy * (1 - (1 - i / n) ** 3))
        step, done = target - done, target
        e = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, -step)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(dur / n)


def osascript(*lines: str) -> str:
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def key(code: int, *mods: str) -> None:
    """Key by virtual key code (36 Return, 53 Escape, 48 Tab). Layout-independent."""
    using = f" using {{{', '.join(m + ' down' for m in mods)}}}" if mods else ""
    osascript(f'tell application "System Events" to key code {code}{using}')


def paste(text: str) -> None:
    """Type any text into the focused native field through the clipboard.
    keystroke follows the active keyboard layout: on a Russian layout "demo" arrives as "вуьщ"."""
    subprocess.run(["pbcopy"], input=text, text=True, check=True)
    osascript('tell application "System Events" to keystroke "v" using command down')


def screenshot(path: str, region: tuple[float, float, float, float] | None = None, points: bool = True) -> str:
    """Capture the screen to look at it. With points=True the image is resized so 1 px = 1 screen point,
    which makes coordinates read off the image directly usable for clicks."""
    args = ["screencapture", "-x"]
    if region:
        args += ["-R", ",".join(str(round(v)) for v in region)]
    subprocess.run([*args, path], check=True)
    if points:
        from PIL import Image

        im = Image.open(path)
        w = round(region[2]) if region else round(screen_size()[0])
        h = round(region[3]) if region else round(screen_size()[1])
        if im.size != (w, h):
            im.resize((w, h)).save(path)
    return path


if __name__ == "__main__":
    print("screen", screen_size(), "cursor", cursor())
    for name, ok in check_permissions().items():
        print(f"{'ok ' if ok else 'MISSING'} {name}")
