# Post-production

Screen Studio gives each take its look. `scripts/assemble.py` turns several takes into one video:
order, cuts, title cards, captions, device frames, crossfades, music, final encode.

## Contents

- [Timeline format](#timeline-format)
- [Layouts](#layouts)
- [Captions](#captions)
- [Design](#design)
- [Motion](#motion)
- [Music and sound](#music-and-sound)
- [Encoding and delivery](#encoding-and-delivery)
- [Beyond assemble.py](#beyond-assemblepy)

## Timeline format

```json
{
  "out": "out/demo.mp4",
  "size": [1920, 1080], "fps": 60, "crossfade": 0.6,
  "accent": "#ACEF81", "on_accent": "#111111", "tint": "#06123C",
  "font": "/System/Library/Fonts/SFNS.ttf", "font_bold": null,
  "music": {"mood": "bright", "bpm": 84, "seed": 7, "density": 0.55, "volume": 0.55},
  "parts": [
    {"type": "card", "bg": {"src": "web.mp4", "t": 2}, "dur": 3.2,
     "logo": "logo.png", "title": "...", "subtitle": "...", "button": "example.com"},
    {"type": "clip", "src": "web.mp4", "start": 0.8, "end": 40, "layout": "fill",
     "marks": "web_marks.json", "project": "/path/to/Area ....screenstudio"},
    {"type": "clip", "src": "phone.mp4", "start": 1, "end": 20, "layout": "device",
     "screen": [60, 72, 503, 1008], "captions": [[1, "On the phone too"], [19, null]]}
  ]
}
```

Paths are relative to the timeline file. `music` may be `{"file": "track.mp3", "volume": 0.3}` or
`null` for silence. A clip uses source seconds (`start`, `end`, caption times). Marks come from
`browser.Marks`; `project` gives the recording start, or pass `"t0"` directly. Inline `captions`
and marks can be combined.

Workflow: `python assemble.py tl.json --still 5` for a PNG at output second 5 (no crossfade blending),
check 3-5 stills across the video, then render the whole thing. Rendering is roughly real time at
1080p60 on Apple silicon.

Cutting one take into several parts is normal: split a web take where the phone segment goes in,
skip a slow wait, reorder.

## Layouts

| Layout | Use | Captions |
|---|---|---|
| `fill` | desktop footage in a canvas of the same aspect; cover-crops the rest | pill at the bottom |
| `fit` | any footage into any canvas, nothing cropped, blurred backdrop around | pill at the bottom |
| `device` | phone footage in a landscape or vertical canvas | large text beside (16:9) or above (9:16) |

`fill` crops. A 16:9 take in a 9:16 canvas with `fill` keeps only a narrow middle strip; use `fit` or
record a separate vertical take.

## Captions

- Bottom pill: medium weight, dark translucent pill, white text, 60 px from the bottom at 1080p. Good
  over busy UI.
- Side text (device layout): bold, 60 px, left aligned, beside the phone. Reads like a slide.
- Captions start at their mark, glide in over 0.6 s with ease-out-quint, and fade over 0.35 s before
  the next one. A `null` caption (`mark("end")`) clears the screen.
- Keep captions off the part of the UI the beat is about. If a caption covers the action, move the
  action in the scenario (scroll first) or use `fit` for that part.

## Design

Choose a direction per project. Base it on the product, not on a template:

- **Accent** from the product's brand colour (buttons on cards). `on_accent` must contrast with it.
- **Tint** for backdrops: a very dark version of the brand hue, so blurred backgrounds stay on-brand
  and white text reads at any frame.
- **Typeface**: the product's own font if you have the file (`font`, `font_bold`); otherwise San
  Francisco (`SFNS.ttf`, variable, Latin and Cyrillic) or New York (`NewYork.ttf`) for an editorial
  feel. One family, two weights.
- **Screen Studio look**: set it in project.json per take, the same for all takes
  (`useLastProjectConfigForNewProjects` helps). Wallpaper for a friendly look, a brand gradient for
  launch videos, a solid tint colour for a minimal look; padding 6-12; radius 12-16; shadow on.

Variants that work:

| Direction | Screen Studio background | Cards | Music |
|---|---|---|---|
| Friendly SaaS | macOS wallpaper | blurred footage, accent button | `bright`, 84 BPM |
| Premium / minimal | solid near-black or off-white | lots of space, one line of text | `night` or `calm`, 72 BPM |
| Bold launch | brand gradient | big title, logo | `warm`, 92 BPM |
| Developer tool | dark solid, small padding | monospace subtitle | `calm`, low density |

Want something assemble.py cannot draw (a logo animation, a custom overlay, an illustrated card)?
Render it as a short MP4 or PNG sequence with any tool and add it as a `clip` with `layout: "fill"`.

## Motion

- Entering things: ease-out (quint or expo). Fades and crossfades: smootherstep. No bounce, no elastic.
- Crossfade 0.5-0.7 s between parts. Hard cuts only on beat changes inside one surface.
- Card elements enter in sequence 0.4 s apart with a 24 px rise.
- Let Screen Studio do camera motion (zooms, pans). Do not add your own zoom on top of its zoom.

## Music and sound

- `scripts/music.py` synthesizes a calm bed: detuned pads on a four-chord loop, a sparse pluck
  arpeggio, delay-line reverb, fade in and out. Change `--mood`, `--bpm`, `--seed` (different
  arpeggio pattern), `--density`.
- Mix low: `volume` 0.55 on the generated bed gives about -24 dB mean, under UI sounds and easy to
  talk over. Measure: `ffmpeg -i out.mp4 -af volumedetect -f null -`.
- A supplied track must be licensed for the use. It is faded out at the end of the cut.
- Narration: record or generate it separately, place it with ffmpeg (`adelay`, `amix`) and duck the
  music under it (`sidechaincompress`), or keep music only and let captions speak.

## Encoding and delivery

assemble.py writes H.264 (`crf 18`, `yuv420p`, `+faststart`) with AAC 160k, which plays everywhere.

| Need | Command |
|---|---|
| Smaller file | `ffmpeg -i demo.mp4 -c:v libx264 -crf 23 -preset slow -c:a copy small.mp4` |
| Fit a size limit | bitrate = size_MB * 8192 / seconds - 160, then two-pass `-b:v <k>k` |
| 30 fps for the web | `-r 30` |
| GIF preview | `ffmpeg -i demo.mp4 -vf "fps=15,scale=800:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse" demo.gif` |
| Poster frame | `ffmpeg -ss 5 -i demo.mp4 -frames:v 1 poster.png` |
| Vertical from the same takes | copy the timeline, set `size` to `[1080, 1920]`, switch desktop parts to `fit` |

Before sending: duration, size, audio level, first and last frame, a still at every caption.

## Beyond assemble.py

For narration timing, many tracks or keyframed overlays, generate an edit for a real editor instead:
an FCPXML for Final Cut Pro or DaVinci Resolve, or a Remotion / Motion Canvas project when the video
is mostly motion graphics. Keep Screen Studio exports as the source clips either way.
