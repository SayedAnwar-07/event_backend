import os
from django.contrib.auth.models import AbstractUser
from django.db import models
from .manager import UserManager

USER_ROLES = (
    ("admin", "Admin"),
    ("seller", "Seller"),
    ("customer", "Customer"),
)

def user_profile_upload_path(instance, filename):
    first_name = instance.first_name or "unknown"
    filename_base, ext = os.path.splitext(filename)
    return f"profiles/{first_name}/{filename_base}{ext}" 

class User(AbstractUser):
    username = None 
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(unique=True)
    
    role = models.CharField(max_length=10, choices=USER_ROLES)
    mobile_no = models.CharField(max_length=20, blank=True)
    is_verified = models.BooleanField(default=False)
    otp = models.CharField(max_length=6, blank=True, null=True)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    token_created_at = models.DateTimeField(null=True, blank=True)
    profile_image = models.ImageField(upload_to=user_profile_upload_path, blank=True, null=True)
    
    accepted_terms = models.BooleanField(
        default=False,
        verbose_name="I accept the terms and conditions",
        help_text="You must accept our terms and conditions to register"
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role', 'mobile_no', 'first_name', 'last_name']

    def __str__(self):
        return f"{self.email} ({self.role})"
