from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer,UserUpdateSerializer
from .models import User
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from utils.rate_limit import check_rate_limit
from django.utils.decorators import method_decorator
from rest_framework.permissions import IsAuthenticated
from apps.core.serializers import EventSerializer
from apps.core.models import Event
import logging
logger = logging.getLogger(__name__)

# register views
class RegisterView(APIView):
    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                return Response(
                    {
                        "success": True,
                        "message": "Registration successful! Please check your email for the verification code.",
                        "data": {
                            "email": user.email,
                            "role": user.role,
                            "is_verified": user.is_verified
                        }
                    },
                    status=status.HTTP_201_CREATED
                )
            except ValidationError as e:
                return Response(
                    {
                        "success": False,
                        "error": "Validation error",
                        "details": str(e),
                        "message": "Please correct the errors and try again."
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return Response(
                    {
                        "success": False,
                        "error": "Registration failed",
                        "message": "An unexpected error occurred. Please try again later."
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Handle serializer errors
        return Response(
            {
                "success": False,
                "error": "Invalid data",
                "details": serializer.errors,
                "message": "Please correct the errors below and try again."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

# verify OTP views
class VerifyOtpView(APIView):
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")

        if not email or not otp:
            return Response(
                {"error": "Both email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if user is already verified
        if user.is_verified:
            return Response(
                {"error": "Email is already verified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check OTP expiration (e.g., 10 minutes)
        if not user.token_created_at:
            return Response(
                {"error": "No OTP was generated for this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if timezone.now() > user.token_created_at + timedelta(minutes=10):
            return Response(
                {"error": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.otp != otp:
            return Response(
                {"error": "Invalid OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user.is_verified = True
            user.otp = None
            user.token_created_at = None
            user.save()
            
            return Response(
                {"message": "Email verified successfully."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "Failed to verify email. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# resend OTP views
class ResendOtpView(APIView):
    def post(self, request):
        ip = request.META.get('REMOTE_ADDR')
        email = request.data.get("email")

        # Rate limit: 5 per hour per IP
        if not check_rate_limit(ip, limit=5, period=3600):
            return Response(
                {"error": "Too many OTP requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            return Response({"error": "Email already verified."}, status=status.HTTP_400_BAD_REQUEST)

        # Local OTP resend limit (1-minute cooldown)
        if user.token_created_at and timezone.now() < user.token_created_at + timedelta(minutes=1):
            return Response(
                {"error": "Please wait at least 1 minute before requesting a new OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = UserSerializer()
        if serializer.resend_otp(user):
            return Response({"message": "OTP sent."}, status=status.HTTP_200_OK)
        return Response({"error": "Failed to send OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 
#  login views
class LoginView(APIView):
    def post(self, request):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response(
                {"error": "Email and password are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "User with this email does not exist."},
                status=status.HTTP_404_NOT_FOUND
            )

        if not user.is_verified:
            return Response(
                {"error": "To continue, please confirm your email using the OTP we just sent"},
                status=status.HTTP_403_FORBIDDEN
            )

        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response(
                {"error": "Invalid email or password.Please try again"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user, context={'request': request}).data
        
        user_data.pop('password', None)
        user_data.pop('confirm_password', None)
        
        if user.role == "seller":
            events = Event.objects.filter(user=user).prefetch_related(
                'services',
                'gallery_images'
            ).order_by('-created_at')
            event_serializer = EventSerializer(
                events, 
                many=True, 
                context={'request': request}
            )
            user_data["events"] = event_serializer.data

        return Response({
            "message": "Login successful.",
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": user_data
        }, status=status.HTTP_200_OK)
                
# get and update profile views
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):
        user = request.user
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Profile updated successfully.",
                "user": serializer.data
            }, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
# forgot password views  
class ForgotPasswordView(APIView):
    def post(self, request):
        ip = request.META.get('REMOTE_ADDR', '')  

        if not check_rate_limit(ip, limit=5, period=3600):
            return Response(
                {"error": "Too many password reset requests. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        email = request.data.get("email")
        if not email:
            return Response(
                {"error": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "No user is registered with this email address."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Local cooldown: 1 min between OTP sends
        if user.token_created_at and timezone.now() < user.token_created_at + timedelta(minutes=1):
            return Response(
                {"error": "Please wait at least 1 minute before requesting a new password reset OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        serializer = UserSerializer()
        if serializer.send_password_reset_otp(user):
            return Response(
                {"message": "If this email exists in our system, you'll receive a password reset OTP."},
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"error": "Failed to send password reset OTP. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
# reset password views
class ResetPasswordView(APIView):
    def post(self, request):
        email = request.data.get("email")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not all([email, otp, new_password, confirm_password]):
            return Response(
                {"error": "Email, OTP, new password and confirm password are all required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"error": "New password and confirm password do not match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid password reset request."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not user.token_created_at:
            return Response(
                {"error": "No password reset OTP was generated for this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if timezone.now() > user.token_created_at + timedelta(minutes=10):
            return Response(
                {"error": "Password reset OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.otp != otp:
            return Response(
                {"error": "Invalid OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate password strength
            if len(new_password) < 8:
                return Response(
                    {"error": "Password must be at least 8 characters long."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Set the new password
            user.set_password(new_password)
            # Clear the OTP fields
            user.otp = None
            user.token_created_at = None
            user.save()
            
            return Response(
                {"message": "Password reset successfully."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Password reset failed for {email}: {str(e)}")
            return Response(
                {"error": "Failed to reset password. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )