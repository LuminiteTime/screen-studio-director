"""Drive Screen Studio (macOS) without touching it by hand.

Screen Studio is an Electron app. Its menus are native (scriptable with System Events), but its own
UI (recording picker, Start button, quick-export widget, dialogs) is web content that macOS hides from
accessibility until AXManualAccessibility is set. After that every label is a findable AXStaticText.
"""
import json
import pathlib
import subprocess
import time

from ApplicationServices import (
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementSetAttributeValue,
    AXValueGetValue,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)

import desktop

APP = "Screen Studio"
SUPPORT = pathlib.Path.home() / "Library/Application Support/Screen Studio"
PREFS = SUPPORT / "user-preferences/settings-persistance.json"


# ---------- app lifecycle ----------
def pid() -> int | None:
    out = subprocess.run(["pgrep", "-x", APP], capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else None


def launch(wait: float = 3.0) -> None:
    subprocess.run(["open", "-a", APP], check=True)
    time.sleep(wait)


def quit_app(timeout: float = 10.0) -> bool:
    """Quit politely. An open unsaved project shows a Save/Delete dialog: handle it with click_text."""
    if not pid():
        return True
    desktop.osascript(f'tell application "{APP}" to quit')
    end = time.time() + timeout
    while time.time() < end:
        if not pid():
            return True
        time.sleep(0.5)
    return False


# ---------- preferences ----------
def prefs() -> dict:
    return json.loads(PREFS.read_text())["json"]


def set_prefs(**values) -> dict:
    """Edit settings-persistance.json. The running app keeps its own copy and writes it back on quit,
    so this quits Screen Studio first. Returns the previous values for restore."""
    quit_app()
    data = json.loads(PREFS.read_text())
    old = {k: data["json"].get(k) for k in values}
    data["json"].update(values)
    PREFS.write_text(json.dumps(data, indent=2))
    return old


def projects_dir() -> pathlib.Path:
    return pathlib.Path(prefs().get("projectsFolderPath") or pathlib.Path.home() / "Screen Studio Projects")


# ---------- native menus ----------
def menu(name: str, item: str) -> None:
    desktop.osascript(
        f'tell application "System Events" to tell process "{APP}" to '
        f'click menu item "{item}" of menu "{name}" of menu bar item "{name}" of menu bar 1'
    )


def menu_items(name: str) -> list[str]:
    out = desktop.osascript(
        f'tell application "System Events" to tell process "{APP}" to '
        f'get name of every menu item of menu "{name}" of menu bar item "{name}" of menu bar 1'
    )
    return [s.strip() for s in out.split(",")]


def is_recording() -> bool:
    return "Stop recording" in menu_items("Record")


def stop_recording() -> None:
    menu("Record", "Stop recording")


# ---------- accessibility over the Electron UI ----------
def _attr(e, name):
    err, v = AXUIElementCopyAttributeValue(e, name, None)
    return v if err == 0 else None


def _rect(e) -> tuple[float, float, float, float] | None:
    p, s = _attr(e, "AXPosition"), _attr(e, "AXSize")
    if p is None or s is None:
        return None
    _, pt = AXValueGetValue(p, kAXValueCGPointType, None)
    _, sz = AXValueGetValue(s, kAXValueCGSizeType, None)
    return pt.x, pt.y, sz.width, sz.height


def _app():
    p = pid()
    if not p:
        raise RuntimeError("Screen Studio is not running")
    app = AXUIElementCreateApplication(p)
    AXUIElementSetAttributeValue(app, "AXManualAccessibility", True)  # Electron exposes its DOM after this
    if not _attr(app, "AXWindows"):  # windows of a background Screen Studio are hidden from AX
        subprocess.run(["open", "-a", APP], check=True)
        time.sleep(1.5)
    return app


def texts() -> list[tuple[str, str, tuple[float, float, float, float]]]:
    """Every visible label and button title: (window title, text, rect in screen points)."""
    out = []

    def walk(e, title):
        role = _attr(e, "AXRole")
        if role in ("AXStaticText", "AXButton"):  # Electron labels are text; native alert buttons have titles
            v, r = _attr(e, "AXValue" if role == "AXStaticText" else "AXTitle"), _rect(e)
            if v and r and r[2] > 0:
                out.append((title, str(v), r))
        for c in _attr(e, "AXChildren") or []:
            walk(c, title)

    for w in _attr(_app(), "AXWindows") or []:
        walk(w, _attr(w, "AXTitle") or "")
    return out


def windows() -> list[tuple[str, tuple[float, float, float, float]]]:
    return [(_attr(w, "AXTitle") or "", _rect(w)) for w in _attr(_app(), "AXWindows") or []]


def find_text(label: str, exact: bool = True, timeout: float = 5.0):
    end = time.time() + timeout
    while True:
        for _, v, (x, y, w, h) in texts():
            if (v == label) if exact else (label in v):
                return x + w / 2, y + h / 2
        if time.time() > end:
            raise RuntimeError(f"Screen Studio label not found: {label!r}")
        time.sleep(0.3)


def click_text(label: str, exact: bool = True, timeout: float = 5.0) -> None:
    x, y = find_text(label, exact, timeout)
    desktop.quick_click(x, y)


# ---------- recording ----------
def _picker() -> None:
    """Show the bottom recording picker with no mode armed. Record > New recording… is the reliable way:
    `open -a` brings the app forward but does not bring the picker back after a take or an export."""
    if not pid():
        launch()
    if not any(t == "Start Recording" for t, _ in windows()):
        menu("Record", "New recording…")
        time.sleep(1.5)
    reset_picker()
    time.sleep(0.5)


def start_window(target: tuple[float, float], countdown: float = 4.0) -> None:
    """Window mode: arm Window, click the target window, press Start recording.
    target is any point inside the window to record; the window must be frontmost and unobstructed."""
    _picker()
    click_text("Window")
    time.sleep(1.0)
    desktop.quick_click(*target)
    time.sleep(1.0)
    click_text("Start recording", timeout=4.0)
    time.sleep(countdown)


def _area_fields() -> list:
    """Size w, Size h, Position x, Position y incrementors of the Area panel, in reading order."""
    found = []

    def walk(e):
        if _attr(e, "AXRole") == "AXIncrementor":
            found.append(e)
        for c in _attr(e, "AXChildren") or []:
            walk(c)

    for w in _attr(_app(), "AXWindows") or []:
        if "Picker Highlighter" in (_attr(w, "AXTitle") or ""):
            walk(w)
    return sorted(found, key=lambda e: (_rect(e)[1], _rect(e)[0]))


def start_area(x: float, y: float, w: float, h: float, countdown: float = 4.0) -> None:
    """Area mode with an exact rectangle in screen points. Screen Studio remembers the last area and a
    drag inside it MOVES it instead of drawing a new one, so the numbers go into the Size/Position
    fields. Keep the rectangle on screen: values past the edge are clamped silently."""
    _picker()
    click_text("Area")
    time.sleep(1.2)
    if len(_area_fields()) < 4:  # first use: no remembered area, so draw one to get the panel
        desktop.drag(x, y, x + w, y + h, 0.5)
        time.sleep(1.0)
    for field, value in zip(_area_fields(), (w, h, x, y)):  # size before position, or position gets clamped
        fx, fy, fw, fh = _rect(field)
        desktop.quick_click(fx + fw / 2, fy + fh / 2)
        desktop.key(0, "command")
        desktop.paste(str(round(value)))
        desktop.key(48)  # Tab commits the value
        time.sleep(0.3)
    got = [round(_attr(f, "AXValue")) for f in _area_fields()]
    if got != [round(v) for v in (w, h, x, y)]:
        raise RuntimeError(f"area is {got}, wanted {[w, h, x, y]}")
    click_text("Start recording", timeout=4.0)
    desktop.warp(x + w * 0.75, y + h * 0.5)
    time.sleep(countdown)


def start_display(countdown: float = 4.0) -> None:
    _picker()
    click_text("Display")
    time.sleep(1.0)
    click_text("Start recording", timeout=4.0)
    time.sleep(countdown)


def reset_picker() -> None:
    """Escape twice: first drops the selection, second disarms the mode."""
    desktop.key(53)
    time.sleep(0.4)
    desktop.key(53)


# ---------- after recording ----------
def latest_project(since: float = 0) -> pathlib.Path | None:
    items = [p for p in projects_dir().glob("*.screenstudio") if p.stat().st_mtime >= since]
    return max(items, key=lambda p: p.stat().st_mtime) if items else None


def recording_start(project: pathlib.Path) -> float:
    """Unix seconds of the first recorded frame. Subtract it from scenario marks to place captions."""
    meta = json.loads((project / "recording/metadata.json").read_text())
    for r in meta["recorders"]:
        for s in r.get("sessions", []):
            if "unixStartMs" in s:
                return s["unixStartMs"] / 1000
    raise RuntimeError(f"no session start in {project}")


def load_project(project: pathlib.Path) -> dict:
    """project.json of a .screenstudio folder: the "json" object holds config (look) and scenes (edit)."""
    return json.loads((project / "project.json").read_text())


def save_project(project: pathlib.Path, data: dict) -> None:
    """Write edits back. Quit Screen Studio first: an open editor keeps its own copy and overwrites the file."""
    if pid():
        quit_app()
    (project / "project.json").write_text(json.dumps(data))


def save_dialog(folder: str, name: str) -> None:
    """Fill a native Save panel: Go-to-folder sheet for the path, clipboard paste for the name."""
    time.sleep(1.2)
    desktop.key(5, "command", "shift")  # ⌘⇧G
    time.sleep(0.8)
    desktop.paste(folder)
    time.sleep(0.4)
    desktop.key(36)
    time.sleep(0.8)
    desktop.key(0, "command")  # ⌘A in the name field
    desktop.paste(name)
    time.sleep(0.4)
    desktop.key(36)


def wait_file(path: pathlib.Path, timeout: float = 600) -> pathlib.Path:
    """Export writes progressively; done when the size stops changing."""
    end, last = time.time() + timeout, -1
    while time.time() < end:
        if path.exists():
            size = path.stat().st_size
            if size == last and size > 0:
                return path
            last = size
        time.sleep(2)
    raise TimeoutError(path)


def quick_export(folder: str, name: str, timeout: float = 600) -> pathlib.Path:
    """From the quick-export widget that appears after a take (uses Settings > Quick export)."""
    click_text("Save...", exact=False, timeout=15)
    save_dialog(folder, name)
    return wait_file(pathlib.Path(folder) / f"{name}.mp4", timeout)


def export_project(project: pathlib.Path, folder: str, name: str, timeout: float = 600) -> pathlib.Path:
    """Open a project in the editor and export it with the quick-export settings."""
    subprocess.run(["open", str(project)], check=True)
    time.sleep(6)
    menu("Export", "Quick export to file…")
    save_dialog(folder, name)
    return wait_file(pathlib.Path(folder) / f"{name}.mp4", timeout)


def widget_rect() -> tuple[float, float, float, float] | None:
    """The quick-export widget is a small window titled "Screen Studio" that holds a "Save..." label."""
    for _, (x, y, w, h) in windows():
        if w < 700 and h < 700 and any(v == "Save..." and x <= r[0] <= x + w and y <= r[1] <= y + h
                                       for _, v, r in texts()):
            return x, y, w, h
    return None


def close_widget(keep: bool) -> bool:
    """Close the quick-export widget. It floats bottom-left and steals clicks meant for your app."""
    rect = widget_rect()
    if not rect:
        return False
    x, y, w, h = rect
    desktop.warp(x + w / 2, y + h / 2)  # the close button only shows on hover
    time.sleep(0.6)
    desktop.quick_click(x + 30, y + 29)
    time.sleep(1.0)
    click_text("Save and close" if keep else "Delete and close", timeout=4)
    return True


if __name__ == "__main__":
    print("running:", bool(pid()))
    if pid():
        for title, rect in windows():
            print("window", repr(title), [round(v) for v in rect] if rect else None)
        for title, text, rect in texts()[:60]:
            print(f"  {title!r:24} {text!r:40} {[round(v) for v in rect]}")
