"""
Admin API routes - requires authentication
"""

import os
import secrets
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query, Form
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Event, Guest
from app.schemas.event import EventCreate, EventResponse, EventDetail
from app.schemas.guest import GuestUpdate, GuestResponse
from app.services.excel_service import ExcelService
from app.services.checkin_service import CheckInService
from app.api.ws import websocket_manager
from app.utils.security import verify_admin_token
from app.utils.responses import success_response, error_response, validation_error, not_found_error
from fastapi.responses import Response

router = APIRouter()

# Initialize check-in service
checkin_service = CheckInService(websocket_manager)

@router.post("/events", response_model=dict)
async def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Create a new event"""
    # Generate unique public code
    public_code = secrets.token_urlsafe(8)
    
    # Ensure uniqueness
    while db.query(Event).filter(Event.public_code == public_code).first():
        public_code = secrets.token_urlsafe(8)
    
    # Create event
    event = Event(
        name=event_data.name,
        date=event_data.date,
        organizer_email=event_data.organizer_email,
        public_code=public_code
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return success_response(
        message="Event created successfully",
        data={
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat(),
            "organizer_email": event.organizer_email,
            "public_code": event.public_code,
            "created_at": event.created_at.isoformat()
        }
    )

@router.get("/events/{event_id}")
async def get_event_details(
    event_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Get detailed event information"""
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Get statistics
    total_guests = db.query(Guest).filter(Guest.event_id == event_id).count()
    checked_in_count = db.query(Guest).filter(
        Guest.event_id == event_id,
        Guest.checked_in == True
    ).count()
    
    # Get unique tables
    tables = db.query(Guest.table_name).filter(Guest.event_id == event_id).distinct().all()
    total_tables = len(tables)
    
    return success_response(
        message="Event details retrieved",
        data={
            "id": event.id,
            "name": event.name,
            "date": event.date.isoformat(),
            "organizer_email": event.organizer_email,
            "public_code": event.public_code,
            "created_at": event.created_at.isoformat(),
            "total_guests": total_guests,
            "total_tables": total_tables,
            "checked_in_count": checked_in_count
        }
    )

