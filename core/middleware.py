import logging
import re

class PrivatePagesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'private, no-store, max-age=0'
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response

class SafeRequestFilter(logging.Filter):
    def filter(self, record):
        # Standard server records can contain URL query strings or exception locals.
        message = record.getMessage()
        record.msg = re.sub(r'(/[^\s\"?]*)\?[^\s\"]*', r'\1?[redacted]', message)
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return True
