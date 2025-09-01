"""
Common Pydantic schemas
"""

from typing import Any, Optional
from pydantic import BaseModel

class StandardResponse(BaseModel):
    """Standard API response"""
    success: bool
    message: str
    data: Optional[Any] = None

class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[Any] = None

class PaginationParams(BaseModel):
    """Pagination parameters"""
    page: int = 1
    per_page: int = 50
    
class SearchParams(BaseModel):
    """Search parameters"""
    search: Optional[str] = None
