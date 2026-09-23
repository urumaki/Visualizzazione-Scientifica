#!/usr/bin/env python3
"""
pop.png - Quota delle decklist MTGGoldfish vs melee.gg nella stessa finestra
(dalla prima all'ultima data melee.gg). Dumbbell per gli archetipi presenti
nella top 15 di entrambe le fonti. Mazzi "Unknown"/vuoti esclusi dalla
classifica ma inclusi nel denominatore.
I nomi che differiscono tra le fonti sono riconciliati con la mappa esplicita
data/archetype_name_map.csv (colonne goldfish, melee, label).

INPUT: data/csv/csv/decks_audit.csv, decks.csv, data/archetype_name_map.csv
"""
import math

import matplotlib.pyplot as plt

from viz_data import goldfish_decks, melee_decks, name_map, is_unknown
from viz_style import INK, GRY, LG, save

TOP_N = 15
MONTHS = "gen feb mar apr mag giu lug ago set ott nov dic".split()


def top_share(names, top_n=TOP_N):
    counts = names.value_counts()
    total = counts.sum()
    known = counts[~is_unknown(counts.index.to_series()).values]
    return known.nlargest(top_n) / total * 100


def main():
    nm = name_map()
    ml = melee_decks()
    start, end = ml["date"].min(), ml["date"].max()
    ml_names = ml["name"].fillna("").replace(dict(zip(nm["melee"], nm["label"])))
    gf = goldfish_decks()
    gf = gf[(gf["date"] >= start) & (gf["date"] <= end)]
    gf_names = gf["archetype"].replace(dict(zip(nm["goldfish"], nm["label"])))

    gold, melee = top_share(gf_names), top_share(ml_names)
    both = [k for k in gold.index if k in melee.index]
    both.sort(key=lambda k: gold[k] + melee[k])
    pairs = [(g, m, lab) for g, m, lab in nm.itertuples(index=False) if lab in both]

    # etichette in grassetto: il leader e il maggior scarto in ciascuna direzione
    leader = max(both, key=lambda k: gold[k])
    live = max(both, key=lambda k: melee[k] / gold[k])
    online = max(both, key=lambda k: gold[k] / melee[k])

    fig, ax = plt.subplots(figsize=(7.8, 5.4))
    for i, k in enumerate(both):
        g, m = gold[k], melee[k]
        ax.plot([g, m], [i, i], color=LG, lw=5, solid_capstyle="round", zorder=1)
        ax.scatter(g, i, color=GRY, s=70, zorder=3)
        ax.scatter(m, i, color=INK, s=70, zorder=3)
    ax.set_yticks(range(len(both)))
    ax.set_yticklabels(both, fontsize=12.5)
    for t in ax.get_yticklabels():
        if t.get_text() in (leader, live, online):
            t.set_fontweight("bold")
    ax.set_xlim(0, max(13, math.ceil(max(gold.max(), melee.max())) + 1))
    ax.set_xlabel(f"Quota delle decklist, {MONTHS[start.month - 1]} {start.year} – "
                  f"{MONTHS[end.month - 1]} {end.year} (%)", fontsize=12)
    ax.scatter([], [], color=GRY, s=70, label="MTGGoldfish (soprattutto MTGO)")
    ax.scatter([], [], color=INK, s=70, label="melee.gg (Regional Championship)")
    ax.legend(loc="lower right", frameon=False, fontsize=11.5)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LG)
    ax.set_axisbelow(True)
    save(fig, "pop.png")
    return {
        "GOLD": {k: round(float(v), 2) for k, v in gold.items()},
        "MELEE": {k: round(float(v), 2) for k, v in melee.items()},
        "both": both,
        "pairs_used": pairs,
        "bold": {"leader": leader, "more_live": live, "more_online": online},
    }


if __name__ == "__main__":
    print(main())
