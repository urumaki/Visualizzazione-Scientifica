#!/usr/bin/env python3
import argparse
import html
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

SEARCH_URL = (
    "https://www.mtggoldfish.com/tournament_searches/create?"
    "tournament_search%5Bname%5D=&tournament_search%5Bformat%5D=modern&"
    "tournament_search%5Bdate_range%5D=08%2F13%2F2020+-+08%2F27%2F2026&commit=Search"
)
MAX_PAGES = 321
CHECKPOINT_FILE = ".scrape_checkpoint.json"


def sanitize_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._()\- ]+", " ", value or "untitled")
    return re.sub(r"\s+", " ", cleaned).strip()[:120]


def normalize_tournament_slug(href: str) -> str:
    return (href or "").replace("/tournament/", "").strip().lower()


def load_checkpoint(output_dir: Path) -> dict:
    checkpoint_path = output_dir / CHECKPOINT_FILE
    if not checkpoint_path.exists():
        return {"completed": [], "failed": []}
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("completed"), list):
            return payload
    except Exception:
        pass
    return {"completed": [], "failed": []}


def save_checkpoint(output_dir: Path, completed_slugs: set[str], failed_slugs: set[str]) -> None:
    checkpoint_path = output_dir / CHECKPOINT_FILE
    payload = {"completed": sorted(completed_slugs), "failed": sorted(failed_slugs)}
    checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_already_downloaded_slugs(output_dir: Path) -> set[str]:
    downloaded = set()
    for base in [output_dir, output_dir / "MTGO"]:
        if not base.exists() or not base.is_dir():
            continue
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            slug = sanitize_name(entry.name).lower()
            if slug:
                downloaded.add(slug)
    return downloaded


def remove_duplicate_tournament_dirs(output_dir: Path) -> int:
    removed = 0
    for base in [output_dir, output_dir / "MTGO"]:
        if not base.exists() or not base.is_dir():
            continue
        for entry in list(base.iterdir()):
            if not entry.is_dir():
                continue
            if "(1)" not in entry.name:
                continue
            canonical_name = entry.name.replace("(1)", "").strip()
            canonical_dir = base / canonical_name
            if canonical_dir.exists() and canonical_dir.is_dir():
                for child in entry.iterdir():
                    child.unlink(missing_ok=True) if child.is_file() else None
                entry.rmdir()
                removed += 1
    return removed


def fetch_tournament_links(limit: int | None = None, max_pages: int = MAX_PAGES):
    seen = set()
    collected = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})
        for page_number in range(1, max_pages + 1):
            page_url = SEARCH_URL if page_number == 1 else f"{SEARCH_URL}&page={page_number}"
            for attempt in range(3):
                try:
                    page.goto(page_url, wait_until="domcontentloaded", timeout=90000)
                    break
                except Exception as exc:
                    print(f"Retry page {page_number} (attempt {attempt + 1}/3): {exc}", flush=True)
                    if attempt == 2:
                        raise
                    page.wait_for_timeout(3000)
            hrefs = page.locator('a[href^="/tournament/"]').evaluate_all(
                "els => [...new Set(els.map(el => el.getAttribute('href')))]"
            )
            if not hrefs and page_number > 1:
                print(f"No tournament links found on page {page_number}; stopping pagination.", flush=True)
                break
            for href in hrefs:
                if not href or href in seen:
                    continue
                seen.add(href)
                collected.append(href)
                if limit is not None and len(collected) >= limit:
                    browser.close()
                    return collected
        browser.close()
    return collected


