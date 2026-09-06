#!/usr/bin/env python3
"""
Melee.gg - Fase 2: standings (W-L-D) per ogni torneo gia' presente in decklists.csv

Per ogni tournament_id trovato in decklists.csv (prodotto da scrape_melee_api.py):
    1. Scarica la pagina HTML del torneo (melee.gg/Tournament/View/{id})
    2. Trova i bottoni round-selector, individua l'ULTIMO round Swiss
       (quello con "Round N" col numero piu' alto: le fasi ad eliminazione
       -- Quarti di finale/Semifinali/Finale o equivalenti -- sono escluse,
       cosi' il record riguarda TUTTI i giocatori del field, non solo chi
       ha superato il taglio)
    3. Chiama POST /Standing/GetRoundStandings con quel roundId
    4. Salva rank, match/game record, points, decklist_id per ogni giocatore

Il decklist_id salvato qui corrisponde al campo "guid" di decklists.csv:
puoi unire i due CSV su quella colonna.

SETUP: stesso cookie di scrape_melee_api.py (vedi APPLICATION_COOKIE sotto).

USO:
    python scrape_melee_standings.py --decks-csv decklists.csv --out standings.csv
"""

import argparse
import csv
import re
import time
from pathlib import Path

import requests

# --- INCOLLA QUI l'INTERA stringa Cookie (tutto quello che sta dopo "Cookie: " nel cURL) ---
FULL_COOKIE_HEADER = "INCOLLA_QUI_LA_STRINGA_COOKIE_COMPLETA"
# ---------------------------------------------------------------------------------------------

TOURNAMENT_URL = "https://melee.gg/Tournament/View/{tournament_id}"
STANDINGS_URL = "https://melee.gg/Standing/GetRoundStandings"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://melee.gg",
}

ROUND_BUTTON_RE = re.compile(
    r'<button[^>]*data-id="(\d+)"[^>]*data-name="([^"]+)"[^>]*>', re.IGNORECASE
)
SWISS_ROUND_RE = re.compile(r'^Round\s+(\d+)$', re.IGNORECASE)

STANDINGS_COLUMNS = [
    ("Rank", True, True),
    ("Player", False, False),
    ("Decklists", False, False),
    ("MatchRecord", False, False),
    ("GameRecord", False, False),
    ("Points", True, True),
    ("OpponentMatchWinPercentage", False, True),
    ("TeamGameWinPercentage", False, True),
    ("OpponentGameWinPercentage", False, True),
    ("FinalTiebreaker", False, True),
    ("OpponentCount", True, True),
]


def build_session():
    if FULL_COOKIE_HEADER == "INCOLLA_QUI_LA_STRINGA_COOKIE_COMPLETA":
        raise SystemExit(
            "Devi prima incollare l'intera stringa Cookie nella variabile "
            "FULL_COOKIE_HEADER in cima al file (tutto cio' che sta dopo 'Cookie: ' nel cURL)."
        )
    session = requests.Session()
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = FULL_COOKIE_HEADER
    session.headers.update(headers)
    return session


def find_last_swiss_round(session, tournament_id: int):
    resp = session.get(TOURNAMENT_URL.format(tournament_id=tournament_id), timeout=30)
    resp.raise_for_status()
    html = resp.text

    buttons = ROUND_BUTTON_RE.findall(html)  # [(id, name), ...]
    if not buttons:
        return None, None

    swiss_candidates = []
    for round_id, name in buttons:
        m = SWISS_ROUND_RE.match(name.strip())
        if m:
            swiss_candidates.append((int(m.group(1)), round_id, name))

    if swiss_candidates:
        swiss_candidates.sort(key=lambda x: x[0])
        _, round_id, name = swiss_candidates[-1]
        return round_id, name

    # Fallback: nessun round "Round N" trovato (evento solo a eliminazione?),
    # usa l'ultimo bottone disponibile e segnala.
    round_id, name = buttons[-1]
    print(f"  [!] Torneo {tournament_id}: nessun round 'Round N' trovato, uso fallback '{name}'.")
    return round_id, name


def build_standings_payload(round_id: str, start: int, length: int) -> dict:
    payload = {
        "draw": "1",
        "order[0][column]": "0",
        "order[0][dir]": "asc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "roundId": str(round_id),
    }
    for i, (name, searchable, orderable) in enumerate(STANDINGS_COLUMNS):
        payload[f"columns[{i}][data]"] = name
        payload[f"columns[{i}][name]"] = name
        payload[f"columns[{i}][searchable]"] = str(searchable).lower()
        payload[f"columns[{i}][orderable]"] = str(orderable).lower()
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"
    return payload


