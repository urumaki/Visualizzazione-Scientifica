#!/usr/bin/env python3
"""
Grafico 1 - Timeline metagame (fonte: MTGGoldfish + Melee.gg)

Area chart impilata: quota % mensile dei top N archetipi da agosto 2020 ad
oggi, con linee verticali sugli aggiornamenti banlist Modern per leggere
l'evoluzione del meta in relazione ai cambi di formato.

Il dataset MTGGoldfish (decks_audit.csv) copre l'intero storico dal 2020 ma
non viene piu' aggiornato di recente con la stessa costanza; il dataset
Melee.gg (decks.csv) e' molto piu' piccolo ma copre i tornei recenti (RCQ /
Regional Championship) con dati puliti. I due dataset vengono quindi
concatenati: il grosso della timeline storica arriva da MTGGoldfish, mentre
i mesi piu' recenti sono arricchiti anche dai tornei Melee.gg.

INPUT: decks_audit.csv (MTGGoldfish) + decks.csv (Melee.gg, opzionale)
       Colonne richieste: archetype + una colonna data tra
       event_date_parsed / tournament_start_date / sort_date

USO:
    python viz_metagame_timeline.py --input decks_audit.csv --melee-input decks.csv \\
        --top-n 10 --out metagame_timeline.png
"""
import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, add_banlist_lines, color_for_rank, BANLIST_EVENTS, parse_date

DATE_CANDIDATES = ["event_date_parsed", "tournament_start_date", "sort_date", "event_date", "date"]

# Melee.gg etichetta gli archetipi con nomi piu' generici/senza colori
# (es. "Energy", "Domain", "Murktide") rispetto a MTGGoldfish (es. "Boros
# Energy", "Domain Zoo", "Murktide Regent"). Senza normalizzazione lo stesso
# mazzo finirebbe in due bucket diversi e gonfierebbe artificialmente la
# fetta "Other" nei mesi recenti. Mappiamo qui solo i casi non ambigui (un
# solo archetipo MTGGoldfish plausibile); i nomi Melee.gg genuinamente
# generici (Aggro, Control, Combo, Midrange, Blink, Prowess, Eldrazi, Storm,
# Burn, Reanimator, ...), che in MTGGoldfish si spalmano su piu' varianti
# colore, restano invece non mappati e finiscono in "Other".
MELEE_ARCHETYPE_ALIASES = {
    "Energy": "Boros Energy",
    "Domain": "Domain Zoo",
    "Murktide": "Murktide Regent",
    "Goryo's": "Goryo's Vengeance",
    "Creativity": "Indomitable Creativity",
    "Ramp": "Eldrazi Ramp",
}


def load_source(path: str, source_label: str) -> pd.DataFrame:
    """Legge un CSV sorgente (goldfish o melee) e lo normalizza a colonne
    archetype/date/source, scartando righe senza data o archetipo valido."""
    df = pd.read_csv(path, low_memory=False)

    if "archetype" not in df.columns:
        raise KeyError(f"Colonna obbligatoria mancante: 'archetype' in {path}. Colonne trovate: {list(df.columns)}")

    date_col = next((c for c in DATE_CANDIDATES if c in df.columns), None)
    if date_col is None:
        raise KeyError(
            f"Colonna data non trovata in {path}. Attesa una tra: {DATE_CANDIDATES}. "
            f"Colonne trovate: {list(df.columns)}"
        )

    out = pd.DataFrame({
        "date": pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_convert(None),
        "archetype": df["archetype"].astype(str).str.strip(),
    })
    out["source"] = source_label
    out = out.dropna(subset=["date"])

    if source_label == "Melee.gg":
        out["archetype"] = out["archetype"].replace(MELEE_ARCHETYPE_ALIASES)

    unknown_mask = out["archetype"].str.lower().isin({"", "unknown", "unk", "n/a", "na", "none", "null", "nan"})
    out.loc[unknown_mask, "archetype"] = "Other"
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="decks_audit.csv", help="Dataset MTGGoldfish (storico)")
    parser.add_argument("--melee-input", default="decks.csv", help="Dataset Melee.gg (tornei recenti)")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--out", default="metagame_timeline.png")
    args = parser.parse_args()

    setup_style()

    frames = [load_source(args.input, "MTGGoldfish")]

    melee_start = None
    if args.melee_input and Path(args.melee_input).exists():
        melee_df = load_source(args.melee_input, "Melee.gg")
        if not melee_df.empty:
            melee_start = melee_df["date"].min()
            frames.append(melee_df)
            print(f"Melee.gg: {len(melee_df)} decklist da {melee_start.date()} a {melee_df['date'].max().date()}")
    else:
        print(f"[!] {args.melee_input} non trovato, uso solo dati MTGGoldfish.")

    df = pd.concat(frames, ignore_index=True)
    if df.empty:
        raise ValueError("Nessun record valido dopo il parsing delle date e il filtro su archetype.")
    df["month"] = df["date"].dt.to_period("M").dt.to_timestamp()

    top_archetypes = (
        df.loc[df["archetype"] != "Other", "archetype"]
        .value_counts()
        .nlargest(args.top_n)
        .index
        .tolist()
    )
    df["archetype_bucket"] = df["archetype"].where(df["archetype"].isin(top_archetypes), "Other")

    monthly = (
        df.groupby(["month", "archetype_bucket"])
        .size()
        .unstack(fill_value=0)
    )
    monthly_pct = monthly.div(monthly.sum(axis=1), axis=0) * 100

    ordered_cols = [a for a in top_archetypes if a in monthly_pct.columns] + (
        ["Other"] if "Other" in monthly_pct.columns else []
    )
    monthly_pct = monthly_pct[ordered_cols]

    fig, ax = plt.subplots(figsize=(11, 6))
    colors = [
        color_for_rank(i, is_other=(name == "Other"))
        for i, name in enumerate(ordered_cols)
    ]
    ax.stackplot(
        monthly_pct.index, monthly_pct.T.values, labels=ordered_cols,
        colors=colors, alpha=0.9,
    )

    add_banlist_lines(ax)
    for date_str, _ in BANLIST_EVENTS:
        d = parse_date(date_str)
        if monthly_pct.index.min() <= d <= monthly_pct.index.max():
            ax.text(d, 98.5, d.strftime("%b %y"), rotation=90, fontsize=7,
                     ha="right", va="top", color="#666666")

    if melee_start is not None:
        melee_month = melee_start.to_period("M").to_timestamp()
        if monthly_pct.index.min() < melee_month <= monthly_pct.index.max():
            ax.axvline(melee_month, color="#185FA5", linestyle=":", linewidth=1.1, alpha=0.8, zorder=1)
            ax.text(melee_month, 4, "  inizio dati Melee.gg", rotation=90, fontsize=7,
                     ha="left", va="bottom", color="#185FA5")

    ax.set_ylim(0, 100)
    ax.set_ylabel("Quota metagame (%)")
    source_note = "MTGGoldfish" if melee_start is None else "MTGGoldfish (storico) + Melee.gg (recenti)"
    ax.set_title(
        f"Evoluzione metagame Modern — top {args.top_n} archetipi (fonte: {source_note})",
        pad=20,
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")


if __name__ == "__main__":
    main()
