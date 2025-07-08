import json
import logging
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from .serializers import EventSerializer, EventCreateSerializer, ReviewSerializer
from django.db.models import Count,Avg
from rest_framework import status
from apps.users.serializers import UserSerializer
from .models import Event
from .models import Review
from django.db import models
from django.utils import timezone
from rest_framework.throttling import UserRateThrottle
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from rest_framework.parsers import MultiPartParser, FormParser


logger = logging.getLogger(__name__)


# create view
class EventCreateView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if request.user.role != 'seller':
            logger.warning(f"User {request.user.email} attempted to create an event without seller privileges")
            return Response({"detail": "Only sellers can create events."}, status=status.HTTP_403_FORBIDDEN)

        # Check event limit (1 event per user)
        if Event.objects.filter(user=request.user).exists():
            logger.warning(f"User {request.user.email} attempted to create more than 1 event")
            return Response(
                {"detail": "You can only create 1 event."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Process services data
        services_data = []
        if 'services' in request.data and request.data['services']:
            services_input = request.data['services']
            if isinstance(services_input, str):
                try:
                    services_data = json.loads(services_input)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.error(f"Error parsing services data: {str(e)}")
                    return Response(
                        {"services": "Invalid JSON format for services."}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif isinstance(services_input, list):
                services_data = services_input
            else:
                return Response(
                    {"services": "Services must be a list of objects."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not all(isinstance(s, dict) and 'name' in s for s in services_data):
                return Response(
                    {"services": "Each service must be an object with 'name' field."}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        data = {
            'event_title': request.data.get('event_title'),
            'brand_name': request.data.get('brand_name'),
            'description': request.data.get('description'),
            'location': request.data.get('location'),
            'logo': request.FILES.get('logo'),
            'services': services_data,
            'gallery_images': request.FILES.getlist('gallery_images', [])
        }

        serializer = EventCreateSerializer(data=data, context={'request': request})

        if not serializer.is_valid():
            logger.error(f"Event creation validation errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            event = serializer.save(user=request.user)
            logger.info(f"Event created successfully by {request.user.email}")
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while creating the event."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Get complete user data with profile image URL
        user_data = UserSerializer(request.user, context={'request': request}).data
        
        # Remove sensitive fields from the response
        user_data.pop('password', None)
        user_data.pop('confirm_password', None)
        
        # Get all events for the seller
        events = Event.objects.filter(user=request.user).prefetch_related(
            'services',
            'gallery_images'
        ).order_by('-created_at')
        
        event_serializer = EventSerializer(
            events, 
            many=True, 
            context={'request': request}
        )
        
        # Include events in user data
        user_data["events"] = event_serializer.data

        # Prepare the complete response
        response_data = {
            "message": "Event created successfully.",
            "event": EventSerializer(event, context={'request': request}).data,
            "user": user_data
        }

        return Response(response_data, status=status.HTTP_201_CREATED)

# edit view
class EventEditView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def get_object(self, pk, user):
        try:
            return Event.objects.get(pk=pk, user=user)
        except Event.DoesNotExist:
            raise Http404

    def put(self, request, pk, *args, **kwargs):
        event = self.get_object(pk, request.user)
        
        # Check seller role
        if request.user.role != 'seller':
            return Response({"detail": "Only sellers can edit events."}, status=status.HTTP_403_FORBIDDEN)
        
        # Ownership check
        if event.user != request.user:
            return Response({"detail": "You can only edit your own events."}, status=status.HTTP_403_FORBIDDEN)
        
        # Parse services data
        services_data = []
        if 'services' in request.data and request.data['services']:
            services_input = request.data['services']
            if isinstance(services_input, str):
                try:
                    services_data = json.loads(services_input)
                except (json.JSONDecodeError, TypeError):
                    return Response({"services": "Invalid JSON format for services."}, status=status.HTTP_400_BAD_REQUEST)
            elif isinstance(services_input, list):
                services_data = services_input
            else:
                return Response({"services": "Services must be a list of objects."}, status=status.HTTP_400_BAD_REQUEST)

            if not all(isinstance(s, dict) and 'name' in s for s in services_data):
                return Response({"services": "Each service must have a 'name' field."}, status=status.HTTP_400_BAD_REQUEST)

        # Build data dict for serializer
        data = {
            'event_title': request.data.get('event_title', event.event_title), 
            'brand_name': request.data.get('brand_name', event.brand_name),
            'description': request.data.get('description', event.description),
            'location': request.data.get('location', event.location),
            'services': services_data,
        }
        if 'logo' in request.FILES:
            data['logo'] = request.FILES['logo']
        else:
            # If no logo provided, keep existing
            data['logo'] = event.logo

        # Handle new gallery images uploads (up to 5)
        gallery_images = request.FILES.getlist('gallery_images')
        if gallery_images and len(gallery_images) > 5:
            return Response({"gallery_images": "You can upload a maximum of 5 images."}, status=status.HTTP_400_BAD_REQUEST)

        existing_gallery_ids = request.data.get('existing_gallery_ids')
        try:
            if existing_gallery_ids:
                existing_ids_list = json.loads(existing_gallery_ids)
                if not isinstance(existing_ids_list, list):
                    raise ValueError
        except Exception:
            return Response({"existing_gallery_ids": "Must be a JSON list of IDs."}, status=status.HTTP_400_BAD_REQUEST)

        context = {
            'request': request,
            'gallery_uploads': gallery_images,
            'existing_gallery_ids': existing_gallery_ids,
        }

        serializer = EventSerializer(event, data=data, partial=True, context=context)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        validated_data = serializer.validated_data
        validated_data['gallery_uploads'] = gallery_images  
        validated_data['existing_gallery_ids'] = existing_gallery_ids  

        try:
            updated_event = serializer.update(event, validated_data)
            response_serializer = EventSerializer(updated_event, context={'request': request})
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": "An error occurred while updating the event."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                 
# delete view
class EventDeleteView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_object(self, pk, user):
        try:
            return Event.objects.get(pk=pk, user=user)
        except Event.DoesNotExist:
            raise Http404
            
    def delete(self, request, pk, *args, **kwargs):
        event = self.get_object(pk, request.user)
        
        # Check if user is a seller
        if request.user.role != 'seller':
            logger.warning(f"User {request.user.email} attempted to delete an event without seller privileges")
            return Response({"detail": "Only sellers can delete events."}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if the event belongs to the user
        if event.user != request.user:
            logger.warning(f"User {request.user.email} attempted to delete event {pk} they don't own")
            return Response({"detail": "You can only delete your own events."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            event.delete()
            logger.info(f"Event {pk} deleted successfully by {request.user.email}")
            return Response(
                {"detail": "Event deleted successfully."}, 
                status=status.HTTP_204_NO_CONTENT
            )
        except Exception as e:
            logger.error(f"Error deleting event {pk}: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while deleting the event."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
# All events
class EventListView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            events = Event.objects.select_related('user').all()
            search_query = request.query_params.get('search', '').strip()

            if search_query:
                events = events.filter(
                    Q(brand_name__icontains=search_query) |
                    Q(user__first_name__icontains=search_query) |
                    Q(user__last_name__icontains=search_query) |
                    Q(user__first_name__icontains=search_query.split()[0]) |
                    Q(user__last_name__icontains=search_query.split()[-1])
                ).distinct()

            serializer = EventSerializer(events, many=True, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error retrieving events list: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while retrieving events."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Add to your views.py
class EventSuggestionsView(APIView):
    """View to provide search suggestions"""
    def get(self, request, *args, **kwargs):
        try:
            search_query = request.query_params.get('search', '').strip()
            suggestions = set()
            
            if len(search_query) >= 2:  # Only search if at least 2 characters
                # Get brand name suggestions
                brand_suggestions = Event.objects.filter(
                    brand_name__icontains=search_query
                ).values_list('brand_name', flat=True).distinct()[:5]
                
                # Get user name suggestions
                user_suggestions = Event.objects.filter(
                    Q(user__first_name__icontains=search_query) |
                    Q(user__last_name__icontains=search_query)
                ).select_related('user').values_list(
                    'user__first_name', 'user__last_name'
                ).distinct()[:5]
                
                # Format user names
                for first, last in user_suggestions:
                    suggestions.add(f"{first} {last}")
                
                suggestions.update(brand_suggestions)
            
            return Response(list(suggestions)[:8], status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error retrieving suggestions: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while retrieving suggestions."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# details event
class EventDetailView(APIView):
    permission_classes = [AllowAny]
    def get_object(self, pk):
        try:
            return Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            raise Http404

    def get(self, request, pk, *args, **kwargs):
        try:
            event = self.get_object(pk)           
            event.view_count = models.F('view_count') + 1
            event.save()
            event.refresh_from_db()  
            
            serializer = EventSerializer(event, context={'request': request})
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Http404:
            logger.warning(f"Attempted to access non-existent event {pk}")
            return Response(
                {"detail": "Event not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving event {pk}: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while retrieving the event."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
class ReviewListPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'count': self.page.paginator.count,
            'results': data
        })

class ReviewCreateThrottle(UserRateThrottle):
    scope = 'review_create'
    rate = '3/day'


class ReviewListView(APIView):
    permission_classes = [AllowAny]
    pagination_class = ReviewListPagination

    def get_event(self, pk):
        try:
            return Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            raise Http404

    def get(self, request, event_pk, *args, **kwargs):
        """List all reviews for an event"""
        try:
            event = self.get_event(event_pk)
            reviews = event.reviews.all().order_by('-created_at')
            
            paginator = self.pagination_class()
            page = paginator.paginate_queryset(reviews, request)
            
            if page is not None:
                serializer = ReviewSerializer(page, many=True, context={'request': request})
                filtered_data = [r for r in serializer.data if r is not None]
                return paginator.get_paginated_response(filtered_data)
            
            serializer = ReviewSerializer(reviews, many=True, context={'request': request})
            filtered_data = [r for r in serializer.data if r is not None]
            return Response(filtered_data, status=status.HTTP_200_OK)
            
        except Http404:
            return Response(
                {"detail": "Event not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving reviews: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while retrieving reviews."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReviewCreateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ReviewCreateThrottle]

    def get_event(self, pk):
        try:
            return Event.objects.get(pk=pk)
        except Event.DoesNotExist:
            raise Http404

    def post(self, request, event_pk, *args, **kwargs):
        try:
            event = self.get_event(event_pk)
            logger.info(f"Creating review for event {event_pk} by user {request.user.id}")

            if Review.objects.filter(event=event, user=request.user).exists():
                logger.warning("Duplicate review attempt")
                return Response(
                    {"detail": "You have already reviewed this event."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            logger.debug(f"Request data: {request.data}")
            serializer = ReviewSerializer(data=request.data, context={'request': request})

            if not serializer.is_valid():
                logger.error(f"Serializer errors: {serializer.errors}")
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            serializer.save(user=request.user, event=event)
            logger.info("Review created successfully")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception("Error in ReviewCreateView")
            return Response(
                {"detail": "Internal server error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReviewEditView(APIView):
    permission_classes = [IsAuthenticated]

    def get_review(self, event_id, user):
        try:
            return Review.objects.get(event_id=event_id, user=user)
        except Review.DoesNotExist:
            raise Http404

    def patch(self, request, pk, *args, **kwargs):
        """Update a review for the specified event"""
        try:
            review = self.get_review(pk, request.user)
            
            time_since_creation = timezone.now() - review.created_at
            if time_since_creation.days > 0 and not request.user.is_staff:
                return Response(
                    {"detail": "Reviews can only be edited within 24 hours of creation."},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            serializer = ReviewSerializer(review, data=request.data, partial=True, context={'request': request})
            
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
            serializer.save()
            return Response(serializer.data)
            
        except Http404:
            return Response(
                {"detail": "Review not found for this event."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error updating review: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while updating the review."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ReviewDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def get_review(self, review_pk):
        try:
            return Review.objects.get(pk=review_pk)
        except Review.DoesNotExist:
            raise Http404

    def delete(self, request, pk, review_pk, *args, **kwargs):
        try:
            review = self.get_review(review_pk)

            if review.user != request.user and not request.user.is_staff:
                return Response(
                    {"detail": "You can only delete your own reviews."},
                    status=status.HTTP_403_FORBIDDEN
                )

            review.delete()
            return Response(
                {"detail": "Review deleted successfully."},
                status=status.HTTP_204_NO_CONTENT
            )

        except Http404:
            return Response(
                {"detail": "Review not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error deleting review: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while deleting the review."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# dashboards views         
class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        if request.user.role != 'seller':
            logger.warning(f"User {request.user.email} attempted to access dashboard without seller privileges")
            return Response(
                {"detail": "Only sellers can access the dashboard."}, 
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Get all seller's events (changed from first() to support multiple events)
            events = Event.objects.filter(user=request.user)
            
            if not events.exists():
                return Response(
                    {"detail": "You don't have any events yet."},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Initialize response data structure
            data = {
                'events': [],
                'aggregated_stats': {
                    'total_views': 0,
                    'total_reviews': 0,
                    'average_rating': 0,
                    'total_comments': 0,
                    'total_events': events.count()
                }
            }

            # Process each event
            for event in events:
                reviews = event.reviews.all()
                review_count = reviews.count()
                average_rating = reviews.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
                comment_count = reviews.exclude(comment__exact='').count()

                # Get recent approved reviews
                recent_reviews = reviews.filter(is_approved=True).order_by('-created_at')[:5]
                recent_reviews_data = ReviewSerializer(recent_reviews, many=True, context={'request': request}).data

                # Prepare event data
                event_data = {
                    'id': event.id,
                    'brand_name': event.brand_name,
                    'logo': request.build_absolute_uri(event.logo.url) if event.logo else None,
                    'location': event.location,
                    'is_active': event.is_active,
                    'stats': {
                        'view_count': event.view_count,
                        'review_count': review_count,
                        'average_rating': round(average_rating, 1),
                        'comment_count': comment_count,
                    },
                    'recent_reviews': recent_reviews_data
                }
                data['events'].append(event_data)

                # Update aggregated stats
                data['aggregated_stats']['total_views'] += event.view_count
                data['aggregated_stats']['total_reviews'] += review_count
                data['aggregated_stats']['total_comments'] += comment_count

            # Calculate overall average rating
            if data['aggregated_stats']['total_reviews'] > 0:
                total_rating = sum(event['stats']['average_rating'] * event['stats']['review_count'] 
                                 for event in data['events'])
                data['aggregated_stats']['average_rating'] = round(
                    total_rating / data['aggregated_stats']['total_reviews'], 
                    1
                )

            # Add rating distribution if needed
            if data['aggregated_stats']['total_reviews'] > 0:
                rating_counts = Review.objects.filter(event__in=events)\
                    .values('rating')\
                    .annotate(count=Count('rating'))\
                    .order_by('rating')
                data['aggregated_stats']['rating_distribution'] = {
                    str(item['rating']): item['count'] for item in rating_counts
                }

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error generating dashboard for user {request.user.email}: {str(e)}", exc_info=True)
            return Response(
                {"detail": "An error occurred while generating dashboard data."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        