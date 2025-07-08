import json
import logging
from django.http import JsonResponse

logger = logging.getLogger(__name__)

class CustomErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_exception(self, request, exception):
        logger.error(f"Request failed: {str(exception)}", exc_info=True)
        return JsonResponse({
            'message': 'Internal server error',
            'errors': {'detail': str(exception)},
            'status': 500
        }, status=500)