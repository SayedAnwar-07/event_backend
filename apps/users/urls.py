from django.urls import path
from .views import (
    RegisterView,
    VerifyOtpView,
    LoginView,
    ResendOtpView,
    ProfileView,
    ForgotPasswordView,
    ResetPasswordView
)

urlpatterns = [
    # Authentication endpoints
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOtpView.as_view(), name='verify-otp'),
    path('resend-otp/', ResendOtpView.as_view(), name='resend-otp'),
    path('login/', LoginView.as_view(), name='login'),
    
    # Password reset endpoints
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    
    # Profile endpoint
    path('profile/', ProfileView.as_view(), name='profile'),
]