#!/usr/bin/env python3
"""
Grafico - Chi ha adottato le carte sbannate il 18 maggio 2026 (Violent
Outburst, Umezawa's Jitte), e se e' servito: il winrate di Living End
(il principale adottante di Violent Outburst) prima/dopo l'unban.

Non guarda le carte bannate (Phlage, Lotus Field): il loro utilizzo scende
banalmente a zero appena non sono piu' legali, non e' un dato interessante.

Due pannelli affiancati:
    a) quali archetipi hanno adottato la carta sbannata piu' giocata
    b) winrate di Living End (tutte le varianti colore), Era 9 vs Era 10

INPUT: cards.csv, decks.csv, matches_fixed.csv (Melee.gg)
USO:
    python viz_banlist_impact.py --cards cards.csv --decks decks.csv --matches matches_fixed.csv \\
        --ban-date 2026-05-18 --out banlist_impact.png
"""
import argparse

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, color_for_rank, wilson_ci

UNBANNED = ["Violent Outburst", "Umezawa's Jitte"]


def living_end_winrate(matches_path, tid_date, era9_start, era10_start, era10_end):
    m = pd.read_csv(matches_path, low_memory=False)
    m["tournament_id"] = m["tournament_id"].astype(str)
    m["date"] = m["tournament_id"].map(tid_date)
    le = m[m["player_decklist_name"].str.contains("Living End", case=False, na=False)]
    le = le[le["outcome"].isin(["win", "loss"])]

    results = {}
    windows = {
        "Era 9": (era9_start, era10_start),
        "Era 10": (era10_start, era10_end),
    }
    for label, (start, end) in windows.items():
        sub = le[(le["date"] >= start) & (le["date"] < end)]
        wins = (sub["outcome"] == "win").sum()
        losses = (sub["outcome"] == "loss").sum()
        p, lo, hi = wilson_ci(int(wins), int(losses))
        results[label] = {"winrate": (p or 0) * 100, "ci_low": (lo or 0) * 100,
                           "ci_high": (hi or 0) * 100, "games": int(wins + losses)}
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cards", default="cards.csv")
    parser.add_argument("--decks", default="decks.csv")
    parser.add_argument("--matches", default="matches_fixed.csv")
    parser.add_argument("--ban-date", default="2026-05-18")
    parser.add_argument("--era9-start", default="2025-03-31")
    parser.add_argument("--era10-end", default="2026-08-29")
    parser.add_argument("--out", default="banlist_impact.png")
    args = parser.parse_args()

    setup_style()

    decks = pd.read_csv(args.decks, low_memory=False)
    decks["start"] = pd.to_datetime(decks["tournament_start_date"], errors="coerce", utc=True).dt.tz_convert(None)
    decks["tournament_id"] = decks["tournament_id"].astype(str)
    tid_date = dict(zip(decks["tournament_id"], decks["start"]))
    archetype_lookup = decks.set_index(["tournament_id", "guid"])["archetype"]

    ban_date = pd.Timestamp(args.ban_date)

    cards = pd.read_csv(args.cards, low_memory=False)
    cards["tournament_id"] = cards["tournament_id"].astype(str)
    sub = cards[cards["card_name"].isin(UNBANNED) & (cards["section"] == "main")].copy()
    sub["date"] = sub["tournament_id"].map(tid_date)
    sub = sub.dropna(subset=["date"])
    sub = sub[sub["date"] >= ban_date]  # solo adozione dopo l'unban
    sub["archetype"] = sub.apply(lambda r: archetype_lookup.get((r["tournament_id"], r["guid"]), "?"), axis=1)

    counts = sub.groupby("card_name")["guid"].nunique()
    for c in UNBANNED:
        if c not in counts.index:
            counts[c] = 0
    print(counts)

    top_card = counts.idxmax()
    by_arch = sub[sub["card_name"] == top_card]["archetype"].value_counts()

    le_wr = living_end_winrate(args.matches, tid_date, pd.Timestamp(args.era9_start), ban_date, pd.Timestamp(args.era10_end))
    print(le_wr)

    fig, axes = plt.subplots(1, 2, figsize=(14, max(0.5 * len(by_arch) + 2, 5)),
                              gridspec_kw={"width_ratios": [1.3, 1]})

    ax = axes[0]
    ax.barh(by_arch.index[::-1], by_arch.values[::-1],
            color=[color_for_rank(i) for i in range(len(by_arch))][::-1])
    for y, v in enumerate(by_arch.values[::-1]):
        ax.text(v + max(by_arch.values) * 0.02, y, f"{v}", va="center", fontsize=9)
    ax.set_xlabel("N. decklist Melee.gg (dopo l'unban)")
    other_card = [c for c in UNBANNED if c != top_card][0]
    ax.set_title(
        f"Chi ha adottato \"{top_card}\"\n"
        f"({counts[top_card]} decklist — \"{other_card}\" quasi ignorata: {counts[other_card]} decklist)",
        fontsize=12,
    )

    ax2 = axes[1]
    labels = ["Era 9", "Era 10"]
    colors = ["#8a8778", "#185FA5"]
    y = range(len(labels))
    winrates = [le_wr[lab]["winrate"] for lab in labels]
    ax2.bar(labels, winrates, color=colors, width=0.5)
    for i, lab in enumerate(labels):
        r = le_wr[lab]
        ax2.errorbar(i, r["winrate"], yerr=[[r["winrate"] - r["ci_low"]], [r["ci_high"] - r["winrate"]]],
                     fmt="none", ecolor="#444444", capsize=4)
        ax2.text(i, r["ci_high"] + 2, f"{r['winrate']:.1f}%\n(n={r['games']})", ha="center", fontsize=9)
    ax2.axhline(50, color="#8a8778", linestyle="--", linewidth=1)
    ax2.set_ylim(0, 100)
    ax2.set_ylabel("Winrate (%)")
    ax2.set_title("Winrate Living End\n(tutte le varianti colore)", fontsize=12)

    fig.suptitle("L'unban di Violent Outburst e Living End", fontweight="bold")
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")


if __name__ == "__main__":
    main()
