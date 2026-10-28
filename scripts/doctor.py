"""Check everything the skill needs and print the fix for anything missing. Exit code 1 if something is.

    python scripts/doctor.py

Standard library only, so it runs before setup.sh has installed anything.
"""
import importlib.util
import pathlib
import platform
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv/bin/python"
APPS = [pathlib.Path("/Applications"), pathlib.Path.home() / "Applications"]


def app_installed(name: str) -> bool:
    return any((d / f"{name}.app").exists() for d in APPS)


def permissions() -> list[tuple[bool, str, str]]:
    if not importlib.util.find_spec("Quartz"):
        return []  # reported as a missing module above
    import Quartz

    fix = "System Settings > Privacy & Security > {}: enable your terminal app, then restart it"
    return [
        (bool(Quartz.CGPreflightPostEventAccess()), "Accessibility permission", fix.format("Accessibility")),
        (bool(Quartz.CGPreflightScreenCaptureAccess()), "Screen Recording permission", fix.format("Screen Recording")),
    ]


def checks() -> list[tuple[bool, str, str]]:
    setup = f"bash {ROOT / 'scripts/setup.sh'}"
    modules = {"playwright": "playwright", "Quartz": "pyobjc-framework-Quartz",
               "ApplicationServices": "pyobjc-framework-ApplicationServices", "PIL": "pillow", "numpy": "numpy"}
    out = [
        (platform.system() == "Darwin", "macOS", "this skill drives macOS only"),
        (sys.version_info >= (3, 10), f"Python 3.10+ (running {platform.python_version()})", "brew install python"),
        (VENV_PY.exists(), f"skill venv {VENV_PY}", setup),
        *[(importlib.util.find_spec(m) is not None, f"python module {pkg}", f"{setup}  (then run scripts with {VENV_PY})")
          for m, pkg in modules.items()],
        (shutil.which("ffmpeg") is not None, "ffmpeg", "brew install ffmpeg"),
        (shutil.which("ffprobe") is not None, "ffprobe", "brew install ffmpeg"),
        (app_installed("Screen Studio"), "Screen Studio app", "install and license it from https://screen.studio"),
        (app_installed("Google Chrome"), "Google Chrome", "brew install --cask google-chrome"),
    ]
    return out + permissions()


def main() -> int:
    missing = 0
    for ok, what, fix in checks():
        print(f"{'ok     ' if ok else 'MISSING'} {what}" + ("" if ok else f"\n        fix: {fix}"))
        missing += not ok
    print("all good" if not missing else f"{missing} missing")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
