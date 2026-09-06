#!/usr/bin/env python3
"""
Genera una matchup matrix archetipo-vs-archetipo PER OGNI ERA DI BANLIST Modern.

Le "ere" sono i periodi tra un aggiornamento della banned list e il successivo,
cosi' i cambi di formato non confondono il segnale del winrate (un archetipo
forte prima di un ban e uno diverso dopo il ban non vengono mischiati insieme).

Date degli aggiornamenti Modern-rilevanti nel range 2020-08-13 / 2026-08-29
(verificate: magic.wizards.com / mtggoldfish / mtg.fandom.com):
    2021-02-15  Field of the Dead, Mystic Sanctuary, Simian Spirit Guide,
                Tibalt's Trickery, Uro banned
    2022-03-07  Lurrus of the Dream-Den banned
    2022-10-10  Yorion, Sky Nomad banned
    2023-08-07  Preordain unbanned
    2023-12-04  Fury, Up the Beanstalk banned
    2024-03-11  Violent Outburst banned
    2024-12-16  The One Ring, Amped Raptor, Jegantha banned;
                Mox Opal, Green Sun's Zenith, Faithless Looting, Splinter Twin unbanned
    2025-03-31  Underworld Breach banned
    2026-05-18  Phlage Titan of Fire's Fury, Lotus Field banned;
                Violent Outburst, Umezawa's Jitte unbanned

Se in futuro escono nuovi aggiornamenti Modern, aggiungi la data alla lista
BANLIST_DATES sotto (formato "YYYY-MM-DD") e rilancia lo script.

INPUT:
    - matches_fixed.csv: match-by-match con outcome
    - decks.csv: serve per la data del torneo (tournament_start_date),
      dato che matches.csv non la contiene direttamente

OUTPUT (in --out-dir, default "matrices_by_era/"):
    - un file era_NN_<inizio>_<fine>.csv per ogni era, formato long:
      archetype_a, archetype_b, win, loss, draw, games, winrate
    - index.csv: riepilogo con date era, n. tornei, n. match

USO:
    python matchup_matrix_by_banlist_era.py --matches matches_fixed.csv --decks decks.csv  --out-dir matrices_by_era --top-n 20
"""
import argparse
import csv
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BANLIST_DATES = [
    "2021-02-15",
    "2022-03-07",
    "2022-10-10",
    "2023-08-07",
    "2023-12-04",
    "2024-03-11",
    "2024-12-16",
    "2025-03-31",
    "2026-05-18",
]

DATASET_START = "2020-08-13"
DATASET_END = "2026-08-29"


def parse_date(raw: str):
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def build_eras():
    bounds = [DATASET_START] + BANLIST_DATES + [DATASET_END]
    eras = []
    for i in range(len(bounds) - 1):
        start = parse_date(bounds[i])
        end = parse_date(bounds[i + 1])
        eras.append({"index": i + 1, "start": start, "end": end,
                      "start_str": bounds[i], "end_str": bounds[i + 1]})
    return eras


def era_for_date(date, eras):
    if date is None:
        return None
    for era in eras:
        if era["start"] <= date < era["end"]:
            return era["index"]
    if date >= eras[-1]["end"]:
        return eras[-1]["index"]
    return None


