#!/usr/bin/env python3
"""
Grafico combinato: ranking winrate + tabella matchup (stile "Frank Karsten").

Pannello sinistro: barre orizzontali del winrate complessivo di ogni
archetipo (record W-L-D nel testo), con intervallo di confidenza 95%
(Wilson), ordinate dal migliore al peggiore.

Pannello destro: tabella colorata (rosso->giallo->verde) con il record
dettagliato di ogni archetipo contro i N avversari piu' frequenti, stesso
ordine righe del pannello sinistro. Gli specchio (mirror match) sono
esclusi e mostrati come "X", coerente con le convenzioni standard di questo
tipo di analisi (winrate = wins/(wins+losses), pareggi esclusi dal %).

INPUT: matches_fixed.csv (+ decks.csv se si filtra per era con --start-date/--end-date)
USO:
    python viz_archetype_ranking_matrix.py --input matches_fixed.csv \\
        --min-games 100 --top-n-cols 10 --out ranking_matrix.png

    # Filtrato su una sola era di banlist (richiede decks.csv per le date torneo):
    python viz_archetype_ranking_matrix.py --input matches_fixed.csv --decks decks.csv \\
        --start-date 2025-03-31 --end-date 2026-05-18 --min-games 250 --out ranking_matrix_era9.png
"""
import argparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from viz_common import setup_style, wilson_ci

