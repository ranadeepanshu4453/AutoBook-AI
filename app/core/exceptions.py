from fastapi import Request
from fastapi.responses import JSONResponse


class AppBaseException(Exception):
    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code    = code
        super().__init__(message)

class DatabaseException(AppBaseException):        pass
class InventoryFetchException(AppBaseException):  pass
class SessionNotFoundException(AppBaseException): pass
class IntentDetectionException(AppBaseException): pass
class AuthenticationException(AppBaseException):  pass
class RateLimitException(AppBaseException):       pass
class InvalidEntitiesException(AppBaseException): pass


# ── FastAPI exception handlers ────────────────────────────────────────
async def database_exception_handler(request: Request, exc: DatabaseException):
    return JSONResponse(status_code=500, content={
        "error": exc.message, "code": exc.code or "DB_ERROR"
    })

async def inventory_exception_handler(request: Request, exc: InventoryFetchException):
    return JSONResponse(status_code=503, content={
        "error": exc.message, "code": exc.code or "INVENTORY_ERROR"
    })

async def session_exception_handler(request: Request, exc: SessionNotFoundException):
    return JSONResponse(status_code=404, content={
        "error": exc.message, "code": exc.code or "SESSION_NOT_FOUND"
    })

async def intent_exception_handler(request: Request, exc: IntentDetectionException):
    return JSONResponse(status_code=422, content={
        "error": exc.message, "code": exc.code or "INTENT_ERROR"
    })

async def auth_exception_handler(request: Request, exc: AuthenticationException):
    return JSONResponse(status_code=401, content={
        "error": exc.message, "code": exc.code or "AUTH_ERROR"
    })

async def rate_limit_exception_handler(request: Request, exc: RateLimitException):
    return JSONResponse(status_code=429, content={
        "error": exc.message, "code": exc.code or "RATE_LIMIT"
    })

async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={
        "error": "An unexpected error occurred. Please try again.",
        "code":  "INTERNAL_ERROR"
    })