def load_tournament_dates(decks_csv: Path) -> dict:
    dates = {}
    with open(decks_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row.get("tournament_id")
            if tid and tid not in dates:
                dates[tid] = parse_date(row.get("tournament_start_date"))
    return dates


JUNK_ARCHETYPE_NAMES = {
    "", "?????", "Paper Decklist", "MTGO Decklist", "Decklist",
    "Unknown", "Untitled Deck", "Modern Deck", "New Deck",
}


def is_valid_archetype(name):
    return bool(name) and name.strip() not in JUNK_ARCHETYPE_NAMES


# Varianti di colore che, per QUESTI archetipi specifici, non sono un piano di
# gioco diverso ma solo un modo diverso in cui i giocatori hanno scritto lo
# stesso mazzo su Melee.gg (es. "Amulet Titan" e' mono-verde per definizione,
# "Domain Zoo" e' per definizione un manabase a 4-5 colori). NON tocchiamo
# invece casi come "Boros/Jeskai/Mardu Energy" o "Izzet/Jeskai/Rakdos Prowess":
# li' il colore e' un vero piano di gioco diverso, unificarli falserebbe il
# winrate. Lista curata a mano sulla base della frequenza in matches_fixed.csv.
REDUNDANT_COLOR_ALIASES = {
    "Mono-Green Amulet Titan": "Amulet Titan",
    "W-U-R-G Domain Zoo": "Domain Zoo",
    "W-U-B-R-G Domain Zoo": "Domain Zoo",
    "W-B-R-G Domain Zoo": "Domain Zoo",
    "Colorless Eldrazi Tron": "Eldrazi Tron",
    "Mono-Blue Merfolk": "Merfolk",
    "Mono-Red Ruby Storm": "Ruby Storm",
    # "Goryo's" e "Goryo's Vengeance" sono lo stesso mazzo (basato sulla
    # stessa carta); alcuni giocatori hanno omesso "Vengeance" dal nome.
    "Esper Goryo's": "Esper Goryo's Vengeance",
    "W-U-B-G Goryo's": "W-U-B-G Goryo's Vengeance",
    "Grixis Goryo's": "Grixis Goryo's Vengeance",
}


def normalize_spelling(name: str) -> str:
    """Uniforma apostrofi (dritti/curvi) e spazi multipli, per non trattare
    come archetipi diversi due stringhe che sono la stessa identica cosa."""
    s = name.replace("’", "'").replace("‘", "'")
    return " ".join(s.split())


def build_archetype_canonicalizer(matches_csv: Path):
    """Prima passata sul file match: raggruppa i nomi archetipo che, una
    volta normalizzati (apostrofi/spazi, case-insensitive), sono identici —
    tipicamente refusi di battitura come "Esper MIdrange" vs "Esper Midrange"
    — e sceglie come forma canonica quella piu' frequente. Poi applica sopra
    gli alias colore ridondanti curati a mano (REDUNDANT_COLOR_ALIASES)."""
    freq = defaultdict(int)
    with open(matches_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            for col in ("player_decklist_name", "opponent_decklist_name"):
                name = row.get(col)
                if name and is_valid_archetype(name):
                    freq[normalize_spelling(name)] += 1

    by_key = defaultdict(list)
    for name, count in freq.items():
        by_key[name.lower()].append((name, count))

    canon = {}
    n_typo_merges = 0
    for variants in by_key.values():
        best = max(variants, key=lambda nc: nc[1])[0]
        for name, _ in variants:
            canon[name] = best
            if name != best:
                n_typo_merges += 1

    for raw, target in REDUNDANT_COLOR_ALIASES.items():
        key = normalize_spelling(raw)
        # L'alias punta al nome canonico gia' risolto per il target (nel caso
        # anche il target avesse a sua volta un refuso dominante altrove).
        canon[key] = canon.get(normalize_spelling(target), normalize_spelling(target))

    print(f"Normalizzazione archetipi: {n_typo_merges} varianti di battitura unificate, "
          f"{len(REDUNDANT_COLOR_ALIASES)} alias colore-ridondante applicati.")
    return canon


def load_matches_by_era(matches_csv: Path, tournament_dates: dict, eras: list, canon: dict):
    by_era = defaultdict(list)
    by_era_tournaments = defaultdict(set)
    n_unassigned = 0
    n_junk = 0
    with open(matches_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a = row.get("player_decklist_name")
            b = row.get("opponent_decklist_name")
            outcome = row.get("outcome")
            tid = row.get("tournament_id")
            if not (a and b and outcome in ("win", "loss", "draw") and tid):
                continue
            if not (is_valid_archetype(a) and is_valid_archetype(b)):
                n_junk += 1
                continue
            a = canon.get(normalize_spelling(a), normalize_spelling(a))
            b = canon.get(normalize_spelling(b), normalize_spelling(b))
            tdate = tournament_dates.get(tid)
            era_idx = era_for_date(tdate, eras)
            if era_idx is None:
                n_unassigned += 1
                continue
            by_era[era_idx].append((a, b, outcome))
            by_era_tournaments[era_idx].add(tid)
    print(f"Match scartati per archetipo placeholder/spazzatura: {n_junk}")
    return by_era, by_era_tournaments, n_unassigned


def build_matrix(match_list, top_n=None):
    freq = defaultdict(int)
    for a, _, _ in match_list:
        freq[a] += 1

    if top_n:
        top = set(sorted(freq, key=lambda k: -freq[k])[:top_n])
        def bucket(name):
            return name if name in top else "Other"
    else:
        def bucket(name):
            return name

    cells = defaultdict(lambda: {"win": 0, "loss": 0, "draw": 0})
    for a, b, outcome in match_list:
        key = (bucket(a), bucket(b))
        cells[key][outcome] += 1

    rows = []
    for (a, b), c in cells.items():
        games = c["win"] + c["loss"] + c["draw"]
        winrate = round(c["win"] / (c["win"] + c["loss"]) * 100, 1) if (c["win"] + c["loss"]) > 0 else ""
        rows.append({
            "archetype_a": a, "archetype_b": b,
            "win": c["win"], "loss": c["loss"], "draw": c["draw"],
            "games": games, "winrate": winrate,
        })
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", default="matches_fixed.csv")
    parser.add_argument("--decks", default="decks.csv")
    parser.add_argument("--out-dir", default="matrices_by_era")
    parser.add_argument("--top-n", type=int, default=20,
                         help="Raggruppa gli archetipi oltre i top N in 'Other' (default 20)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    eras = build_eras()
    tournament_dates = load_tournament_dates(Path(args.decks))
    canon = build_archetype_canonicalizer(Path(args.matches))
    by_era, by_era_tournaments, n_unassigned = load_matches_by_era(
        Path(args.matches), tournament_dates, eras, canon
    )

    index_rows = []
    for era in eras:
        idx = era["index"]
        match_list = by_era.get(idx, [])
        label = f"era_{idx:02d}_{era['start_str']}_{era['end_str']}"
        out_path = out_dir / f"{label}.csv"

        rows = build_matrix(match_list, top_n=args.top_n) if match_list else []
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["archetype_a", "archetype_b", "win", "loss", "draw", "games", "winrate"])
            writer.writeheader()
            writer.writerows(rows)

        index_rows.append({
            "era_index": idx,
            "start_date": era["start_str"],
            "end_date": era["end_str"],
            "n_tournaments": len(by_era_tournaments.get(idx, set())),
            "n_matches": len(match_list),
            "file": out_path.name,
        })
        print(f"Era {idx:2d} [{era['start_str']} -> {era['end_str']}]: "
              f"{len(by_era_tournaments.get(idx, set()))} tornei, {len(match_list)} match")

    with open(out_dir / "index.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "era_index", "start_date", "end_date", "n_tournaments", "n_matches", "file",
        ])
        writer.writeheader()
        writer.writerows(index_rows)

    print()
    print(f"Match con torneo senza data valida (non assegnati a nessuna era): {n_unassigned}")
    print(f"Output in: {out_dir}/  (vedi index.csv per l'elenco)")


if __name__ == "__main__":
    main()
