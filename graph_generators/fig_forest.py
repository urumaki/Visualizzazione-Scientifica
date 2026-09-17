#!/usr/bin/env python3
"""
forest.png - Winrate aggregato melee.gg per archetipo (>= 300 partite decise,
pareggi esclusi), con IC 95% di Wilson.
Verde = IC interamente sopra il 50%, arancione = sotto, grigio = include il 50%.
Dimensione del punto proporzionale alle partite.

INPUT: data/csv/csv/matches_fixed.csv (+ decks.csv per le date)
"""
import matplotlib.pyplot as plt

from viz_data import melee_matches, decided, record
from viz_style import INK, POS, NEG, GRY, LG, MID, wilson, save

MIN_GAMES = 300


def aggregate(min_games=MIN_GAMES):
    """[(archetipo, wins, losses, draws)] per archetipi con W+L >= min_games."""
    m = melee_matches()
    m = m[m["outcome"].isin(["win", "loss", "draw"])]
    rows = []
    for name, sub in m.groupby("player"):
        w, l, d = record(sub)
        if w + l >= min_games:
            rows.append((name, w, l, d))
    return rows


def main():
    agg = aggregate()
    rows = [(n,) + wilson(w, w + l) + (w + l,) for n, w, l, d in agg]
    rows.sort(key=lambda r: r[1])

    fig, ax = plt.subplots(figsize=(8.2, 5.9))
    ax.axvline(50, color=INK, lw=1, ls=(0, (3, 3)), zorder=0)
    for i, (n, p, lo, hi, N) in enumerate(rows):
        c = POS if lo > .5 else NEG if hi < .5 else GRY
        ax.plot([lo * 100, hi * 100], [i, i], color=c, lw=2.2, solid_capstyle="round")
        ax.scatter(p * 100, i, s=18 + N / 18, color=c, zorder=3, edgecolor="white", lw=.8)
        ax.text(65.3, i, f"{p * 100:.1f}%", va="center", ha="right", fontsize=11.5,
                color=c if c != GRY else MID, fontweight="bold" if c != GRY else "normal")
        ax.text(69.6, i, f"{N:,}".replace(",", "."), va="center", ha="right", fontsize=11, color=MID)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=12)
    for t, r in zip(ax.get_yticklabels(), rows):
        if r[2] > .5 or r[3] < .5:
            t.set_fontweight("bold")
    ax.set_xlim(40, 70)
    ax.set_ylim(-.7, len(rows) - .3)
    ax.set_xticks([40, 45, 50, 55, 60])
    ax.set_xlabel("Winrate (%)  ·  IC 95% di Wilson", fontsize=12)
    ax.text(65.3, len(rows) - .2, "WR", ha="right", fontsize=11, color=MID, fontweight="bold")
    ax.text(69.6, len(rows) - .2, "partite", ha="right", fontsize=11, color=MID, fontweight="bold")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LG, lw=.8)
    ax.set_axisbelow(True)
    save(fig, "forest.png")

    above = [r for r in rows if r[2] > .5]
    below = [r for r in rows if r[3] < .5]
    return {
        "AGG": {n: (w, l, d) for n, w, l, d in agg},
        "above": sorted([(r[0], round(r[1] * 100, 1)) for r in above], key=lambda x: -x[1]),
        "below": sorted([(r[0], round(r[1] * 100, 1), r[4]) for r in below], key=lambda x: x[1]),
    }


if __name__ == "__main__":
    print(main())
