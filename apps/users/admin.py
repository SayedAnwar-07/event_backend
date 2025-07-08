from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User

class CustomUserAdmin(UserAdmin):
    model = User
    list_display = (
        'email', 
        'profile_image_display', 
        'first_name', 
        'last_name', 
        'role', 
        'mobile_no', 
        'is_verified', 
        'is_staff', 
        'is_active',
        'date_joined_short'
    )
    list_filter = ('role', 'is_verified', 'is_staff', 'is_active', 'date_joined')
    search_fields = ('email', 'mobile_no', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    readonly_fields = ('date_joined', 'last_login', 'profile_image_preview')
    list_per_page = 25
    date_hierarchy = 'date_joined'
    
    # Custom display methods for admin list view
    def profile_image_display(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="width: 30px; height: 30px; border-radius: 50%;"/>',
                obj.profile_image.url
            )
        return "No Image"
    profile_image_display.short_description = 'Profile'
    
    def date_joined_short(self, obj):
        return obj.date_joined.strftime('%Y-%m-%d')
    date_joined_short.short_description = 'Joined'
    date_joined_short.admin_order_field = 'date_joined'

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {
            'fields': (
                'profile_image', 
                'profile_image_preview',
                'first_name', 
                'last_name', 
                'mobile_no'
            )
        }),
        ('Permissions', {
            'fields': (
                'role', 
                'is_verified', 
                'is_staff', 
                'is_active', 
                'is_superuser', 
                'groups', 
                'user_permissions'
            )
        }),
        ('Important Dates', {
            'fields': (
                'last_login', 
                'date_joined'
            )
        }),
        ('Verification', {
            'fields': (
                'otp', 
                'token_created_at'
            ),
            'classes': ('collapse',) 
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'email', 
                'first_name', 
                'last_name', 
                'role', 
                'mobile_no', 
                'password1', 
                'password2', 
                'is_staff', 
                'is_active'
            )
        }),
    )
    
    # Profile image preview in edit view
    def profile_image_preview(self, obj):
        if obj.profile_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; max-width: 200px;"/>',
                obj.profile_image.url
            )
        return "No image uploaded"
    profile_image_preview.short_description = 'Profile Image Preview'
    profile_image_preview.allow_tags = True

    # Custom form handling
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser
        
        if not is_superuser:
            # Restrict certain fields for non-superusers
            disabled_fields = set(['is_superuser', 'is_staff', 'groups', 'user_permissions'])
            
            for field_name in disabled_fields:
                if field_name in form.base_fields:
                    form.base_fields[field_name].disabled = True
        
        return form

    # Custom actions
    actions = [
        'mark_as_verified', 
        'mark_as_unverified',
        'activate_users',
        'deactivate_users'
    ]
    
    def mark_as_verified(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f"{updated} users were marked as verified.")
    mark_as_verified.short_description = "Mark selected users as verified"
    
    def mark_as_unverified(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f"{updated} users were marked as unverified.")
    mark_as_unverified.short_description = "Mark selected users as unverified"
    
    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} users were activated.")
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} users were deactivated.")
    deactivate_users.short_description = "Deactivate selected users"

admin.site.register(User, CustomUserAdmin)