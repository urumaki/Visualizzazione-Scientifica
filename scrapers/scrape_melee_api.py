#!/usr/bin/env python3
"""
Melee.gg - scraping diretto via API (POST /Decklist/SearchDecklists)

Non serve piu' Selenium/Playwright per questa parte: e' una chiamata DataTables
server-side che restituisce gia' JSON strutturato, inclusa la decklist completa
(maindeck + sideboard) dentro ogni riga -- quindi non serve nemmeno visitare le
pagine delle singole decklist.

COSA MANCA ANCORA: il record W-L-D (TeamMatchWins/Losses/Draws e' sempre null
su questo endpoint). Quello va preso da un endpoint diverso, specifico per
torneo (standings), e poi unito qui tramite TournamentId + nome giocatore.
Questo script fa solo la parte Decklists; l'unione con gli standings sara'
un secondo script separato.

SETUP:
    pip install requests

    1. Apri melee.gg, fai login, vai sulla pagina Decklists, applica il filtro
       che vuoi (game/format/date range/tournament type).
    2. F12 -> Network -> XHR -> trova la chiamata "SearchDecklists" -> tasto
       destro -> Copy -> Copy as cURL (bash).
    3. Apri quel cURL e copia SOLO il valore del cookie
       ".AspNet.ApplicationCookie" (una stringa lunga) e incollalo qui sotto
       in APPLICATION_COOKIE. Questo cookie scade periodicamente: se lo script
       inizia a fallire con errori di autenticazione/redirect, ripeti questo
       passaggio per prenderne uno fresco.

USO:
    python scrape_melee_api.py --out-decks decklists.csv --out-cards cards.csv \\
        --tournament-tag "Regional Championship [MTG]"
"""

import argparse
import csv
import json
import time
from pathlib import Path

import requests

# --- INCOLLA QUI il tuo cookie di sessione (solo il valore, senza "Cookie: ...") ---
APPLICATION_COOKIE = "INCOLLA_QUI_IL_TUO_COOKIE"
# ------------------------------------------------------------------------------------

SEARCH_URL = "https://melee.gg/Decklist/SearchDecklists"

BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:154.0) Gecko/20100101 Firefox/154.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
    "Origin": "https://melee.gg",
}

# Definizione colonne cosi' come le manda il sito (DataTables). Non toccare
# gli indici/nomi, sono quelli richiesti dal backend.
COLUMNS = [
    ("DecklistName", True, True),
    ("Game", True, True),
    ("FormatId", True, False),
    ("FormatName", True, True),
    ("OwnerDisplayName", True, True),
    ("TournamentName", True, True),
    ("SortDate", True, True),
    ("TeamRank", False, True),
    ("TeamMatchWins", False, False),
    ("OrganizationName", True, True),
    ("Records", True, False),
    ("Archetypes", True, False),
    ("TournamentTags", True, False),
    ("LeaderName", True, False),
    ("SecondaryName", True, False),
]


def build_payload(start: int, length: int, game: str, format_id: str,
                  date_range: str, tournament_tag: str) -> dict:
    payload = {
        "draw": "1",
        "order[0][column]": "6",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
    }
    for i, (name, searchable, orderable) in enumerate(COLUMNS):
        payload[f"columns[{i}][data]"] = name
        payload[f"columns[{i}][name]"] = name
        payload[f"columns[{i}][searchable]"] = str(searchable).lower()
        payload[f"columns[{i}][orderable]"] = str(orderable).lower()
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    payload["columns[1][search][value]"] = game
    payload["columns[2][search][value]"] = format_id
    payload["columns[6][search][value]"] = date_range
    payload["columns[12][search][value]"] = tournament_tag
    return payload