def fetch_widget_deck(page, deck_id: str):
    payload = page.evaluate(
        r'''
        async ({ deckId }) => {
          const res = await fetch(`/widgets/deck/js?domId=deck-${deckId}&deckId=${encodeURIComponent(deckId)}`, {
            credentials: 'same-origin',
            headers: {
              'Accept': 'text/javascript, application/javascript, */*; q=0.01',
              'X-Requested-With': 'XMLHttpRequest'
            }
          });
          if (!res.ok) {
            throw new Error(`status ${res.status}`);
          }
          const raw = await res.text();
          const cleaned = raw
            .replace(/\\"/g, '"')
            .replace(/\\'/g, "'")
            .replace(/\\n/g, '\n')
            .replace(/\\\//g, '/');
          const deckInput = (cleaned.match(/name="deck_input\[deck\]".*?value="(.*?)"\s+autocomplete="off"/s) || [null, ''])[1];
          const deckName = (cleaned.match(/name="deck_input\[name\]".*?value="(.*?)"\s+autocomplete="off"/s) || [null, ''])[1];
          const author = (cleaned.match(/<span class=['\"]author['\"]>by\s*(.*?)<\/span>/is) || [null, 'unknown'])[1];
          const paper = (cleaned.match(/<div class=['\"]deck-price-v2 paper['\"][^>]*>([\s\S]*?)<\/div>/is) || [null, 'N/A'])[1];
          const online = (cleaned.match(/<div class=['\"]deck-price-v2 online['\"][^>]*>([\s\S]*?)<\/div>/is) || [null, 'N/A'])[1];
          const archetype = (cleaned.match(/Archetype:\s*<a[^>]*href="[^"]*\/archetype\/[^\"]*">([^<]+)<\/a>/is) || [null, 'Unknown'])[1];
          return { deckInput, deckName, author, paper, online, archetype };
        }
        ''',
        {"deckId": deck_id},
    )
    return {
        "deckInput": html.unescape((payload["deckInput"] or "").replace("&#39;", "'")),
        "deckName": html.unescape((payload["deckName"] or "Unknown").replace("&#39;", "'")),
        "author": html.unescape((payload["author"] or "unknown").replace("&#39;", "'")),
        "paper": re.sub(r"<[^>]+>", " ", payload["paper"] or "N/A").replace("\u00a0", " ").replace("\xa0", " ").strip(),
        "online": re.sub(r"<[^>]+>", " ", payload["online"] or "N/A").replace("\u00a0", " ").replace("\xa0", " ").strip(),
        "archetype": html.unescape((payload["archetype"] or "Unknown").replace("&#39;", "'")),
    }


def extract_tournament_metadata(page):
    return page.evaluate(
        r'''
        () => {
          const text = document.body.innerText || document.body.textContent || '';
          const dateMatch = text.match(/Date:\s*([^\n\r]+)/i);
          const date = dateMatch ? dateMatch[1].trim() : 'Unknown';
          const sourceAnchor = [...document.querySelectorAll('p a[href]')].find(el => /mtgo\.com|www\.mtgo\.com/i.test(el.href));
          const source = sourceAnchor ? sourceAnchor.href : 'Unknown';
          const title = document.querySelector('h2')?.textContent?.trim() || 'Unknown';
          return { title, date, source };
        }
        '''
    )


def build_deck_file_text(tournament_title: str, deck_name: str, author: str, event_date: str, rank: int, paper_cost: str, online_cost: str, archetype: str, source_url: str, deck_text: str) -> str:
    lines = [
        f"Tournament: {tournament_title}",
        f"Event Date: {event_date}",
        f"Deck: {deck_name}",
        f"Pilot: {author}",
        f"Rank: {rank}",
        f"Archetype: {archetype}",
        f"Paper Cost: {paper_cost}",
        f"MTGO Cost: {online_cost}",
        f"Source: {source_url}",
        "",
        deck_text.strip(),
    ]
    return "\n".join(lines) + "\n"


def write_deck(output_dir: Path, tournament_title: str, deck_name: str, author: str, event_date: str, rank: int, paper_cost: str, online_cost: str, archetype: str, source_url: str, deck_text: str, mtgo: bool):
    target_dir = output_dir / ("MTGO" if mtgo else "")
    target_dir.mkdir(parents=True, exist_ok=True)
    tournament_dir = target_dir / sanitize_name(tournament_title)
    tournament_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{rank:02d} - {sanitize_name(deck_name)} - {sanitize_name(author)}.txt"
    output_path = tournament_dir / filename
    output_path.write_text(
        build_deck_file_text(tournament_title, deck_name, author, event_date, rank, paper_cost, online_cost, archetype, source_url, deck_text),
        encoding="utf-8",
    )
    return output_path


def tournament_output_dir(output_dir: Path, tournament_title: str, mtgo: bool) -> Path:
    target_dir = output_dir / ("MTGO" if mtgo else "")
    return target_dir / sanitize_name(tournament_title)


