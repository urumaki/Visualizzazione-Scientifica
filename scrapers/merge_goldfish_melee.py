from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GOLDFISH_OUTPUT = ROOT.parent / "Output"
MELEE_DATA_DIR = ROOT / "melee_gg_tournament_data"


def normalize(value: str | None) -> str:
    if value is None:
        return ""
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def read_goldfish_metadata(path: Path) -> dict:
    metadata = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:12]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    return metadata


def build_melee_index() -> dict:
    index = {}
    if not MELEE_DATA_DIR.exists():
        return index
    for csv_file in MELEE_DATA_DIR.rglob("*.csv"):
        try:
            with csv_file.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                if reader.fieldnames is None:
                    continue
                for row in reader:
                    tournament = row.get("Tournament") or row.get("tournament") or row.get("Event") or ""
                    deck = row.get("Deck Name") or row.get("Deck") or row.get("deck_name") or ""
                    pilot = row.get("Player Name") or row.get("Pilot") or row.get("Player") or row.get("Player Profile Name") or ""
                    key = (normalize(tournament), normalize(deck), normalize(pilot))
                    if key[0] and key[1] and key[2]:
                        index[key] = row
        except Exception:
            continue
    return index


def update_goldfish_files() -> int:
    melee_index = build_melee_index()
    if not melee_index:
        print(f"No Melee CSV data found under {MELEE_DATA_DIR}. Nothing to merge.")
        return 0

    updated = 0
    for txt_file in sorted(GOLDFISH_OUTPUT.rglob("*.txt")):
        metadata = read_goldfish_metadata(txt_file)
        tournament = metadata.get("Tournament", "")
        deck = metadata.get("Deck", "")
        pilot = metadata.get("Pilot", "")
        key = (normalize(tournament), normalize(deck), normalize(pilot))
        if key not in melee_index:
            continue

        row = melee_index[key]
        source = row.get("Source") or row.get("URL") or row.get("Decklist URL") or "melee.gg"
        archetype = row.get("Archetype") or row.get("Deck Strategy") or metadata.get("Archetype", "Unknown")
        date_value = row.get("Event Date") or row.get("Date") or metadata.get("Event Date", "")
        content = txt_file.read_text(encoding="utf-8", errors="ignore")
        lines = content.splitlines()
        rewritten = []
        for line in lines:
            if line.startswith("Source:"):
                rewritten.append(f"Source: {source}")
            elif line.startswith("Archetype:"):
                rewritten.append(f"Archetype: {archetype}")
            elif line.startswith("Event Date:") and date_value:
                rewritten.append(f"Event Date: {date_value}")
            else:
                rewritten.append(line)
        if "Melee.gg sync" not in "\n".join(rewritten):
            rewritten.insert(9, "Melee.gg sync: matched with melee.gg data")
        txt_file.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
        updated += 1

    print(f"Merged {updated} Goldfish file(s) from Melee.gg data when a direct match was available.")
    return updated


if __name__ == "__main__":
    update_goldfish_files()
