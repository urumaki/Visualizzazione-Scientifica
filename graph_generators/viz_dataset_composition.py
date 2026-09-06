#!/usr/bin/env python3
"""
Grafico 6 - Composizione del dataset (trasparenza metodologica).

Tre pannelli:
    a) MTGGoldfish: split Paper vs MTGO
    b) MTGGoldfish: n. decklist per anno (copertura temporale, buchi visibili)
    c) melee.gg: split per tipo torneo (tournament_tags)

INPUT:
    --goldfish  decks_audit.csv  (colonne: source, event_date_parsed)
    --melee     decks.csv        (colonna: tournament_tags)

USO:
    python viz_dataset_composition.py --goldfish decks_audit.csv --melee decks.csv --out dataset_composition.png
"""
import argparse

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, color_for_rank


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldfish", default="decks_audit.csv")
    parser.add_argument("--melee", default="decks.csv")
    parser.add_argument("--out", default="dataset_composition.png")
    args = parser.parse_args()

    setup_style()
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    # (a) MTGGoldfish: Paper vs MTGO
    gf = pd.read_csv(args.goldfish)
    source_counts = gf["source"].value_counts()
    axes[0].pie(
        source_counts.values, labels=source_counts.index, autopct="%1.0f%%",
        colors=[color_for_rank(i) for i in range(len(source_counts))],
        wedgeprops={"edgecolor": "white"},
    )
    axes[0].set_title("MTGGoldfish: Paper vs MTGO")

    # (b) MTGGoldfish: copertura temporale per anno
    gf["date"] = pd.to_datetime(gf["event_date_parsed"], errors="coerce")
    gf_valid = gf.dropna(subset=["date"])
    by_year = gf_valid["date"].dt.year.value_counts().sort_index()
    axes[1].bar(by_year.index.astype(str), by_year.values, color="#185FA5")
    axes[1].set_title("MTGGoldfish: decklist per anno")
    axes[1].set_ylabel("N. decklist")
    axes[1].tick_params(axis="x", rotation=45)

    # (c) melee.gg: split per tipo torneo
    ml = pd.read_csv(args.melee)
    tag_counts = ml["tournament_tags"].value_counts().nlargest(8)
    axes[2].barh(
        tag_counts.index[::-1], tag_counts.values[::-1],
        color=[color_for_rank(i) for i in range(len(tag_counts))][::-1],
    )
    axes[2].set_title("melee.gg: tipo torneo")
    axes[2].set_xlabel("N. decklist")

    fig.suptitle("Composizione del dataset", fontweight="bold")
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")
    print(f"MTGGoldfish: {len(gf)} righe totali, {len(gf_valid)} con data valida")
    print(f"melee.gg: {len(ml)} righe totali")


if __name__ == "__main__":
    main()
