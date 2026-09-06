#!/usr/bin/env python3
"""
Grafico a linee - Numero di piazzamenti in top 3 per archetipo, per era di
banlist Modern, usando SOLO le decklist MTGO (source == "MTGO" in
decks_audit.csv). Le decklist MTGO sono le uniche nel dataset MTGGoldfish
con un vero piazzamento numerico (rank_order) confrontabile fra tornei
diversi — Modern Challenge, Preliminary, ecc. — quindi sono l'unica fonte
sensata per contare "quante volte un mazzo è arrivato in top 3".

Le ere sono le stesse (e con gli stessi confini) usate ovunque nel progetto
(BANLIST_EVENTS/DATASET_START/DATASET_END in viz_common.py), cosi' i cambi
di formato restano il riferimento comune per leggere l'evoluzione del meta.

INPUT: decks_audit.csv (MTGGoldfish) — colonne: source, rank_order,
       archetype, event_date_parsed
USO:
    python viz_top3_by_era.py --input decks_audit.csv --top-n 8 --max-rank 3 \\
        --out top3_by_era.png
"""
import argparse

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, color_for_rank, parse_date, BANLIST_EVENTS, DATASET_START, DATASET_END


def build_eras():
    bounds = [DATASET_START] + [d for d, _ in BANLIST_EVENTS] + [DATASET_END]
    eras = []
    for i in range(len(bounds) - 1):
        start, end = parse_date(bounds[i]), parse_date(bounds[i + 1])
        eras.append({"index": i + 1, "start": start, "end": end, "label": f"Era {i + 1}\n{bounds[i][:7]}"})
    return eras


def era_for_date(date, eras):
    if date is None:
        return None
    for era in eras:
        if era["start"] <= date < era["end"]:
            return era["index"]
    if date >= eras[-1]["end"]:
        return eras[-1]["index"]
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="decks_audit.csv")
    parser.add_argument("--max-rank", type=int, default=3, help="Soglia piazzamento (default: top 3)")
    parser.add_argument("--top-n", type=int, default=8, help="N. archetipi mostrati (per totale top-3 su tutte le ere)")
    parser.add_argument("--out", default="top3_by_era.png")
    args = parser.parse_args()

    setup_style()

    df = pd.read_csv(args.input, low_memory=False)
    df = df[df["source"] == "MTGO"].copy()
    df["archetype"] = df["archetype"].astype(str).str.strip()
    unknown_mask = df["archetype"].str.lower().isin({"", "unknown", "unk", "n/a", "na", "none", "null", "nan"})
    df = df[~unknown_mask]
    df["date"] = pd.to_datetime(df["event_date_parsed"], errors="coerce", utc=True).dt.tz_convert(None)
    df = df.dropna(subset=["date"])

    top3 = df[df["rank_order"] <= args.max_rank].copy()
    print(f"Decklist MTGO totali: {len(df)}. Piazzamenti top {args.max_rank}: {len(top3)}.")

    eras = build_eras()
    era_bounds = [(e["index"], e["start"].to_pydatetime() if hasattr(e["start"], "to_pydatetime") else e["start"]) for e in eras]
    top3["era_index"] = top3["date"].apply(lambda d: era_for_date(d, eras))
    top3 = top3.dropna(subset=["era_index"])

    top_archetypes = top3["archetype"].value_counts().nlargest(args.top_n).index.tolist()

    counts = (
        top3[top3["archetype"].isin(top_archetypes)]
        .groupby(["era_index", "archetype"]).size()
        .unstack(fill_value=0)
        .reindex(columns=top_archetypes, fill_value=0)
    )
    # Mostra solo le ere che hanno almeno un dato (le ere senza tornei MTGO tracciati restano fuori)
    era_totals = top3.groupby("era_index").size()
    active_eras = [e for e in eras if e["index"] in era_totals.index]
    counts = counts.reindex(index=[e["index"] for e in active_eras], fill_value=0)

    fig, ax = plt.subplots(figsize=(11, 6))
    for i, archetype in enumerate(top_archetypes):
        ax.plot(range(len(active_eras)), counts[archetype], marker="o", color=color_for_rank(i), label=archetype)

    ax.set_xticks(range(len(active_eras)))
    ax.set_xticklabels([e["label"] for e in active_eras], fontsize=8)
    ax.set_ylabel(f"N. piazzamenti in top {args.max_rank}")
    ax.set_title(f"Piazzamenti in top {args.max_rank} per archetipo, per era (fonte: MTGGoldfish, solo decklist MTGO)")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")


if __name__ == "__main__":
    main()
