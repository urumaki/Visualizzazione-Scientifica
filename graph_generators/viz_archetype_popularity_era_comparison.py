#!/usr/bin/env python3
"""
Grafico - "Il meta si sposta": popolarita' degli archetipi, Era 9 vs Era 10
(fonte: MTGGoldfish, decks_audit.csv).

Prima e dopo l'ultimo aggiornamento banlist (18 maggio 2026: ban Phlage,
Lotus Field; unban Violent Outburst, Umezawa's Jitte). Usa MTGGoldfish e non
Melee.gg perche' il campione Melee.gg dell'Era 10 e' troppo piccolo (~2.500
partite, 22 tornei) per un confronto di popolarita' affidabile; MTGGoldfish
copre 45.764 decklist in Era 9 e 13.419 in Era 10.

INPUT: decks_audit.csv — colonne: archetype + una colonna data tra
       event_date_parsed / tournament_start_date / sort_date

USO:
    python viz_archetype_popularity_era_comparison.py --input decks_audit.csv \\
        --era9-start 2025-03-31 --era10-start 2026-05-18 --era10-end 2026-08-29 \\
        --top-n 15 --out popularity_era_comparison.png
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz_common import setup_style

DATE_CANDIDATES = ["event_date_parsed", "tournament_start_date", "sort_date", "event_date", "date"]


def load_dated_archetypes(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    if "archetype" not in df.columns:
        raise KeyError(f"Colonna obbligatoria mancante: 'archetype'. Colonne trovate: {list(df.columns)}")
    date_col = next((c for c in DATE_CANDIDATES if c in df.columns), None)
    if date_col is None:
        raise KeyError(f"Colonna data non trovata. Attesa una tra: {DATE_CANDIDATES}.")

    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_convert(None),
        "archetype": df["archetype"].astype(str).str.strip(),
    })
    out = out.dropna(subset=["date"])
    unknown_mask = out["archetype"].str.lower().isin({"", "unknown", "unk", "n/a", "na", "none", "null", "nan"})
    out = out[~unknown_mask]
    return out


def era_share(df: pd.DataFrame, start: str, end: str) -> pd.Series:
    mask = (df["date"] >= start) & (df["date"] < end)
    sub = df.loc[mask, "archetype"]
    return sub.value_counts() / len(sub) * 100, len(sub)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="decks_audit.csv")
    parser.add_argument("--era9-start", default="2025-03-31")
    parser.add_argument("--era10-start", default="2026-05-18")
    parser.add_argument("--era10-end", default="2026-08-29")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--out", default="popularity_era_comparison.png")
    args = parser.parse_args()

    setup_style()

    df = load_dated_archetypes(args.input)
    pct9, n9 = era_share(df, args.era9_start, args.era10_start)
    pct10, n10 = era_share(df, args.era10_start, args.era10_end)
    print(f"Era 9: {n9} decklist. Era 10: {n10} decklist.")

    union_top = set(pct9.nlargest(args.top_n).index) | set(pct10.nlargest(args.top_n).index)
    order = sorted(union_top, key=lambda a: pct10.get(a, 0), reverse=True)

    v9 = [pct9.get(a, 0) for a in order]
    v10 = [pct10.get(a, 0) for a in order]

    y = np.arange(len(order))
    h = 0.38

    fig, ax = plt.subplots(figsize=(11.5, 0.32 * len(order) + 1.7))
    color9, color10 = "#8a8778", "#185FA5"
    ax.barh(y + h / 2, v9, height=h, color=color9, label=f"Era 9 ({args.era9_start} → {args.era10_start})")
    ax.barh(y - h / 2, v10, height=h, color=color10, label=f"Era 10 ({args.era10_start} → {args.era10_end})")

    for yi, v in zip(y + h / 2, v9):
        ax.text(v + 0.3, yi, f"{v:.1f}%", va="center", fontsize=7, color="#333333")
    for yi, v in zip(y - h / 2, v10):
        ax.text(v + 0.3, yi, f"{v:.1f}%", va="center", fontsize=7, color="#333333")

    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Quota decklist nell'era (%)")
    ax.set_title("Il meta si sposta: popolarità archetipi, Era 9 vs Era 10 (fonte: MTGGoldfish)", pad=15)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")


if __name__ == "__main__":
    main()
