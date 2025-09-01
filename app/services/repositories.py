"""
Repository layer abstracting storage (SQLAlchemy vs Firebase Firestore).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Event, Guest
from app.services.firebase_client import get_firestore_client


def use_firestore() -> bool:
    return settings.USE_FIREBASE is True


# -------- Event repository --------

class EventRepo:
    @staticmethod
    def get_by_public_code_sql(db: Session, public_code: str) -> Optional[Event]:
        return db.query(Event).filter(Event.public_code == public_code).first()

    @staticmethod
    def get_by_id_sql(db: Session, event_id: int) -> Optional[Event]:
        return db.query(Event).filter(Event.id == event_id).first()

    @staticmethod
    def create_sql(db: Session, name: str, date: datetime, organizer_email: str, public_code: str) -> Event:
        event = Event(name=name, date=date, organizer_email=organizer_email, public_code=public_code)
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    # Firestore shape: collection "events/{public_code}" document with fields
    @staticmethod
    def get_by_public_code_fs(public_code: str) -> Optional[Dict[str, Any]]:
        fs = get_firestore_client()
        if not fs:
            return None
        doc = fs.collection("events").document(public_code).get()
        return doc.to_dict() if doc.exists else None

    @staticmethod
    def create_fs(name: str, date_iso: str, organizer_email: str, public_code: str) -> Dict[str, Any]:
        fs = get_firestore_client()
        data = {
            "name": name,
            "date": date_iso,
            "organizer_email": organizer_email,
            "public_code": public_code,
            "created_at": datetime.utcnow().isoformat(),
        }
        fs.collection("events").document(public_code).set(data)
        return data


# -------- Guest repository --------

class GuestRepo:
    @staticmethod
    def find_by_name_sql(db: Session, event_id: int, name_icontains: str) -> Optional[Guest]:
        from sqlalchemy import func
        return db.query(Guest).filter(
            Guest.event_id == event_id,
            func.lower(Guest.name).like(f"%{name_icontains.lower()}%")
        ).first()

    @staticmethod
    def list_table_sql(db: Session, event_id: int, table_name: str) -> List[Guest]:
        return db.query(Guest).filter(Guest.event_id == event_id, Guest.table_name == table_name).order_by(Guest.seat_no).all()

    @staticmethod
    def set_checked_in_sql(db: Session, guest: Guest) -> None:
        guest.checked_in = True
        guest.updated_at = datetime.utcnow()
        db.commit()

    # Firestore guest docs under collection events/{public_code}/guests
    @staticmethod
    def find_by_name_fs(public_code: str, name_icontains: str) -> Optional[Dict[str, Any]]:
        fs = get_firestore_client()
        if not fs:
            return None
        guests = fs.collection("events").document(public_code).collection("guests").where("name_lower", "==", name_icontains.lower()).get()
        if guests:
            doc = guests[0]
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        # fallback: prefix search
        return None

    @staticmethod
    def list_table_fs(public_code: str, table_name: str) -> List[Dict[str, Any]]:
        fs = get_firestore_client()
        docs = fs.collection("events").document(public_code).collection("guests").where("table_name", "==", table_name).order_by("seat_no").get()
        results: List[Dict[str, Any]] = []
        for d in docs:
            item = d.to_dict()
            item["id"] = d.id
            results.append(item)
        return results

    @staticmethod
    def set_checked_in_fs(public_code: str, guest_id: str) -> None:
        fs = get_firestore_client()
        fs.collection("events").document(public_code).collection("guests").document(guest_id).set({
            "checked_in": True,
            "updated_at": datetime.utcnow().isoformat()
        }, merge=True)