def fetch_page(session, start, length, game, format_id, date_range, tournament_tag):
    payload = build_payload(start, length, game, format_id, date_range, tournament_tag)
    resp = session.post(SEARCH_URL, data=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def flatten_deck_row(row: dict):
    attrs = {a["k"]: a["v"] for a in row.get("Attributes", []) if a.get("k") not in ("ARCHETYPE",)}
    archetype = next((a["v"] for a in row.get("Attributes", []) if a.get("k") == "ARCHETYPE"), "")
    tournament_type = ", ".join(
        a["v"] for a in row.get("Attributes", [])
        if a.get("k") == "TOURNAMENT" and a.get("v") not in (row.get("Game"), row.get("FormatName"))
    )
    return {
        "tournament_id": row.get("TournamentId"),
        "tournament_name": row.get("TournamentName"),
        "organization_name": row.get("OrganizationName"),
        "tournament_start_date": row.get("TournamentStartDate"),
        "sort_date": row.get("SortDate"),
        "format_name": row.get("FormatName"),
        "game": row.get("Game"),
        "owner_display_name": row.get("OwnerDisplayName"),
        "owner_username": row.get("OwnerUsername"),
        "decklist_name": row.get("DecklistName"),
        "archetype": archetype,
        "tournament_tags": tournament_type,
        "team_rank": row.get("TeamRank"),
        "team_match_wins": row.get("TeamMatchWins"),
        "team_match_losses": row.get("TeamMatchLosses"),
        "team_match_draws": row.get("TeamMatchDraws"),
        "tournament_status": row.get("TournamentStatusDescription"),
        "guid": row.get("Guid"),
        "is_public": row.get("IsPublic"),
    }


def flatten_cards(row: dict):
    guid = row.get("Guid")
    cards = []
    for card in row.get("Records", []):
        cards.append({
            "guid": guid,
            "tournament_id": row.get("TournamentId"),
            "card_name": card.get("n"),
            "quantity": card.get("q"),
            "section": "sideboard" if card.get("c") == 99 else "main",
            "card_type": card.get("t"),
        })
    return cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-decks", default="decklists.csv")
    parser.add_argument("--out-cards", default="cards.csv")
    parser.add_argument("--game", default="MagicTheGathering")
    parser.add_argument("--format-id", default="8a296155-bd05-4b76-b8fc-5f91a73da2a8", help="Modern")
    parser.add_argument("--date-range", default="2020-08-13|2026-08-29")
    parser.add_argument("--tournament-tag", default="Regional Championship [MTG]")
    parser.add_argument("--page-size", type=int, default=100, help="Righe per richiesta (DataTables 'length')")
    parser.add_argument("--delay", type=float, default=1.0, help="Pausa tra richieste (s)")
    parser.add_argument("--resume-start", type=int, default=0, help="Riparti da questo offset invece che 0")
    args = parser.parse_args()

    if APPLICATION_COOKIE == "INCOLLA_QUI_IL_TUO_COOKIE":
        raise SystemExit(
            "Devi prima incollare il tuo cookie di sessione nella variabile "
            "APPLICATION_COOKIE in cima al file. Vedi le istruzioni nel docstring."
        )

    session = requests.Session()
    session.headers.update(BASE_HEADERS)
    session.cookies.set(".AspNet.ApplicationCookie", APPLICATION_COOKIE, domain="melee.gg")

    decks_path = Path(args.out_decks)
    cards_path = Path(args.out_cards)
    write_decks_header = not decks_path.exists()
    write_cards_header = not cards_path.exists()

    deck_fields = list(flatten_deck_row({}).keys())
    card_fields = ["guid", "tournament_id", "card_name", "quantity", "section", "card_type"]

    f_decks = open(decks_path, "a", newline="", encoding="utf-8")
    f_cards = open(cards_path, "a", newline="", encoding="utf-8")
    w_decks = csv.DictWriter(f_decks, fieldnames=deck_fields)
    w_cards = csv.DictWriter(f_cards, fieldnames=card_fields)
    if write_decks_header:
        w_decks.writeheader()
    if write_cards_header:
        w_cards.writeheader()

    start = args.resume_start
    total_filtered = None
    total_written = 0

    try:
        while True:
            data = fetch_page(
                session, start, args.page_size,
                args.game, args.format_id, args.date_range, args.tournament_tag
            )
            if total_filtered is None:
                total_filtered = data.get("recordsFiltered", 0)
                print(f"Righe totali per questo filtro: {total_filtered}")

            rows = data.get("data", [])
            if not rows:
                print("Nessuna riga restituita, fine (o errore auth: controlla il cookie).")
                break

            for row in rows:
                w_decks.writerow(flatten_deck_row(row))
                for card in flatten_cards(row):
                    w_cards.writerow(card)
                total_written += 1

            f_decks.flush()
            f_cards.flush()

            print(f"[{start + len(rows)}/{total_filtered}] scritte {total_written} decklist finora. "
                  f"Per riprendere da qui: --resume-start {start + len(rows)}")

            start += len(rows)
            if start >= total_filtered:
                break

            time.sleep(args.delay)
    finally:
        f_decks.close()
        f_cards.close()
        print(f"Fatto. Decklist totali scritte: {total_written}. Output: {decks_path}, {cards_path}")


if __name__ == "__main__":
    main()