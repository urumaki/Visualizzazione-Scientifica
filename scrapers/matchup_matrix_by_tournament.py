#!/usr/bin/env python3
"""
Genera una matchup matrix archetipo-vs-archetipo PER OGNI TORNEO nel dataset.

INPUT:
    - matches_fixed.csv (o matches.csv riparato): match-by-match con outcome
    - decks.csv: serve per etichettare ogni torneo (nome, data)

OUTPUT (in --out-dir, default "matrices_by_tournament/"):
    - un file <tournament_id>_matchup.csv per ogni torneo, formato long:
      archetype_a, archetype_b, win, loss, draw, games, winrate
    - index.csv: riepilogo con tournament_id, nome, data, n. archetipi, n. match

USO:
    python matchup_matrix_by_tournament.py --matches matches_fixed.csv --decks decks.csv \\
        --out-dir matrices_by_tournament --min-games 0
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def load_tournament_meta(decks_csv: Path) -> dict:
    meta = {}
    with open(decks_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row.get("tournament_id")
            if tid and tid not in meta:
                meta[tid] = {
                    "tournament_name": row.get("tournament_name"),
                    "tournament_start_date": row.get("tournament_start_date"),
                    "organization_name": row.get("organization_name"),
                }
    return meta


JUNK_ARCHETYPE_NAMES = {
    "", "?????", "Paper Decklist", "MTGO Decklist", "Decklist",
    "Unknown", "Untitled Deck", "Modern Deck", "New Deck",
}


def is_valid_archetype(name):
    return bool(name) and name.strip() not in JUNK_ARCHETYPE_NAMES


def load_matches_by_tournament(matches_csv: Path) -> dict:
    by_tournament = defaultdict(list)
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
            by_tournament[tid].append((a, b, outcome))
    print(f"Match scartati per archetipo placeholder/spazzatura: {n_junk}")
    return by_tournament


def build_matrix(match_list, top_n=None):
    """match_list: lista di (archetype_a, archetype_b, outcome). Ritorna righe long-format."""
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
    parser.add_argument("--out-dir", default="matrices_by_tournament")
    parser.add_argument("--min-games", type=int, default=20,
                         help="Salta i tornei con meno match totali di questo valore (default 20, dataset troppo piccoli non sono utili)")
    parser.add_argument("--top-n", type=int, default=None,
                         help="Se impostato, raggruppa gli archetipi oltre i top N in 'Other'")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = load_tournament_meta(Path(args.decks))
    by_tournament = load_matches_by_tournament(Path(args.matches))

    index_rows = []
    n_written = 0
    n_skipped = 0

    for tid, match_list in by_tournament.items():
        if len(match_list) < args.min_games:
            n_skipped += 1
            continue

        rows = build_matrix(match_list, top_n=args.top_n)
        n_archetypes = len(set(a for a, _, _ in match_list) | set(b for _, b, _ in match_list))

        out_path = out_dir / f"{tid}_matchup.csv"
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["archetype_a", "archetype_b", "win", "loss", "draw", "games", "winrate"])
            writer.writeheader()
            writer.writerows(rows)

        m = meta.get(tid, {})
        index_rows.append({
            "tournament_id": tid,
            "tournament_name": m.get("tournament_name", ""),
            "tournament_start_date": m.get("tournament_start_date", ""),
            "organization_name": m.get("organization_name", ""),
            "n_archetypes": n_archetypes,
            "n_matches": len(match_list),
            "file": out_path.name,
        })
        n_written += 1

    index_rows.sort(key=lambda r: r["tournament_start_date"] or "")
    with open(out_dir / "index.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "tournament_id", "tournament_name", "tournament_start_date",
            "organization_name", "n_archetypes", "n_matches", "file",
        ])
        writer.writeheader()
        writer.writerows(index_rows)

    print(f"Tornei con matrice generata: {n_written}")
    print(f"Tornei saltati (meno di {args.min_games} match): {n_skipped}")
    print(f"Output in: {out_dir}/  (vedi index.csv per l'elenco)")


if __name__ == "__main__":
    main()
