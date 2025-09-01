"""
Seating arrangement and validation service
"""

from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Event, Guest, Table
from app.schemas.event import SeatingInfo
from app.services.repositories import EventRepo, GuestRepo, use_firestore

class SeatingService:
    """Service for seating arrangement operations"""
    
    @staticmethod
    def get_guest_seating_info(
        public_code: str, 
        guest_name: str, 
        db: Session
    ) -> Optional[SeatingInfo]:
        """Get seating information for a specific guest"""
        
        if not use_firestore():
            event = EventRepo.get_by_public_code_sql(db, public_code)
            if not event:
                return None

            guest = db.query(Guest).filter(
                Guest.event_id == event.id,
                func.lower(Guest.name).like(f"%{guest_name.lower()}%")
            ).first()
            if not guest:
                return None

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
        else:
            event_doc = EventRepo.get_by_public_code_fs(public_code)
            if not event_doc:
                return None

            guest_doc = GuestRepo.find_by_name_fs(public_code, guest_name)
            if not guest_doc:
                return None

            mates = GuestRepo.list_table_fs(public_code, guest_doc["table_name"])
            table_mates_info = [
                {
                    "name": m.get("name"),
                    "seat_no": m.get("seat_no"),
                    "checked_in": m.get("checked_in"),
                    "dietary": m.get("dietary"),
                }
                for m in mates
                if m.get("id") != guest_doc.get("id")
            ]

            return SeatingInfo(
                guest_name=guest_doc.get("name"),
                table_name=guest_doc.get("table_name"),
                seat_no=guest_doc.get("seat_no"),
                dietary=guest_doc.get("dietary"),
                checked_in=bool(guest_doc.get("checked_in")),
                table_mates=table_mates_info
            )
    
    @staticmethod
    def get_seating_summary(
        public_code: str, 
        db: Session,
        include_names: bool = False
    ) -> Dict:
        """Get public seating summary"""
        
        if not use_firestore():
            event = EventRepo.get_by_public_code_sql(db, public_code)
            if not event:
                return None
        
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
        else:
            event_doc = EventRepo.get_by_public_code_fs(public_code)
            if not event_doc:
                return None

            # gather table stats from Firestore guests
            mates = GuestRepo.list_table_fs(public_code, table_name="*") if False else None  # placeholder unused
            # Simplified: fetch all guests in event
            from app.services.firebase_client import get_firestore_client
            fs = get_firestore_client()
            docs = fs.collection("events").document(public_code).collection("guests").get()
            all_guests = [d.to_dict() for d in docs]

            tables_map: dict[str, list[dict]] = {}
            for g in all_guests:
                tables_map.setdefault(g.get("table_name"), []).append(g)

            tables = []
            for table_name, people in tables_map.items():
                table_info = {
                    "table_name": table_name,
                    "total_guests": len(people),
                    "checked_in": sum(1 for p in people if p.get("checked_in")),
                    "available_seats": 12 - len(people)
                }
                if include_names:
                    table_info["guests"] = [
                        {
                            "name": p.get("name"),
                            "seat_no": p.get("seat_no"),
                            "checked_in": p.get("checked_in"),
                            "dietary": p.get("dietary")
                        }
                        for p in sorted(people, key=lambda x: x.get("seat_no") or 0)
                    ]
                tables.append(table_info)

            return {
                "event_name": event_doc.get("name"),
                "event_date": event_doc.get("date"),
                "total_guests": sum(len(v) for v in tables_map.values()),
                "checked_in_guests": sum(1 for g in all_guests if g.get("checked_in")),
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
