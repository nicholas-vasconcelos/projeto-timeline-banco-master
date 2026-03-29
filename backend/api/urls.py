from django.urls import path
from .views import market_data_view, events_view

urlpatterns = [
     # Mounted under /api/ from core/urls.py
     path('market-data/', market_data_view),
     path('events/',      events_view),
]