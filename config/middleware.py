from django.db import DatabaseError
from django.http import HttpResponse


class DatabaseUnavailableMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except DatabaseError:
            return HttpResponse(
                "<!doctype html><html lang=\"en\"><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
                "<title>Service temporarily unavailable</title>"
                "<main><h1>Service temporarily unavailable</h1>"
                "<p>This page needs the college database, which is currently unavailable. "
                "Please try again later.</p></main></html>",
                status=503,
                content_type="text/html; charset=utf-8",
            )
