"""Cut Screen Studio exports into one finished video from a timeline JSON.

    python assemble.py timeline.json                 # renders timeline["out"]
    python assemble.py timeline.json --still 12.5    # one PNG of the output at 12.5 s, for design checks

Parts play in order with smooth crossfades. Each part is a title card or a clip of an export:
  layout "fill"    cover-crop to the canvas, captions as a bottom pill (desktop / web footage)
  layout "fit"     whole frame on a blurred backdrop, captions as a pill (any aspect into any canvas)
  layout "device"  crop the screen rect, draw a phone around it on a blurred backdrop, big side caption
Captions are (source_seconds, text) pairs, given inline or computed from a marks file written during
the take (see browser.Marks) minus the recording's start time. A null text hides the caption.
See examples/timeline.json for every field. Output: H.264 + AAC, faststart, yuv420p.
"""
import argparse
import json
import pathlib
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SCRIPTS = pathlib.Path(__file__).parent
DEFAULT_FONT = "/System/Library/Fonts/SFNS.ttf"  # variable San Francisco; covers Latin and Cyrillic


# ---------- easing ----------
def ease(k: float) -> float:
    """ease-out-quint: quick start, long soft landing. Use for anything entering."""
    k = min(1.0, max(0.0, k))
    return 1 - (1 - k) ** 5


def smooth(k: float) -> float:
    """smootherstep: symmetric, for fades and crossfades."""
    k = min(1.0, max(0.0, k))
    return k * k * k * (k * (k * 6 - 15) + 10)


def rgb(hex_: str) -> tuple[int, int, int]:
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


