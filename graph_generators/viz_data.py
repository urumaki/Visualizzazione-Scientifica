"""
Caricamento dei dataset gia' puliti dagli scraper (data/csv/csv) per gli
script dei grafici. Nessuna logica di scraping o pulizia qui: solo lettura,
normalizzazione dei nomi degli archetipi e date delle ere di banlist.
"""
import re
from functools import lru_cache

import pandas as pd

from viz_style import ROOT

CSV_DIR = ROOT / "data" / "csv" / "csv"
DATA_DIR = ROOT / "data"

# Aggiornamenti banlist Modern nel range del dataset
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
BAN_DATES = [pd.Timestamp(d) for d, _ in BANLIST_EVENTS]
ERA9_START = pd.Timestamp("2025-03-31")
ERA10_START = pd.Timestamp("2026-05-18")

# Carte bannate durante il periodo coperto dai dati e ancora bannate oggi
# (Violent Outburst e' stata sbannata il 18.05.26, quindi non compare).
BANNED_CARDS = {
    "Uro, Titan of Critical Mass", "Simian Spirit Guide", "Tibalt's Trickery",
    "Field of the Dead", "Mystic Sanctuary", "Lurrus of the Dream-Den",
    "Yorion, Sky Nomad", "Fury", "Up the Beanstalk", "The One Ring",
    "Amped Raptor", "Jegantha, the Wellspring", "Underworld Breach",
    "Phlage, Titan of Fire's Fury", "Lotus Field",
}

# Mazzi che la fonte non ha classificato: restano nei denominatori dove
# indicato, ma non compaiono mai come archetipo.
UNKNOWN_LABELS = {"", "unknown", "unk", "n/a", "na", "none", "null", "nan"}
JUNK_ARCHETYPE_NAMES = {
    "", "?????", "Paper Decklist", "MTGO Decklist", "Decklist",
    "Unknown", "Untitled Deck", "Modern Deck", "New Deck",
}

# Su melee.gg decklist_name porta il prefisso colore ("Mono-Green Amulet
# Titan"); si toglie solo se il nome risultante e' un archetipo non ambiguo.
UNAMBIGUOUS_DECKLIST_NAMES = {
    "Amulet Titan", "Domain Zoo", "Goryo's Vengeance", "Goryo's",
    "Eldrazi Ramp", "Eldrazi Tron", "Eldrazi Aggro", "Eldrazi Broodscale",
    "Broodscale", "Ruby Storm", "Grinding Breach", "Birthing Ritual",
    "Samwise Gamgee Combo", "Samwise Combo", "Living End", "Belcher",
    "Affinity", "Hardened Scales", "Yawgmoth",
}
DECKLIST_NAME_TYPOS = {"roodscale": "Broodscale"}

# Il campo "archetype" di melee.gg e' generico ("Energy", "Domain"): alias
# verso i nomi MTGGoldfish, solo per i casi non ambigui.
MELEE_ARCHETYPE_ALIASES = {
    "Energy": "Boros Energy",
    "Domain": "Domain Zoo",
    "Murktide": "Murktide Regent",
    "Goryo's": "Goryo's Vengeance",
    "Creativity": "Indomitable Creativity",
    "Ramp": "Eldrazi Ramp",
}


def normalize_decklist_name(name):
    s = str(name).strip()
    stripped = re.sub(r"^Mono-(?:White|Blue|Black|Red|Green)\s+", "", s)
    stripped = re.sub(r"^(?:[WUBRG]-){1,4}[WUBRG]\s+", "", stripped)
    stripped = DECKLIST_NAME_TYPOS.get(stripped, stripped)
    if stripped in UNAMBIGUOUS_DECKLIST_NAMES:
        return stripped
    return s


def is_unknown(series):
    return series.fillna("").astype(str).str.strip().str.lower().isin(UNKNOWN_LABELS)


def _to_naive(series):
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


@lru_cache(maxsize=None)
def melee_decks():
    """decks.csv (melee.gg): una riga per decklist, con data torneo e nome normalizzato."""
    d = pd.read_csv(CSV_DIR / "decks.csv", low_memory=False)
    d["tournament_id"] = d["tournament_id"].astype(str)
    d["date"] = _to_naive(d["tournament_start_date"])
    d["name"] = d["decklist_name"].where(d["decklist_name"].isna(),
                                         d["decklist_name"].map(normalize_decklist_name))
    return d


@lru_cache(maxsize=None)
def melee_matches():
    """matches_fixed.csv (melee.gg), stessi filtri della vecchia ranking matrix:
    decklist del giocatore nota e non segnaposto, avversario non segnaposto."""
    m = pd.read_csv(CSV_DIR / "matches_fixed.csv", low_memory=False)
    m = m[m["player_decklist_name"].notna() & (m["player_decklist_name"] != "")]
    m = m[~m["player_decklist_name"].isin(JUNK_ARCHETYPE_NAMES)]
    m = m[~m["opponent_decklist_name"].isin(JUNK_ARCHETYPE_NAMES)].copy()
    m["player"] = m["player_decklist_name"].map(normalize_decklist_name)
    m["opponent"] = m["opponent_decklist_name"].map(
        lambda x: normalize_decklist_name(x) if isinstance(x, str) else x)
    m["tournament_id"] = m["tournament_id"].astype(str)
    tid_date = melee_decks().drop_duplicates("tournament_id").set_index("tournament_id")["date"]
    m["date"] = m["tournament_id"].map(tid_date)
    return m


def decided(m):
    return m[m["outcome"].isin(["win", "loss"])]


def record(m):
    """(wins, losses, draws) di un sottoinsieme di partite."""
    o = m["outcome"]
    return int((o == "win").sum()), int((o == "loss").sum()), int((o == "draw").sum())


@lru_cache(maxsize=None)
def goldfish_decks():
    """decks_audit.csv (MTGGoldfish): archetipo, data, fonte, piazzamento."""
    g = pd.read_csv(CSV_DIR / "decks_audit.csv", low_memory=False)
    g["date"] = _to_naive(g["event_date_parsed"])
    g = g.dropna(subset=["date"]).copy()
    g["archetype"] = g["archetype"].fillna("").astype(str).str.strip()
    g["unknown"] = is_unknown(g["archetype"])
    return g


def goldfish_end():
    return goldfish_decks()["date"].max()


@lru_cache(maxsize=None)
def name_map():
    """data/archetype_name_map.csv: nome MTGGoldfish, nome melee.gg, etichetta comune."""
    return pd.read_csv(DATA_DIR / "archetype_name_map.csv")


def months_between(a, b):
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.44
