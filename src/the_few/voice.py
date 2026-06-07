"""Read the current titles aloud — the voice half of the gate.

Uses macOS `say` (zero dependencies, already on the machine). The flow is meant to
be conversational: you hear the headlines, say which ones interest you, and those
get kept. `build_spoken` produces the script; `speak` plays or records it.
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess


def build_spoken(rows: list[sqlite3.Row], name_by_slug: dict[str, str]) -> str:
    """Turn a list of items into a short spoken script."""
    if not rows:
        return "Nothing new. Enjoy the quiet."
    parts = [f"Here {'is' if len(rows) == 1 else 'are'} {len(rows)} headline" +
             ("" if len(rows) == 1 else "s") + "."]
    for i, row in enumerate(rows, start=1):
        source = name_by_slug.get(row["source_slug"], row["source_slug"])
        parts.append(f"Number {i}. From {source}. {row['title']}.")
    parts.append("Which ones interest you?")
    return " ".join(parts)


def have_say() -> bool:
    return shutil.which("say") is not None


def speak(text: str, *, voice: str | None = None, rate: int | None = None,
          out_file: str | None = None) -> bool:
    """Speak text via macOS `say`. Returns False if `say` isn't available.

    With out_file, records to an audio file instead of playing through speakers.
    """
    if not have_say():
        return False
    cmd = ["say"]
    if voice:
        cmd += ["-v", voice]
    if rate:
        cmd += ["-r", str(rate)]
    if out_file:
        cmd += ["-o", out_file]
    cmd.append(text)
    subprocess.run(cmd, check=True)
    return True
