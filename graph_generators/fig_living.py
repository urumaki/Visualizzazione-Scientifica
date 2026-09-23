#!/usr/bin/env python3
"""
living.png - Winrate di Living End (tutte le varianti colore) su melee.gg,
Era 9 vs Era 10, con IC 95% di Wilson. Pareggi esclusi.

INPUT: data/csv/csv/matches_fixed.csv, decks.csv
"""
import matplotlib.pyplot as plt

from viz_data import melee_matches, decided, ERA9_START, ERA10_START
from viz_style import INK, NEG, GRY, LG, wilson, save


def records():
    m = decided(melee_matches())
    le = m[m["player_decklist_name"].str.contains("Living End", case=False, na=False)]
    eras = (("Era 9", le[(le["date"] >= ERA9_START) & (le["date"] < ERA10_START)]),
            ("Era 10", le[le["date"] >= ERA10_START]))
    return [(label, int((sub["outcome"] == "win").sum()), len(sub)) for label, sub in eras]


def main():
    vals = records()
    fig, ax = plt.subplots(figsize=(3.5, 4.5))
    ax.axhline(50, color=INK, lw=1, ls=(0, (3, 3)))
    cis = []
    for i, (lab, w, n) in enumerate(vals):
        pp, lo, hi = wilson(w, n)
        cis.append((lo, hi))
        c = GRY if i == 0 else NEG
        ax.plot([i, i], [lo * 100, hi * 100], color=c, lw=3, solid_capstyle="round")
        ax.scatter(i, pp * 100, s=90, color=c, zorder=3)
        ax.text(i + .14, pp * 100, f"{pp * 100:.1f}%\nn={n}", va="center", fontsize=13, color=INK,
                bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.set_xticks([0, 1])
    ax.set_xticklabels([v[0] for v in vals], fontsize=13)
    ax.set_xlim(-.3, 1.75)
    ax.set_ylim(30, 70)
    ax.set_ylabel("Winrate Living End (%)", fontsize=12)
    ax.grid(axis="y", color=LG)
    ax.set_axisbelow(True)
    save(fig, "living.png")
    res = {lab: (w, n, round(w / n * 100, 1) if n else None) for lab, w, n in vals}
    res["ci_overlap"] = bool(cis[1][0] <= cis[0][1] and cis[0][0] <= cis[1][1])
    return {"LIVING": res}


if __name__ == "__main__":
    print(main())
