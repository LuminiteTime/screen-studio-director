# Driving the product on camera

## Contents

- [Why real input](#why-real-input)
- [desktop.py](#desktoppy)
- [The Chrome rig](#the-chrome-rig)
- [Finding elements](#finding-elements)
- [Writing a scenario](#writing-a-scenario)
- [Native macOS apps](#native-macos-apps)
- [Looking at the screen](#looking-at-the-screen)

## Why real input

Screen Studio records the screen and separately logs the system cursor (`mousemoves-0.json`,
`mouseclicks-0.json`). Its smooth cursor, click zooms and click effects all come from that log. Input
injected into a page (Playwright `page.mouse`, CDP `Input.dispatch*`, Selenium) changes the page but
never moves the system cursor, so the video shows a frozen pointer and no zooms. Quartz events posted
at `kCGHIDEventTap` move the real cursor and Screen Studio treats them as a person.

Permissions: the app that runs Python (Terminal, iTerm, VS Code, Claude Code's host) needs
Accessibility (to post events and read Screen Studio's AX tree) and Screen Recording (screenshots).
`python scripts/desktop.py` checks both.

## desktop.py

| Call | Notes |
|---|---|
| `move(x, y, dur=0.8)` | ease-in-out path with a slight arc at 120 Hz. 0.5-1.2 s per move looks human |
| `click(x, y, dur)` | move, land exactly, 0.12 s aim pause, press 0.07 s |
| `quick_click(x, y)` | jump and click. Setup only, never inside a take |
| `warp(x, y)` | jump without a path, for parking the cursor before a take |
| `drag(x0, y0, x1, y1)` | press, linear drag, release |
| `scroll(dy, dur)` | pixel wheel events eased like a trackpad flick, under the cursor. Positive reveals content below |
| `key(code, *mods)` | virtual key codes: 36 Return, 48 Tab, 53 Escape, 51 Delete, 123-126 arrows; `key(0, "command")` is ⌘A |
| `paste(text)` | clipboard + ⌘V, layout-independent |
| `screenshot(path, region)` | saved at 1 px = 1 pt |

Scroll goes to whatever is under the cursor. Park the cursor over the scrollable list first; over a
map it zooms the map instead.

## The Chrome rig

```python
from playwright.sync_api import sync_playwright
from browser import Browser, Marks

with sync_playwright() as pw:
    b = Browser(pw, "https://example.com", x=4, y=60, w=1440, h=838)
```

What `Browser` does and why:

- System Chrome (`channel="chrome"`) in `--app=URL` mode: no tabs, no address bar, no bookmarks. The
  URL must be ASCII; percent-encode query strings (`urllib.parse.quote`) or Chrome opens a normal
  tabbed window instead.
- `ignore_default_args=["--enable-automation", "--no-sandbox"]`: both make Chrome show an infobar
  across the top of the page.
- `no_viewport=True`: the page lays out at the real window size, so page coordinates map 1:1 to
  screen points.
- A fresh temporary profile each run: no logged-in state, no extensions, no history suggestions.
  If the demo needs a logged-in user, prepare it inside the scenario setup (API call, cookie via
  `ctx.add_cookies`) rather than reusing the user's real profile.

Page to screen: `origin = (screenX + (outerWidth - innerWidth) / 2, screenY + outerHeight - innerHeight)`.
`Browser.screen(x, y)` adds it. Self-check with `python scripts/browser.py`: it moves the real cursor
and asserts the page saw `pointermove` at the expected spot.

Window placement: leave room for the Dock (often bottom or right; autohide can get stuck showing, and
`killall Dock` resets it), keep the bottom ~100 pt free for the Screen Studio picker, and stay below
the menu bar and notch. 1440x838 at (4, 60) fits a 1512x982 MacBook screen.

Typing: `b.type(text)` uses Playwright keyboard input with a per-key delay. It shows on screen like
real typing and does not need the cursor. Click the field with a real click first so the caret is
where the viewer expects.

## Finding elements

Always find at run time, right before the action. Layout shifts after every load, toast and banner.

- DOM apps: `b.box("text=Compare")`, `b.box("role=button[name='Search']")`, `b.box("#id")`. Returns
  the centre in page coordinates.
- Flutter web draws on a canvas. Call `b.flutter_enable()` once (clicks the hidden
  `flt-semantics-placeholder`), then `b.flutter("Label")` finds `flt-semantics` nodes by aria-label
  prefix, `contains=True` for substring, `nth` for the nth from the top. Flutter nests several nodes
  with the same label; the finder deduplicates by position.
- Text that changes between runs (counts, prices, minutes): match the stable part.
- Off-screen targets: `b.scroll_to(lambda: b.box("text=Reviews"), y_target=420)` scrolls, measures
  and corrects, because wheel distance per pixel differs between pages.
- Count selections by unique position, not by node count: duplicate semantic nodes double the count.

## Writing a scenario

Keep `scenario(b, mark)` pure: only product actions and marks, no Screen Studio calls. The dry run and
the take then do the same thing.

```python
def scenario(b, mark):
    mark("cap", "Describe the hotel you want")       # caption starts here
    b.click(*b.box("input[name=q]"))
    b.type("quiet room with a sea view")
    b.wait(0.8)
    b.click(*b.box("text=Search"))
    b.wait(2.5)                                      # let the result land and be read
    mark("cap", "Every match comes with proof")
    b.move(*b.box("text=Verified"), dur=1.0)         # hover to point at it, no click
    b.wait(2.0)
    mark("end")                                      # caption off
```

Marks are unix timestamps. After the take, `t0 = ss.recording_start(project)` and caption times in the
video are `mark - t0`. `assemble.py` does this when a clip has `marks` and `project` (or `t0`).

Timing that reads well:

- 0.8-1.0 s still before the first move, 1.0-1.5 s after the last result.
- After a click that changes the page: 1.5-3 s, longer when there is text to read.
- One caption per idea, each on screen at least 2.5 s.
- Hovering a thing for 1-2 s points at it; Screen Studio may zoom on clicks but not on hovers.

Things that ruin a take: tooltips covering the next target (move away before the next click), banners
or toasts sliding over a button (scroll first or wait for them), clicks on links you only meant to
point at, network spinners (warm the cache in the dry run, keep the same Chrome open for the take).

## Native macOS apps

The same rules, other locators:

- Activate and place the window: `osascript -e 'tell application "Notes" to activate'` and
  System Events `set position/size of window 1 of process "Notes"`.
- Find controls through accessibility the same way `screen_studio.texts()` does: walk `AXWindows`,
  read `AXRole`, `AXTitle`, `AXValue`, `AXDescription`, `AXPosition`, `AXSize`. Native Cocoa apps
  expose this without `AXManualAccessibility`; Electron apps (Slack, VS Code, Figma, Notion) need it.
- Click with `desktop.click` at the element's centre; type with `desktop.paste` or key codes.
- Menus through System Events, like `ss.menu`.

## Looking at the screen

You cannot see the screen unless you capture it. Screenshot at every state the scenario depends on
during the dry run (`desktop.screenshot`), and pull stills from the export at each mark:

```bash
ffmpeg -ss 12.5 -i web.mp4 -frames:v 1 still_12.5.png
```

Look at them before cutting: is the cursor on the target, did the zoom frame the right thing, is
anything private, half-loaded or overlapping?
