import json
import os
import logging
from django.http import JsonResponse
from django.conf import settings

logger = logging.getLogger(__name__)

def get_market_data(request):
    """
    Serves the pre-calculated market data from the Phase 1 JSON cache.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    # Assumes brb_market_data.json is in the root directory alongside manage.py
    file_path = os.path.join(settings.BASE_DIR, 'brb_market_data.json')
    
    try:
        if not os.path.exists(file_path):
            logger.error(f"Cache file missing: {file_path}")
            return JsonResponse({"error": "Data cache not found. Run the Phase 1 pipeline first."}, status=404)
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # safe=False is required because our data is a List of dicts, not a single dict
        return JsonResponse(data, safe=False, status=200)
        
    except json.JSONDecodeError as e:
        logger.error(f"Corrupted JSON cache: {str(e)}")
        return JsonResponse({"error": "Data cache is corrupted."}, status=500)
    except Exception as e:
        logger.error(f"Unexpected error serving market data: {str(e)}")
        return JsonResponse({"error": "Internal server error."}, status=500)