#!/usr/bin/env python3
"""
Audit del dataset Modern scraped da MTGGoldfish (formato prodotto da scrape_modern.py).

Uso:
    python audit_dataset.py --input Output --out-csv decks_audit.csv --out-cards-csv cards_audit.csv

Cosa fa:
    - Cammina l'albero Output/<Torneo>/*.txt e Output/MTGO/<Torneo>/*.txt
    - Parsa l'header di ogni file deck (Tournament, Event Date, Deck, Pilot, Rank,
      Archetype, Paper Cost, MTGO Cost, Source) e il corpo (lista carte)
    - Produce due CSV:
        1) decks_audit.csv  -> una riga per deck, con metadati + flag di qualità
        2) cards_audit.csv  -> una riga per (deck, carta, quantità, sezione)
    - Stampa un report riassuntivo in console con i punti da controllare
      prima di usare i dati per un progetto di visualizzazione scientifica.

Nota: questo script NON valuta correttezza del contenuto (es. se una carta
esiste davvero in Modern), solo consistenza/copertura strutturale del dataset.
"""

import argparse
import csv
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HEADER_FIELDS = [
    "Tournament",
    "Event Date",
    "Deck",
    "Pilot",
    "Rank",
    "Archetype",
    "Paper Cost",
    "MTGO Cost",
    "Source",
]

DATE_FORMATS = [
    "%B %d, %Y",   # "August 27, 2026"
    "%b %d, %Y",   # "Aug 27, 2026"
    "%Y-%m-%d",
    "%m/%d/%Y",
]

CARD_LINE_RE = re.compile(r"^\s*(\d+)\s+(.+?)\s*$")


def parse_header(text: str) -> dict:
    header = {}
    lines = text.splitlines()
    body_start = 0
    for i, line in enumerate(lines):
        matched = False
        for field in HEADER_FIELDS:
            prefix = f"{field}:"
            if line.startswith(prefix):
                header[field] = line[len(prefix):].strip()
                matched = True
                break
        if not matched:
            # first non-header, non-empty-after-header line = start of body
            if line.strip() == "" and header:
                body_start = i + 1
                break
    body = "\n".join(lines[body_start:]).strip()
    return header, body


def parse_deck_body(body: str):
    """Split into (main_cards, sideboard_cards), each a list of (qty, name)."""
    lines = [l for l in body.splitlines()]
    main, side = [], []
    in_sideboard = False
    blank_seen = False
    for raw in lines:
        line = raw.strip()
        if line == "":
            blank_seen = True
            continue
        if line.lower().startswith("sideboard"):
            in_sideboard = True
            continue
        m = CARD_LINE_RE.match(line)
        if not m:
            continue
        qty, name = int(m.group(1)), m.group(2).strip()
        if in_sideboard or blank_seen:
            side.append((qty, name))
        else:
            main.append((qty, name))
    return main, side