def scrape_tournaments(limit: int | None = None, output_dir: str = "Output", max_pages: int = MAX_PAGES):
    tournament_links = fetch_tournament_links(limit=limit, max_pages=max_pages)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    removed_duplicates = remove_duplicate_tournament_dirs(output_path)
    if removed_duplicates:
        print(f"Removed {removed_duplicates} duplicate tournament folders with '(1)'.", flush=True)
    checkpoint = load_checkpoint(output_path)
    completed_slugs = {str(x).strip().lower() for x in checkpoint.get("completed", []) if str(x).strip()}
    failed_slugs = {str(x).strip().lower() for x in checkpoint.get("failed", []) if str(x).strip()}
    completed_slugs |= list_already_downloaded_slugs(output_path)
    if completed_slugs:
        save_checkpoint(output_path, completed_slugs, failed_slugs)
    pending_links = [href for href in tournament_links if normalize_tournament_slug(href) not in completed_slugs]
    failed_first_links = [href for href in pending_links if normalize_tournament_slug(href) in failed_slugs]
    fresh_links = [href for href in pending_links if normalize_tournament_slug(href) not in failed_slugs]
    pending_links = failed_first_links + fresh_links

    print(f"Starting scrape for {len(pending_links)} tournaments into '{output_dir}'", flush=True)
    print("Progress: fetching each tournament and decklist; this may take a few minutes...\n", flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})
        for idx, href in enumerate(pending_links, start=1):
            short = href.replace("/tournament/", "")
            print(f"[{idx}/{len(pending_links)}] Tournament {short}: loading page...", flush=True)
            loaded = False
            for attempt in range(10):
                try:
                    page.goto(f"https://www.mtggoldfish.com{href}", wait_until="domcontentloaded", timeout=180000)
                    loaded = True
                    break
                except Exception as exc:
                    print(f"    - Retry tournament {short} ({attempt + 1}/10): {exc}", flush=True)
                    page.wait_for_timeout(10000)
            if not loaded:
                print(f"    - Failed tournament {short}: queued in failed list for retry in next run.\n", flush=True)
                failed_slugs.add(normalize_tournament_slug(href))
                save_checkpoint(output_path, completed_slugs, failed_slugs)
                page.wait_for_timeout(250)
                continue
            failed_slugs.discard(normalize_tournament_slug(href))
            tournament_meta = extract_tournament_metadata(page)
            tournament_title = tournament_meta["title"]
            event_date = tournament_meta["date"]
            source_url = tournament_meta["source"]
            mtgo = "mtgo.com" in (source_url or "").lower()
            out_dir = tournament_output_dir(output_path, tournament_title, mtgo)
            if out_dir.exists() and any(out_dir.glob("*.txt")):
                print(f"    - Skipped: {tournament_title} (already present in output)\n", flush=True)
                completed_slugs.add(normalize_tournament_slug(href))
                failed_slugs.discard(normalize_tournament_slug(href))
                save_checkpoint(output_path, completed_slugs, failed_slugs)
                continue
            print(f"    - {tournament_title} | date={event_date} | MTGO={mtgo}", flush=True)
            rows = page.locator('.tournament-decklist-toggle').evaluate_all(
                "els => els.map((el, index) => ({ deckId: el.getAttribute('data-deckid'), rank: index + 1 }))"
            )
            deck_rank = {entry["deckId"]: entry["rank"] for entry in rows if entry.get("deckId")}
            for deck_idx, entry in enumerate(rows, start=1):
                deck_id = entry.get("deckId")
                if not deck_id:
                    continue
                print(f"      * Deck {deck_idx}/{len(rows)} ({deck_id}) downloading...", flush=True)
                deck_info = fetch_widget_deck(page, deck_id)
                deck_name = deck_info["deckName"].strip() or "Unknown"
                author = deck_info["author"].strip() or "unknown"
                deck_text = deck_info["deckInput"].strip() or ""
                paper_cost = deck_info["paper"]
                online_cost = deck_info["online"]
                archetype = deck_info["archetype"]
                write_deck(
                    output_path,
                    tournament_title,
                    deck_name,
                    author,
                    event_date,
                    entry.get("rank") or deck_rank.get(deck_id) or idx,
                    paper_cost,
                    online_cost,
                    archetype,
                    source_url,
                    deck_text,
                    mtgo,
                )
            print(f"    - Done: {tournament_title}\n", flush=True)
            completed_slugs.add(normalize_tournament_slug(href))
            failed_slugs.discard(normalize_tournament_slug(href))
            save_checkpoint(output_path, completed_slugs, failed_slugs)
            page.wait_for_timeout(250)
        browser.close()

    print("Scrape complete.", flush=True)
    return pending_links


def parse_args():
    parser = argparse.ArgumentParser(description="Download Modern tournament decklists from MTGGoldfish.")
    parser.add_argument("--limit", type=int, help="Process only the first N tournaments (useful for tests).")
    parser.add_argument("--output", default="Output", help="Directory for scraped decklists.")
    parser.add_argument("--max-pages", type=int, default=MAX_PAGES, help="Maximum number of search result pages to traverse.")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    links = scrape_tournaments(limit=args.limit, output_dir=args.output, max_pages=args.max_pages)
    print(f"Scraped {len(links)} tournaments into {args.output}.")
