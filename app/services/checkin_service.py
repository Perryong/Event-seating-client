"""
Guest check-in service with real-time broadcasting
"""

from datetime import datetime
from typing import Optional, Dict
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Event, Guest
from app.api.ws import WebSocketManager
from app.services.repositories import EventRepo, GuestRepo, use_firestore

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
        # SQLAlchemy path
        if not use_firestore():
            event = EventRepo.get_by_public_code_sql(db, public_code)
            if not event:
                return None

            guest = GuestRepo.find_by_name_sql(db, event.id, guest_name)
            if not guest:
                return None

            was_checked_in = guest.checked_in
            GuestRepo.set_checked_in_sql(db, guest)

            message_guest = {
                "name": guest.name,
                "table_name": guest.table_name,
                "seat_no": guest.seat_no,
                "dietary": guest.dietary,
            }

        else:
            # Firestore path
            event_doc = EventRepo.get_by_public_code_fs(public_code)
            if not event_doc:
                return None

            guest_doc = GuestRepo.find_by_name_fs(public_code, guest_name)
            if not guest_doc:
                return None

            was_checked_in = bool(guest_doc.get("checked_in"))
            GuestRepo.set_checked_in_fs(public_code, guest_doc["id"])

            message_guest = {
                "name": guest_doc.get("name"),
                "table_name": guest_doc.get("table_name"),
                "seat_no": guest_doc.get("seat_no"),
                "dietary": guest_doc.get("dietary"),
            }

        # Prepare broadcast message
        message = {
            "type": "checkin",
            "guest": message_guest,
            "timestamp": datetime.utcnow().isoformat(),
            "was_already_checked_in": was_checked_in
        }
        
        # Broadcast to all connected clients for this event
        await self.websocket_manager.broadcast_to_event(public_code, message)
        
        return {"guest": message_guest, "was_already_checked_in": was_checked_in}
    
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