def fetch_all_standings(session, round_id: str, page_size: int = 200):
    all_rows = []
    start = 0
    while True:
        payload = build_standings_payload(round_id, start, page_size)
        resp = session.post(STANDINGS_URL, data=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        rows = data.get("data", [])
        all_rows.extend(rows)
        total = data.get("recordsFiltered", len(all_rows))
        start += len(rows)
        if not rows or start >= total:
            break
    return all_rows


def flatten_standing_row(row: dict, tournament_id, round_id, round_name):
    team = row.get("Team", {}) or {}
    players = team.get("Players") or [{}]
    decklists = team.get("Decklists") or [{}]

    base = {
        "tournament_id": tournament_id,
        "round_id": round_id,
        "round_name": round_name,
        "rank": row.get("Rank"),
        "points": row.get("Points"),
        "match_wins": row.get("MatchWins"),
        "match_losses": row.get("MatchLosses"),
        "match_draws": row.get("MatchDraws"),
        "match_record": row.get("MatchRecord"),
        "game_wins": row.get("GameWins"),
        "game_losses": row.get("GameLosses"),
        "game_draws": row.get("GameDraws"),
        "game_record": row.get("GameRecord"),
        "opponent_match_win_pct": row.get("OpponentMatchWinPercentage"),
        "team_game_win_pct": row.get("TeamGameWinPercentage"),
        "opponent_game_win_pct": row.get("OpponentGameWinPercentage"),
        "status": (team.get("StatusDescription") or ""),
    }

    out = []
    for i, player in enumerate(players):
        decklist = decklists[i] if i < len(decklists) else (decklists[0] if decklists else {})
        r = dict(base)
        r["player_display_name"] = player.get("DisplayName")
        r["player_username"] = player.get("Username")
        r["player_id"] = player.get("ID")
        r["decklist_id"] = decklist.get("DecklistId")
        r["decklist_name"] = decklist.get("DecklistName")
        out.append(r)
    return out


def get_processed_tournament_ids(out_path: Path) -> set:
    if not out_path.exists():
        return set()
    processed = set()
    with open(out_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed.add(row["tournament_id"])
    return processed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks-csv", default="decklists.csv")
    parser.add_argument("--out", default="standings.csv")
    parser.add_argument("--delay", type=float, default=1.5, help="Pausa tra tornei (s)")
    parser.add_argument("--max-tournaments", type=int, default=None, help="Per test")
    args = parser.parse_args()

    session = build_session()

    decks_path = Path(args.decks_csv)
    if not decks_path.exists():
        raise SystemExit(f"Non trovo {decks_path}. Esegui prima scrape_melee_api.py.")

    tournament_ids = []
    seen = set()
    with open(decks_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row.get("tournament_id")
            if tid and tid not in seen:
                seen.add(tid)
                tournament_ids.append(tid)

    print(f"Tornei distinti trovati in {decks_path}: {len(tournament_ids)}")

    out_path = Path(args.out)
    already_done = get_processed_tournament_ids(out_path)
    if already_done:
        print(f"Gia' processati in precedenza (skip): {len(already_done)}")

    write_header = not out_path.exists()
    fieldnames = [
        "tournament_id", "round_id", "round_name", "rank", "points",
        "match_wins", "match_losses", "match_draws", "match_record",
        "game_wins", "game_losses", "game_draws", "game_record",
        "opponent_match_win_pct", "team_game_win_pct", "opponent_game_win_pct",
        "status", "player_display_name", "player_username", "player_id",
        "decklist_id", "decklist_name",
    ]
    f_out = open(out_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    done_count = 0
    try:
        for tid in tournament_ids:
            if tid in already_done:
                continue
            if args.max_tournaments and done_count >= args.max_tournaments:
                print("Raggiunto --max-tournaments, stop (modalita' test).")
                break

            print(f"Torneo {tid}: cerco ultimo round Swiss...")
            round_id, round_name = find_last_swiss_round(session, tid)
            if round_id is None:
                print(f"  [!] Torneo {tid}: nessun round trovato (pagina vuota/errore?), skip.")
                continue

            print(f"  -> {round_name} (roundId {round_id}), scarico standings...")
            rows = fetch_all_standings(session, round_id)
            print(f"  -> {len(rows)} righe standings.")

            for row in rows:
                for flat in flatten_standing_row(row, tid, round_id, round_name):
                    writer.writerow(flat)
            f_out.flush()

            done_count += 1
            time.sleep(args.delay)
    finally:
        f_out.close()
        print(f"Fatto. Tornei processati in questa run: {done_count}. Output: {out_path}")


if __name__ == "__main__":
    main()
