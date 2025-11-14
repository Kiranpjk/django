import logging
import sys

class SuppressBrokenPipeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except (BrokenPipeError, ConnectionResetError):
            logging.warning("💨 Client disconnected before response finished.")
            sys.stderr.flush()
            return None
