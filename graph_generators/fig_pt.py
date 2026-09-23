#!/usr/bin/env python3
"""
pt.png - Winrate nei Regional Championship (melee.gg, questo dataset) contro
il Pro Tour MSH per gli archetipi presenti in entrambi, con IC 95% di Wilson.
I dati del Pro Tour sono esterni (Frank Karsten) e stanno in
data/pro_tour_msh.csv.

INPUT: data/csv/csv/matches_fixed.csv, data/pro_tour_msh.csv
"""
import matplotlib.pyplot as plt
import pandas as pd

from fig_forest import aggregate
from viz_data import DATA_DIR
from viz_style import INK, NEG, LG, MID, wilson, save


def main():
    agg = {n: (w, l) for n, w, l, d in aggregate(min_games=1)}
    pt = pd.read_csv(DATA_DIR / "pro_tour_msh.csv")
    pt = {r.archetype: (int(r.wins), int(r.losses)) for r in pt.itertuples() if r.archetype in agg}
    keys = sorted(pt, key=lambda k: agg[k][0] / sum(agg[k]))

    fig, ax = plt.subplots(figsize=(8.2, 5.4))
    ax.axvline(50, color=INK, lw=1, ls=(0, (3, 3)))
    delta = {}
    for i, k in enumerate(keys):
        p1, l1, u1 = wilson(agg[k][0], sum(agg[k]))
        p2, l2, u2 = wilson(pt[k][0], sum(pt[k]))
        y1, y2 = i + .14, i - .14
        ax.plot([l1 * 100, u1 * 100], [y1, y1], color=INK, lw=2.4)
        ax.scatter(p1 * 100, y1, color=INK, s=40, zorder=3)
        ax.plot([l2 * 100, u2 * 100], [y2, y2], color=NEG, lw=2.4)
        ax.scatter(p2 * 100, y2, color=NEG, s=40, zorder=3)
        dd = (p2 - p1) * 100
        delta[k] = (round(p1 * 100, 1), round(p2 * 100, 1), round(dd, 1))
        ax.text(70.5, i, f"{dd:+.1f}", ha="right", va="center", fontsize=12,
                color=NEG if dd < -5 else MID, fontweight="bold" if abs(dd) > 5 else "normal")
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys, fontsize=12.5)
    worst = min(delta, key=lambda k: delta[k][2])
    ax.get_yticklabels()[keys.index(worst)].set_fontweight("bold")
    ax.set_xlim(36, 71)
    ax.set_xticks([40, 45, 50, 55, 60, 65])
    ax.set_xlabel("Winrate (%)  ·  IC 95% di Wilson", fontsize=12)
    ax.text(70.5, len(keys) - .35, "Δ PT−RC", ha="right", fontsize=11, color=MID, fontweight="bold")
    ax.plot([], [], color=INK, lw=2.4, marker="o", label="Regional Championship (questo dataset)")
    ax.plot([], [], color=NEG, lw=2.4, marker="o", label="Pro Tour MSH (dati F. Karsten)")
    ax.legend(loc="lower left", frameon=False, fontsize=11, bbox_to_anchor=(0, -.3), ncol=2)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LG)
    ax.set_axisbelow(True)
    save(fig, "pt.png")
    return {"PT_delta": delta}


if __name__ == "__main__":
    print(main())
