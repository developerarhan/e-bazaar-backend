import uuid
import logging

logger = logging.getLogger('django.request')


class RequestIDMiddleware:
    """
    Adds a unique request_id to every request.
    This lets you trace all log lines from a single request.
    
    Example: a payment that fails might log:
        [req_id: abc123] Payment verification initiated
        [req_id: abc123] Razorpay signature check failed
        [req_id: abc123] Payment marked as FAILED
    
    All three lines share the same req_id — easy to trace.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate a unique ID for this request
        request.request_id = str(uuid.uuid4())[:8]  # short version: "a3f9b2c1"
        response = self.get_response(request)

        # Add it to the response headers too
        # Your frontend can log this to help with debugging
        response['X-Request-ID'] = request.request_id

        return response