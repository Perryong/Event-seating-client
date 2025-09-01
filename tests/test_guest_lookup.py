"""
Tests for guest lookup and check-in functionality
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import Event, Guest, Table
from app.services.seating_service import SeatingService

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_lookup.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    """Create test database session"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture
def sample_event_with_guests(db_session):
    """Create a sample event with guests for testing"""
    # Create event
    event = Event(
        name="Test Wedding",
        date=datetime(2024, 6, 15),
        organizer_email="test@example.com",
        public_code="TEST123"
    )
    db_session.add(event)
    db_session.flush()
    
    # Create tables
    table_a1 = Table(event_id=event.id, table_name="A1")
    table_b1 = Table(event_id=event.id, table_name="B1")
    db_session.add(table_a1)
    db_session.add(table_b1)
    
    # Create guests
    guests = [
        Guest(
            event_id=event.id,
            name="John Doe",
            table_name="A1",
            seat_no=1,
            dietary="none",
            checked_in=False
        ),
        Guest(
            event_id=event.id,
            name="Jane Smith",
            table_name="A1",
            seat_no=2,
            dietary="vegetarian",
            checked_in=True
        ),
        Guest(
            event_id=event.id,
            name="Bob Johnson",
            table_name="A1",
            seat_no=3,
            dietary="halal",
            checked_in=False
        ),
        Guest(
            event_id=event.id,
            name="Alice Brown",
            table_name="B1",
            seat_no=1,
            dietary="allergies:nuts",
            checked_in=False
        )
    ]
    
    for guest in guests:
        db_session.add(guest)
    
    db_session.commit()
    db_session.refresh(event)
    return event

def test_get_guest_seating_info_exact_match(db_session, sample_event_with_guests):
    """Test guest lookup with exact name match"""
    seating_info = SeatingService.get_guest_seating_info(
        public_code="TEST123",
        guest_name="John Doe",
        db=db_session
    )
    
    assert seating_info is not None
    assert seating_info.guest_name == "John Doe"
    assert seating_info.table_name == "A1"
    assert seating_info.seat_no == 1
    assert seating_info.dietary == "none"
    assert seating_info.checked_in == False
    
    # Check table mates
    assert len(seating_info.table_mates) == 2  # Jane and Bob
    table_mate_names = [mate["name"] for mate in seating_info.table_mates]
    assert "Jane Smith" in table_mate_names
    assert "Bob Johnson" in table_mate_names

def test_get_guest_seating_info_partial_match(db_session, sample_event_with_guests):
    """Test guest lookup with partial name match"""
    seating_info = SeatingService.get_guest_seating_info(
        public_code="TEST123",
        guest_name="jane",  # lowercase partial
        db=db_session
    )
    
    assert seating_info is not None
    assert seating_info.guest_name == "Jane Smith"
    assert seating_info.checked_in == True

def test_get_guest_seating_info_not_found(db_session, sample_event_with_guests):
    """Test guest lookup with non-existent guest"""
    seating_info = SeatingService.get_guest_seating_info(
        public_code="TEST123",
        guest_name="Nonexistent Person",
        db=db_session
    )
    
    assert seating_info is None

def test_get_guest_seating_info_invalid_event(db_session, sample_event_with_guests):
    """Test guest lookup with invalid event code"""
    seating_info = SeatingService.get_guest_seating_info(
        public_code="INVALID",
        guest_name="John Doe",
        db=db_session
    )
    
    assert seating_info is None

def test_get_seating_summary(db_session, sample_event_with_guests):
    """Test getting seating summary"""
    summary = SeatingService.get_seating_summary(
        public_code="TEST123",
        db=db_session,
        include_names=False
    )
    
    assert summary is not None
    assert summary["event_name"] == "Test Wedding"
    assert summary["total_guests"] == 4
    assert summary["checked_in_guests"] == 1
    assert summary["total_tables"] == 2
    
    # Check table information
    tables = summary["tables"]
    assert len(tables) == 2
    
    table_a1 = next((t for t in tables if t["table_name"] == "A1"), None)
    assert table_a1 is not None
    assert table_a1["total_guests"] == 3
    assert table_a1["checked_in"] == 1
    assert table_a1["available_seats"] == 9

def test_get_seating_summary_with_names(db_session, sample_event_with_guests):
    """Test getting seating summary with guest names"""
    summary = SeatingService.get_seating_summary(
        public_code="TEST123",
        db=db_session,
        include_names=True
    )
    
    assert summary is not None
    
    # Check that guest names are included
    table_a1 = next((t for t in summary["tables"] if t["table_name"] == "A1"), None)
    assert "guests" in table_a1
    assert len(table_a1["guests"]) == 3
    
    guest_names = [guest["name"] for guest in table_a1["guests"]]
    assert "John Doe" in guest_names
    assert "Jane Smith" in guest_names
    assert "Bob Johnson" in guest_names

def test_validate_table_capacity(db_session, sample_event_with_guests):
    """Test table capacity validation"""
    event = sample_event_with_guests
    
    # A1 currently has 3 guests, should allow more
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="A1",
        exclude_guest_id=None,
        db=db_session
    )
    assert valid
    
    # Add guests to reach capacity
    for i in range(4, 13):  # Add 9 more guests (total 12)
        guest = Guest(
            event_id=event.id,
            name=f"Test Guest {i}",
            table_name="A1",
            seat_no=i,
            dietary="none"
        )
        db_session.add(guest)
    db_session.commit()
    
    # Now table should be at capacity
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="A1",
        exclude_guest_id=None,
        db=db_session
    )
    assert not valid

def test_validate_seat_uniqueness(db_session, sample_event_with_guests):
    """Test seat uniqueness validation"""
    event = sample_event_with_guests
    
    # Seat 1 in A1 is taken by John Doe
    valid = SeatingService.validate_seat_uniqueness(
        event_id=event.id,
        table_name="A1",
        seat_no=1,
        exclude_guest_id=None,
        db=db_session
    )
    assert not valid
    
    # Seat 5 in A1 should be available
    valid = SeatingService.validate_seat_uniqueness(
        event_id=event.id,
        table_name="A1",
        seat_no=5,
        exclude_guest_id=None,
        db=db_session
    )
    assert valid
    
    # Seat 1 in A1 should be valid if we exclude John Doe
    john_doe = db_session.query(Guest).filter(
        Guest.event_id == event.id,
        Guest.name == "John Doe"
    ).first()
    
    valid = SeatingService.validate_seat_uniqueness(
        event_id=event.id,
        table_name="A1",
        seat_no=1,
        exclude_guest_id=john_doe.id,
        db=db_session
    )
    assert valid

def test_get_table_guests(db_session, sample_event_with_guests):
    """Test getting guests for a specific table"""
    event = sample_event_with_guests
    
    guests = SeatingService.get_table_guests(
        event_id=event.id,
        table_name="A1",
        db=db_session
    )
    
    assert len(guests) == 3
    
    # Should be ordered by seat number
    assert guests[0]["seat_no"] == 1
    assert guests[0]["name"] == "John Doe"
    assert guests[1]["seat_no"] == 2
    assert guests[1]["name"] == "Jane Smith"
    assert guests[2]["seat_no"] == 3
    assert guests[2]["name"] == "Bob Johnson"
    
    # Check B1 table
    guests_b1 = SeatingService.get_table_guests(
        event_id=event.id,
        table_name="B1",
        db=db_session
    )
    
    assert len(guests_b1) == 1
    assert guests_b1[0]["name"] == "Alice Brown"
