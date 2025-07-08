from rest_framework import serializers
from .models import User
from django.contrib.auth.hashers import make_password
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import random
import logging
from apps.core.serializers import EventSerializer

# Initialize logger
logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
   
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text="Password must be at least 8 characters long"
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Must match the password field"
    )

    profile_image = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text="User profile image"
    )
    
    events = EventSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'mobile_no', 
                 'password', 'confirm_password', 'profile_image', 'accepted_terms', 'events']
        extra_kwargs = {
            'email': {
                'required': True,
                'help_text': "A valid email address"
            },
            'first_name': {
                'required': True,
                'help_text': "First name is required"
            },
            'last_name': {
                'required': True,
                'help_text': "Last name is required"
            },
            'role': {
                'required': True,
                'help_text': "User role (admin, seller, or customer)"
            },
            'mobile_no': {
                'required': True,
                'help_text': "Mobile number is required"
            },
            'accepted_terms': {
                'required': True,
                'help_text': "You must accept the terms and conditions"
            }
        }
        
    def validate(self, attrs):
        errors = {}

        # Password validation
        if attrs['password'] != attrs['confirm_password']:
            errors['confirm_password'] = "Passwords do not match."
        
        if len(attrs['password']) < 8:
            errors['password'] = "Password must be at least 8 characters long."

        # Email validation
        if User.objects.filter(email=attrs['email']).exists():
            errors['email'] = {
                "message": "This email is already registered.",
                "suggestion": "Please try logging in or use password recovery if you've forgotten your credentials."
            }

        # Mobile number validation
        if not attrs['mobile_no'].isdigit():
            errors['mobile_no'] = "Mobile number must contain only digits."

        # Terms acceptance validation
        if not attrs.get('accepted_terms', False):
            errors['accepted_terms'] = "You must accept the terms and conditions to register."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        validated_data['password'] = make_password(validated_data['password'])

        validated_data['otp'] = str(random.randint(100000, 999999))
        validated_data['token_created_at'] = timezone.now()
        validated_data['is_verified'] = False

        try:
            print("DEBUG: Creating user with data:", validated_data)
            user = super().create(validated_data)
            print("DEBUG: Created user:", user)
            self._send_otp_email(user)
            return user
        except Exception as e:
            print("ERROR:", e)  # <-- This should show the real error in your terminal
            logger.error(f"User creation failed for {validated_data['email']}: {str(e)}")
            raise serializers.ValidationError(
                {"error": "Account creation failed. Please try again later."}
            )

    def _send_otp_email(self, user):
        """Sends an HTML email with embedded CSS containing the OTP."""
        try:
            subject = f"{settings.SITE_NAME} - Email Verification Code"
            from_email = f"{settings.SITE_NAME} <{settings.DEFAULT_FROM_EMAIL}>"
            to_email = [user.email]

            context = {
                'site_name': settings.SITE_NAME,
                'user_email': user.email,
                'otp': user.otp,
                'expiry_minutes': settings.OTP_EXPIRY_MINUTES,
            }

            text_content = f"""
Hello {user.email},

Thank you for registering with {settings.SITE_NAME}!

Your verification code is: {user.otp}

This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes.

If you didn't request this code, please ignore this email.

Regards,
The {settings.SITE_NAME} Team
            """

            html_content = render_to_string("emails/otp_email.html", context)

            email = EmailMultiAlternatives(subject, text_content.strip(), from_email, to_email)
            email.attach_alternative(html_content, "text/html")
            email.send()

            logger.info(f"OTP email sent to {user.email}")

        except Exception as e:
            logger.error(f"Failed to send OTP email to {user.email}: {str(e)}")
            raise serializers.ValidationError(
                {"error": "Failed to send verification email. Please try again later."}
            )

    def resend_otp(self, user):
        """Regenerate and send a new OTP to the user"""
        user.otp = str(random.randint(100000, 999999))
        user.token_created_at = timezone.now()
        user.save()
        
        try:
            self._send_otp_email(user)
            return True
        except Exception as e:
            logger.error(f"Failed to resend OTP to {user.email}: {str(e)}")
            return False

    def send_password_reset_otp(self, user):
        """Generate and send OTP for password reset"""
        user.otp = str(random.randint(100000, 999999))
        user.token_created_at = timezone.now()
        user.save()
        
        try:
            self._send_password_reset_email(user)
            return True
        except Exception as e:
            logger.error(f"Failed to send password reset OTP to {user.email}: {str(e)}")
            return False

    def _send_password_reset_email(self, user):
        """Sends password reset email with OTP"""
        try:
            subject = f"{settings.SITE_NAME} - Password Reset Code"
            from_email = f"{settings.SITE_NAME} <{settings.DEFAULT_FROM_EMAIL}>"
            to_email = [user.email]

            context = {
                'site_name': settings.SITE_NAME,
                'user_email': user.email,
                'otp': user.otp,
                'expiry_minutes': settings.OTP_EXPIRY_MINUTES,
            }

            text_content = f"""
Hello {user.email},

You requested a password reset for your {settings.SITE_NAME} account.

Your password reset code is: {user.otp}

This code will expire in {settings.OTP_EXPIRY_MINUTES} minutes.

If you didn't request this password reset, please ignore this email.

Regards,
The {settings.SITE_NAME} Team
            """

            html_content = render_to_string("emails/password_reset_email.html", context)

            email = EmailMultiAlternatives(subject, text_content.strip(), from_email, to_email)
            email.attach_alternative(html_content, "text/html")
            email.send()

            logger.info(f"Password reset OTP email sent to {user.email}")

        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
            raise
        
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'mobile_no', 'profile_image']
        extra_kwargs = {
            'email': {'read_only': True},  
        }