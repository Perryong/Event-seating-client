"""
Guest check-in service with real-time broadcasting
"""

from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Event, Guest
from app.api.ws import WebSocketManager

class CheckInService:
    """Service for handling guest check-ins"""
    
    def __init__(self, websocket_manager: WebSocketManager):
        self.websocket_manager = websocket_manager
    
    async def check_in_guest(
        self,
        public_code: str,
        guest_name: str,
        db: Session
    ) -> Optional[Dict]:
        """Check in a guest and broadcast the update"""
        
        # Find the event
        event = db.query(Event).filter(Event.public_code == public_code).first()
        if not event:
            return None
        
        # Find the guest (case-insensitive search)
        guest = db.query(Guest).filter(
            Guest.event_id == event.id,
            func.lower(Guest.name).like(f"%{guest_name.lower()}%")
        ).first()
        
        if not guest:
            return None
        
        # Update check-in status
        was_checked_in = guest.checked_in
        guest.checked_in = True
        guest.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Prepare broadcast message
        message = {
            "type": "checkin",
            "guest": {
                "name": guest.name,
                "table_name": guest.table_name,
                "seat_no": guest.seat_no,
                "dietary": guest.dietary
            },
            "timestamp": datetime.utcnow().isoformat(),
            "was_already_checked_in": was_checked_in
        }
        
        # Broadcast to all connected clients for this event
        await self.websocket_manager.broadcast_to_event(public_code, message)
        
        return {
            "guest": guest,
            "was_already_checked_in": was_checked_in
        }
    
    async def broadcast_seating_update(
        self,
        public_code: str,
        update_type: str = "seating_update"
    ):
        """Broadcast seating data update to connected clients"""
        
        message = {
            "type": update_type,
            "timestamp": datetime.utcnow().isoformat(),
            "message": "Seating arrangement has been updated"
        }
        
        await self.websocket_manager.broadcast_to_event(public_code, message)
    
    async def broadcast_guest_update(
        self,
        public_code: str,
        guest: Guest,
        update_type: str = "guest_update"
    ):
        """Broadcast individual guest update"""
        
        message = {
            "type": update_type,
            "guest": {
                "name": guest.name,
                "table_name": guest.table_name,
                "seat_no": guest.seat_no,
                "dietary": guest.dietary,
                "checked_in": guest.checked_in
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.websocket_manager.broadcast_to_event(public_code, message)
