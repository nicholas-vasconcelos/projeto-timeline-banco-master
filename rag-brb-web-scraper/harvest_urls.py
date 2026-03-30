import json
import re
import time
import argparse
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ── Configuration ────────────────────────────────────────────────────────────
DEFAULT_JSON      = Path(__file__).parent / "brb_market_data.json"
OUTPUT_URLS_FILE  = Path(__file__).parent / "scraper" / "urls.txt"
SPIKE_THRESHOLD   = 5.0   # % absolute price change to flag as spike
VOLUME_MULTIPLIER = 3.0   # volume ratio vs previous day to flag as spike
SEARCH_WINDOW     = 2     # days before/after spike to search (catches T-1 articles)
MAX_URLS_PER_DATE = 5     # maximum URLs to collect per spike date
REQUEST_DELAY     = 2.0   # seconds between requests (be polite to Google)

MONTH_BR = {
    "01": "janeiro", "02": "fevereiro", "03": "março",  "04": "abril",
    "05": "maio",    "06": "junho",     "07": "julho",   "08": "agosto",
    "09": "setembro","10": "outubro",   "11": "novembro","12": "dezembro",
}

# High-quality Brazilian financial news domains to prefer
PREFERRED_DOMAINS = [
    "infomoney.com.br",
    "valoreconomico.com.br",
    "valor.com.br",
    "estadao.com.br",
    "folha.uol.com.br",
    "oglobo.globo.com",
    "exame.com",
    "bloomberg.com.br",
    "moneytimes.com.br",
    "investing.com",
    "b3.com.br",
    "cvm.gov.br",
    "bcb.gov.br",           # Central Bank official releases
    "cov.com",              # Covington & Burling report
    "reuters.com",
    "bloomberg.com",
]

# Domains to block (aggregators, low-quality, or irrelevant)
BLOCKED_DOMAINS = [
    "youtube.com", "twitter.com", "x.com", "facebook.com",
    "instagram.com", "reddit.com", "tiktok.com",
    "br.advfn.com",  # often paywalled with poor content
]

# ── Step 1: Detect spikes from JSON ─────────────────────────────────────────
def detect_spikes(data: list, pct_threshold: float, vol_multiplier: float) -> list:
    """
    Returns list of spike dicts sorted by date.
    Flags both price spikes and volume anomalies.
    """
    spikes = []
    for i in range(1, len(data)):
        prev = data[i - 1]
        curr = data[i]
        if prev["Close"] == 0 or curr["Volume"] == 0:
            continue

        pct_change = (curr["Close"] - prev["Close"]) / prev["Close"] * 100
        vol_ratio  = curr["Volume"] / max(prev["Volume"], 1)
        intraday   = ((curr["High"] - curr["Low"]) / max(curr["Low"], 0.001)) * 100

        is_price_spike  = abs(pct_change) >= pct_threshold
        is_volume_spike = vol_ratio >= vol_multiplier and abs(pct_change) >= 2.0

        if is_price_spike or is_volume_spike:
            spikes.append({
                "date":          curr["Date"],
                "pct_change":    round(pct_change, 2),
                "close":         round(curr["Close"], 2),
                "prev_close":    round(prev["Close"], 2),
                "volume":        int(curr["Volume"]),
                "vol_ratio":     round(vol_ratio, 1),
                "intraday_pct":  round(intraday, 1),
                "direction":     "bullish" if pct_change > 0 else "bearish",
                "trigger":       "price" if is_price_spike else "volume",
            })

    return sorted(spikes, key=lambda x: x["date"])


