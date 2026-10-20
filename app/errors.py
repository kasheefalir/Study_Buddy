"""Stable failure categories shared by clients, workflows, and the API."""
import httpx


class StudyError(ValueError):
    def __init__(self, message, code="invalid_request"):
        super().__init__(message)
        self.code = code


def transport_code(exc):
    if isinstance(exc, httpx.TimeoutException):
        return "model_timeout"
    if isinstance(exc, httpx.ConnectError):
        return "ollama_offline"
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in {401, 403}:
            return "model_access"
        if status == 429:
            return "rate_limit"
        if status == 404:
            return "model_missing"
    return "model_service"
