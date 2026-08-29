from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError

def api_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        exc = ValidationError("This record has dependent history. Deactivate it instead of deleting it.")
    elif isinstance(exc, IntegrityError):
        exc = ValidationError("A duplicate or invalid related record prevented saving. Check the fields and try again.")
    response = exception_handler(exc, context)
    if response is None:
        return None
    response.data = {"error": {"code": getattr(exc, "default_code", "request_error"), "message": "The request could not be processed.", "details": response.data}}
    return response
