"""
Guest-facing API routes
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.guest import LookupRequest, CheckInRequest
from app.services.seating_service import SeatingService
from app.services.checkin_service import CheckInService
from app.api.ws import websocket_manager
from app.utils.security import rate_limit_check, get_client_ip
from app.utils.responses import success_response, error_response, rate_limit_error, not_found_error

router = APIRouter()

# Initialize check-in service with WebSocket manager
checkin_service = CheckInService(websocket_manager)

@router.post("/lookup")
async def lookup_guest(
    request: Request,
    lookup_data: LookupRequest,
    db: Session = Depends(get_db)
):
    """Look up guest seating information"""
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limit_check(client_ip):
        return rate_limit_error()
    
    # Get seating info
    seating_info = SeatingService.get_guest_seating_info(
        public_code=lookup_data.public_code,
        guest_name=lookup_data.name,
        db=db
    )
    
    if not seating_info:
        return error_response(
            message="Guest not found. Please check your name spelling or contact the organizer.",
            status_code=404
        )
    
    return success_response(
        message="Guest information found",
        data=seating_info.dict()
    )

@router.post("/checkin")
async def check_in_guest(
    request: Request,
    checkin_data: CheckInRequest,
    db: Session = Depends(get_db)
):
    """Check in a guest and broadcast update"""
    # Rate limiting
    client_ip = get_client_ip(request)
    if not rate_limit_check(client_ip):
        return rate_limit_error()
    
    # Check in guest
    result = await checkin_service.check_in_guest(
        public_code=checkin_data.public_code,
        guest_name=checkin_data.name,
        db=db
    )
    
    if not result:
        return error_response(
            message="Guest not found. Please check your name spelling or contact the organizer.",
            status_code=404
        )
    
    guest = result["guest"]
    was_already_checked_in = result["was_already_checked_in"]
    
    message = "Successfully checked in!" if not was_already_checked_in else "You were already checked in!"
    
    return success_response(
        message=message,
        data={
            "guest": {
                "name": guest.name,
                "table_name": guest.table_name,
                "seat_no": guest.seat_no,
                "dietary": guest.dietary,
                "checked_in": guest.checked_in
            },
            "was_already_checked_in": was_already_checked_in
        }
    )

@router.get("/portal")
async def guest_portal(request: Request, event: str = ""):
    """Serve guest portal page"""
    # This would typically serve an HTML template
    # For now, return information about accessing the portal
    if not event:
        return error_response(
            message="Event code is required",
            status_code=400
        )
    
    return success_response(
        message="Guest portal access",
        data={
            "event_code": event,
            "instructions": "Use the lookup endpoint to find your seating information",
            "lookup_url": "/guest/lookup",
            "checkin_url": "/guest/checkin"
        }
    )
