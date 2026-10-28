---
name: screen-studio-director
description: Directs, records and edits polished product demo videos on macOS with Screen Studio, driven entirely by scripts. Moves the real system cursor through Quartz so Screen Studio's auto-zoom and smooth cursor work, rehearses scenarios in Chrome via Playwright, films phone-sized takes, starts and stops recordings, edits project.json (zooms, speed, background), exports, then cuts a finished video with title cards, captions, device frames, crossfades and generated background music. Use whenever the user asks to record a demo, screencast, product video, walkthrough, promo, launch video, tutorial, reel or short of an app or website, mentions Screen Studio, wants a "screen recording with zooms", or wants such recordings edited into one video, even if they do not name Screen Studio.
---

# Screen Studio Director

You are the director, the camera operator and the editor. Screen Studio is the camera: it records the
screen and makes it look good (cursor smoothing, auto-zoom on clicks, padding, wallpaper, shadows). You
drive it and the product with scripts, so every take is repeatable and you can reshoot in a minute.

The user usually only sees the final video. Everything they asked for in the brief (length, language,
what to show, tone, music, aspect ratio, where it will be posted) is the acceptance test. Keep a
checklist of it and check the result against it before you deliver.

## Ground truth

- Screen Studio follows the **system cursor**. Playwright, CDP and Selenium clicks do not move it, so
  Screen Studio sees a frozen pointer, makes no zooms and records clicks in the wrong place. Every
  pointer action in a take goes through `scripts/desktop.py` (Quartz CGEvents). Keyboard text can still
  go through Playwright.
- Screen Studio is an Electron app. Its own UI (picker, Start button, export widget) becomes clickable by
  text after `AXManualAccessibility` is set; `scripts/screen_studio.py` does this. Native menus (Record,
  Export, File, View) are driven through System Events. Never click its UI by hard-coded coordinates.
- All coordinates are **screen points**, top-left origin, not retina pixels. `desktop.screenshot()`
  saves images at 1 px = 1 pt so you can read coordinates straight off them.

## Workflow

1. **Preflight.** Run `python3 scripts/doctor.py` from the skill folder. If anything is missing, run
   `bash scripts/setup.sh` once: it installs ffmpeg through Homebrew and the Python packages into
   `.venv` in the skill folder, then re-checks. Two things stay manual and need the user: Accessibility
   and Screen Recording permission for the terminal app (System Settings > Privacy & Security, then
   restart the terminal), and an installed, licensed Screen Studio. Then check the screen size, where
   the Dock is, and turn on Do Not Disturb.
2. **Brief to storyboard.** Write the story as beats: one idea per beat, one caption per beat, the
   action that proves it. Decide length, aspect ratio (16:9, 9:16, 1:1, several), language, captions,
   music. Read [references/storytelling.md](references/storytelling.md).
3. **Rig.** Open the product in a window you control (`scripts/browser.py` for web, see
   [references/automation.md](references/automation.md) for native apps and finding elements).
   For phones read [references/devices.md](references/devices.md).
4. **Rehearse.** Run the scenario with recording off (`--dry`). Take a screenshot at each key state and
   look at it. Fix every miss before the first take: a take that fails halfway costs a full reshoot.
5. **Prepare Screen Studio.** Turn off the recording widget, close any leftover export widget, pick
   quick-export settings. See [references/screen-studio.md](references/screen-studio.md).
6. **Take.** `ss.start_area(...)` or `ss.start_window(...)`, run the scenario while writing marks
   (`browser.Marks`), `ss.stop_recording()`. One take per surface (web, phone, ...), not one giant take.
7. **Review.** Export (`ss.quick_export` or `ss.export_project`), pull stills with ffmpeg at the marks
   and look at them: cursor on target, zoom on the right thing, nothing private on screen, no widgets,
   no Dock, no notifications.
8. **Polish in the project** if needed: zooms, speed-ups, background, cursor size, by editing
   `project.json` with Screen Studio closed, then re-export.
9. **Cut.** Describe the edit in a timeline JSON and render it with `scripts/assemble.py`. Check
   `--still` frames first, then render. See [references/post-production.md](references/post-production.md).