def parse_date(raw: str):
    raw = (raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def walk_deck_files(input_dir: Path):
    for txt_path in input_dir.rglob("*.txt"):
        if txt_path.name.startswith("."):
            continue
        yield txt_path


def main():
    parser = argparse.ArgumentParser(description="Audit MTGGoldfish scraped dataset.")
    parser.add_argument("--input", default="Output", help="Root folder produced by scrape_modern.py")
    parser.add_argument("--out-csv", default="decks_audit.csv", help="Output CSV, one row per deck")
    parser.add_argument("--out-cards-csv", default="cards_audit.csv", help="Output CSV, one row per card line")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        raise SystemExit(f"Input dir not found: {input_dir}")

    deck_rows = []
    card_rows = []

    n_files = 0
    n_parse_fail = 0
    n_empty_main = 0
    n_missing_archetype = 0
    n_missing_price_paper = 0
    n_missing_price_online = 0
    n_offsize_main = 0  # main deck != 60 cards (heuristic flag, not always wrong)
    archetype_counter = Counter()
    source_counter = Counter()
    year_month_counter = Counter()
    tournaments_seen = set()
    unparsed_dates = 0

    for txt_path in walk_deck_files(input_dir):
        n_files += 1
        try:
            text = txt_path.read_text(encoding="utf-8")
        except Exception:
            n_parse_fail += 1
            continue

        header, body = parse_header(text)
        if not header.get("Tournament"):
            n_parse_fail += 1
            continue

        main_cards, side_cards = parse_deck_body(body)
        main_count = sum(q for q, _ in main_cards)
        side_count = sum(q for q, _ in side_cards)

        if main_count == 0:
            n_empty_main += 1
        if main_count not in (60,):
            n_offsize_main += 1

        archetype = header.get("Archetype", "Unknown") or "Unknown"
        if archetype.strip().lower() == "unknown":
            n_missing_archetype += 1
        archetype_counter[archetype] += 1

        paper_cost = header.get("Paper Cost", "")
        online_cost = header.get("MTGO Cost", "")
        if not paper_cost or "N/A" in paper_cost:
            n_missing_price_paper += 1
        if not online_cost or "N/A" in online_cost:
            n_missing_price_online += 1

        source_url = header.get("Source", "")
        is_mtgo = "mtgo.com" in source_url.lower() or "/MTGO/" in str(txt_path)
        source_counter["MTGO" if is_mtgo else "Paper/Other"] += 1

        event_date = parse_date(header.get("Event Date", ""))
        if event_date is None:
            unparsed_dates += 1
        else:
            year_month_counter[f"{event_date.year}-{event_date.month:02d}"] += 1

        tournaments_seen.add(header.get("Tournament"))

        deck_rows.append({
            "file": str(txt_path.relative_to(input_dir)),
            "tournament": header.get("Tournament"),
            "event_date_raw": header.get("Event Date"),
            "event_date_parsed": event_date.isoformat() if event_date else "",
            "deck_name": header.get("Deck"),
            "pilot": header.get("Pilot"),
            "rank_order": header.get("Rank"),
            "archetype": archetype,
            "paper_cost": paper_cost,
            "online_cost": online_cost,
            "source": "MTGO" if is_mtgo else "Paper/Other",
            "main_deck_count": main_count,
            "sideboard_count": side_count,
            "flag_empty_main": main_count == 0,
            "flag_offsize_main": main_count != 60,
            "flag_missing_archetype": archetype.strip().lower() == "unknown",
        })

        for qty, name in main_cards:
            card_rows.append({
                "file": str(txt_path.relative_to(input_dir)),
                "tournament": header.get("Tournament"),
                "pilot": header.get("Pilot"),
                "archetype": archetype,
                "section": "main",
                "quantity": qty,
                "card_name": name,
            })
        for qty, name in side_cards:
            card_rows.append({
                "file": str(txt_path.relative_to(input_dir)),
                "tournament": header.get("Tournament"),
                "pilot": header.get("Pilot"),
                "archetype": archetype,
                "section": "sideboard",
                "quantity": qty,
                "card_name": name,
            })

    # write CSVs
    if deck_rows:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(deck_rows[0].keys()))
            writer.writeheader()
            writer.writerows(deck_rows)

    if card_rows:
        with open(args.out_cards_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(card_rows[0].keys()))
            writer.writeheader()
            writer.writerows(card_rows)

    # ---- report ----
    print("=" * 60)
    print("MTGGoldfish Modern dataset — audit report")
    print("=" * 60)
    print(f"File .txt trovati:            {n_files}")
    print(f"File non parsabili (header):  {n_parse_fail}")
    print(f"Tornei distinti:               {len(tournaments_seen)}")
    print(f"Deck totali validi:            {len(deck_rows)}")
    print()
    print(f"Deck con main deck vuoto:      {n_empty_main}")
    print(f"Deck con main deck != 60 carte:{n_offsize_main}  (controlla: normale per alcune varianti, ma verifica outlier)")
    print(f"Deck con archetipo 'Unknown':  {n_missing_archetype} ({(n_missing_archetype / max(1, len(deck_rows)) * 100):.1f}%)")
    print(f"Deck senza prezzo paper:       {n_missing_price_paper}")
    print(f"Deck senza prezzo online:      {n_missing_price_online}")
    print(f"Date non parsabili:            {unparsed_dates}")
    print()
    print(f"Split fonte:                   {dict(source_counter)}")
    print()
    print(f"Etichette archetipo distinte:  {len(archetype_counter)}")
    print("Top 15 archetipi per frequenza:")
    for name, count in archetype_counter.most_common(15):
        print(f"    {count:6d}  {name}")
    print()
    if year_month_counter:
        print("Copertura temporale (deck per anno-mese), controlla buchi:")
        for ym in sorted(year_month_counter):
            print(f"    {ym}: {year_month_counter[ym]}")
    print()
    print(f"NOTA: 'rank_order' NON e' un piazzamento/win-rate reale, e' solo")
    print(f"l'ordine di comparsa del deck nella pagina torneo (vedi scrape_modern.py).")
    print(f"Se serve il win-loss per player, va scrapato separatamente dalla pagina standings.")
    print("=" * 60)
    print(f"CSV scritti: {args.out_csv} ({len(deck_rows)} righe), {args.out_cards_csv} ({len(card_rows)} righe)")


if __name__ == "__main__":
    main()
