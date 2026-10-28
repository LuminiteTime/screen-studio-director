# Troubleshooting

Every row happened at least once. Symptom first, then cause and fix.

## Input and capture

| Symptom | Cause | Fix |
|---|---|---|
| Cursor frozen in the video, no zooms | Clicks sent through Playwright/CDP | Real Quartz input (`desktop.py`) |
| Clicks in the video land above or beside their targets | Video captured with CDP `Page.startScreencast`, which returns cropped, downscaled frames on retina Macs | Record with Screen Studio; never use screencast frames as footage |
| Click lands a few points off | Origin computed with viewport emulation on, or window moved after measuring | `no_viewport=True`; `freeze_origin()` before emulating; re-measure after moving the window |
| Scroll does nothing or zooms a map | Cursor was over another scrollable element | Park the cursor over the list before scrolling |
| Vertical feed will not page with a drag | Feed listens to wheel/touch, not mouse drags | Wheel bursts: `desktop.scroll(600, 0.6)` |
| One wheel event moved nothing | Single large delta ignored | Many small eased events (`desktop.scroll` does this) |
| Typed text is gibberish (`фффф`) | `keystroke` follows the active layout | `desktop.paste` for native fields, Playwright `type` for pages |
| Target not found on the second run | Label text changed (counts, minutes) | Match by prefix or substring |
| Second item never selected | A tooltip or banner covered it, or the count included duplicate nodes | Move the cursor away, scroll the list first, count by unique position |
| Hover pill navigated to another page | It was a link and the scenario clicked it | Hover only, or click only what the beat is about |
| `screencapture` fails | Output folder missing, or no Screen Recording permission | `mkdir -p`; grant permission and restart the terminal |

## Screen Studio

| Symptom | Cause | Fix |
|---|---|---|
| `label not found` for picker labels | Picker hidden, or the app is in the background | `ss._picker()` uses Record > New recording…; `_app()` activates |
| Recording never starts | Return pressed instead of clicking Start; or an extra Escape left Area toggled off | `click_text("Start recording")`; `reset_picker()` before arming |
| Recorded area is the old one, shifted | A drag inside the remembered area moves it | `start_area` sets Size/Position fields |
| Area shorter than asked | Rectangle went past the screen edge, clamped silently | Move the window up; check `cropRect` in metadata.json |
| Recording stopped by itself mid-take | A click landed on the recording widget | `set_prefs(showRecordingWidget=False)` for takes |
| Clicks after a take hit nothing / open the wrong thing | Quick export widget floating bottom-left | `close_widget(keep=...)` before the next take |
| Clicked "Screen Studio's timer" in the notch, nothing happened | It was another notch utility | Stop through the Record menu |
| Record > Record window did nothing | That item does not arm the picker mode | Click the `Window` label |
| Preference change lost | App wrote its copy back on quit | `set_prefs` quits first |
| project.json edit lost | Editor had the project open | `save_project` quits first; reopen after |
| Speed change went the wrong way | `timeScale` is a duration multiplier | `0.5` = 2x faster, `2` = half speed |
| Export is a different size than expected | Height = chosen resolution, width = recording aspect + padding | Read the size with ffprobe and design the layout around it |
| Finder pops up after export | Save panel / export reveal | Close Finder windows before the next take |

## Screen and system

| Symptom | Cause | Fix |
|---|---|---|
| Dock visible in the recording | Window extends under an auto-hide Dock that got stuck | Keep the window clear of the Dock; `killall Dock` (it may bring another app forward, re-activate yours) |
| Notification banner in the take | Do Not Disturb off | Turn on Focus / DND before recording |
| `--no-sandbox` or "controlled by automated software" bar | Playwright default args | `ignore_default_args=["--enable-automation", "--no-sandbox"]` |
| Normal tabbed window instead of `--app` | Non-ASCII URL | Percent-encode the URL |
| Mac slows down, frames drop | Heavy builds or models running during the take | Stop them; one take at a time |

## Edit

| Symptom | Cause | Fix |
|---|---|---|
| Phone segment has a visible seam or wallpaper edge | Export padding left in the crop | Measure `screen` from a still of that export |
| Side captions hard to read | Backdrop too bright | Darker `tint`, or raise the backdrop mix in `Style.backdrop` |
| Caption over the thing it talks about | Beat composition | Scroll first, or use `fit` for that part |
| Captions early or late | Wrong `t0` or the clip was re-exported from an edited project with cuts | Use the project's `recording_start`; after speed edits, place captions inline instead of from marks |
| Video longer than the music | Supplied track too short | Use `music.py` (any length) or loop the track with ffmpeg `-stream_loop` |
| Telegram bot refuses the upload | Over 50 MB | Re-encode with `crf 23-26` or a target bitrate |
