from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from .models import Event, EventGallery, Service, Review, EventService
import json
import logging

logger = logging.getLogger(__name__)

def create_gallery_images(event, images):
    for image in images:
        EventGallery.objects.create(event=event, image=image)


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ['id', 'name']
        read_only_fields = ['id']

    def validate_name(self, value):
        valid_choices = [choice[0] for choice in Service.SERVICE_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError(f"Invalid service. Must be one of: {', '.join(valid_choices)}")
        return value


class EventGallerySerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = EventGallery
        fields = ['id', 'image', 'image_url', 'uploaded_at', 'is_primary', 'caption']
        read_only_fields = ['id', 'uploaded_at', 'image_url']

    def get_image_url(self, obj):
        request = self.context.get('request')
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None

    def validate(self, data):
        event = self.context.get('event')
        if event and event.gallery_images.count() >= 5:
            raise serializers.ValidationError("Maximum 5 images allowed per event")
        return data


class ReviewSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source='user.email', read_only=True)
    event_id = serializers.CharField(source='event.id', read_only=True)
    user_full_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            'id', 'user', 'user_full_name', 'profile_image', 'user_email', 'event_id',
            'rating', 'comment', 'created_at', 'updated_at', 'is_approved'
        ]
        read_only_fields = [
            'id', 'user', 'user_full_name', 'user_email', 'event_id', 'profile_image',
            'created_at', 'updated_at'
        ]

    def get_user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    def get_profile_image(self, obj):
        request = self.context.get('request')
        if obj.user.profile_image and request:
            return request.build_absolute_uri(obj.user.profile_image.url)
        return None

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def validate_comment(self, value):
        if len(value) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return value

    def validate(self, data):
        if 'rating' not in data and 'comment' not in data:
            raise serializers.ValidationError("At least one of rating or comment must be provided.")
        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        
        if not instance.is_approved:
            if not request or not request.user.is_authenticated:
                return None
            if request.user != instance.event.user and not request.user.is_staff:
                return None
        
        return data


class EventServiceSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='service.name')
    
    class Meta:
        model = EventService
        fields = ['name', 'service_short_description']
    
    def validate_name(self, value):
        valid_choices = [choice[0] for choice in Service.SERVICE_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError("Invalid service name.")
        return value


class EventSerializer(serializers.ModelSerializer):
    services = EventServiceSerializer(source='eventservice_set', many=True, required=False)
    gallery_images = EventGallerySerializer(many=True, required=False, read_only=True)
    gallery_uploads = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        max_length=5
    )
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_first_name = serializers.CharField(source='user.first_name', read_only=True)
    user_last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_profile_image = serializers.SerializerMethodField()
    user_mobile_no = serializers.CharField(source='user.mobile_no', read_only=True)
    logo_url = serializers.SerializerMethodField()
    view_count = serializers.IntegerField(read_only=True)

    all_reviews = ReviewSerializer(many=True, read_only=True)
    all_rating_count = serializers.IntegerField(read_only=True)
    all_comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Event
        fields = [
            'id', 'user', 'user_email', 'user_first_name', 'user_mobile_no', 'user_last_name',
            'user_profile_image', 
            'brand_name', 'event_title', 'description', 'location', 'logo', 'logo_url',
            'services', 'gallery_images', 'gallery_uploads',
            'created_at', 'updated_at', 'view_count', 'is_active',
            'all_reviews', 'all_rating_count', 'all_comment_count'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at', 'view_count',
            'all_reviews', 'all_rating_count', 'all_comment_count'
        ]

    def get_user_profile_image(self, obj):
        request = self.context.get('request')
        if obj.user.profile_image and request:
            return request.build_absolute_uri(obj.user.profile_image.url)
        return None

    def get_logo_url(self, obj):
        request = self.context.get('request')
        if obj.logo and request:
            return request.build_absolute_uri(obj.logo.url)
        return None

    def validate_gallery_uploads(self, value):
        if len(value) > 5:
            raise serializers.ValidationError("You can upload a maximum of 5 images.")
        return value
    
    def validate_description(self, value):
        if len(value) > 10000:
            raise serializers.ValidationError("Description is too long (max 10000 characters)")
        return value

    def create(self, validated_data):
        services_data = validated_data.pop('eventservice_set', [])
        gallery_images = validated_data.pop('gallery_uploads', [])
        
        event = Event.objects.create(**validated_data)
        
        # Create EventService records with descriptions
        for service_data in services_data:
            try:
                service = Service.objects.get(name=service_data['service']['name'])
                EventService.objects.create(
                    event=event,
                    service=service,
                    service_short_description=service_data.get('service_short_description', '')
                )
            except ObjectDoesNotExist:
                raise serializers.ValidationError(f"Service '{service_data['service']['name']}' does not exist.")

        create_gallery_images(event, gallery_images)
        return event

    def update(self, instance, validated_data):
        services_data = validated_data.pop('eventservice_set', None)
        gallery_images = validated_data.pop('gallery_uploads', [])
        existing_gallery_ids = validated_data.pop('existing_gallery_ids', None)

        # Update basic fields
        for attr, value in validated_data.items():
            if attr == 'logo' and value is None:  # Skip if logo is None (not being updated)
                continue
            setattr(instance, attr, value)
        
        try:
            instance.save()
        except Exception as e:
            raise serializers.ValidationError(f"Error saving event: {str(e)}")

        # Handle services update if provided
        if services_data is not None:
            try:
                # Get existing EventService records
                existing_services = {es.service.name: es for es in instance.eventservice_set.all()}
                
                # Process each service in update data
                for service_data in services_data:
                    try:
                        service_name = service_data['service']['name']
                        service = Service.objects.get(name=service_name)
                        
                        # Update or create EventService record
                        event_service, created = EventService.objects.get_or_create(
                            event=instance,
                            service=service,
                            defaults={
                                'service_short_description': service_data.get('service_short_description', '')
                            }
                        )
                        if not created:
                            event_service.service_short_description = service_data.get('service_short_description', '')
                            event_service.save()
                        
                        # Remove from existing services dict
                        if service.name in existing_services:
                            del existing_services[service.name]
                    
                    except Service.DoesNotExist:
                        raise serializers.ValidationError(f"Service '{service_name}' does not exist.")

                # Delete services that weren't in the update data
                for remaining_service in existing_services.values():
                    remaining_service.delete()
            except Exception as e:
                raise serializers.ValidationError(f"Error updating services: {str(e)}")

        # Handle gallery images update
        try:
            if existing_gallery_ids is not None:
                try:
                    existing_ids = json.loads(existing_gallery_ids) if isinstance(existing_gallery_ids, str) else existing_gallery_ids
                    if not isinstance(existing_ids, list):
                        existing_ids = []
                except json.JSONDecodeError:
                    existing_ids = []
                
                # Delete images not in the keep list
                instance.gallery_images.exclude(id__in=existing_ids).delete()
            
            # Add new images
            create_gallery_images(instance, gallery_images)
        except Exception as e:
            raise serializers.ValidationError(f"Error updating gallery images: {str(e)}")

        return instance


class EventCreateSerializer(serializers.ModelSerializer):
    services = EventServiceSerializer(many=True, required=False, source='eventservice_set')
    gallery_images = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False,
        max_length=5
    )

    class Meta:
        model = Event
        fields = [
            'brand_name', 'event_title', 'description', 'location', 'logo', 
            'services', 'gallery_images'
        ]

    def validate(self, data):
        required_fields = ['event_title', 'brand_name', 'description', 'location']
        for field in required_fields:
            if not data.get(field):
                raise serializers.ValidationError({field: "This field is required."})
        return data

    def validate_gallery_images(self, value):
        if len(value) > 5:
            raise serializers.ValidationError("You can upload a maximum of 5 images.")
        return value

    def create(self, validated_data):
        services_data = validated_data.pop('eventservice_set', [])
        gallery_images = validated_data.pop('gallery_images', [])

        event = Event.objects.create(**validated_data)

        for service_data in services_data:
            try:
                service = Service.objects.get(name=service_data['service']['name'])
                EventService.objects.create(
                    event=event,
                    service=service,
                    service_short_description=service_data.get('service_short_description', '')
                )
            except ObjectDoesNotExist:
                raise serializers.ValidationError(f"Service '{service_data['service']['name']}' does not exist.")

        create_gallery_images(event, gallery_images)
        return event