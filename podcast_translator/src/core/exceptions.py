class PCTException(Exception):
    """Base exception for Podcast Translator"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class AuthenticationError(PCTException):
    """Authentication failed or invalid token"""
    pass

class TokenExpiredError(AuthenticationError):
    """Token has expired"""
    pass

class QuotaExceededError(PCTException):
    """User has exceeded their quota"""
    pass

class TooManyActiveTasksError(PCTException):
    """User already has the maximum number of in-flight tasks"""
    pass

class ValidationError(PCTException):
    """Input validation failed"""
    pass

class TaskDispatchError(PCTException):
    """Background task dispatch failed"""
    pass


class StaleWorkerGenerationError(PCTException):
    """A superseded worker attempted to mutate task state."""
    pass

class ResourceNotFoundError(PCTException):
    """Resource not found"""
    pass


class FeatureDisabledError(PCTException):
    """Feature is disabled in the current environment"""
    pass
