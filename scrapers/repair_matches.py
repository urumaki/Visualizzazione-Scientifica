#!/usr/bin/env python3
"""
Ripara matches.csv in locale, senza richieste di rete:
    1. Ricalcola "outcome" da parole chiave in raw_short_result, sia in
       italiano che in inglese (il bug precedente cercava solo l'italiano).
       NON e' un parsing puro del punteggio numerico: se un formato non
       previsto compare (bye, no-show, forfeit, o puramente numerico senza
       parola), la riga cade in "unknown" e perde anche il punteggio a
       cascata. I valori raw_short_result che finiscono in "unknown" vengono
       stampati a fine esecuzione, cosi' i pattern non gestiti si scoprono
       subito invece che a valle nei numeri della presentazione.
    2. Ricalcola "player_decklist_id"/"player_decklist_name" usando
       standings.csv come fonte primaria e decks.csv (owner_display_name +
       tournament_id) come fallback quando lo standings ha il campo vuoto
       (bug lato sito: a volte Team.Decklists non e' popolato nella risposta).
       I nomi placeholder (es. "?????") sono esclusi sia dalla mappa di
       fallback sia dal suo utilizzo, e un nome duplicato nello stesso
       torneo disabilita il fallback per quel nome invece di assegnare la
       decklist a caso.

USO:
    python repair_matches.py --matches matches.csv --decks decks.csv \\
        --standings standings.csv --out matches_fixed.csv
"""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path

RESULT_RE = re.compile(r"(\d+)-(\d+)-(\d+)")

# Nomi placeholder con cui Melee.gg a volte indica un giocatore/decklist
# anonimo o non ancora assegnato. Se due giocatori nello stesso torneo
# risultassero entrambi con questo nome, usarlo come chiave in
# load_decklist_by_name farebbe collidere silenziosamente le loro decklist
# nel dizionario (l'ultima riga letta sovrascrive le precedenti) — quindi
# vanno esclusi sia dalla mappa sia dal fallback che la consulta.
JUNK_DISPLAY_NAMES = {
    "", "?????", "Anonymous", "Anonymous Player", "Unknown", "N/A", "TBD",
}


def is_valid_display_name(name):
    return bool(name) and name.strip() not in JUNK_DISPLAY_NAMES


def fix_outcome(raw_short_result: str):
    if not raw_short_result:
        return "unknown"
    t = raw_short_result.lower()
    if "vittoria" in t or "win" in t:
        return "win"
    if "sconfitta" in t or "loss" in t or "defeat" in t:
        return "loss"
    if "pareggio" in t or "draw" in t:
        return "draw"
    return "unknown"


def own_perspective_score(outcome: str, raw_short_result: str):
    """I numeri in raw_short_result sono sempre {punteggio vincitore}-{punteggio perdente}-{pareggi},
    NON {mio punteggio}-{punteggio avversario}. Li riordiniamo dal punto di vista del giocatore."""
    m = RESULT_RE.search(raw_short_result or "")
    if not m:
        return None, None, None
    winner_score, loser_score, draws = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if outcome == "win":
        return winner_score, loser_score, draws
    if outcome == "loss":
        return loser_score, winner_score, draws
    if outcome == "draw":
        return winner_score, loser_score, draws
    return None, None, None


def load_decklist_by_name(decks_csv: Path) -> dict:
    mapping = {}
    n_skipped_junk = 0
    n_collisions = 0
    with open(decks_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row.get("tournament_id")
            name = row.get("owner_display_name")
            if not (tid and is_valid_display_name(name)):
                if tid and name:
                    n_skipped_junk += 1
                continue
            key = (tid, name)
            if key in mapping:
                # Due giocatori con lo stesso nome nello stesso torneo: non
                # possiamo sapere quale decklist sia la loro, meglio non
                # indovinare che assegnarne una a caso.
                n_collisions += 1
                mapping[key] = None
                continue
            mapping[key] = (row.get("guid"), row.get("decklist_name"))
    if n_skipped_junk:
        print(f"load_decklist_by_name: {n_skipped_junk} righe scartate per nome placeholder/spazzatura.")
    if n_collisions:
        print(f"load_decklist_by_name: {n_collisions} collisioni (tournament_id, owner_display_name) duplicato, fallback disabilitato per quei nomi.")
    return {k: v for k, v in mapping.items() if v is not None}


def load_standings_lookup(standings_csv: Path) -> dict:
    lookup = {}
    with open(standings_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tid = row.get("tournament_id")
            pid = row.get("player_id")
            if tid and pid:
                lookup[(tid, pid)] = (
                    row.get("decklist_id"),
                    row.get("decklist_name"),
                    row.get("player_display_name"),
                )
    return lookup


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--matches", default="matches.csv")
    parser.add_argument("--decks", default="decks.csv")
    parser.add_argument("--standings", default="standings.csv")
    parser.add_argument("--out", default="matches_fixed.csv")
    args = parser.parse_args()

    decklist_by_name = load_decklist_by_name(Path(args.decks))
    standings_lookup = load_standings_lookup(Path(args.standings))

    n_total = 0
    n_outcome_fixed = 0
    n_deck_fixed_from_standings = 0
    n_deck_fixed_from_fallback = 0
    n_deck_still_missing = 0
    unknown_raw_values = Counter()

    with open(args.matches, newline="", encoding="utf-8") as f_in, \
         open(args.out, "w", newline="", encoding="utf-8") as f_out:
        reader = csv.DictReader(f_in)
        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()

        for row in reader:
            n_total += 1

            old_outcome = row["outcome"]
            new_outcome = fix_outcome(row.get("raw_short_result"))
            if new_outcome != old_outcome:
                n_outcome_fixed += 1
            if new_outcome == "unknown":
                unknown_raw_values[row.get("raw_short_result") or "(vuoto)"] += 1
            row["outcome"] = new_outcome

            gw, gl, gd = own_perspective_score(new_outcome, row.get("raw_short_result"))
            if gw is not None:
                row["game_wins"], row["game_losses"], row["game_draws"] = gw, gl, gd

            tid = row.get("tournament_id")
            pid = row.get("player_id")

            deck_id, deck_name, display_name = standings_lookup.get(
                (tid, pid), (None, None, None)
            )
            if deck_id:
                n_deck_fixed_from_standings += 1
            elif is_valid_display_name(display_name):
                fallback = decklist_by_name.get((tid, display_name))
                if fallback:
                    deck_id, deck_name = fallback
                    n_deck_fixed_from_fallback += 1
                else:
                    n_deck_still_missing += 1
            else:
                n_deck_still_missing += 1

            row["player_decklist_id"] = deck_id or ""
            row["player_decklist_name"] = deck_name or ""

            writer.writerow(row)

    print(f"Righe totali:                         {n_total}")
    print(f"Outcome corretti (era 'unknown'/errato): {n_outcome_fixed}")
    print(f"Decklist trovata via standings.csv:    {n_deck_fixed_from_standings}")
    print(f"Decklist trovata via fallback (decks.csv): {n_deck_fixed_from_fallback}")
    print(f"Decklist ancora mancante:              {n_deck_still_missing}")
    if unknown_raw_values:
        print(f"\nraw_short_result distinti finiti in 'unknown' ({sum(unknown_raw_values.values())} righe totali, "
              f"{len(unknown_raw_values)} valori distinti — pattern non riconosciuti da fix_outcome, "
              f"non solo parole chiave mancanti ma anche punteggio perso a cascata):")
        for value, count in unknown_raw_values.most_common(20):
            print(f"  {count:6d}  {value!r}")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
