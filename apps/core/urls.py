from django.urls import path
from .views import (
    EventCreateView,
    EventEditView,
    EventDeleteView,
    EventListView,
    EventDetailView,
    ReviewListView,
    ReviewCreateView,
    ReviewEditView,
    ReviewDeleteView,
    DashboardView,
    EventSuggestionsView
)

urlpatterns = [
    # Public endpoints (no authentication required)
    path('events/', EventListView.as_view(), name='event-list'), 
    path('events/<int:pk>/', EventDetailView.as_view(), name='event-detail'),  
    
    # Protected endpoints (require authentication and seller role)
    path('events/suggestions/', EventSuggestionsView.as_view(), name='event-suggestions'),
    path('events/create/', EventCreateView.as_view(), name='event-create'),
    path('events/edit/<int:pk>/', EventEditView.as_view(), name='event-edit'),
    path('events/delete/<int:pk>/', EventDeleteView.as_view(), name='event-delete'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Review endpoints
    path('events/<int:event_pk>/reviews/', ReviewListView.as_view(), name='event-reviews-list'),
    path('events/<int:event_pk>/reviews/create/', ReviewCreateView.as_view(), name='event-reviews-create'),
    path('events/<int:pk>/reviews/<int:review_pk>/edit/', ReviewEditView.as_view(), name='review-edit'),
    path('events/<int:pk>/reviews/<int:review_pk>/delete/', ReviewDeleteView.as_view(), name='review-delete'),
]