# ── Step 2: Build search queries per spike date ───────────────────────────────
def build_queries(spike: dict) -> list[str]:
    """
    Returns multiple search queries for a spike date.
    Searches a ±2-day window to catch preview and reaction articles.
    """
    date  = spike["date"]
    y, m, d = date.split("-")
    month = MONTH_BR[m]

    # Determine context based on known timeline knowledge
    context_queries = {
        "2025-08-04": ["BRB BSLI aprovação legislativa agosto 2025"],
        "2025-08-20": ["BRB CLDF PL aprovação agosto 2025 Banco Master"],
        "2025-09-03": ["Banco Central rejeita aquisição BRB Banco Master setembro 2025"],
        "2025-09-04": ["BSLI queda BACEN veto Banco Master setembro 2025"],
        "2025-11-17": ["Vorcaro preso Guarulhos Operação Compliance Zero"],
        "2025-11-18": ["Banco Master liquidação extrajudicial Banco Central novembro 2025"],
        "2025-11-25": ["BRB BSLI queda novembro 2025 Banco Master"],
        "2025-12-12": ["BRB BSLI ações dezembro 2025 Banco Master investigação"],
        "2026-01-30": ["BRB capitalização janeiro 2026 Banco Master rombo"],
        "2026-02-09": ["BRB BSLI4 queda 13% plano recapitalização fevereiro 2026"],
        "2026-03-03": ["Vorcaro preso novamente março 2026 STF BRB"],
        "2026-03-17": ["BRB aumento capital março 2026 ações BSLI"],
    }

    queries = []

    # Add context-specific queries if we know the event
    if date in context_queries:
        queries.extend(context_queries[date])

    # Generic date-based queries in Portuguese
    queries += [
        f'BRB "Banco de Brasília" BSLI {d} {month} {y}',
        f'"Banco Master" BRB {d} {month} {y}',
        f'BSLI3 OR BSLI4 {d} {month} {y}',
        f'"Banco Master" {month} {y} notícias',
    ]

    # English fallback (for Bloomberg, Reuters, Covington etc.)
    queries.append(f'"Banco Master" BRB {y} {month}')

    return queries


