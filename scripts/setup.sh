#!/usr/bin/env bash
# One-time setup: ffmpeg through Homebrew, Python deps in a venv inside the skill folder, then a check.
# Safe to re-run. Permissions and the Screen Studio licence stay manual: doctor.py says what to do.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v ffmpeg >/dev/null; then
  if command -v brew >/dev/null; then
    brew install ffmpeg
  else
    echo "ffmpeg missing and Homebrew not found: install Homebrew from https://brew.sh, then re-run" >&2
  fi
fi

# A venv, because Homebrew's Python refuses global pip installs (PEP 668).
PY="$(command -v python3)"
[ -d "$ROOT/.venv" ] || "$PY" -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --quiet --upgrade pip
"$ROOT/.venv/bin/pip" install --quiet -r "$ROOT/scripts/requirements.txt"

"$ROOT/.venv/bin/python" "$ROOT/scripts/doctor.py"