@router.post("/events/{event_id}/upload")
async def upload_excel(
    event_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Upload and process Excel file"""
    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        return error_response(
            message="Invalid file format. Please upload an Excel file (.xlsx or .xls)",
            status_code=400
        )
    
    # Read file content
    file_content = await file.read()
    
    # Save original file
    ExcelService.save_original_file(file_content, event_id)
    
    # Process Excel file
    success, errors, processed_count = ExcelService.process_excel_upload(
        file_content=file_content,
        event_id=event_id,
        db=db
    )
    
    if not success:
        return error_response(
            message="Excel file validation failed",
            details=errors,
            status_code=422
        )
    
    # Broadcast seating update
    await checkin_service.broadcast_seating_update(
        public_code=event.public_code,
        update_type="seating_uploaded"
    )
    
    return success_response(
        message=f"Excel file processed successfully. {processed_count} guests imported.",
        data={
            "processed_count": processed_count,
            "filename": file.filename
        }
    )

@router.get("/events/{event_id}/export/original.xlsx")
async def export_original_excel(
    event_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Download original uploaded Excel file"""
    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Check if original file exists
    file_path = f"uploads/{event_id}/original.xlsx"
    if not os.path.exists(file_path):
        return error_response(
            message="Original file not found",
            status_code=404
        )
    
    # Read and return file
    with open(file_path, 'rb') as f:
        file_content = f.read()
    
    return Response(
        content=file_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=original_{event.public_code}.xlsx"}
    )

@router.get("/events/{event_id}/export/updated.xlsx")
async def export_updated_excel(
    event_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Export current guest data to Excel"""
    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Export current data
    excel_content = ExcelService.export_current_data(event_id, db, include_checkin=True)
    
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=current_seating_{event.public_code}.xlsx"}
    )

@router.get("/events/{event_id}/guests")
async def search_guests(
    event_id: int,
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Search and list guests for an event"""
    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Build query
    query = db.query(Guest).filter(Guest.event_id == event_id)
    
    if search:
        query = query.filter(Guest.name.ilike(f"%{search}%"))
    
    # Pagination
    offset = (page - 1) * per_page
    guests = query.offset(offset).limit(per_page).all()
    total = query.count()
    
    guest_data = [
        {
            "id": guest.id,
            "name": guest.name,
            "table_name": guest.table_name,
            "seat_no": guest.seat_no,
            "dietary": guest.dietary,
            "checked_in": guest.checked_in,
            "updated_at": guest.updated_at.isoformat()
        }
        for guest in guests
    ]
    
    return success_response(
        message="Guests retrieved successfully",
        data={
            "guests": guest_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": (total + per_page - 1) // per_page
            }
        }
    )

@router.patch("/events/{event_id}/guests/{guest_id}")
async def update_guest(
    event_id: int,
    guest_id: int,
    guest_update: GuestUpdate,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Update guest information"""
    # Verify event exists
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Find guest
    guest = db.query(Guest).filter(
        Guest.id == guest_id,
        Guest.event_id == event_id
    ).first()
    if not guest:
        raise not_found_error("Guest")
    
    # Validate updates
    errors = []
    
    if guest_update.table_name and guest_update.table_name != guest.table_name:
        from app.services.seating_service import SeatingService
        if not SeatingService.validate_table_capacity(
            event_id, guest_update.table_name, guest.id, db
        ):
            errors.append(f"Table '{guest_update.table_name}' would exceed maximum capacity of 12 guests")
    
    if guest_update.seat_no and guest_update.seat_no != guest.seat_no:
        table_name = guest_update.table_name or guest.table_name
        from app.services.seating_service import SeatingService
        if not SeatingService.validate_seat_uniqueness(
            event_id, table_name, guest_update.seat_no, guest.id, db
        ):
            errors.append(f"Seat {guest_update.seat_no} is already taken in table '{table_name}'")
    
    if errors:
        return error_response(
            message="Validation failed",
            details=errors,
            status_code=422
        )
    
    # Apply updates
    if guest_update.name:
        guest.name = guest_update.name
    if guest_update.table_name:
        guest.table_name = guest_update.table_name
    if guest_update.seat_no:
        guest.seat_no = guest_update.seat_no
    if guest_update.dietary:
        guest.dietary = guest_update.dietary
    if guest_update.checked_in is not None:
        guest.checked_in = guest_update.checked_in
    
    guest.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(guest)
    
    # Broadcast update
    await checkin_service.broadcast_guest_update(
        public_code=event.public_code,
        guest=guest,
        update_type="guest_updated"
    )
    
    return success_response(
        message="Guest updated successfully",
        data={
            "id": guest.id,
            "name": guest.name,
            "table_name": guest.table_name,
            "seat_no": guest.seat_no,
            "dietary": guest.dietary,
            "checked_in": guest.checked_in,
            "updated_at": guest.updated_at.isoformat()
        }
    )

@router.post("/create-event-with-excel")
async def create_event_with_excel(
    name: str = Form(...),
    date: str = Form(...),
    organizer_email: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Create event and upload Excel file in one step (public endpoint)"""
    from datetime import datetime
    
    # Validate file type
    if not file.filename.endswith(('.xlsx', '.xls')):
        return error_response(
            message="Invalid file format. Please upload an Excel file (.xlsx or .xls)",
            status_code=400
        )
    
    try:
        # Parse date
        event_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
        
        # Generate unique public code
        public_code = secrets.token_urlsafe(8)
        while db.query(Event).filter(Event.public_code == public_code).first():
            public_code = secrets.token_urlsafe(8)
        
        # Create event
        event = Event(
            name=name,
            date=event_date,
            organizer_email=organizer_email,
            public_code=public_code
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        # Process Excel file
        file_content = await file.read()
        
        # Save original file
        ExcelService.save_original_file(file_content, event.id)
        
        # Process Excel file
        success, errors, processed_count = ExcelService.process_excel_upload(
            file_content=file_content,
            event_id=event.id,
            db=db
        )
        
        if not success:
            # Delete event if Excel processing failed
            db.delete(event)
            db.commit()
            return error_response(
                message="Excel file validation failed",
                details=errors,
                status_code=422
            )
        
        # Broadcast seating update
        await checkin_service.broadcast_seating_update(
            public_code=event.public_code,
            update_type="event_created"
        )
        
        return success_response(
            message=f"Event created and Excel file processed successfully. {processed_count} guests imported.",
            data={
                "id": event.id,
                "name": event.name,
                "date": event.date.isoformat(),
                "organizer_email": event.organizer_email,
                "public_code": event.public_code,
                "guest_count": processed_count,
                "filename": file.filename
            }
        )
        
    except Exception as e:
        return error_response(
            message=f"Failed to create event: {str(e)}",
            status_code=500
        )

@router.delete("/events/{event_id}")
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    token: str = Depends(verify_admin_token)
):
    """Soft delete an event"""
    # Find event
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise not_found_error("Event")
    
    # Delete all related data (cascade should handle this)
    db.delete(event)
    db.commit()
    
    return success_response(
        message="Event deleted successfully",
        data={"deleted_event_id": event_id}
    )
