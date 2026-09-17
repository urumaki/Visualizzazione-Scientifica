#!/usr/bin/env python3
"""
outburst.png - Decklist melee.gg con Violent Outburst nel main deck dopo
l'unban del 18.05.26, per archetipo (campo "archetype" di melee.gg).
Living End, il principale adottante, in evidenza. Le decklist senza
archetipo non compaiono come barra ma restano nel totale citato nel testo
della slide ("22 su 37").

INPUT: data/csv/csv/cards.csv, decks.csv
"""
import matplotlib.pyplot as plt
import pandas as pd

from viz_data import CSV_DIR, ERA10_START, melee_decks
from viz_style import INK, GRY, LG, MID, save

CARD = "Violent Outburst"
HIGHLIGHT = "Living End"


def adoption():
    decks = melee_decks()
    decks = decks[decks["date"] >= ERA10_START]
    cards = pd.read_csv(CSV_DIR / "cards.csv", usecols=["guid", "tournament_id", "card_name", "section"],
                        low_memory=False)
    cards["tournament_id"] = cards["tournament_id"].astype(str)
    vo = cards[(cards["card_name"] == CARD) & (cards["section"] == "main")].drop_duplicates(["tournament_id", "guid"])
    vo = vo.merge(decks[["tournament_id", "guid", "archetype"]], on=["tournament_id", "guid"], how="inner")
    counts = vo["archetype"].dropna().value_counts()
    counts = counts.loc[sorted(counts.index, key=lambda a: (counts[a], a))]
    return counts, int(vo["guid"].nunique())


def main():
    counts, total = adoption()
    names, vals = counts.index.tolist(), counts.values.tolist()

    fig, ax = plt.subplots(figsize=(5.4, 4.3))
    cols = [INK if n == HIGHLIGHT else GRY for n in names]
    ax.barh(range(len(vals)), vals, color=cols, height=.66)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * .015, i, f"{v}", va="center", fontsize=12.5, color=MID)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=13)
    for t in ax.get_yticklabels():
        if t.get_text() == HIGHLIGHT:
            t.set_fontweight("bold")
    ax.set_xlim(0, max(vals) * 1.12)
    ax.set_xlabel("Decklist con Violent Outburst (dal 18.05.26)", fontsize=12)
    ax.tick_params(axis="x", labelsize=11)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LG, lw=.8)
    ax.set_axisbelow(True)
    save(fig, "outburst.png")
    return {"VO": counts.to_dict(), "VO_total": total}


if __name__ == "__main__":
    print(main())
