#!/usr/bin/env python3
"""
Grafico - Carte piu' giocate, main deck e sideboard (fonte: MTGGoldfish +
Melee.gg).

Per ogni carta calcola la quota di mazzi che la include (non la somma delle
copie: una carta giocata 4x conta come 1 mazzo, non 4, altrimenti i 4-of
schiaccerebbero il grafico senza dire nulla sulla diffusione reale). Tutte
le terre (basi, fetchland, shockland, dual land, utility land, ...) sono
escluse di default: la lista dei nomi-terra viene derivata da cards.csv
(Melee.gg), l'unica delle due fonti che porta anche il campo card_type.

Produce due grafici a barre orizzontali separati: uno per il main deck, uno
per il sideboard.

INPUT:
    cards_audit.csv (MTGGoldfish) - colonne: file, section, card_name
    cards.csv       (Melee.gg)    - colonne: guid, section, card_name

USO:
    python viz_top_cards.py --goldfish-cards cards_audit.csv --melee-cards cards.csv \\
        --top-n 20 --out-main top_cards_main.png --out-side top_cards_sideboard.png
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, color_for_rank

BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def load_cards(path: str, deck_col: str, source_label: str) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=[deck_col, "section", "card_name"], low_memory=False)
    df = df.rename(columns={deck_col: "deck_id"})
    df["deck_id"] = source_label + ":" + df["deck_id"].astype(str)
    df["source"] = source_label
    return df


def load_land_names(melee_cards_path: str) -> set:
    """Deriva l'elenco completo delle terre (basi + fetch/shock/dual/utility)
    dal campo card_type di cards.csv (Melee.gg), assente in cards_audit.csv."""
    if not Path(melee_cards_path).exists():
        return set(BASIC_LANDS)
    df = pd.read_csv(melee_cards_path, usecols=["card_name", "card_type"], low_memory=False)
    names = set(df.loc[df["card_type"] == "Land", "card_name"].astype(str).str.strip())
    return names | BASIC_LANDS


def plot_top_cards(df: pd.DataFrame, section: str, total_decks: int, top_n: int, title: str, out_path: str):
    section_df = df[df["section"] == section]
    inclusion = section_df.drop_duplicates(["deck_id", "card_name"])
    counts = inclusion["card_name"].value_counts().nlargest(top_n)
    pct = (counts / total_decks * 100).sort_values(ascending=True)

    fig, ax = plt.subplots(figsize=(9, 0.4 * top_n + 2))
    ax.barh(pct.index, pct.values, color=[color_for_rank(i) for i in range(len(pct))])
    for y, (name, value) in enumerate(pct.items()):
        ax.text(value + 0.5, y, f"{value:.1f}%", va="center", fontsize=8, color="#333333")

    ax.set_xlabel("Quota mazzi che la includono (%)")
    ax.set_xlim(0, max(pct.values) * 1.15)
    ax.set_title(title, pad=15)
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    print(f"Salvato: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldfish-cards", default="cards_audit.csv")
    parser.add_argument("--melee-cards", default="cards.csv")
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--out-main", default="top_cards_main.png")
    parser.add_argument("--out-side", default="top_cards_sideboard.png")
    parser.add_argument("--include-lands", action="store_true",
                         help="Include le terre (escluse di default, poco informative)")
    args = parser.parse_args()

    setup_style()

    frames = [load_cards(args.goldfish_cards, "file", "MTGGoldfish")]
    if Path(args.melee_cards).exists():
        frames.append(load_cards(args.melee_cards, "guid", "Melee.gg"))
    else:
        print(f"[!] {args.melee_cards} non trovato, uso solo dati MTGGoldfish.")

    df = pd.concat(frames, ignore_index=True)
    df["card_name"] = df["card_name"].astype(str).str.strip()

    if not args.include_lands:
        land_names = load_land_names(args.melee_cards)
        print(f"Terre escluse dal conteggio: {len(land_names)} nomi")
        df = df[~df["card_name"].isin(land_names)]

    total_decks = df["deck_id"].nunique()
    print(f"Mazzi totali (goldfish + melee): {total_decks}")

    plot_top_cards(
        df, "main", total_decks, args.top_n,
        f"Top {args.top_n} carte piu' giocate — Main deck (fonte: MTGGoldfish + Melee.gg)",
        args.out_main,
    )
    plot_top_cards(
        df, "sideboard", total_decks, args.top_n,
        f"Top {args.top_n} carte piu' giocate — Sideboard (fonte: MTGGoldfish + Melee.gg)",
        args.out_side,
    )


if __name__ == "__main__":
    main()
