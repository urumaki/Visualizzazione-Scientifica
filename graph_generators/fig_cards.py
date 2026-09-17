#!/usr/bin/env python3
"""
cards.png - Top 20 carte del main deck e del sideboard (MTGGoldfish +
melee.gg): quota di mazzi che includono la carta, non numero di copie.
Terre escluse (nomi derivati da card_type == "Land" in cards.csv, piu' le
base). Carte bannate durante il periodo dei dati in arancione.

INPUT: data/csv/csv/cards_audit.csv (MTGGoldfish), cards.csv (melee.gg)
"""
import math

import matplotlib.pyplot as plt
import pandas as pd

from viz_data import CSV_DIR, BANNED_CARDS
from viz_style import INK, NEG, GRY, LG, MID, save

TOP_N = 20
BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest", "Wastes"}


def _read(name, cols):
    try:
        return pd.read_csv(CSV_DIR / name, usecols=cols, engine="pyarrow")
    except (ImportError, ValueError):
        return pd.read_csv(CSV_DIR / name, usecols=cols, low_memory=False)


def load():
    gf = _read("cards_audit.csv", ["file", "section", "card_name"]).rename(columns={"file": "deck_id"})
    gf["deck_id"] = "gf:" + gf["deck_id"].astype(str)
    ml = _read("cards.csv", ["guid", "section", "card_name", "card_type"])
    lands = set(ml.loc[ml["card_type"] == "Land", "card_name"].astype(str).str.strip()) | BASIC_LANDS
    ml = ml.drop(columns="card_type").rename(columns={"guid": "deck_id"})
    ml["deck_id"] = "ml:" + ml["deck_id"].astype(str)
    df = pd.concat([gf, ml], ignore_index=True)
    df["card_name"] = df["card_name"].astype(str).str.strip()
    df = df[~df["card_name"].isin(lands)]
    return df


def top_cards(df, section, total):
    inc = df[df["section"] == section].drop_duplicates(["deck_id", "card_name"])
    counts = inc["card_name"].value_counts().nlargest(TOP_N)
    return [(n, round(c / total * 100, 1)) for n, c in counts.items()]


def main():
    df = load()
    total = df["deck_id"].nunique()
    main_cards = top_cards(df, "main", total)
    side_cards = top_cards(df, "sideboard", total)
    xmax = max(31, math.ceil(max(v for _, v in main_cards + side_cards)) + 3)

    fig, axs = plt.subplots(1, 2, figsize=(12.3, 5.1), gridspec_kw=dict(wspace=.55))
    for ax, data, t in ((axs[0], main_cards, "Main deck (top 20)"), (axs[1], side_cards, "Sideboard (top 20)")):
        names = [d[0] for d in data][::-1]
        vals = [d[1] for d in data][::-1]
        cols = [NEG if n in BANNED_CARDS else (INK if v >= 20 else GRY) for n, v in zip(names, vals)]
        ax.barh(range(len(names)), vals, color=cols, height=.72)
        for i, v in enumerate(vals):
            ax.text(v + .4, i, f"{v:.1f}", va="center", fontsize=10.5, color=MID)
        ax.set_yticks(range(len(names)))
        ax.set_yticklabels(names, fontsize=11)
        for tl in ax.get_yticklabels():
            if tl.get_text() in BANNED_CARDS:
                tl.set_color(NEG)
                tl.set_fontweight("bold")
        ax.set_xlim(0, xmax)
        ax.set_title(t, loc="left", fontsize=14, color=INK)
        ax.spines["left"].set_visible(False)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("% di mazzi che includono la carta", fontsize=11)
        ax.axvline(25, color=LG, lw=1, zorder=0)
    save(fig, "cards.png")
    return {
        "total_decks": int(total), "MAIN": main_cards, "SIDE": side_cards,
        "banned_in_top20": sorted({n for n, _ in main_cards + side_cards} & BANNED_CARDS),
    }


if __name__ == "__main__":
    print(main())
