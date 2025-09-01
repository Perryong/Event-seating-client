"""
Standardized response utilities
"""

from typing import Any, Optional
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from app.schemas.common import StandardResponse, ErrorResponse

def success_response(
    message: str,
    data: Any = None,
    status_code: int = 200
) -> JSONResponse:
    """Create standardized success response"""
    response = StandardResponse(
        success=True,
        message=message,
        data=data
    )
    return JSONResponse(
        content=response.dict(),
        status_code=status_code
    )

def error_response(
    message: str,
    error_code: Optional[str] = None,
    details: Any = None,
    status_code: int = 400
) -> JSONResponse:
    """Create standardized error response"""
    response = ErrorResponse(
        message=message,
        error_code=error_code,
        details=details
    )
    return JSONResponse(
        content=response.dict(),
        status_code=status_code
    )

def validation_error(
    message: str,
    errors: list,
    status_code: int = 422
) -> HTTPException:
    """Create validation error exception"""
    raise HTTPException(
        status_code=status_code,
        detail={
            "message": message,
            "errors": errors
        }
    )

def not_found_error(resource: str = "Resource"):
    """Create not found error"""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{resource} not found"
    )

def unauthorized_error(message: str = "Unauthorized"):
    """Create unauthorized error"""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message
    )

def forbidden_error(message: str = "Forbidden"):
    """Create forbidden error"""
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message
    )

def rate_limit_error():
    """Create rate limit error"""
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Please try again later."
    )
