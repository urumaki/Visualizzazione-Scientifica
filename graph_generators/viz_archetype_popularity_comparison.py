#!/usr/bin/env python3
"""
Grafico 4 - Popolarita' archetipi: MTGGoldfish (storico ampio) vs melee.gg
(Regional Championship, segnale competitivo piu' "puro").

Due pannelli affiancati, stesso ordine di lettura, per mostrare se le due
fonti raccontano una storia simile o divergono (utile anche come nota
metodologica sul perche' le due fonti restano separate nel progetto).

Il lato melee.gg usa "decklist_name" (nome pieno, con prefisso colore: es.
"Boros Energy", "Izzet Prowess") e non "archetype" (il campo "famiglia"
generico di Melee.gg: "Energy", "Prowess", senza colore) — altrimenti questo
grafico userebbe un livello di aggregazione diverso da tutti gli altri
grafici del progetto basati su melee.gg (matchup, ranking, winrate, che
usano tutti player_decklist_name/decklist_name), col rischio di sommare
insieme varianti a colori diversi dello stesso "archetipo famiglia" e di
non corrispondere piu' ai nomi citati nel testo delle slide.

INPUT:
    --goldfish   decks_audit.csv (colonna: archetype)
    --melee      decks.csv       (colonna: decklist_name, oppure archetype se decklist_name e' vuoto)

USO:
    python viz_archetype_popularity_comparison.py --goldfish decks_audit.csv --melee decks.csv --top-n 15 --out archetype_popularity.png
"""
import argparse

import matplotlib.pyplot as plt
import pandas as pd

from viz_common import setup_style, color_for_rank

# Non sono archetipi: sono mazzi che la fonte non e' riuscita a classificare.
# Restano nel denominatore (la % deve riflettere la quota sul totale reale
# dei mazzi, categorizzati o no) ma non possono comparire come una barra del
# "top N" — altrimenti "Unknown" finisce per sembrare un archetipo vero e
# competere per la seconda posizione assoluta, senza nessuna spiegazione.
UNKNOWN_LABELS = {"", "unknown", "unk", "n/a", "na", "none", "null", "nan"}


def top_share(df, col, top_n):
    counts = df[col].value_counts()
    total = counts.sum()
    known = counts[~counts.index.str.strip().str.lower().isin(UNKNOWN_LABELS)]
    top = known.nlargest(top_n)
    pct = (top / total * 100).sort_values(ascending=True)
    return pct


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goldfish", default="decks_audit.csv")
    parser.add_argument("--melee", default="decks.csv")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--out", default="archetype_popularity.png")
    args = parser.parse_args()

    setup_style()

    gf = pd.read_csv(args.goldfish)
    gf = gf.dropna(subset=["archetype"])
    gf_pct = top_share(gf, "archetype", args.top_n)

    ml = pd.read_csv(args.melee)
    ml_col = "decklist_name" if "decklist_name" in ml.columns and ml["decklist_name"].notna().any() else "archetype"
    ml = ml.dropna(subset=[ml_col])
    ml_pct = top_share(ml, ml_col, args.top_n)

    fig, axes = plt.subplots(1, 2, figsize=(13, 0.35 * args.top_n + 2))

    axes[0].barh(gf_pct.index, gf_pct.values,
                 color=[color_for_rank(i) for i in range(len(gf_pct))])
    axes[0].set_title("MTGGoldfish (2020–2026, storico ampio)")
    axes[0].set_xlabel("Quota decklist (%)")

    axes[1].barh(ml_pct.index, ml_pct.values,
                 color=[color_for_rank(i) for i in range(len(ml_pct))])
    axes[1].set_title("melee.gg — Regional Championship")
    axes[1].set_xlabel("Quota decklist (%)")

    fig.suptitle(f"Top {args.top_n} archetipi per fonte", fontweight="bold")
    fig.text(0.5, -0.02, "Mazzi non categorizzati (\"Unknown\"/vuoto) esclusi dalla classifica ma inclusi nel totale usato per le %.",
              ha="center", fontsize=8, color="#666666")
    fig.tight_layout()
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")


if __name__ == "__main__":
    main()
