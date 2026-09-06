#!/usr/bin/env python3
"""
Melee.gg Decklists table scraper (Magic: The Gathering, Modern, 2020-08-13 -> 2026-08-29)

FASE 1: scrapa solo la tabella di ricerca Decklists (~3915 pagine):
    deck_name, deck_url, player, tournament, tournament_url, date, place, record, organizer

Il "record" (W-L-D) e' gia' presente in questa tabella, quindi questa fase NON
richiede di aprire la pagina di ogni singolo giocatore (a differenza dello script
del repo GitHub, pensato per gli standings di UN torneo alla volta).

La lista carte del mazzo (main + sideboard) va presa in una FASE 2 separata,
visitando deck_url per ogni riga raccolta qui -- volutamente non inclusa in
questo script perche' moltiplica enormemente il numero di pagine da caricare.

REQUISITI:
    pip install selenium
    Chromedriver compatibile con la versione di Chrome installata, nel PATH.

USO:
    # Test rapido su 2 pagine prima di lanciare tutto:
    python scrape_melee_decklists.py --out test.csv --max-pages 2

    # Run completo (puoi interromperlo e riprenderlo, vedi --resume-page):
    python scrape_melee_decklists.py --out decklists_raw.csv

NOTE IMPORTANTI:
    - melee.gg/robots.txt disallow-a l'accesso automatizzato a /Decklists.
      Questo script usa un browser reale (non headless di default) e un
      delay conservativo tra le pagine; non maschera in alcun modo il fatto
      di essere automatizzato. La decisione se procedere e come e' tua.
    - I selettori CSS (TABLE_ROW_SELECTOR, NEXT_BUTTON_SELECTOR) sono una
      stima non verificata: la pagina e' protetta da robots.txt e non ho
      potuto ispezionarla direttamente. PRIMA del run completo, apri la
      pagina nel browser, ispeziona una riga della tabella e il bottone
      "successivo", e correggi le costanti qui sotto se necessario.
    - Con ~3915 pagine e un delay di 2-3s, il solo giro Fase 1 richiede
      circa 3-4 ore. Pianifica di conseguenza (lascia il browser aperto).
"""

import argparse
import csv
import random
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

SEARCH_URL = (
    "https://melee.gg/Decklists?q="
    "eyJnYW1lIjoiTWFnaWNUaGVHYXRoZXJpbmciLCJmb3JtYXRJZCI6IjhhMjk2MTU1LWJkMDUtNGI3Ni1iOGZjLTVmOTFhNzNkYTJhOCIsInN0YXJ0RGF0ZSI6IjIwMjAtMDgtMTJUMjI6MDA6MDAuMDAwWiIsImVuZERhdGUiOiIyMDI2LTA4LTI5VDE3OjI0OjI1LjU5NFoiLCJ0b3VybmFtZW50VHlwZSI6IlJlZ2lvbmFsIENoYW1waW9uc2hpcCBbTVRHXSJ9"
    # Filtrato: tournamentType = "Regional Championship [MTG]"
)

# --- DA VERIFICARE MANUALMENTE nel browser prima del run completo ---
TABLE_ROW_SELECTOR = "table tbody tr"
NEXT_BUTTON_SELECTOR = "a.paginate_button.next, li.next a, a[aria-label='Next']"
EXPECTED_COLUMNS = [
    "deck_name", "player", "tournament", "date", "place", "record", "organizer"
]
# ----------------------------------------------------------------------

FIELDNAMES = [
    "deck_name", "deck_url", "player", "tournament", "tournament_url",
    "date", "place", "record", "organizer",
]


def build_driver(headless: bool = False, chromedriver_path: str = None, chrome_binary: str = None):
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    if headless:
        # Sconsigliato: aumenta il rischio di essere trattati diversamente
        # dal sito rispetto a un browser "normale". Usa solo se necessario.
        options.add_argument("--headless=new")
    if chrome_binary:
        options.binary_location = chrome_binary

    if chromedriver_path:
        # Bypassa Selenium Manager (utile se il download automatico fallisce
        # dietro firewall/antivirus, es. "error decoding response body").
        from selenium.webdriver.chrome.service import Service
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    return driver


def wait_for_table(driver, timeout=20):
    WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, TABLE_ROW_SELECTOR))
    )


