"""
Stile condiviso da tutti i grafici della presentazione.

- font Carlito (fallback Calibri, poi DejaVu Sans)
- palette fissa (INK/POS/NEG/GRY/LG/MID)
- spine top/right rimosse, dpi 220, bbox tight
- nessun titolo dentro i grafici: il titolo sta nella slide
"""
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager as fm  # noqa: E402

INK = "#1C2233"
POS = "#1B998B"
NEG = "#E4572E"
GRY = "#A7ADB5"
LG = "#E6E8EB"
MID = "#5B6270"

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "figures"


def _pick_font():
    for f in fm.findSystemFonts():
        name = Path(f).name.lower()
        if "carlito" in name or "calibri" in name:
            try:
                fm.fontManager.addfont(f)
            except Exception:
                pass
    available = {f.name for f in fm.fontManager.ttflist}
    for family in ("Carlito", "Calibri", "DejaVu Sans"):
        if family in available:
            return family
    return "DejaVu Sans"


FONT = _pick_font()

plt.rcParams.update({
    "font.family": FONT,
    "font.size": 14,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": GRY,
    "axes.labelcolor": MID,
    "xtick.color": MID,
    "ytick.color": INK,
    "axes.titleweight": "bold",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})


def wilson(w, n, z=1.96):
    """Winrate e intervallo di Wilson al 95%: restituisce (p, low, high) in [0, 1]."""
    if n == 0:
        return (float("nan"),) * 3
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, c - h, c + h


def save(fig, name):
    FIG_DIR.mkdir(exist_ok=True)
    out = FIG_DIR / name
    fig.savefig(out)
    plt.close(fig)
    print(f"Salvato: {out.relative_to(ROOT)}")
    return out
