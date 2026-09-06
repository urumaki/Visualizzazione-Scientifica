"""
Funzioni condivise dagli script di visualizzazione del progetto.
Non va lanciato direttamente: viene importato dagli altri script (deve stare
nella stessa cartella).
"""
import math
from datetime import datetime

import matplotlib.pyplot as plt

# Date degli aggiornamenti banlist Modern rilevanti nel range del dataset
# (verificate: magic.wizards.com / mtggoldfish.com / mtg.fandom.com)
BANLIST_EVENTS = [
    ("2021-02-15", "Field of the Dead, Uro, ..."),
    ("2022-03-07", "Lurrus"),
    ("2022-10-10", "Yorion"),
    ("2023-08-07", "Preordain unban"),
    ("2023-12-04", "Fury, Up the Beanstalk"),
    ("2024-03-11", "Violent Outburst"),
    ("2024-12-16", "The One Ring, Amped Raptor, Jegantha; 4 unban"),
    ("2025-03-31", "Underworld Breach"),
    ("2026-05-18", "Phlage, Lotus Field; 2 unban"),
]
DATASET_START = "2020-08-13"
DATASET_END = "2026-08-29"


def parse_date(raw):
    """Parsa sia date ISO con ora (tornei melee.gg) sia date semplici."""
    if not raw or (isinstance(raw, float) and math.isnan(raw)):
        return None
    raw = str(raw).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            # Restituisce datetime naive in UTC per evitare mismatch aware/naive.
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def wilson_ci(wins: int, losses: int, z: float = 1.96):
    """Intervallo di confidenza di Wilson (95% default) per un winrate,
    piu' affidabile del semplice +-1.96*sqrt(p(1-p)/n) su campioni piccoli
    (comune nelle celle con poche partite di una matchup matrix)."""
    n = wins + losses
    if n == 0:
        return None, None, None
    p = wins / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half_width = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return p, max(0.0, center - half_width), min(1.0, center + half_width)


def add_banlist_lines(ax, y_top=1.0, date_range=None):
    """Aggiunge linee verticali tratteggiate alle date banlist su un asse con
    asse X di tipo datetime. date_range: (start_str, end_str) per filtrare
    quali linee mostrare (default: tutte)."""
    for date_str, label in BANLIST_EVENTS:
        d = parse_date(date_str)
        if date_range:
            start, end = parse_date(date_range[0]), parse_date(date_range[1])
            if d < start or d > end:
                continue
        ax.axvline(d, color="#8a8778", linestyle="--", linewidth=0.8, alpha=0.7, zorder=1)


def setup_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#444444",
        "axes.labelcolor": "#222222",
        "text.color": "#222222",
        "xtick.color": "#444444",
        "ytick.color": "#444444",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 120,
    })


# Palette qualitativa per fino a ~16 archetipi + "Other" in grigio
QUALITATIVE_PALETTE = [
    "#185FA5", "#A32D2D", "#2D8A4E", "#B8860B", "#6B4C9A",
    "#C2703D", "#3D8FA8", "#A83D6E", "#5C7A29", "#8A5C3D",
    "#3D5CA8", "#A85C3D", "#4E8A6E", "#7A3D5C", "#8A8729",
    "#3D7A8A",
]
OTHER_COLOR = "#c3c2b7"


def color_for_rank(rank: int, is_other: bool = False):
    if is_other:
        return OTHER_COLOR
    return QUALITATIVE_PALETTE[rank % len(QUALITATIVE_PALETTE)]


def diverging_winrate_cmap():
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(
        "winrate_diverging", ["#D7263D", "#F5F0E1", "#1768D1"]
    )
