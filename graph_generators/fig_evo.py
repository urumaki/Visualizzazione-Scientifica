#!/usr/bin/env python3
"""
evo.png - Evoluzione mensile della quota dei 6 archetipi piu' giocati
(MTGGoldfish storico + melee.gg recenti, nomi riconciliati con gli alias).
Small multiples 2x3 con la stessa scala Y: area grigio chiaro, linea INK,
linee verticali tratteggiate sugli aggiornamenti della banlist.
I mazzi "Unknown" restano nel denominatore mensile.

INPUT: data/csv/csv/decks_audit.csv, decks.csv
"""
import math

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from viz_data import goldfish_decks, melee_decks, BAN_DATES, MELEE_ARCHETYPE_ALIASES, UNKNOWN_LABELS
from viz_style import INK, GRY, LG, MID, save

TOP_N = 6


def monthly_shares():
    gf = goldfish_decks()[["date", "archetype"]]
    ml = melee_decks()
    ml = pd.DataFrame({"date": ml["date"],
                       "archetype": ml["archetype"].fillna("").astype(str).str.strip().replace(MELEE_ARCHETYPE_ALIASES)})
    df = pd.concat([gf, ml.dropna(subset=["date"])], ignore_index=True)
    df.loc[df["archetype"].str.lower().isin(UNKNOWN_LABELS), "archetype"] = "Other"
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()
    top = df.loc[df["archetype"] != "Other", "archetype"].value_counts().nlargest(TOP_N).index.tolist()
    monthly = df.groupby(["month", "archetype"]).size().unstack(fill_value=0)
    pct = monthly.div(monthly.sum(axis=1), axis=0) * 100
    return pct[top], top


def main():
    pct, top = monthly_shares()
    ymax = math.ceil(pct.max().max() / 5) * 5

    fig, axes = plt.subplots(2, 3, figsize=(12.3, 5.0), sharex=True, sharey=True,
                             gridspec_kw=dict(hspace=.35, wspace=.08))
    for ax, name in zip(axes.flat, top):
        s = pct[name]
        for d in BAN_DATES:
            if s.index.min() <= d <= s.index.max():
                ax.axvline(d, color=GRY, lw=.9, ls=(0, (3, 3)), zorder=1)
        ax.fill_between(s.index, s.values, color=LG, lw=0, zorder=2)
        ax.plot(s.index, s.values, color=INK, lw=1.6, zorder=3)
        ax.text(.02, .97, name, transform=ax.transAxes, ha="left", va="top", fontsize=13,
                fontweight="bold", color=INK)
        ax.set_ylim(0, ymax)
        ax.set_xlim(s.index.min(), s.index.max())
        ax.grid(axis="y", color=LG, lw=.8)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=11)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for ax in axes[:, 0]:
        ax.set_ylabel("Quota (%)", fontsize=12, color=MID)
    save(fig, "evo.png")
    peaks = {n: (round(float(pct[n].max()), 1), f"{pct[n].idxmax():%Y-%m}") for n in top}
    return {"EVO_top": top, "EVO_peaks": peaks}


if __name__ == "__main__":
    print(main())
