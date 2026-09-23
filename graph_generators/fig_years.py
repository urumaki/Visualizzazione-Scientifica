#!/usr/bin/env python3
"""
years.png - Numero di decklist MTGGoldfish per anno (migliaia). L'ultimo anno
e' parziale e porta l'asterisco (spiegato nella nota della slide).

INPUT: data/csv/csv/decks_audit.csv
"""
import matplotlib.pyplot as plt

from viz_data import goldfish_decks
from viz_style import GRY, LG, MID, save


def main():
    g = goldfish_decks()
    by_year = g["date"].dt.year.value_counts().sort_index()
    years = by_year.index.astype(int).tolist()
    vals = (by_year / 1000).round(1).tolist()
    labels = [str(y) for y in years]
    labels[-1] += "*"

    fig, ax = plt.subplots(figsize=(6.3, 3.4))
    ax.bar(range(len(vals)), vals, color=GRY, width=.68)
    for i, v in enumerate(vals):
        ax.text(i, v + max(vals) * .02, f"{v:.1f}", ha="center", va="bottom",
                fontsize=12, color=MID)
    ax.set_xticks(range(len(vals)))
    ax.set_xticklabels(labels, fontsize=12)
    ax.set_ylim(0, max(vals) * 1.15)
    ax.set_ylabel("Decklist (migliaia)", fontsize=12)
    ax.tick_params(axis="y", labelsize=11)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=LG, lw=.8)
    ax.set_axisbelow(True)
    save(fig, "years.png")

    src = g["source"].value_counts(normalize=True) * 100
    return {"YEARS": dict(zip(years, vals)), "decklists": dict(zip(years, by_year.astype(int).tolist())),
            "source_pct": {k: round(v) for k, v in src.items()}, "goldfish_decks": int(len(g))}


if __name__ == "__main__":
    print(main())