10. **Deliver.** Check size and duration limits of the destination, restore every Screen Studio
    preference you changed, and send intermediate results early when the user is waiting.

## Hard rules

These come from real failures. Each one cost a reshoot.

1. Real input only during a take. `desktop.click/move/scroll/drag`, or `Browser.click/move/scroll`.
2. Rehearse first. Never let the first run of a scenario be the recorded one.
3. Find targets at run time by text, label or locator, never by remembered coordinates. Labels
   change between runs ("3 min" became "4 min"): match by prefix or substring.
4. Map page coordinates to the screen with the window's real origin (`Browser.origin()`). Do not use
   viewport emulation for desktop takes, and do not use CDP screencast as the recording: on retina
   Macs it returns cropped, downscaled frames and every click lands visibly off its target.
5. Keep the recorded rectangle clear of the Dock, the menu bar, notch widgets, the Screen Studio
   picker and both Screen Studio widgets. Anything that floats over it gets recorded, and anything
   under the cursor eats the click. The recording widget stopped a take when a click landed on it.
6. Set the Area by numbers (`start_area` does it). Screen Studio remembers the last area, and a drag
   inside it moves the old rectangle instead of drawing a new one.
7. Type into native dialogs through the clipboard (`desktop.paste`). `keystroke` follows the active
   keyboard layout and turns `demo` into `вуьщ` on a Russian layout.
8. Hover is safe, a click is a commitment. A click on a pill or link may navigate away mid-take.
9. Give every action time: aim pause before a click, a beat after the result appears, 1-2 s of still
   frames at the start and end of each take for clean cuts.
10. Quit Screen Studio before editing its preferences or a project.json. It rewrites both from memory.
11. `timeScale` in project slices is a duration multiplier: `2` plays at half speed, `0.5` at double.
12. Never put secrets, personal data or other people's content on screen. Check the stills.
13. Restore what you changed: preferences, Dock, window positions, the user's projects folder.

## Scripts

| Script | What it does |
|---|---|
| `scripts/desktop.py` | Quartz mouse and scroll with human easing, key codes, clipboard paste, screenshots in points, permission check |
| `scripts/screen_studio.py` | Launch/quit, prefs, menus, AX text clicks, start window/area/display takes, stop, latest project, project.json load/save, quick export, export from project, close widget |
| `scripts/browser.py` | Chrome `--app` window via Playwright, page-to-screen mapping, locators and Flutter semantics, phone viewport, filmed actions, `Marks` |
| `scripts/assemble.py` | Timeline JSON to finished MP4: cards, fill/fit/device layouts, captions from marks, crossfades, music; `--still T` previews |
| `scripts/music.py` | Synthesized ambient bed of any length, moods `bright`, `calm`, `warm`, `night` |
| `scripts/doctor.py` | Checks macOS, Python, packages, ffmpeg, Chrome, Screen Studio, permissions; prints the fix for each miss |
| `scripts/setup.sh` | One-time install of ffmpeg and the Python packages (venv), then runs doctor |

Run every script with the skill's interpreter, `<skill>/.venv/bin/python`, and keep the scripts folder
on `sys.path` (see `examples/take_web.py`). Start a new take
script by copying `examples/take_web.py`; start a new edit from `examples/timeline.json`.

## References

| Read | When |
|---|---|
| [references/screen-studio.md](references/screen-studio.md) | Controlling the app: picker, modes, menus, prefs, widgets, export, project.json schema |
| [references/automation.md](references/automation.md) | Driving the product: real input, Chrome rig, coordinate mapping, finding elements, native apps |
| [references/devices.md](references/devices.md) | Phone and tablet footage: viewport phones, iOS Simulator, Android emulator, real devices |
| [references/storytelling.md](references/storytelling.md) | Turning a brief into beats, pacing, caption copy, length per platform |
| [references/post-production.md](references/post-production.md) | Timeline format, layouts, design variants, typography, motion, music, encoding, delivery |
| [references/troubleshooting.md](references/troubleshooting.md) | Symptom to cause to fix, for everything that has gone wrong before |
