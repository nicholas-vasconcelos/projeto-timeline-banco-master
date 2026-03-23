from django.urls import path
from . import views

urlpatterns = [
    path('market-data/', views.get_market_data, name='market_data'),
]