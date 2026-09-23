#!/usr/bin/env python3
"""
top3.png - Piazzamenti in top 3 nei tornei MTGO per archetipo ed era di
banlist (Ere 4-10), divisi per la durata dell'era in mesi: le ere durano da
3 a 14 mesi, i conteggi grezzi non sono confrontabili.
Heatmap sequenziale; riquadro arancione sul massimo di ogni colonna.
Archetipi mostrati: gli 8 con piu' piazzamenti in top 3 sulle Ere 4-10.

INPUT: data/csv/csv/decks_audit.csv (source == "MTGO", rank_order)
"""
import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap

from viz_data import goldfish_decks, goldfish_end, months_between
from viz_style import INK, POS, NEG, save

ERA_START_DATES = ["2022-10-10", "2023-08-07", "2023-12-04", "2024-03-11", "2024-12-16", "2025-03-31", "2026-05-18"]
FIRST_ERA = 4
TOP_N = 8
MAX_RANK = 3


def counts():
    g = goldfish_decks()
    g = g[(g["source"] == "MTGO") & ~g["unknown"]]
    end = goldfish_end()
    bounds = [np.datetime64(d) for d in ERA_START_DATES] + [np.datetime64(end + np.timedelta64(1, "D"))]
    g = g[(g["date"] >= bounds[0]) & (g["date"] < bounds[-1])].copy()
    g["era"] = np.searchsorted(np.array(bounds[1:-1], dtype="datetime64[ns]"), g["date"].values, side="right")
    top3 = g[g["rank_order"] <= MAX_RANK]
    table = top3.groupby(["archetype", "era"]).size().unstack(fill_value=0).reindex(columns=range(len(ERA_START_DATES)), fill_value=0)
    names = table.sum(axis=1).nlargest(TOP_N).index.tolist()
    tournaments = g.groupby("era")["tournament"].nunique().reindex(range(len(ERA_START_DATES)), fill_value=0)
    return table.loc[names], end, tournaments


def main():
    table, end, tournaments = counts()
    dates = ERA_START_DATES + [f"{end:%Y-%m-%d}"]
    months = np.array([months_between(dates[i], dates[i + 1]) for i in range(len(ERA_START_DATES))])
    names = table.index.tolist()
    M = table.values / months
    eras = [f"Era {FIRST_ERA + i}" for i in range(len(ERA_START_DATES))]

    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    cmap = LinearSegmentedColormap.from_list("s", ["#F4F5F7", "#9FD8CF", POS, "#0E4F48"])
    vmax = max(33, math.ceil(M.max()))
    ax.imshow(M, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    for i in range(M.shape[0]):
        for jj in range(M.shape[1]):
            v = M[i, jj]
            ax.text(jj, i, "–" if v == 0 else f"{v:.1f}", ha="center", va="center", fontsize=12.5,
                    color="white" if v > vmax * 17 / 33 else INK)
    lab = [f"{e}\n{x[5:7]}/{x[2:4]}–{y[5:7]}/{y[2:4]}\n{mm:.0f} mesi"
           for e, x, y, mm in zip(eras, dates[:-1], dates[1:], months)]
    ax.set_xticks(range(len(eras)))
    ax.set_xticklabels(lab, fontsize=10.5)
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=12.5)
    ax.set_xticks(np.arange(-.5, len(eras)), minor=True)
    ax.set_yticks(np.arange(-.5, len(names)), minor=True)
    ax.grid(which="minor", color="white", lw=2.5)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    for jj in range(len(eras)):
        i = M[:, jj].argmax()
        ax.add_patch(plt.Rectangle((jj - .5, i - .5), 1, 1, fill=False, edgecolor=NEG, lw=3, zorder=5))
    save(fig, "top3.png")

    return {
        "TOP3": {n: table.loc[n].astype(int).tolist() for n in names},
        "per_month": {n: [round(v, 1) for v in M[i]] for i, n in enumerate(names)},
        "leader": [names[M[:, j].argmax()] for j in range(len(eras))],
        "months": [round(x, 1) for x in months],
        "tournaments": tournaments.astype(int).tolist(),
    }


if __name__ == "__main__":
    print(main())
