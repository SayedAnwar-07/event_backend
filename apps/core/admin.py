from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from .models import Service, Event, EventGallery, Review,EventService

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_name_display', 'event_count', 'active_event_count') 
    list_display_links = ('id', 'get_name_display')  
    search_fields = ('name',)
    list_filter = ('name',)
    readonly_fields = ('id', 'event_count', 'active_event_count')  
    list_per_page = 20
    
    def event_count(self, obj):
        return obj.events.count()
    event_count.short_description = 'Total Events'
    event_count.admin_order_field = 'events__count'
    
    def active_event_count(self, obj):
        return obj.events.filter(is_active=True).count()
    active_event_count.short_description = 'Active Events'
    active_event_count.admin_order_field = 'events__count'
    
class EventServiceInline(admin.TabularInline):
    model = EventService
    extra = 0
    autocomplete_fields = ['service']

class EventGalleryInline(admin.TabularInline):
    model = EventGallery
    extra = 0
    readonly_fields = ('id', 'uploaded_at', 'preview_image', 'is_primary', 'caption') 
    fields = ('preview_image', 'image', 'is_primary', 'caption', 'uploaded_at', 'id')
    
    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" height="auto" />', obj.image.url)
        return "-"
    preview_image.short_description = 'Preview'

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ('id', 'user', 'rating', 'created_at', 'comment_preview', 'is_approved')
    fields = ('user', 'rating', 'comment_preview', 'is_approved', 'created_at', 'id')
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comment Preview'

class RatingFilter(admin.SimpleListFilter):
    title = 'rating'
    parameter_name = 'rating'
    
    def lookups(self, request, model_admin):
        return (
            ('4+', '4+ Stars'),
            ('3+', '3+ Stars'),
            ('2+', '2+ Stars'),
            ('1+', '1+ Stars'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == '4+':
            return queryset.filter(average_rating__gte=4)
        if self.value() == '3+':
            return queryset.filter(average_rating__gte=3)
        if self.value() == '2+':
            return queryset.filter(average_rating__gte=2)
        if self.value() == '1+':
            return queryset.filter(average_rating__gte=1)
        return queryset

class EventAdmin(admin.ModelAdmin):
    list_display = ('id', 'brand_name', 'event_title', 'user', 'location', 'created_at', 
                    'service_list', 'logo_preview', 'average_rating', 
                    'review_count', 'is_active')
    list_display_links = ('id', 'brand_name')
    list_filter = ('created_at', 'is_active', RatingFilter)
    search_fields = ('brand_name', 'user__email', 'user__first_name', 'location')
    readonly_fields = ('id', 'created_at', 'updated_at', 'logo_preview', 
                       'average_rating', 'review_count', 'view_count')
    inlines = [EventServiceInline, EventGalleryInline, ReviewInline]
    date_hierarchy = 'created_at'
    list_per_page = 20
    actions = ['activate_events', 'deactivate_events']

    fieldsets = (
        (None, {
            'fields': ('id', 'is_active')
        }),
        ('Basic Information', {
            'fields': ('user', 'event_title', 'brand_name', 'description', 'location')
        }),
        ('Media', {
            'fields': ('logo', 'logo_preview')
        }),
        ('Statistics', {
            'fields': ('view_count', 'average_rating', 'review_count'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _average_rating=Avg('reviews__rating'),
            _review_count=Count('reviews')
        )
        return queryset

    def average_rating(self, obj):
        return f"{obj._average_rating:.1f}" if obj._average_rating else "No ratings"
    average_rating.short_description = 'Avg Rating'
    average_rating.admin_order_field = '_average_rating'

    def review_count(self, obj):
        return obj._review_count
    review_count.short_description = 'Reviews'
    review_count.admin_order_field = '_review_count'

    def service_list(self, obj):
        return ", ".join([service.get_name_display() for service in obj.services.all()[:3]]) + (
            "..." if obj.services.count() > 3 else "")
    service_list.short_description = 'Services'

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="100" height="auto" />', obj.logo.url)
        return "-"
    logo_preview.short_description = 'Logo Preview'

    @admin.action(description='Activate selected events')
    def activate_events(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} events were successfully activated.')

    @admin.action(description='Deactivate selected events')
    def deactivate_events(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} events were successfully deactivated.')

class EventGalleryAdmin(admin.ModelAdmin):
    list_display = ('id', 'event_owner_email', 'event', 'is_primary', 'uploaded_at', 'preview_image', 'caption_preview')  
    list_display_links = ('id', 'event')
    list_filter = ('event__user__email', 'event__brand_name', 'uploaded_at', 'is_primary')
    search_fields = ('event__user__email', 'event__brand_name', 'caption')
    readonly_fields = ('id', 'uploaded_at', 'preview_image') 
    date_hierarchy = 'uploaded_at'
    list_editable = ('is_primary',)
    list_per_page = 20

    def event_owner_email(self, obj):
        return obj.event.user.email if obj.event and obj.event.user else "-"
    event_owner_email.short_description = 'Owner Email'
    event_owner_email.admin_order_field = 'event__user__email'

    def preview_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-width:60px; height:auto;" />', obj.image.url)
        return "-"
    preview_image.short_description = 'Preview'

    def caption_preview(self, obj):
        return obj.caption[:30] + '...' if obj.caption and len(obj.caption) > 30 else obj.caption or "-"
    caption_preview.short_description = 'Caption'


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'user', 'rating', 'is_approved', 
                   'created_at', 'comment_preview')
    list_display_links = ('id', 'event')
    list_filter = ('rating', 'created_at', 'event__brand_name', 'is_approved')
    search_fields = ('event__brand_name', 'user__email', 'comment')
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_editable = ('is_approved',)
    list_per_page = 20
    actions = ['approve_reviews', 'disapprove_reviews']
    
    fieldsets = (
        (None, {
            'fields': ('id', 'user', 'event')
        }),
        ('Review Details', {
            'fields': ('rating', 'comment', 'is_approved')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment or "-"
    comment_preview.short_description = 'Comment Preview'
    
    @admin.action(description='Approve selected reviews')
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews were successfully approved.')
    
    @admin.action(description='Disapprove selected reviews')
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews were successfully disapproved.')

admin.site.register(Service, ServiceAdmin)
admin.site.register(Event, EventAdmin)
admin.site.register(EventGallery, EventGalleryAdmin)
admin.site.register(Review, ReviewAdmin)