#!/usr/bin/env python3
"""
banlist.png - Quota delle decklist MTGGoldfish, Era 9 vs Era 10 (ban del
18.05.26). Archetipi mostrati: unione dei 15 principali di ciascuna era
(20 con i dati attuali), cosi' compaiono anche i mazzi quasi spariti
nell'Era 10 come Jeskai Blink. Frecce dal valore Era 9 (grigio) al valore
Era 10 (colore), ordinate per variazione; colonna delta in p.p.
Mazzi "Unknown" esclusi anche dal denominatore (come nella slide approvata).

INPUT: data/csv/csv/decks_audit.csv
"""
import matplotlib.pyplot as plt

from viz_data import goldfish_decks, goldfish_end, ERA9_START, ERA10_START
from viz_style import INK, POS, NEG, GRY, LG, MID, save

TOP_N = 15


def shares():
    g = goldfish_decks()
    g = g[~g["unknown"]]
    end = goldfish_end()
    e9 = g[(g["date"] >= ERA9_START) & (g["date"] < ERA10_START)]["archetype"]
    e10 = g[(g["date"] >= ERA10_START) & (g["date"] <= end)]["archetype"]
    p9 = e9.value_counts() / len(e9) * 100
    p10 = e10.value_counts() / len(e10) * 100
    top = list(p10.nlargest(TOP_N).index) + [a for a in p9.nlargest(TOP_N).index if a not in p10.nlargest(TOP_N).index]
    return [(a, float(p9.get(a, 0.0)), float(p10.get(a, 0.0))) for a in top], end


def main():
    era910, end = shares()
    rows = sorted(era910, key=lambda r: r[2] - r[1])
    drops = {r[0] for r in sorted(rows, key=lambda r: r[2] - r[1])[:2]}
    xmax = max(18.7, max(max(a, b) for _, a, b in rows) + 3.7)

    fig, ax = plt.subplots(figsize=(8.2, 5.9))
    for i, (n, a, b) in enumerate(rows):
        c = POS if b > a else NEG if b < a else GRY
        ax.annotate("", xy=(b, i), xytext=(a, i),
                    arrowprops=dict(arrowstyle="-|>", color=c, lw=2, mutation_scale=12, shrinkA=0, shrinkB=3))
        ax.scatter(a, i, s=34, color=GRY, zorder=3)
        d = round(b - a, 1)
        ax.text(xmax - .1, i, f"{d:+.1f}", va="center", ha="right", fontsize=11.5, color=c,
                fontweight="bold" if abs(d) >= 2 else "normal")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=12)
    for t, r in zip(ax.get_yticklabels(), rows):
        if r[0] in drops:
            t.set_fontweight("bold")
    ax.set_xlim(-.3, xmax)
    ax.set_ylim(-.7, len(rows) - .3)
    ax.text(xmax - .1, len(rows) - .1, "Δ p.p.", ha="right", fontsize=11, color=MID, fontweight="bold")
    ax.set_xlabel("Quota delle decklist nell'era (%)", fontsize=12)
    ax.scatter([], [], s=34, color=GRY, label="Era 9  (31.03.25 → 18.05.26)")
    ax.plot([], [], color=INK, lw=2, label=f"→ Era 10  (18.05.26 → {end:%d.%m.%y})")
    ax.legend(loc="upper right", bbox_to_anchor=(0.93, 1.0), frameon=False, fontsize=11.5)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="x", color=LG)
    ax.set_axisbelow(True)
    save(fig, "banlist.png")
    return {"ERA910": [(n, round(a, 2), round(b, 2)) for n, a, b in era910]}


if __name__ == "__main__":
    print(main())
