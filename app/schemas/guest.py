"""
Guest-related Pydantic schemas
"""

from typing import Optional
from pydantic import BaseModel

class GuestCreate(BaseModel):
    """Schema for creating a guest"""
    name: str
    table_name: str
    seat_no: int
    dietary: str = "none"

class GuestUpdate(BaseModel):
    """Schema for updating a guest"""
    name: Optional[str] = None
    table_name: Optional[str] = None
    seat_no: Optional[int] = None
    dietary: Optional[str] = None
    checked_in: Optional[bool] = None

class GuestResponse(BaseModel):
    """Guest response schema"""
    id: int
    name: str
    table_name: str
    seat_no: int
    dietary: str
    checked_in: bool
    
    class Config:
        from_attributes = True

class LookupRequest(BaseModel):
    """Guest lookup request"""
    public_code: str
    name: str

class CheckInRequest(BaseModel):
    """Guest check-in request"""
    public_code: str
    name: str
