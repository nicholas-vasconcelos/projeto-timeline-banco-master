import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from query import query_rag

OUTPUT_DIR   = Path(__file__).parent / "output"
EVENTS_FILE  = OUTPUT_DIR / "events.json"
MANUAL_FILE  = OUTPUT_DIR / "events_manual.json"
OUTPUT_DIR.mkdir(exist_ok=True)

SENTIMENT_SCORE = {"bullish": 1, "neutral": 0, "bearish": -1, "crisis": -2}

CATEGORY_COLOR = {
    "regulatory": "#378ADD",
    "legal":      "#534AB7",
    "market":     "#64748b",
    "fraud":      "#ea580c",
    "governance": "#b45309",
    "arrest":     "#dc2626",
}

def _timestamp_ms(date_str: str) -> int:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0

def normalize_event(ev: dict) -> dict:
    """
    Normalise and enrich a raw event dict to schema v2.
    Handles both old single-language events (title/description)
    and new bilingual events (title_en/title_pt/description_en/description_pt).
    """
    date_str  = ev.get("date", "1970-01-01")
    sentiment = ev.get("sentiment", "neutral")
    category  = ev.get("category", "market")

    title_en = ev.get("title_en") or ev.get("title") or ""
    title_pt = ev.get("title_pt") or ev.get("title") or ""
    description_en = ev.get("description_en") or ev.get("description") or ""
    description_pt = ev.get("description_pt") or ev.get("description") or ""

    return {
        "date":             date_str,
        "timestamp_ms":     _timestamp_ms(date_str),
        "title_en":         title_en,
        "title_pt":         title_pt,
        "description_en":   description_en,
        "description_pt":   description_pt,
        "bsli3_change_pct": ev.get("bsli3_change_pct"),
        "bsli4_change_pct": ev.get("bsli4_change_pct"),
        "price_bsli4":      ev.get("price_bsli4"),
        "sentiment":        sentiment,
        "sentiment_score":  SENTIMENT_SCORE.get(sentiment, 0),
        "category":         category,
        "color":            CATEGORY_COLOR.get(category, "#64748b"),
        "sources":          ev.get("sources", []),
        "manual":           ev.get("manual", False),
    }

def deduplicate(events: list) -> list:
    """
    Merge events with the same date and similar title.
    Manual events take priority over RAG events for content fields.
    """
    seen   = {}
    result = []

    for ev in events:
        key = (ev["date"], ev["title_en"][:20].lower())
        if key in seen:
            existing = result[seen[key]]
            for field in ("bsli3_change_pct", "bsli4_change_pct", "price_bsli4"):
                if existing[field] is None and ev[field] is not None:
                    existing[field] = ev[field]
            for field in ("title_pt", "description_en", "description_pt"):
                if not existing.get(field) and ev.get(field):
                    existing[field] = ev[field]
            if ev.get("manual") and not existing.get("manual"):
                for field in ("title_en", "title_pt", "description_en", "description_pt"):
                    if ev.get(field):
                        existing[field] = ev[field]
                existing["manual"] = True
            existing["sources"] = list(set(existing["sources"] + ev["sources"]))
        else:
            seen[key] = len(result)
            result.append(ev)

    return result

def validate_bilingual(events: list) -> None:
    missing = [e for e in events if not e.get("description_pt") or not e.get("title_pt")]
    if missing:
        print(f"\n  WARNING: {len(missing)} event(s) missing Portuguese fields (UI will fall back to English):")
        for e in missing:
            print(f"     {e['date']} — {e['title_en'][:50]}")
    else:
        print("  All events have bilingual content.")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--merge",       action="store_true")
    parser.add_argument("--manual-only", action="store_true")
    args = parser.parse_args()

    events = []

    if not args.manual_only:
        print("=== Step 1: RAG extraction ===")
        raw = query_rag()
        rag_events = [normalize_event(ev) for ev in raw.get("events", [])]
        print(f"RAG produced {len(rag_events)} events.")
        events.extend(rag_events)
    else:
        print("=== Skipping RAG (--manual-only) ===")

    if args.merge or args.manual_only:
        if MANUAL_FILE.exists():
            raw_manual = json.loads(MANUAL_FILE.read_text(encoding="utf-8"))
            manual_list = (raw_manual.get("events", raw_manual)
                           if isinstance(raw_manual, dict) else raw_manual)
            manual_events = [normalize_event({**ev, "manual": True})
                             for ev in manual_list]
            print(f"Loaded {len(manual_events)} manual events from {MANUAL_FILE.name}")
            events.extend(manual_events)
        else:
            print(f"  No manual file at {MANUAL_FILE} — skipping.")

    print("\n=== Step 2: Post-processing ===")
    events = deduplicate(events)
    events.sort(key=lambda e: e["date"])
    print(f"  {len(events)} events after dedup + sort.")
    validate_bilingual(events)

    output = {
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "total_events":   len(events),
        "schema_version": "2.0",
        "events":         events,
    }

    EVENTS_FILE.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {EVENTS_FILE}")
    print("Schema version: 2.0 (bilingual EN/PT)")
    if events:
        s = events[0]
        print(f"\nSample (first event):")
        print(f"  {s['date']}  title_en: {s['title_en']}")
        print(f"             title_pt: {s['title_pt']}")

if __name__ == "__main__":
    main()