"""
scrape.py — reads urls.txt, scrapes each page with Playwright,
converts to clean markdown, saves to ../raw_docs/<slug>.md
"""
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from markdownify import markdownify as md

URLS_FILE = Path(__file__).parent / "urls.txt"
OUT_DIR   = Path(__file__).parent.parent / "raw_docs"
OUT_DIR.mkdir(exist_ok=True)

# ── Request blocking ──────────────────────────────────────────────────────────
# These third-party scripts fire background XHRs indefinitely, which is why
# networkidle never settles on news sites. Blocking them also speeds up loads.
_BLOCK_PATTERNS = [
    # Analytics / tracking
    "google-analytics", "googletagmanager", "googlesyndication",
    "doubleclick", "facebook.net", "connect.facebook",
    "hotjar", "clarity.ms", "segment.io", "mixpanel",
    "amplitude.com", "fullstory", "newrelic", "datadog-rum",
    # Ad networks
    "googletag", "adservice", "pagead", "moatads",
    "outbrain", "taboola", "revcontent",
    # Social embed widgets
    "platform.twitter", "syndication.twitter", "staticxx.facebook",
    # Push notification services
    "onesignal", "pushcrew", "pushengage",
    # Video CDN pings (separate from the player DOM elements)
    "jwplatform", "jwpcdn", "akamaized.net/cvs",
]


def _should_block(url: str) -> bool:
    low = url.lower()
    return any(pat in low for pat in _BLOCK_PATTERNS)


# ── DOM elements to remove before HTML→markdown conversion ───────────────────
NOISE_SELECTORS = [
    # Layout chrome
    "nav", "header", "footer", "aside",
    # Cookie / paywall / newsletter banners
    ".cookie", ".paywall", ".newsletter", "[class*='cookie']",
    "[class*='paywall']", "[class*='newsletter']", "[class*='banner']",
    "[class*='popup']", "[class*='modal']", "[class*='overlay']",
    # Ads
    ".ad", ".ads", "[class*='advertisement']", "[class*='sponsored']",
    # Video players and related UI (G1, UOL, Globoplay, generic)
    "video", "figure.video", "[class*='video']", "[class*='player']",
    "[class*='media-player']", "[class*='embed']",
    "[data-type='video']", "[data-component='video']",
    # Social sharing / follow CTAs
    "[class*='social']", "[class*='share']", "[class*='whatsapp']",
    "[class*='follow']",
    # Related / recommended content rails
    "[class*='related']", "[class*='recommended']", "[class*='mais-lidas']",
    "[class*='read-more']", "[class*='leia-mais']",
    # Image captions that duplicate alt text
    "figcaption",
    # Inline scripts and styles
    "script", "style", "noscript",
]

# ── Post-conversion markdown cleaning ────────────────────────────────────────
_VIDEO_UI_LINES = {
    # Portuguese (G1, Globo, UOL, R7, Band)
    "assista também no", "assista ao próximo", "assista também",
    "assistir agora", "pular resumo", "pular abertura",
    "assistir do início", "sair do vídeo", "minimizar vídeo",
    "espelhar em outro dispositivo", "cancelar", "reveja",
    "use as teclas", "para avançar", "título:", "subtítulo:",
    # English equivalents
    "watch now", "skip intro", "minimize player", "mirror to device",
    "next video", "watch also", "full screen", "close video",
}

_NOISE_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                         # lone numbers (countdown "10")
    re.compile(r"^\s*[-–]{2,}:[-–]{2,}/[\d:]+"),        # timestamps: --:--/00:00
    re.compile(r"^\s*[-–]{2,}:[-–]{2,}/[-–]{2,}:[-–]{2,}"),  # --:--/--:--
    re.compile(r"^\s*AGORA\s*$", re.IGNORECASE),         # "AGORA" live badge
    re.compile(r"^\s*\d+\s+de\s+\d+\s*$"),              # "1 de 1" (image counter)
    re.compile(r"^\s*[✅☑️📌🔔▶️⏩⏭]\s*.*"),            # emoji-only CTAs
    re.compile(r"leia mais notícias", re.IGNORECASE),    # footer CTA
    re.compile(r"clique aqui para seguir", re.IGNORECASE),
    re.compile(r"^\s*g1\s+(política|df|sp|rj|esporte)", re.IGNORECASE),
    re.compile(r"^\s*[-*]?\s*(Envie sua notícia|Erramos\?|Ombudsman)", re.IGNORECASE),
    re.compile(r"^\s*[—\-]\s*Foto:\s*.+$", re.IGNORECASE),  # orphaned captions
]