# ── Step 3: Google News RSS fetch (no API key required) ───────────────────────
def fetch_google_news_rss(query: str) -> list[dict]:
    """
    Fetches Google News RSS for a query.
    Returns list of {title, url, published} dicts.
    No API key required — uses the public Google News RSS endpoint.
    """
    encoded = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=pt-BR&gl=BR&ceid=BR:pt-419"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    }

    try:
        req  = urllib.request.Request(rss_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el  = item.find("link")
            pub_el   = item.find("pubDate")
            if title_el is not None and link_el is not None:
                url = link_el.text or ""
                # Google News wraps URLs — extract the real URL
                url = resolve_google_news_url(url)
                items.append({
                    "title":     title_el.text or "",
                    "url":       url,
                    "published": pub_el.text if pub_el is not None else "",
                })
        return items
    except Exception as e:
        print(f"    RSS fetch error for '{query[:50]}': {e}")
        return []


def resolve_google_news_url(url: str) -> str:
    """
    Google News RSS links are wrapped in a redirect.
    Extract the actual destination URL from the query string.
    """
    if "news.google.com" not in url:
        return url
    # Try to parse the URL query param
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    if "url" in params:
        return params["url"][0]
    # Fallback: return as-is (Playwright scraper will follow the redirect)
    return url


# ── Step 4: Filter and score URLs ────────────────────────────────────────────
def score_url(url: str, title: str, spike_date: str) -> float:
    """
    Score a URL for relevance. Higher = better.
    Returns -1 to reject.
    """
    url_lower = url.lower()

    # Hard block
    for blocked in BLOCKED_DOMAINS:
        if blocked in url_lower:
            return -1.0

    score = 0.0

    # Prefer high-quality domains
    for preferred in PREFERRED_DOMAINS:
        if preferred in url_lower:
            score += 3.0
            break

    # Title relevance signals
    title_lower = title.lower()
    for kw in ["brb", "bsli", "banco master", "vorcaro", "compliance zero",
               "bacen", "banco de brasília", "liquidação", "capitalização"]:
        if kw in title_lower:
            score += 1.5

    # Penalise very generic results
    for generic in ["mercado hoje", "bolsa hoje", "ibovespa"]:
        if generic in title_lower and "brb" not in title_lower:
            score -= 2.0

    return score


def filter_urls(candidates: list[dict], spike_date: str,
                max_urls: int) -> list[dict]:
    scored = []
    for item in candidates:
        s = score_url(item["url"], item["title"], spike_date)
        if s >= 0:
            scored.append({**item, "score": s})

    # Deduplicate by domain (max 2 per domain)
    domain_count: dict[str, int] = defaultdict(int)
    deduped = []
    seen_urls = set()
    for item in sorted(scored, key=lambda x: -x["score"]):
        if item["url"] in seen_urls:
            continue
        domain = urllib.parse.urlparse(item["url"]).netloc.replace("www.", "")
        if domain_count[domain] < 2:
            deduped.append(item)
            domain_count[domain] += 1
            seen_urls.add(item["url"])
        if len(deduped) >= max_urls:
            break

    return deduped


# ── Step 5: Orchestrate and write urls.txt ────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json",      default=str(DEFAULT_JSON))
    parser.add_argument("--threshold", type=float, default=SPIKE_THRESHOLD)
    parser.add_argument("--vol-mult",  type=float, default=VOLUME_MULTIPLIER)
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--max-urls",  type=int, default=MAX_URLS_PER_DATE)
    args = parser.parse_args()

    # Load data
    data = json.loads(Path(args.json).read_text())
    print(f"Loaded {len(data)} trading days from {args.json}")

    # Detect spikes
    spikes = detect_spikes(data, args.threshold, args.vol_mult)
    print(f"Detected {len(spikes)} spike events (threshold: ±{args.threshold}%)\n")

    for s in spikes:
        direction = "▲" if s["pct_change"] > 0 else "▼"
        print(f"  {s['date']}  {direction}{s['pct_change']:+.1f}%  "
              f"vol={s['volume']:,}  ({s['trigger']} spike)")

    if args.dry_run:
        print("\n[dry-run] Showing queries that would be executed:\n")
        for spike in spikes:
            print(f"\n── {spike['date']} ({spike['pct_change']:+.1f}%) ──")
            for q in build_queries(spike):
                print(f"   SEARCH: {q}")
        return

    # Harvest URLs
    print(f"\n{'─'*60}")
    print(f"Harvesting URLs for {len(spikes)} spike dates...")
    print(f"(This will take ~{len(spikes) * 4 * REQUEST_DELAY:.0f}s due to rate limiting)")
    print(f"{'─'*60}\n")

    all_results: dict[str, list] = {}
    already_seen = set()

    for spike in spikes:
        date = spike["date"]
        print(f"\n[{date}] {spike['pct_change']:+.1f}% | vol={spike['volume']:,}")
        queries = build_queries(spike)
        candidates = []

        for query in queries:
            print(f"  Searching: {query[:70]}...")
            results = fetch_google_news_rss(query)
            print(f"    Got {len(results)} raw results")
            candidates.extend(results)
            time.sleep(REQUEST_DELAY)

        # Filter and deduplicate
        filtered = filter_urls(candidates, date, args.max_urls)
        # Remove URLs already collected for other dates
        new_filtered = [f for f in filtered if f["url"] not in already_seen]
        for f in new_filtered:
            already_seen.add(f["url"])

        all_results[date] = new_filtered
        print(f"  → Kept {len(new_filtered)} URLs for {date}")
        for item in new_filtered:
            print(f"    [{item['score']:.1f}] {item['title'][:70]}")
            print(f"          {item['url'][:80]}")

    # Write urls.txt
    OUTPUT_URLS_FILE.parent.mkdir(exist_ok=True)
    lines = [
        "# BRB / Banco Master — Auto-harvested URLs",
        f"# Generated: {datetime.now().isoformat()[:19]}",
        f"# Source JSON: {args.json}",
        f"# Spike threshold: ±{args.threshold}%",
        f"# Total URLs: {sum(len(v) for v in all_results.values())}",
        "",
    ]

    total = 0
    for date, items in sorted(all_results.items()):
        if not items:
            continue
        spike = next(s for s in spikes if s["date"] == date)
        lines.append(f"# ── {date}  {spike['pct_change']:+.1f}%  "
                     f"close={spike['close']}  vol={spike['volume']:,} ──")
        for item in items:
            lines.append(f"# {item['title'][:80]}")
            lines.append(item["url"])
            total += 1
        lines.append("")

    OUTPUT_URLS_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{'='*60}")
    print(f"Wrote {total} URLs across {len(all_results)} dates")
    print(f"Output: {OUTPUT_URLS_FILE}")
    print(f"\nNext step: python scraper/scrape.py")

if __name__ == "__main__":
    main()