# ---------- style ----------
class Style:
    def __init__(self, cfg: dict):
        self.W, self.H = cfg.get("size", [1920, 1080])
        self.fps = cfg.get("fps", 60)
        self.xfade = cfg.get("crossfade", 0.6)
        self.accent = rgb(cfg.get("accent", "#ACEF81"))
        self.on_accent = rgb(cfg.get("on_accent", "#111111"))
        self.tint = rgb(cfg.get("tint", "#06123C"))
        self.font_path = cfg.get("font", DEFAULT_FONT)
        self.bold_path = cfg.get("font_bold", self.font_path)
        self._fonts: dict = {}
        self.portrait = self.H > self.W
        self.u = min(self.W, self.H) / 1080  # 1.0 at 1080p; everything scales from it

    def font(self, size: float, bold: bool = False) -> ImageFont.FreeTypeFont:
        key = (round(size * self.u), bold)
        if key not in self._fonts:
            f = ImageFont.truetype(self.bold_path if bold else self.font_path, max(6, key[0]))
            try:
                f.set_variation_by_name("Bold" if bold else "Medium")
            except OSError:
                pass  # static font file: the weight is the file
            self._fonts[key] = f
        return self._fonts[key]

    def backdrop(self, img: Image.Image, blur: float = 28, mix: float = 0.6) -> Image.Image:
        """The frame itself, cover-scaled, blurred and tinted: colours match the footage, text stays readable."""
        bg = cover(img.resize((max(1, img.width // 8), max(1, img.height // 8))), self.W // 6, self.H // 6)
        bg = bg.filter(ImageFilter.GaussianBlur(blur / 6)).resize((self.W, self.H), Image.BICUBIC)
        return Image.blend(bg, Image.new("RGB", (self.W, self.H), self.tint), mix)


def cover(img: Image.Image, w: int, h: int) -> Image.Image:
    k = max(w / img.width, h / img.height)
    r = img.resize((max(w, round(img.width * k)), max(h, round(img.height * k))), Image.LANCZOS)
    x, y = (r.width - w) // 2, (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))


def wrap(text: str, font, width: float) -> list[str]:
    lines, cur = [], ""
    for word in text.split():
        probe = f"{cur} {word}".strip()
        if cur and font.getlength(probe) > width:
            lines.append(cur)
            cur = word
        else:
            cur = probe
    return lines + [cur]


def fade_in_layer(frame: Image.Image, layer: Image.Image, xy, k: float) -> None:
    if k <= 0:
        return
    frame.paste(layer, xy, layer.split()[3].point(lambda v: round(v * k)))


# ---------- captions ----------
class Captions:
    def __init__(self, items: list, st: Style, big: bool):
        self.items = sorted(items, key=lambda c: c[0])
        self.st, self.big = st, big
        self._cache: dict[str, Image.Image] = {}

    @classmethod
    def from_part(cls, part: dict, base: pathlib.Path, st: Style, big: bool) -> "Captions":
        items = [tuple(c) for c in part.get("captions", [])]
        if "marks" in part:
            t0 = part["t0"] if "t0" in part else recording_start(base / part["project"])
            marks = json.loads((base / part["marks"]).read_text())
            items += [(t - t0, text) for t, kind, text in marks if kind in ("cap", "end")]
        return cls(items, st, big)

    def pill(self, text: str) -> Image.Image:
        st = self.st
        f = st.font(36)
        pad, h = round(34 * st.u), round(74 * st.u)
        lines = wrap(text, f, st.W * 0.8)
        lh = round(46 * st.u)
        hh = h + lh * (len(lines) - 1)
        w = int(max(f.getlength(s) for s in lines) + 2 * pad)
        img = Image.new("RGBA", (w, hh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, hh - 1), min(h // 2, hh // 2), fill=(12, 16, 28, 215))
        for i, s in enumerate(lines):
            d.text((w / 2, h / 2 + i * lh + 1), s, font=f, fill=(255, 255, 255, 255), anchor="mm")
        return img

    def block(self, text: str) -> Image.Image:
        st = self.st
        f = st.font(60 if not st.portrait else 56, bold=True)
        width = st.W * (0.34 if not st.portrait else 0.84)
        lines = wrap(text, f, width)
        lh = round(78 * st.u)
        img = Image.new("RGBA", (int(width + 40), lh * len(lines) + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i, s in enumerate(lines):
            x = img.width / 2 if st.portrait else 0
            d.text((x, i * lh), s, font=f, fill=(255, 255, 255, 255), anchor="ma" if st.portrait else "la")
        return img

    def draw(self, frame: Image.Image, t: float, side_box=None) -> None:
        """side_box: (x, y, w, h) free area for big captions next to a device; None = bottom pill."""
        past = [c for c in self.items if c[0] <= t]
        if not past or not past[-1][1]:
            return
        start, text = past[-1]
        nxt = next((c[0] for c in self.items if c[0] > t), 1e9)
        k = min(ease((t - start) / 0.6), smooth((nxt - t) / 0.35))  # glide in, quick fade before the next one
        if k <= 0:
            return
        st = self.st
        if text not in self._cache:
            self._cache[text] = self.block(text) if self.big else self.pill(text)
        img = self._cache[text]
        if self.big and side_box:
            bx, by, bw, bh = side_box
            if st.portrait:
                xy = (round(bx + (bw - img.width) / 2), round(by + (bh - img.height) / 2 + 18 * st.u * (1 - k)))
            else:
                xy = (round(bx - 24 * st.u * (1 - k)), round(by + (bh - img.height) / 2))
        else:
            xy = ((st.W - img.width) // 2, round(st.H - 60 * st.u - img.height + 18 * st.u * (1 - k)))
        fade_in_layer(frame, img, xy, k)


def recording_start(project: pathlib.Path) -> float:
    meta = json.loads((project / "recording/metadata.json").read_text())
    return next(s["unixStartMs"] / 1000 for r in meta["recorders"] for s in r.get("sessions", []) if "unixStartMs" in s)


# ---------- device frame ----------
class Device:
    """A plain phone body (thin bezel, soft shadow). No notch or buttons: attention stays on the screen."""

    def __init__(self, st: Style, screen_aspect: float):
        self.st = st
        if st.portrait:
            h = round(st.H * 0.66)
            w = round(h * screen_aspect)
            self.xy = ((st.W - w) // 2, round(st.H * 0.30))
            self.free = (0, 0, st.W, self.xy[1] - 40 * st.u)
        else:
            h = round(st.H * 0.867)
            w = round(h * screen_aspect)
            self.xy = (round(st.W * 0.59), (st.H - h) // 2)
            self.free = (round(st.W * 0.135), 0, self.xy[0] - st.W * 0.18, st.H)
        self.size = (w, h)
        self._layers()

    def _layers(self) -> None:
        (w, h), (x, y), u = self.size, self.xy, self.size[1] / 936  # 1.0 = the 936 px tall phone of a 1080p canvas
        bezel, pad = round(14 * u), round(80 * u)
        r_body, r_screen = round(62 * u), round(48 * u)
        sh = Image.new("L", (w + 2 * bezel + 2 * pad, h + 2 * bezel + 2 * pad), 0)
        ImageDraw.Draw(sh).rounded_rectangle(
            (pad, pad + 26 * u, pad + w + 2 * bezel, pad + h + 2 * bezel + 26 * u), r_body + 2, fill=170)
        self.shadow, self.shadow_xy = sh.filter(ImageFilter.GaussianBlur(34 * u)), (x - bezel - pad, y - bezel - pad)
        self.body = Image.new("L", (w + 2 * bezel, h + 2 * bezel), 0)
        ImageDraw.Draw(self.body).rounded_rectangle((0, 0, self.body.width - 1, self.body.height - 1), r_body, fill=255)
        self.body_xy = (x - bezel, y - bezel)
        self.mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(self.mask).rounded_rectangle((0, 0, w - 1, h - 1), r_screen, fill=255)

    def put(self, frame: Image.Image, screen: Image.Image) -> None:
        frame.paste((0, 0, 0), self.shadow_xy, self.shadow)
        frame.paste((14, 15, 18), self.body_xy, self.body)
        frame.paste(screen.resize(self.size, Image.LANCZOS), self.xy, self.mask)


# ---------- parts ----------
def probe_size(path: pathlib.Path) -> tuple[int, int]:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout
    w, h = out.strip().split(",")[:2]
    return int(w), int(h)


def read_frames(path: pathlib.Path, start: float, dur: float, size, fps: int):
    w, h = size
    p = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                          "-vf", f"fps={fps}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    try:
        while True:
            buf = p.stdout.read(w * h * 3)
            if len(buf) < w * h * 3:
                return
            yield Image.frombytes("RGB", (w, h), buf)
    finally:
        p.kill()


class Clip:
    def __init__(self, part: dict, base: pathlib.Path, st: Style):
        self.st, self.src = st, base / part["src"]
        self.size = probe_size(self.src)
        self.start, self.end = part.get("start", 0.0), part["end"]
        self.n = round((self.end - self.start) * st.fps)
        self.layout = part.get("layout", "fill")
        self.screen = tuple(part.get("screen") or (0, 0, *self.size))
        self.caps = Captions.from_part(part, base, st, big=self.layout == "device")
        if self.layout == "device":
            x0, y0, x1, y1 = self.screen
            self.device = Device(st, (x1 - x0) / (y1 - y0))
        self._bg = None

    def frames(self):
        last = None
        src = read_frames(self.src, self.start, self.end - self.start, self.size, self.st.fps)
        for i in range(self.n):
            last = next(src, last)  # hold the last frame if the export is a hair shorter than asked
            yield self.compose(last, self.start + i / self.st.fps)

    def frame(self, t: float) -> Image.Image:
        return self.compose(next(read_frames(self.src, t, 0.1, self.size, self.st.fps)), t)

    def compose(self, img: Image.Image, t: float) -> Image.Image:
        st = self.st
        if self.layout == "device":
            frame = st.backdrop(img, blur=36, mix=0.5)
            self.device.put(frame, img.crop(self.screen))
            self.caps.draw(frame, t, self.device.free)
            return frame
        if self.layout == "fit":
            frame = st.backdrop(img)
            k = min(st.W * 0.9 / img.width, st.H * 0.82 / img.height)
            fit = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)
            frame.paste(fit, ((st.W - fit.width) // 2, round((st.H - fit.height) * 0.42)))
        else:
            frame = cover(img, st.W, st.H)
        self.caps.draw(frame, t)
        return frame


class Card:
    """Title card on a blurred still of the footage: optional logo, title, subtitle, button."""

    def __init__(self, part: dict, base: pathlib.Path, st: Style):
        self.st, self.p = st, part
        self.n = round(part["dur"] * st.fps)
        src, t = base / part["bg"]["src"], part["bg"].get("t", 0)
        self.bg = st.backdrop(next(read_frames(src, t, 0.1, probe_size(src), st.fps)), blur=28, mix=0.62)
        self.logo = Image.open(base / part["logo"]).convert("RGBA") if part.get("logo") else None

    def frames(self):
        for i in range(self.n):
            yield self.frame(i / self.st.fps)

    def frame(self, t: float) -> Image.Image:
        st, p, u = self.st, self.p, self.st.u
        f = self.bg.copy()
        rows = []  # (height, draw(y, k)) stacked and centred, each row entering 0.4 s after the previous
        if self.logo:
            lh = round(130 * u)
            logo = self.logo.resize((round(self.logo.width * lh / self.logo.height), lh), Image.LANCZOS)
            rows.append((lh + 30 * u, lambda y, k: fade_in_layer(f, logo, ((st.W - logo.width) // 2, round(y)), k)))
        for key, size, bold, alpha in (("title", 84, True, 1.0), ("subtitle", 40, False, 0.85)):
            if p.get(key):
                font = st.font(size, bold)
                lines = wrap(p[key], font, st.W * 0.8)
                lh = size * 1.25 * u
                rows.append((lh * len(lines) + 16 * u, self._text(f, lines, font, lh, alpha)))
        if p.get("button"):
            rows.append((130 * u, self._button(f, p["button"])))
        total = sum(h for h, _ in rows)
        y = (st.H - total) / 2
        for i, (h, draw) in enumerate(rows):
            k = ease((t - 0.4 * i) / 0.9)
            draw(y + 24 * u * (1 - k), k)
            y += h
        return f

    def _text(self, f, lines, font, lh, alpha):
        def draw(y, k):
            layer = Image.new("RGBA", f.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            for i, s in enumerate(lines):
                d.text((self.st.W / 2, y + i * lh), s, font=font, fill=(255, 255, 255, round(255 * alpha * k)), anchor="ma")
            f.paste(layer, (0, 0), layer)
        return draw

    def _button(self, f, text):
        st, u = self.st, self.st.u
        font = st.font(40, bold=True)
        w, h = font.getlength(text) + 120 * u, 84 * u

        def draw(y, k):
            layer = Image.new("RGBA", f.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            x0, y0 = st.W / 2 - w / 2, y + 20 * u
            d.rounded_rectangle((x0, y0, x0 + w, y0 + h), h / 2, fill=(*st.accent, round(255 * k)))
            d.text((st.W / 2, y0 + h / 2 + 2), text, font=font, fill=(*st.on_accent, round(255 * k)), anchor="mm")
            f.paste(layer, (0, 0), layer)
        return draw


def build(cfg: dict, base: pathlib.Path, st: Style) -> list:
    kinds = {"card": Card, "clip": Clip}
    return [kinds[p.get("type", "clip")](p, base, st) for p in cfg["parts"]]


# ---------- audio + encode ----------
def music_track(cfg: dict, base: pathlib.Path, dur: float, out: pathlib.Path) -> pathlib.Path | None:
    m = cfg.get("music", {"generate": True})
    if m is None or m is False:
        return None
    if m.get("file"):
        return base / m["file"]
    wav = out.with_suffix(".music.wav")
    args = [sys.executable, str(SCRIPTS / "music.py"), f"{dur:.2f}", str(wav)]
    for k in ("mood", "bpm", "seed", "density"):
        if k in m:
            args += [f"--{k}", str(m[k])]
    subprocess.run(args, check=True)
    return wav


def encoder(out: pathlib.Path, st: Style, audio: pathlib.Path | None, volume: float, dur: float):
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{st.W}x{st.H}",
           "-r", str(st.fps), "-i", "-"]
    if audio:
        fade = f"afade=t=out:st={max(0, dur - 2.5):.2f}:d=2.5"  # a supplied track may be longer than the cut
        cmd += ["-i", str(audio), "-filter_complex", f"[1:a]volume={volume},{fade}[a]", "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def render(parts: list, st: Style, enc, dur: float) -> None:
    """Stream parts through the encoder, overlapping each pair by the crossfade length."""
    nx = round(st.xfade * st.fps)
    tail: list[Image.Image] = []
    written = 0

    def put(img):
        nonlocal written
        enc.stdin.write(img.tobytes())
        written += 1
        if written % (st.fps * 5) == 0:
            print(f"{written / st.fps:.0f}/{dur:.0f}s", file=sys.stderr, flush=True)

    for idx, part in enumerate(parts):
        gen = part.frames()
        for i, prev in enumerate(tail):
            put(Image.blend(prev, next(gen), smooth((i + 1) / (nx + 1))))
        buf: list[Image.Image] = []
        for fr in gen:
            buf.append(fr)
            if len(buf) > nx:
                put(buf.pop(0))
        if idx == len(parts) - 1:
            for fr in buf:
                put(fr)
        tail = buf
    enc.stdin.close()
    enc.wait()


def still(parts: list, st: Style, t: float, out: pathlib.Path) -> None:
    """Render one output frame without the crossfade blend: fast feedback on layout and type."""
    nx = st.xfade * st.fps
    for part in parts:
        length = part.n - nx
        if t * st.fps < length or part is parts[-1]:
            local = t
            frame = part.frame(local) if isinstance(part, Card) else part.frame(part.start + local)
            frame.save(out)
            print(out)
            return
        t -= length / st.fps


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("timeline")
    ap.add_argument("--still", type=float, help="write one PNG at this output time instead of the video")
    ap.add_argument("--out", help="override timeline['out']")
    a = ap.parse_args()
    path = pathlib.Path(a.timeline).resolve()
    cfg = json.loads(path.read_text())
    base = path.parent
    st = Style(cfg)
    parts = build(cfg, base, st)
    out = (base / (a.out or cfg.get("out", "final.mp4"))).resolve()
    if a.still is not None:
        still(parts, st, a.still, out.with_name(f"{out.stem}_{a.still:g}s.png"))
        return
    nx = round(st.xfade * st.fps)
    dur = (sum(p.n for p in parts) - nx * (len(parts) - 1)) / st.fps
    audio = music_track(cfg, base, dur, out)
    render(parts, st, encoder(out, st, audio, (cfg.get("music") or {}).get("volume", 0.55), dur), dur)
    print(f"done {out} {dur:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