# Hard stop: everything after these headings is off-topic "related articles"
_FOOTER_RAIL_HEADINGS = re.compile(
    r"^\s*#{1,4}\s*(últimas notícias|leia também|veja também|mais lidas|"
    r"relacionadas|continue lendo|você também pode gostar)",
    re.IGNORECASE,
)

_MD_IMAGE = re.compile(r"^!\[.*?\]\(.*?\)\s*$")


def clean_markdown(text: str) -> str:
    lines = text.splitlines()
    cleaned = []
    prev_stripped = ""

    for line in lines:
        stripped = line.strip()

        # Hard stop at footer article rails
        if _FOOTER_RAIL_HEADINGS.match(stripped):
            break

        if stripped.lower() in _VIDEO_UI_LINES:
            continue

        if any(p.search(stripped) for p in _NOISE_PATTERNS):
            continue

        # Deduplicate back-to-back identical image tags
        if _MD_IMAGE.match(stripped) and stripped == prev_stripped:
            continue

        # Deduplicate bare alt-text line immediately following its image tag
        if prev_stripped and _MD_IMAGE.match(prev_stripped):
            alt_match = re.match(r"^!\[(.*?)\]", prev_stripped)
            if alt_match and alt_match.group(1) and stripped == alt_match.group(1):
                continue

        cleaned.append(line)
        prev_stripped = stripped

    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))
    return result.strip()


def slugify(url: str) -> str:
    slug = re.sub(r"https?://", "", url)
    slug = re.sub(r"[^\w]+", "-", slug)
    return slug[:80].strip("-")


def _goto(page, url: str) -> None:
    """
    Navigate and wait for content to be ready.

    'load' fires once the DOM and blocking resources are done — reliable and
    sufficient to read article HTML. networkidle is then attempted briefly;
    on ad-heavy news pages it will almost always time out because analytics
    and tracking scripts keep firing indefinitely. That's expected and safe
    to ignore — the article is fully loaded by the time 'load' has fired.
    """
    page.goto(url, wait_until="load", timeout=30_000)
    try:
        page.wait_for_load_state("networkidle", timeout=5_000)
    except Exception:
        pass  # timeout expected on news sites; article DOM is ready


def _follow_google_news_redirect(page) -> None:
    """Google News RSS links redirect to the real article; follow the hop."""
    if "news.google." not in page.url:
        return

    meta = page.query_selector("meta[http-equiv='refresh']")
    if meta:
        content = meta.get_attribute("content") or ""
        match = re.search(r"url=([^;]+)", content, re.IGNORECASE)
        if match:
            _goto(page, match.group(1).strip())
            return

    link = page.query_selector("a[href]")
    if link:
        href = link.get_attribute("href") or ""
        if href:
            _goto(page, urljoin(page.url, href))


def scrape_url(page, url: str) -> str:
    try:
        _goto(page, url)
        _follow_google_news_redirect(page)

        for sel in NOISE_SELECTORS:
            for el in page.query_selector_all(sel):
                el.evaluate("el => el.remove()")

        for candidate in ["article", "main", ".article-body", ".content", "body"]:
            el = page.query_selector(candidate)
            if el:
                html = el.inner_html()
                break
        else:
            html = page.content()

        raw_markdown = md(html, heading_style="ATX", strip=["a", "img"])
        return clean_markdown(raw_markdown)

    except Exception as e:
        print(f"  ERROR scraping {url}: {e}")
        return ""


def main():
    urls = [u.strip() for u in URLS_FILE.read_text().splitlines()
            if u.strip() and not u.startswith("#")]
    print(f"Scraping {len(urls)} URLs...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 Chrome/120 Safari/537.36"
        )
        page = context.new_page()

        # Block analytics, ads, and tracking — the primary cause of networkidle
        # never settling, and completely irrelevant to article content.
        page.route("**/*", lambda route: (
            route.abort() if _should_block(route.request.url) else route.continue_()
        ))

        for i, url in enumerate(urls, 1):
            slug = slugify(url)
            out_path = OUT_DIR / f"{slug}.md"
            if out_path.exists():
                print(f"[{i}/{len(urls)}] SKIP (cached): {slug}")
                continue
            print(f"[{i}/{len(urls)}] Scraping: {url}")
            text = scrape_url(page, url)
            if text and len(text) > 100:  # sanity check to avoid saving empty or near-empty files
                header = f"---\nsource_url: {url}\n---\n\n"
                out_path.write_text(header + text, encoding="utf-8")
                print(f"  Saved {len(text):,} chars → {out_path.name}")
            else:
                print(f"  WARN: too little content, skipping")

        browser.close()
    print("Done.")


if __name__ == "__main__":
    main()