JUNK_ARCHETYPE_NAMES = {
    "", "?????", "Paper Decklist", "MTGO Decklist", "Decklist",
    "Unknown", "Untitled Deck", "Modern Deck", "New Deck",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="matches_fixed.csv")
    parser.add_argument("--decks", default=None,
                         help="decks.csv (Melee.gg), richiesto solo se si passa --start-date/--end-date")
    parser.add_argument("--start-date", default=None, help="Filtra i match a tournament_start_date >= questa data (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Filtra i match a tournament_start_date < questa data (YYYY-MM-DD)")
    parser.add_argument("--min-games", type=int, default=300,
                         help="Min. partite decise (W+L) per comparire nel ranking a sinistra (alza per liste più corte/leggibili)")
    parser.add_argument("--top-n-cols", type=int, default=10,
                         help="N. avversari (colonne) nella tabella a destra")
    parser.add_argument("--min-cell-games", type=int, default=1,
                         help="Sotto questa soglia la cella viene comunque mostrata ma segnalata come campione minimo")
    parser.add_argument("--title-suffix", default="",
                         help="Testo aggiunto al titolo del grafico (es. 'Era 9')")
    parser.add_argument("--out", default="ranking_matrix.png")
    args = parser.parse_args()

    setup_style()

    df = pd.read_csv(args.input)
    df = df[df["player_decklist_name"].notna() & (df["player_decklist_name"] != "")]
    df = df[~df["player_decklist_name"].isin(JUNK_ARCHETYPE_NAMES)]
    df = df[~df["opponent_decklist_name"].isin(JUNK_ARCHETYPE_NAMES)]

    if args.start_date or args.end_date:
        if not args.decks:
            raise SystemExit("--start-date/--end-date richiedono anche --decks (per le date torneo)")
        decks = pd.read_csv(args.decks, low_memory=False)
        decks["start"] = pd.to_datetime(decks["tournament_start_date"], errors="coerce", utc=True).dt.tz_convert(None)
        tid_date = dict(zip(decks["tournament_id"].astype(str), decks["start"]))
        df = df.copy()
        df["_date"] = df["tournament_id"].astype(str).map(tid_date)
        if args.start_date:
            df = df[df["_date"] >= pd.Timestamp(args.start_date)]
        if args.end_date:
            df = df[df["_date"] < pd.Timestamp(args.end_date)]

    decided = df[df["outcome"].isin(["win", "loss"])]
    all_outcomes = df[df["outcome"].isin(["win", "loss", "draw"])]

    # --- Ranking generale (pannello sinistro) ---
    overall = decided.groupby("player_decklist_name")["outcome"].value_counts().unstack(fill_value=0)
    overall["wins"] = overall.get("win", 0)
    overall["losses"] = overall.get("loss", 0)
    overall["games"] = overall["wins"] + overall["losses"]
    draws = all_outcomes[all_outcomes["outcome"] == "draw"].groupby("player_decklist_name").size()
    overall["draws"] = overall.index.map(draws).fillna(0).astype(int)
    overall = overall[overall["games"] >= args.min_games]

    rows = []
    for name, r in overall.iterrows():
        p, lo, hi = wilson_ci(int(r["wins"]), int(r["losses"]))
        rows.append({
            "archetype": name, "wins": int(r["wins"]), "losses": int(r["losses"]),
            "draws": int(r["draws"]), "winrate": p * 100, "ci_low": lo * 100, "ci_high": hi * 100,
        })
    ranking = pd.DataFrame(rows).sort_values("winrate", ascending=True)  # ascending: il migliore finisce in alto nel plot (barh)

    row_order = ranking["archetype"].tolist()  # dal peggiore al migliore (per barh dal basso)
    n_rows = len(row_order)

    # --- Colonne della tabella: avversari piu' frequenti in assoluto ---
    top_cols = decided["opponent_decklist_name"].value_counts().nlargest(args.top_n_cols).index.tolist()

    # --- Costruzione tabella matchup ---
    cell_wins = np.zeros((n_rows, len(top_cols)))
    cell_losses = np.zeros((n_rows, len(top_cols)))
    is_mirror = np.zeros((n_rows, len(top_cols)), dtype=bool)

    for i, arche in enumerate(row_order):
        sub = decided[decided["player_decklist_name"] == arche]
        for j, opp in enumerate(top_cols):
            if opp == arche:
                is_mirror[i, j] = True
                continue
            m = sub[sub["opponent_decklist_name"] == opp]
            cell_wins[i, j] = (m["outcome"] == "win").sum()
            cell_losses[i, j] = (m["outcome"] == "loss").sum()

    winrate_matrix = np.divide(
        cell_wins, cell_wins + cell_losses,
        out=np.full_like(cell_wins, np.nan), where=(cell_wins + cell_losses) > 0
    ) * 100

    # --- Plot ---
    fig, (ax_bar, ax_table) = plt.subplots(
        1, 2, figsize=(9 + 0.9 * len(top_cols), 0.4 * n_rows + 2.5),
        gridspec_kw={"width_ratios": [3, 2.2 + 0.35 * len(top_cols)]},
    )

    cmap = plt.get_cmap("RdYlGn")
    y = np.arange(n_rows)
    bar_colors = [cmap(v / 100) for v in ranking["winrate"]]
    ax_bar.barh(y, ranking["winrate"], color=bar_colors, edgecolor="none")
    ax_bar.errorbar(
        ranking["winrate"], y,
        xerr=[ranking["winrate"] - ranking["ci_low"], ranking["ci_high"] - ranking["winrate"]],
        fmt="none", ecolor="black", elinewidth=1, capsize=3,
    )
    ax_bar.axvline(50, color="black", linestyle=":", linewidth=1)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(row_order, fontsize=9)
    ax_bar.set_xlim(0, 100)
    ax_bar.set_xlabel("Winrate (%)")

    for i, r in enumerate(ranking.itertuples()):
        record = f"{r.wins}-{r.losses}-{r.draws} ({r.winrate:.1f}%)"
        ax_bar.text(2, i, record, va="center", ha="left", fontsize=7.5,
                     color="black" if r.winrate < 60 else "white")

    ax_bar.set_title("Winrate complessivo", fontsize=11, loc="left")

    ax_table.set_xlim(-0.5, len(top_cols) - 0.5)
    ax_table.set_ylim(-0.5, n_rows - 0.5)
    for i in range(n_rows):
        for j in range(len(top_cols)):
            if is_mirror[i, j]:
                ax_table.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color="#e5e3da"))
                ax_table.text(j, i, "X", ha="center", va="center", fontsize=8, color="#888888")
                continue
            wr = winrate_matrix[i, j]
            games = cell_wins[i, j] + cell_losses[i, j]
            color = cmap(wr / 100) if not np.isnan(wr) else "#f5f4ef"
            ax_table.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, color=color))
            label = f"{int(cell_wins[i,j])}-{int(cell_losses[i,j])}\n({wr:.0f}%)" if games > 0 else "0-0\n(-)"
            txt_color = "black"
            if not np.isnan(wr) and (wr < 25 or wr > 75):
                txt_color = "white"
            ax_table.text(j, i, label, ha="center", va="center", fontsize=6.5, color=txt_color)

    ax_table.set_xticks(range(len(top_cols)))
    ax_table.set_xticklabels(top_cols, rotation=45, ha="left", fontsize=8)
    ax_table.xaxis.tick_top()
    ax_table.set_yticks([])
    for spine in ax_table.spines.values():
        spine.set_visible(False)
    ax_table.set_title(f"Matchup vs top {args.top_n_cols} avversari", fontsize=11, loc="left", pad=40)

    title_suffix = f" — {args.title_suffix}" if args.title_suffix else ""
    fig.suptitle(f"Modern — winrate per archetipo (fonte: melee.gg Regional Championship){title_suffix}",
                  fontweight="bold", fontsize=13, y=1.02)
    fig.text(0.01, -0.02,
              "Barre di errore = intervallo di confidenza 95% (Wilson). "
              "Winrate calcolato su wins/(wins+losses), pareggi esclusi. Specchio = X.",
              fontsize=7.5, color="#666666")

    fig.tight_layout()
    fig.subplots_adjust(right=0.97)
    fig.savefig(args.out, bbox_inches="tight")
    print(f"Salvato: {args.out}")
    print(f"Archetipi nel ranking (>= {args.min_games} partite decise): {n_rows}")


if __name__ == "__main__":
    main()
