# Phone and tablet footage

Four ways to get mobile footage, from most to least controllable. Only the first was verified end to
end while writing this skill; the others are marked.

## Contents

- [Phone viewport in Chrome (verified)](#phone-viewport-in-chrome-verified)
- [iOS Simulator](#ios-simulator)
- [Android emulator](#android-emulator)
- [Real device over cable](#real-device-over-cable)
- [Framing phone footage](#framing-phone-footage)

## Phone viewport in Chrome (verified)

For mobile web, PWAs and Flutter/React Native web builds.

Chrome windows cannot be narrower than about 500 pt, so a 390 pt window is impossible. Instead keep a
normal window and override the page metrics:

```python
b = Browser(pw, url, x=4, y=40, w=520, h=900)
rect = b.emulate_phone(390, 844, dpr=2)     # freezes the origin, then emulates
ss.start_area(*rect)                        # records exactly the phone viewport
```

- `mobile: False` in the override keeps mouse input working 1:1 at the top-left of the window. With
  `mobile: True` Chrome scales the viewport and real clicks land off target.
- Freeze the origin before emulating: after the override `innerWidth/innerHeight` report the
  emulated size and the origin formula breaks.
- Place the window so `y + 844` stays on screen, or Screen Studio clamps the area height.
- Swipes in a vertical feed (reels, stories): mouse drags do not page most feeds; bursts of wheel
  events do. `desktop.scroll(600, 0.6)` per page, wait for the snap, repeat.
- The page sees a mouse, not touch. Sites that branch on `pointer: coarse` or touch events show their
  desktop behaviour; test the specific flow in the dry run.
- Hide the cursor for a touch look: set `hideCursor: true` in project.json, or keep it (it shows the
  viewer where the "finger" is). For short-form social video keep it and set `cursorSize` 2-2.5.

## iOS Simulator

Unverified here (no Xcode on the test machine). The approach:

- `xcrun simctl boot "iPhone 16"`, `open -a Simulator`, `xcrun simctl openurl booted <url>`,
  `xcrun simctl install booted App.app`, `xcrun simctl launch booted <bundle id>`.
- Clean status bar: `xcrun simctl status_bar booted override --time 9:41 --batteryLevel 100
  --cellularBars 4 --wifiBars 3`.
- Record with Window mode on the Simulator window, or Area on its screen. Window > Physical Size or
  Point Accurate keeps the scale predictable.
- Clicks into the Simulator window are taps, so `desktop.click` works and Screen Studio sees the
  cursor. Find targets with a screenshot of the window, or through the Simulator's accessibility tree
  (it exposes the app's elements as AX children of the window).
- `xcrun simctl io booted recordVideo out.mp4` records the device screen without any cursor; useful
  for a clean device-frame layout where the cursor would look wrong.

## Android emulator

Unverified here. `emulator -avd <name>` opens a window; Window mode records it and clicks are taps.
`adb shell input tap x y` does not move the Mac cursor, so prefer real clicks while Screen Studio
records. Turn on touch dots for footage without a cursor:
`adb shell settings put system show_touches 1`. `adb shell screenrecord /sdcard/out.mp4` records
the device screen without Screen Studio.

## Real device over cable

Screen Studio's `Device` mode records an iPhone or iPad connected by USB-C/Lightning (pref
`enableExternalDeviceRecording`). Unverified here. You cannot drive a real phone with Quartz: the
user performs the actions, or use iPhone Mirroring (macOS 15+) and record its window, where Mac
clicks become taps. Screen Studio can wrap Device recordings in a device frame
(`deviceFrameKey`, `enableDeviceMockup` in project.json).

## Framing phone footage

Screen Studio's export of a phone-sized area is tall and narrow (390x844 exported at 572x1080, with
padding and wallpaper). Three ways to place it in the final video, all in `assemble.py`:

- `layout: "device"` crops the screen rectangle out of the export (`screen: [x0, y0, x1, y1]` in
  export pixels; for a 390x844 area at 1080p it was `[60, 72, 503, 1008]`), draws a plain phone body
  with a soft shadow on a blurred, darkened backdrop of the same footage, and puts big captions in
  the free space (left in 16:9, above in 9:16). Best for a phone segment inside a landscape video.
- `layout: "fit"` keeps Screen Studio's own padding and wallpaper and centres it on a blurred
  backdrop.
- A 9:16 canvas (`size: [1080, 1920]`) with `fill` turns a phone take into a vertical reel.

Find the screen rectangle once per export size: pull a still and read it off, or detect where the
wallpaper ends. Recheck it whenever the area size or padding changes.

Do not put the phone and the desktop side by side in one frame unless the user asks: both become too
small to read. Cut between them instead.
