"""
Public API routes - no authentication required
"""

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import Response, JSONResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models import Event
from app.services.excel_service import ExcelService
from app.services.qr_service import QRService
from app.services.seating_service import SeatingService
from app.utils.security import rate_limit_check, get_client_ip
from app.utils.responses import success_response, error_response, rate_limit_error

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@router.get("/events/{public_code}/template.xlsx")
async def download_template(
    public_code: str,
    db: Session = Depends(get_db)
):
    """Download Excel template for event"""
    # Verify event exists
    event = db.query(Event).filter(Event.public_code == public_code).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Generate template
    template_bytes = ExcelService.create_template()
    
    return Response(
        content=template_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=seating_template_{public_code}.xlsx"}
    )

@router.get("/events/{public_code}/qr.png")
async def get_qr_code(
    public_code: str,
    db: Session = Depends(get_db)
):
    """Get QR code image for event"""
    # Verify event exists
    event = db.query(Event).filter(Event.public_code == public_code).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Generate QR code
    qr_bytes = QRService.generate_event_qr(public_code)
    
    return Response(
        content=qr_bytes,
        media_type="image/png",
        headers={"Content-Disposition": f"inline; filename=qr_{public_code}.png"}
    )

@router.get("/template/wedding_seating_template.xlsx")
async def download_general_template():
    """Download general Excel template for seating arrangements"""
    # Generate template
    template_bytes = ExcelService.create_template()
    
    return Response(
        content=template_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=wedding_seating_template.xlsx"}
    )

@router.get("/events/{public_code}/seating")
async def get_seating_summary(
    public_code: str,
    request: Request,
    include_names: bool = False,
    admin_token: str = None,
    db: Session = Depends(get_db)
):
    """Get public seating summary"""
    # Rate limiting for public access
    client_ip = get_client_ip(request)
    if not rate_limit_check(client_ip):
        raise rate_limit_error()
    
    # Check if names should be included (admin only)
    if include_names:
        from app.core.config import settings
        if admin_token != settings.ADMIN_TOKEN:
            include_names = False
    
    # Get seating summary
    summary = SeatingService.get_seating_summary(
        public_code=public_code,
        db=db,
        include_names=include_names
    )
    
    if summary is None:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return success_response(
        message="Seating summary retrieved successfully",
        data=summary
    )
