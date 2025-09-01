"""
Event-related Pydantic schemas
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr

class EventCreate(BaseModel):
    """Schema for creating an event"""
    name: str
    date: datetime
    organizer_email: EmailStr

class EventResponse(BaseModel):
    """Basic event response"""
    id: int
    name: str
    date: datetime
    organizer_email: str
    public_code: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class EventDetail(EventResponse):
    """Detailed event response with counts"""
    total_guests: int
    total_tables: int
    checked_in_count: int
    
class SeatingInfo(BaseModel):
    """Seating information for a guest"""
    guest_name: str
    table_name: str
    seat_no: int
    dietary: str
    checked_in: bool
    table_mates: List[dict]  # List of {name, seat_no, checked_in}