def extract_rows(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, TABLE_ROW_SELECTOR)
    data = []
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        if len(cells) < 7:
            continue  # riga non valida / header interno / riga vuota

        try:
            deck_a = cells[0].find_element(By.TAG_NAME, "a")
            deck_name, deck_url = deck_a.text.strip(), deck_a.get_attribute("href")
        except NoSuchElementException:
            deck_name, deck_url = cells[0].text.strip(), ""

        player = cells[1].text.strip()

        try:
            tourn_a = cells[2].find_element(By.TAG_NAME, "a")
            tournament, tournament_url = tourn_a.text.strip(), tourn_a.get_attribute("href")
        except NoSuchElementException:
            tournament, tournament_url = cells[2].text.strip(), ""

        date = cells[3].text.strip()
        place = cells[4].text.strip()
        record = cells[5].text.strip()
        organizer = cells[6].text.strip()

        data.append({
            "deck_name": deck_name,
            "deck_url": deck_url,
            "player": player,
            "tournament": tournament,
            "tournament_url": tournament_url,
            "date": date,
            "place": place,
            "record": record,
            "organizer": organizer,
        })
    return data


def go_to_next_page(driver) -> bool:
    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, NEXT_BUTTON_SELECTOR)
    except NoSuchElementException:
        return False
    classes = (next_btn.get_attribute("class") or "").lower()
    if "disabled" in classes:
        return False
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", next_btn)
    driver.execute_script("arguments[0].click();", next_btn)
    return True


def skip_to_page(driver, current_page: int, target_page: int, delay: float):
    """Clicca 'next' finche' non si raggiunge target_page, senza scrivere righe (per --resume-page)."""
    while current_page < target_page:
        wait_for_table(driver)
        if not go_to_next_page(driver):
            raise RuntimeError(
                f"Impossibile avanzare oltre pagina {current_page} durante il resume."
            )
        current_page += 1
        time.sleep(delay)
    return current_page


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="decklists_raw.csv")
    parser.add_argument("--delay", type=float, default=2.5, help="Delay base tra pagine (s)")
    parser.add_argument("--max-pages", type=int, default=None, help="Ferma dopo N pagine (per test)")
    parser.add_argument("--resume-page", type=int, default=1,
                         help="Riparti da questa pagina invece che da 1 (per riprendere un run interrotto)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--chromedriver-path", default=None,
                         help=r"Es: C:\WebDriver\chromedriver.exe (bypassa il download automatico)")
    parser.add_argument("--chrome-binary", default=None,
                         help="Path a chrome.exe, solo se Chrome non e' nella posizione standard")
    args = parser.parse_args()

    driver = build_driver(
        headless=args.headless,
        chromedriver_path=args.chromedriver_path,
        chrome_binary=args.chrome_binary,
    )
    driver.get(SEARCH_URL)
    wait_for_table(driver)

    current_page = 1
    if args.resume_page > 1:
        print(f"Salto fino a pagina {args.resume_page}...")
        current_page = skip_to_page(driver, current_page, args.resume_page, args.delay)
        print(f"Ripreso da pagina {current_page}.")

    out_path = Path(args.out)
    write_header = not out_path.exists()
    f = open(out_path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    if write_header:
        writer.writeheader()

    pages_done = 0
    total_rows = 0
    try:
        while True:
            wait_for_table(driver)
            rows = extract_rows(driver)
            if not rows:
                print(f"[pagina {current_page}] 0 righe estratte: controlla i selettori CSS.")
            for r in rows:
                writer.writerow(r)
            total_rows += len(rows)
            pages_done += 1

            if pages_done % 25 == 0:
                f.flush()
                print(f"[checkpoint] pagina corrente: {current_page}, "
                      f"pagine fatte in questa run: {pages_done}, righe totali: {total_rows}. "
                      f"Per riprendere da qui: --resume-page {current_page + 1}")

            if args.max_pages and pages_done >= args.max_pages:
                print(f"Raggiunto --max-pages {args.max_pages}, stop (modalita' test).")
                break

            if not go_to_next_page(driver):
                print("Nessuna pagina successiva disponibile: fine paginazione (o selettore 'next' da correggere).")
                break

            current_page += 1
            time.sleep(args.delay + random.uniform(0, 1.0))
    finally:
        f.close()
        driver.quit()
        print(f"Fatto. Pagine scrapate in questa run: {pages_done}. Righe: {total_rows}. Output: {out_path}")


if __name__ == "__main__":
    main()
