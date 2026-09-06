#!/usr/bin/env python3
"""
Melee.gg - Fase 3: storico match per giocatore (GET /Player/GetPlayerDetails?id=...)

Una sola chiamata per giocatore restituisce TUTTI i suoi match (round Swiss +
eventuali playoff) con: round, decklist/archetipo avversario, nome avversario,
risultato. Non serve piu' GetRoundMatches (una chiamata per round) ne'
indovinare il formato di ResultString: qui e' gia' pulito.

La risposta non include il tournament_id esplicito per ogni match, quindi lo
deriviamo incrociando "opponentDecklistId" con decklists.csv (guid -> tournament_id).
Questo scarta automaticamente eventuali match fuori dal dataset filtrato
(es. tornei non-Regional-Championship se il giocatore ne ha giocati altri).

INPUT NECESSARI (gia' prodotti dagli script precedenti):
    - decklists.csv  (da scrape_melee_api.py)      -> serve "guid","tournament_id"
    - standings.csv  (da scrape_melee_standings.py) -> serve "player_id","decklist_id","decklist_name","tournament_id"

USO:
    python scrape_melee_player_matches.py --decks-csv decklists.csv \\
        --standings-csv standings.csv --out matches.csv
"""

import argparse
import csv
import re
import time
from pathlib import Path

import requests

# --- INCOLLA QUI l'INTERA stringa Cookie (stessa degli altri script) ---
FULL_COOKIE_HEADER = "INCOLLA_QUI_LA_STRINGA_COOKIE_COMPLETA"
# -------------------------------------------------------------------------

PLAYER_DETAILS_URL = "https://melee.gg/Player/GetPlayerDetails"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "*/*",
    "X-Requested-With": "XMLHttpRequest",
}

RESULT_RE = re.compile(r"(\d+)-(\d+)-(\d+)")


def build_session():
    if FULL_COOKIE_HEADER == "INCOLLA_QUI_LA_STRINGA_COOKIE_COMPLETA":
        raise SystemExit(
            "Devi prima incollare l'intera stringa Cookie nella variabile "
            "FULL_COOKIE_HEADER in cima al file."
        )
    session = requests.Session()
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = FULL_COOKIE_HEADER
    session.headers.update(headers)
    return session


def load_guid_to_tournament(decks_csv: Path) -> dict:
    mapping = {}
    with open(decks_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            guid = row.get("guid")
            if guid:
                mapping[guid] = row.get("tournament_id")
    return mapping


def load_standings_lookup(standings_csv: Path):
    """Ritorna: dict (tournament_id, player_id) -> (decklist_id, decklist_name),
    e la lista di player_id unici da interrogare."""
    lookup = {}
    player_ids = []
    seen_players = set()
    with open(standings_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row.get("tournament_id")
            pid = row.get("player_id")
            if not tid or not pid:
                continue
            lookup[(tid, pid)] = (row.get("decklist_id"), row.get("decklist_name"))
            if pid not in seen_players:
                seen_players.add(pid)
                player_ids.append(pid)
    return lookup, player_ids


def parse_outcome(short_result: str):
    if not short_result:
        return "unknown", None, None, None
    text = short_result.strip().lower()
    m = RESULT_RE.search(short_result)
    wins = losses = draws = None
    if m:
        wins, losses, draws = m.group(1), m.group(2), m.group(3)
    if text.startswith("vittoria"):
        outcome = "win"
    elif text.startswith("pareggio") or text.startswith("draw"):
        outcome = "draw"
    elif text.startswith("sconfitta") or text.startswith("loss") or text.startswith("defeat"):
        outcome = "loss"
    else:
        outcome = "unknown"
    return outcome, wins, losses, draws


def fetch_player_details(session, player_id: str):
    resp = session.get(PLAYER_DETAILS_URL, params={"id": player_id}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def get_processed_player_ids(out_path: Path) -> set:
    if not out_path.exists():
        return set()
    done = set()
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            done.add(row["player_id"])
    return done


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks-csv", default="decklists.csv")
    parser.add_argument("--standings-csv", default="standings.csv")
    parser.add_argument("--out", default="matches.csv")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-players", type=int, default=None, help="Per test")
    args = parser.parse_args()

    session = build_session()

    guid_to_tournament = load_guid_to_tournament(Path(args.decks_csv))
    standings_lookup, player_ids = load_standings_lookup(Path(args.standings_csv))
    print(f"Giocatori distinti da processare: {len(player_ids)}")

    out_path = Path(args.out)
    already_done = get_processed_player_ids(out_path)
    if already_done:
        print(f"Gia' processati (skip): {len(already_done)}")

    fieldnames = [
        "tournament_id", "round_name",
        "player_id", "player_decklist_id", "player_decklist_name",
        "opponent_player_id", "opponent_username",
        "opponent_decklist_id", "opponent_decklist_name",
        "outcome", "game_wins", "game_losses", "game_draws",
        "raw_result", "raw_short_result",
    ]
    write_header = not out_path.exists()
    f_out = open(out_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    done_count = 0
    skipped_matches_out_of_scope = 0
    try:
        for pid in player_ids:
            if pid in already_done:
                continue
            if args.max_players and done_count >= args.max_players:
                print("Raggiunto --max-players, stop (modalita' test).")
                break

            try:
                data = fetch_player_details(session, pid)
            except Exception as e:
                print(f"  [!] player_id {pid}: errore richiesta ({e}), skip.")
                continue

            matches = data.get("matches", []) or []
            written_for_player = 0
            for m in matches:
                opp_decklist_id = m.get("opponentDecklistId")
                tournament_id = guid_to_tournament.get(opp_decklist_id)
                if tournament_id is None:
                    # Match fuori dal nostro dataset filtrato (torneo non scrapato)
                    skipped_matches_out_of_scope += 1
                    continue

                own_decklist_id, own_decklist_name = standings_lookup.get(
                    (tournament_id, pid), (None, None)
                )
                outcome, w, l, d = parse_outcome(m.get("shortResult"))

                writer.writerow({
                    "tournament_id": tournament_id,
                    "round_name": m.get("roundName"),
                    "player_id": pid,
                    "player_decklist_id": own_decklist_id,
                    "player_decklist_name": own_decklist_name,
                    "opponent_player_id": m.get("opponentPlayerId"),
                    "opponent_username": m.get("opponentUsername"),
                    "opponent_decklist_id": opp_decklist_id,
                    "opponent_decklist_name": m.get("opponentDecklistName"),
                    "outcome": outcome,
                    "game_wins": w,
                    "game_losses": l,
                    "game_draws": d,
                    "raw_result": m.get("result"),
                    "raw_short_result": m.get("shortResult"),
                })
                written_for_player += 1

            f_out.flush()
            done_count += 1
            if done_count % 20 == 0:
                print(f"[checkpoint] {done_count}/{len(player_ids)} giocatori processati, "
                      f"match fuori scope finora: {skipped_matches_out_of_scope}")

            time.sleep(args.delay)
    finally:
        f_out.close()
        print(f"Fatto. Giocatori processati in questa run: {done_count}. "
              f"Match scartati (torneo fuori dataset): {skipped_matches_out_of_scope}. "
              f"Output: {out_path}")


if __name__ == "__main__":
    main()
