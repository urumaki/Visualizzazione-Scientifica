#!/usr/bin/env python3
"""
matrix.png - Matchup 10x10 tra i 10 archetipi piu' giocati su melee.gg
(per partite decise; righe = colonne, stesso ordine). Valore = winrate del mazzo in riga.
Scala divergente NEG-bianco-POS centrata a 50 (30-70); celle con < 30 partite
tratteggiate; mirror in grigio chiaro; grassetto se l'IC 95% esclude il 50%.

La riga di Izzet Prowess viene evidenziata solo se resta il caso notevole:
sotto il 50% in almeno 8 dei 9 matchup e IC complessivo sotto il 50%.

INPUT: data/csv/csv/matches_fixed.csv (+ decks.csv per le date)
"""
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm

from viz_data import melee_matches, decided
from viz_style import INK, POS, NEG, GRY, LG, MID, wilson, save

TOP_N = 10
MIN_CELL = 30
HIGHLIGHT = "Izzet Prowess"
SHORT = {
    "Boros Energy": "Boros En.", "Amulet Titan": "Amulet", "Izzet Prowess": "Prowess",
    "Jeskai Blink": "Jeskai Bl.", "Izzet Affinity": "Affinity", "Domain Zoo": "Zoo",
    "Esper Blink": "Esper Bl.", "Belcher": "Belcher", "Esper Goryo's": "Esper Gor.",
    "Goryo's Vengeance": "Goryo's V.",
}


def top_archetypes(n=TOP_N):
    """I piu' giocati = piu' partite decise, stesso criterio (e ordine) del forest plot."""
    return decided(melee_matches())["player"].value_counts().nlargest(n).index.tolist()


def cells(cols):
    m = decided(melee_matches())
    m = m[m["player"].isin(cols) & m["opponent"].isin(cols)]
    g = m.groupby(["player", "opponent"])["outcome"].value_counts().unstack(fill_value=0)
    mu = {}
    for r in cols:
        row = []
        for c in cols:
            if r == c:
                row.append(None)
            elif (r, c) in g.index:
                row.append((int(g.loc[(r, c)].get("win", 0)), int(g.loc[(r, c)].get("loss", 0))))
            else:
                row.append((0, 0))
        mu[r] = row
    return mu


def main():
    cols = top_archetypes()
    mu = cells(cols)
    n = len(cols)

    # la riga di Izzet Prowess resta il caso notevole?
    hl = None
    if HIGHLIGHT in cols:
        row = [c for c in mu[HIGHLIGHT] if c is not None]
        under = sum(1 for w, l in row if w + l and w / (w + l) < .5)
        m = decided(melee_matches())
        s = m[m["player"] == HIGHLIGHT]
        _, _, hi = wilson(int((s["outcome"] == "win").sum()), len(s))
        if under >= n - 2 and hi < .5:
            hl = cols.index(HIGHLIGHT)
        print(f"{HIGHLIGHT}: sotto il 50% in {under}/{n - 1} matchup, IC alto {hi * 100:.1f}% "
              f"-> {'evidenziata' if hl is not None else 'NON evidenziata'}")

    cmap = LinearSegmentedColormap.from_list("d", [NEG, "#F7F7F7", POS])
    norm = TwoSlopeNorm(50, 30, 70)
    fig, ax = plt.subplots(figsize=(8.4, 6.0))
    n_sig = 0
    for i, r in enumerate(cols):
        for j, c in enumerate(mu[r]):
            if c is None:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, color=LG))
                ax.text(j, i, "mirror", ha="center", va="center", fontsize=8.5, color=GRY)
                continue
            w, l = c
            N = w + l
            if N < MIN_CELL:
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, facecolor="white", edgecolor=LG, hatch="///", lw=0))
                ax.text(j, i, f"n={N}", ha="center", va="center", fontsize=9, color=GRY)
                continue
            p = w / N
            ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1, color=cmap(norm(p * 100))))
            _, lo, hi = wilson(w, N)
            sig = lo > .5 or hi < .5
            n_sig += sig
            strong = abs(p - .5) > .13
            ax.text(j, i - .08, f"{p * 100:.0f}", ha="center", va="center", fontsize=14 if sig else 12.5,
                    fontweight="bold" if sig else "normal", color="white" if strong else INK)
            ax.text(j, i + .27, f"n={N}", ha="center", va="center", fontsize=8, color="white" if strong else MID)
    for k in range(n + 1):
        ax.axhline(k - .5, color="white", lw=2)
        ax.axvline(k - .5, color="white", lw=2)
    ax.set_xlim(-.5, n - .5)
    ax.set_ylim(n - .5, -.5)
    ax.set_xticks(range(n))
    ax.set_xticklabels([SHORT.get(c, c) for c in cols], rotation=35, ha="left", fontsize=11.5)
    ax.xaxis.tick_top()
    ax.set_yticks(range(n))
    ax.set_yticklabels(cols, fontsize=12)
    if hl is not None:
        ax.get_yticklabels()[hl].set_fontweight("bold")
        ax.get_yticklabels()[hl].set_color(NEG)
        ax.add_patch(plt.Rectangle((-.5, hl - .5), n, 1, fill=False, edgecolor=INK, lw=2.2, zorder=5))
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    ax.set_xlabel("Avversario  →   (valore = winrate % del mazzo in riga; grassetto = IC 95% esclude il 50%)",
                  fontsize=10.5, labelpad=8)
    save(fig, "matrix.png")

    return {"COLS": cols, "MU": mu, "highlight": hl is not None, "n_significant": n_sig}


if __name__ == "__main__":
    print(main())
