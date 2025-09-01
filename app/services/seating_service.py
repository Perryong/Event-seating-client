"""
Seating arrangement and validation service
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Event, Guest, Table
from app.schemas.event import SeatingInfo

class SeatingService:
    """Service for seating arrangement operations"""
    
    @staticmethod
    def get_guest_seating_info(
        public_code: str, 
        guest_name: str, 
        db: Session
    ) -> Optional[SeatingInfo]:
        """Get seating information for a specific guest"""
        
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
        
        # Get table mates
        table_mates = db.query(Guest).filter(
            Guest.event_id == event.id,
            Guest.table_name == guest.table_name,
            Guest.id != guest.id
        ).all()
        
        table_mates_info = [
            {
                "name": mate.name,
                "seat_no": mate.seat_no,
                "checked_in": mate.checked_in,
                "dietary": mate.dietary
            }
            for mate in table_mates
        ]
        
        return SeatingInfo(
            guest_name=guest.name,
            table_name=guest.table_name,
            seat_no=guest.seat_no,
            dietary=guest.dietary,
            checked_in=guest.checked_in,
            table_mates=table_mates_info
        )
    
    @staticmethod
    def get_seating_summary(
        public_code: str, 
        db: Session,
        include_names: bool = False
    ) -> Dict:
        """Get public seating summary"""
        
        event = db.query(Event).filter(Event.public_code == public_code).first()
        if not event:
            return None
        
        # Get table statistics
        table_stats = db.query(
            Guest.table_name,
            func.count(Guest.id).label('total_guests'),
            func.sum(Guest.checked_in.cast('integer')).label('checked_in')
        ).filter(
            Guest.event_id == event.id
        ).group_by(Guest.table_name).all()
        
        tables = []
        for stat in table_stats:
            table_info = {
                "table_name": stat.table_name,
                "total_guests": stat.total_guests,
                "checked_in": stat.checked_in or 0,
                "available_seats": 12 - stat.total_guests
            }
            
            if include_names:
                guests = db.query(Guest).filter(
                    Guest.event_id == event.id,
                    Guest.table_name == stat.table_name
                ).order_by(Guest.seat_no).all()
                
                table_info["guests"] = [
                    {
                        "name": guest.name,
                        "seat_no": guest.seat_no,
                        "checked_in": guest.checked_in,
                        "dietary": guest.dietary
                    }
                    for guest in guests
                ]
            
            tables.append(table_info)
        
        # Overall statistics
        total_guests = db.query(func.count(Guest.id)).filter(Guest.event_id == event.id).scalar()
        checked_in_guests = db.query(func.count(Guest.id)).filter(
            Guest.event_id == event.id,
            Guest.checked_in == True
        ).scalar()
        
        return {
            "event_name": event.name,
            "event_date": event.date.isoformat(),
            "total_guests": total_guests,
            "checked_in_guests": checked_in_guests,
            "total_tables": len(tables),
            "tables": tables
        }
    
    @staticmethod
    def validate_table_capacity(
        event_id: int,
        table_name: str,
        exclude_guest_id: Optional[int],
        db: Session
    ) -> bool:
        """Validate that a table doesn't exceed capacity"""
        
        query = db.query(func.count(Guest.id)).filter(
            Guest.event_id == event_id,
            Guest.table_name == table_name
        )
        
        if exclude_guest_id:
            query = query.filter(Guest.id != exclude_guest_id)
        
        current_count = query.scalar()
        return current_count < 12
    
    @staticmethod
    def validate_seat_uniqueness(
        event_id: int,
        table_name: str,
        seat_no: int,
        exclude_guest_id: Optional[int],
        db: Session
    ) -> bool:
        """Validate that seat number is unique within table"""
        
        query = db.query(Guest).filter(
            Guest.event_id == event_id,
            Guest.table_name == table_name,
            Guest.seat_no == seat_no
        )
        
        if exclude_guest_id:
            query = query.filter(Guest.id != exclude_guest_id)
        
        existing_guest = query.first()
        return existing_guest is None
    
    @staticmethod
    def get_table_guests(
        event_id: int,
        table_name: str,
        db: Session
    ) -> List[Dict]:
        """Get all guests for a specific table"""
        
        guests = db.query(Guest).filter(
            Guest.event_id == event_id,
            Guest.table_name == table_name
        ).order_by(Guest.seat_no).all()
        
        return [
            {
                "id": guest.id,
                "name": guest.name,
                "seat_no": guest.seat_no,
                "dietary": guest.dietary,
                "checked_in": guest.checked_in
            }
            for guest in guests
        ]
