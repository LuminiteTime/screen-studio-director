# Controlling Screen Studio

Verified on Screen Studio 3.5 (bundle id `com.timpler.screenstudio`), macOS 26, English UI. Labels
below are the English ones; if the user runs another UI language, dump the labels first
(`python scripts/screen_studio.py`) and use what it prints.

## Contents

- [Seeing the UI](#seeing-the-ui)
- [The recording picker](#the-recording-picker)
- [Starting and stopping](#starting-and-stopping)
- [Preferences](#preferences)
- [Widgets that get in the way](#widgets-that-get-in-the-way)
- [Exporting](#exporting)
- [Project files](#project-files)
- [Editing project.json](#editing-projectjson)

## Seeing the UI

Screen Studio's windows are Chromium web content. macOS hides their contents from accessibility until
the app is told a screen reader is present:

```python
app = AXUIElementCreateApplication(pid)
AXUIElementSetAttributeValue(app, "AXManualAccessibility", True)
```

After that every label is an `AXStaticText` with a value and a screen rect, and native alert buttons
are `AXButton`s with a title. `screen_studio.texts()` walks all windows and returns
`(window title, text, rect)`; `find_text` / `click_text` use it. Two quirks:

- Windows of a background Screen Studio are not listed. `_app()` activates the app when the list is
  empty.
- Icons are private-use glyphs (`'\U001003dc'`). Click the text label under or next to an icon.

Native menus are normal Cocoa menus. List them with
`ss.menu_items("Record")` and click with `ss.menu("Record", "Stop recording")`.

| Menu | Items that matter |
|---|---|
| Record | Record display, Record window, Record area, After recording: Create project / Export and copy to clipboard / Export and create shareable link / Export and save to file, Automatically create zooms, New recording…, Stop recording (only while recording) |
| Export (editor) | Export…, Quick export to clipboard, Quick export to file…, Quick export to shareable link, Extract raw recording files…, Export current frame as image… |
| File | Open project…, Save, Save as…, Show project in Finder, Remove project, Create project from video…, Import preset… |
| View | Background, Screen, Cursor, Camera, Captions, Audio, Animations, Show recording widget |

`ss.is_recording()` checks whether "Stop recording" is in the Record menu.

## The recording picker

A bar near the bottom of the screen, window title `Start Recording`. Labels: `Display`, `Window`,
`Area`, `Device`, `No camera`, `No microphone`, `No system audio`, sometimes
`Recover N unfinished recordings`.

- Show it with Record > `New recording…`. `open -a "Screen Studio"` does not bring it back after a take
  or an export. The Record > `Record window` / `Record area` items did not arm the mode in testing; click
  the picker labels instead.
- Escape twice resets it: the first drops the current selection, the second disarms the mode.
  `ss.reset_picker()`.
- Return does not start a recording. Click the `Start recording` label.

### Modes

**Window.** Click `Window`, then click inside the target window. A purple `Start recording` button
appears over the window's centre. The window must be frontmost and unobstructed. Output keeps the
window's aspect ratio plus Screen Studio padding (a 1440x838 window exported at 1688x1080).

**Area.** Click `Area`. If an area was used before, Screen Studio shows it again with a panel:
`Size` (two fields), `Position` (two fields), `Any` (aspect preset), `Saved` (saved areas),
`Start recording`. The fields are `AXIncrementor`s; click one, select all, paste a number, press Tab.
Set size before position or the position gets clamped. A drag that starts inside the old rectangle
moves it; it does not draw a new one. Rectangles past the screen edge are clamped without a warning
(asked 844 tall, got 835). `ss.start_area(x, y, w, h)` handles all of it and raises if the fields do
not read back the values you asked for. The recorded rect is in
`recording/metadata.json` > recorders > `configuration.cropRect`.

Use Area for a page without browser chrome (pass `Browser.content_rect()`), for phone viewports, and
for any exact framing. Use Window when the window frame itself belongs in the shot.

**Display.** Whole screen. Rarely what you want: menu bar, Dock and notifications come with it.

**Device.** Records an iPhone or iPad connected by cable. See [devices.md](devices.md).

A countdown may run after Start (pref `recordingCountdownDuration`). `start_*` sleep `countdown`
seconds (default 4) before returning; raise it if you set a longer countdown.

## Starting and stopping

```python
import screen_studio as ss
ss.close_widget(keep=False)          # leftover export widget from a previous take
ss.start_area(x, y, w, h)            # returns after the countdown
...scenario...
ss.stop_recording()                  # Record > Stop recording
time.sleep(4)                        # project gets written
project = ss.latest_project(since=start_time - 10)
t0 = ss.recording_start(project)     # unix seconds of the first frame, for captions
```

Do not stop by clicking the notch or menu bar: a notch utility can sit exactly where you expect
Screen Studio's timer.

## Preferences

`~/Library/Application Support/Screen Studio/user-preferences/settings-persistance.json`, key `json`.
The running app keeps them in memory and writes them back on quit, so `ss.set_prefs(**values)` quits
the app first and returns the old values for restoring.

| Key | Use |
|---|---|
| `showRecordingWidget` | `false` for takes. The floating widget sits low on the screen and a click on it stops the recording. |
| `showQuickExportWidget` | `true` if you export from the widget, `false` if you export from the project |
| `actionAfterRecording` | `create-project` (default) keeps an editable project |
| `createAutomaticZooms` | `true` gives click-following zooms for free |
| `recordingCountdownDuration` | seconds |
| `projectsFolderPath` | where `.screenstudio` projects go |
| `useLastProjectConfigForNewProjects` | `true` makes every new take inherit the last project's look (background, cursor, padding): set the look once in the editor, then all takes match |
| `defaultPresetId`, `defaultZoomLevel` | preset and zoom used for new projects |
| `hideDesktopContentWhileRecording` | hides desktop icons and files |
| `enableExternalDeviceRecording` | needed for Device mode |
| `actionAfterQuickExport` | `do-nothing` by default |

```python
old = ss.set_prefs(showRecordingWidget=False)
try:
    ...takes...
finally:
    ss.set_prefs(**old)
```

## Widgets that get in the way

- **Recording widget** (`recording-manager-widget`, low centre of the screen): controls for the
  running recording. Turn it off for takes.
- **Quick export widget** (window titled `Screen Studio`, bottom-left, about 270-360 pt wide): appears
  after every take with `Save...`, `Copy`, `Share`, `Edit` and a gear for export settings. It stays on
  top and swallows clicks on whatever is under it. `ss.widget_rect()` finds it, `ss.close_widget(keep)`
  hovers it, clicks its close button and answers the alert with `Save and close` or `Delete and close`.

## Exporting

**From the widget** right after a take: `ss.quick_export(folder, name)` clicks `Save...`, fills the
native Save panel (⌘⇧G, paste folder, Return; ⌘A, paste name, Return) and waits until the file stops
growing. Finder may open showing the file; close it before the next take.

**From a project**: `ss.export_project(project, folder, name)` opens it in the editor and runs
Export > `Quick export to file…`.

Quick export uses the settings under the widget's gear: format MP4 or GIF, 60 fps, resolution 720p /
1080p / 4K, compression Studio / Social Media / Web / Web (Low). Use 1080p + Studio as the master for
editing; let the final encode decide the delivery size. The height is the resolution (1080), the width
follows the recording's aspect plus padding (a 390x844 area exported at 572x1080).

Export > `Export…` opens the full dialog with output aspect ratio and presets; drive it with
`click_text` after dumping its labels.

## Project files

`~/Screen Studio Projects/<Mode> <date> <time>.screenstudio/` is a folder:

```
project.json              look (config) + edit (scenes)
meta.json
recording/
  metadata.json           recorders and sessions: unixStartMs, durationMs, cropRect, displayId
  channel-1-display-0.mp4 raw screen capture, no effects
  mousemoves-0.json  mouseclicks-0.json  keystrokes-0.json
  cursors/  cursors.json
  polyrecorder.log
```

The raw capture is useful for your own effects; the export is what has Screen Studio's look.

## Editing project.json

Quit Screen Studio (or at least close the project), then:

```python
data = ss.load_project(project)
cfg, scene = data["json"]["config"], data["json"]["scenes"][0]
...change...
ss.save_project(project, data)
subprocess.run(["open", str(project)])   # the editor shows the changes
```

### config (the look)

| Key | Values |
|---|---|
| `backgroundType` | `system` (macOS wallpaper by `backgroundSystemName`, e.g. `macOS/tahoe-light.jpg`), `color` (`backgroundColor` `#RRGGBB`), `gradient` (`backgroundGradient` `{start:{x,y}, end:{x,y}, stops:[{color, at}]}`), `image` (`backgroundImage`) |
| `backgroundPaddingRatio` | padding around the screen, default 10 |
| `backgroundBlur` | 0..1 |
| `windowBorderRadius` | default 12 |
| `shadowIntensity`, `shadowAngle`, `shadowDistance`, `shadowBlur` | drop shadow |
| `insetPadding` `{top,right,bottom,left}`, `insetColor`, `insetAlpha` | inner border |
| `cursorSize` | default 1.5; 2-2.5 reads better in vertical video |
| `cursorSet` | `{id: "macos-tahoe", variants: {}}` |
| `hideCursor` | true for touch-style footage |
| `hideNotMovingCursorAfterMs` | hide an idle cursor |
| `clickEffect`, `clickSoundEffect`, `clickSoundEffectVolume` | click feedback |
| `motionBlurAmount` and `motionBlur{Cursor,ScreenMove,ScreenZoom}Amount` | 0..1 |
| `mouseMovementSpring` `{stiffness 470, damping 70, mass 3}` | cursor smoothing; more mass = lazier |
| `screenMovementSpring` `{mass 2.25, stiffness 200, damping 40}` | zoom/pan camera |
| `alwaysKeepZoomedIn` | stay zoomed between zoom ranges |
| `defaultOutputAspectRatio` | null = recording aspect |
| `deviceFrameKey`, `enableDeviceMockup` | device frames for Device recordings |
| `backgroundAudioFileName`, `backgroundAudioVolume` (0.05) | music inside Screen Studio |
| `showShortcuts`, `showTranscript` | keystroke and caption overlays |
| `recordingRange` `[startMs, endMs]`, `recordingCrop` `{x,y,width,height}` 0..1 | trim and crop |

### scenes[0].zoomRanges

```json
{"id": "Zm1", "zoom": 2, "type": "follow-click-groups", "manualTargetPoint": {"x": 0.5, "y": 0.5},
 "snapToEdgesRatio": 0.25, "glideDirection": null, "glideSpeed": 0.5, "isDisabled": false,
 "startTime": 13420, "endTime": 18647, "isSystem": false, "hasInstantAnimation": false}
```

Times are source milliseconds. `type: "manual"` with `manualTargetPoint` (0..1 of the frame) zooms
on a fixed spot, which is good for reading text. Automatic zooms are `follow-click-groups`; disable
one with `isDisabled: true` rather than deleting it. Give every id a new random string.

### scenes[0].slices

```json
{"id": "Sl1", "timeScale": 1, "sourceStartMs": 0, "sourceEndMs": 29769.3, "volume": 1,
 "systemAudioVolume": 1, "hideCursor": false, "disableSmoothMouseMovement": false,
 "externalDeviceAudioVolume": 1}
```

Split a slice to speed up a wait: three slices `[0, a]` at 1, `[a, b]` at `0.25` (4x faster),
`[b, end]` at 1. `timeScale` multiplies duration, so values below 1 are faster.
