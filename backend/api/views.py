import json
import os
import logging
from pathlib import Path
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt

EVENTS_FILE = Path(__file__).resolve().parent.parent / 'data' / 'events.json'
MARKET_FILE = Path(__file__).resolve().parent.parent / 'data' / 'brb_market_data.json'

logger = logging.getLogger(__name__)

@require_GET
def market_data_view(request):
    """
    GET /api/market-data/
    Returns the full OHLCV + SMA + Volatility array from brb_market_data.json
    """
    try:
        data = json.loads(MARKET_FILE.read_text(encoding='utf-8'))
        return JsonResponse(data, safe=False)
    except FileNotFoundError:
        return JsonResponse({'error': f'Market data file not found: {MARKET_FILE}'}, status=404)
    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'JSON parse error: {e}'}, status=500)
 
 
@require_GET
def events_view(request):
    """
    GET /api/events/
    Returns the events array from events.json (schema v2, bilingual).
    Supports ?category=arrest|legal|regulatory|market|governance filter.
    """
    try:
        raw = json.loads(EVENTS_FILE.read_text(encoding='utf-8'))
        # Handle both { "events": [...] } and plain array formats
        events = raw.get('events', raw) if isinstance(raw, dict) else raw
 
        category = request.GET.get('category')
        if category:
            events = [e for e in events if e.get('category') == category]
 
        return JsonResponse(events, safe=False)
    except FileNotFoundError:
        return JsonResponse({'error': f'Events file not found: {EVENTS_FILE}'}, status=404)
    except json.JSONDecodeError as e:
        return JsonResponse({'error': f'JSON parse error: {e}'}, status=500)
 