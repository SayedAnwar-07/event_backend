from django.db import models
from apps.users.models import User 
from django.utils.html import strip_tags

class Service(models.Model):
    SERVICE_CHOICES = [
        ('photography', 'Photography'),
        ('cinematography', 'Cinematography'),
        ('catering', 'Catering'),
        ('lighting', 'Lighting'),
        ('dj', 'DJ'),
        ('hall_booking', 'Hall Booking'),
    ]
    name = models.CharField(max_length=50, choices=SERVICE_CHOICES)

    def __str__(self):
        return self.get_name_display()


class Event(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events') 
    event_title = models.CharField(max_length=500, default="Untitled Event")
    brand_name = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='uploads/logos', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    services = models.ManyToManyField(Service, related_name='events')
    view_count = models.PositiveIntegerField(default=0)  
    is_active = models.BooleanField(default=True)  

    def __str__(self):
        return f"{self.brand_name} (by {self.user.first_name})"

    def increment_view_count(self):
        """Helper method to increment view count"""
        self.view_count += 1
        self.save()
    def clean_description(self):
        """Returns plain text version for SEO or other uses"""
        return strip_tags(self.description)
    
    @property
    def all_reviews(self):
        """Returns all related reviews"""
        return self.reviews.all()
    
    @property
    def all_rating_count(self):
        """Returns the total number of approved reviews with a rating"""
        return self.reviews.filter(is_approved=True).count()

    @property
    def all_comment_count(self):
        """Returns the total number of approved reviews with a non-empty comment"""
        return self.reviews.filter(is_approved=True).exclude(comment__exact='').count()


class EventGallery(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='gallery_images')
    image = models.ImageField(upload_to='uploads/event_gallery', null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_primary = models.BooleanField(default=False)  
    caption = models.CharField(max_length=255, blank=True)  

    def __str__(self):
        return f"Image for {self.event.brand_name}"

    class Meta:
        verbose_name_plural = "Event Galleries"
        ordering = ['-is_primary', '-uploaded_at']


class Review(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_reviews')
    rating = models.PositiveSmallIntegerField()  
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  
    is_approved = models.BooleanField(default=True) 

    class Meta:
        unique_together = ('event', 'user')  
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.first_name}'s review for {self.event.brand_name} - {self.rating}★"

    def save(self, *args, **kwargs):
        """Ensure rating is between 1 and 5"""
        if self.rating not in range(1, 6):
            raise ValueError("Rating must be between 1 and 5")
        super().save(*args, **kwargs)