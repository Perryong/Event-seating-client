"""
Tests for seating service functionality
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import Event, Guest, Table
from app.services.seating_service import SeatingService

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_seating.db"
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
def complex_event(db_session):
    """Create a complex event with multiple tables and guests"""
    # Create event
    event = Event(
        name="Large Wedding",
        date=datetime(2024, 8, 20),
        organizer_email="organizer@example.com",
        public_code="LARGE123"
    )
    db_session.add(event)
    db_session.flush()
    
    # Create tables
    tables = ["A1", "A2", "B1", "B2", "VIP1"]
    for table_name in tables:
        table = Table(event_id=event.id, table_name=table_name)
        db_session.add(table)
    
    # Create guests with different scenarios
    guests_data = [
        # Table A1 - almost full (11 guests)
        *[{"name": f"A1_Guest_{i}", "table": "A1", "seat": i, "dietary": "none", "checked_in": i <= 5} for i in range(1, 12)],
        
        # Table A2 - full (12 guests)
        *[{"name": f"A2_Guest_{i}", "table": "A2", "seat": i, "dietary": "vegetarian" if i % 2 == 0 else "none", "checked_in": i <= 8} for i in range(1, 13)],
        
        # Table B1 - half full (6 guests)
        *[{"name": f"B1_Guest_{i}", "table": "B1", "seat": i, "dietary": "halal" if i % 3 == 0 else "none", "checked_in": i <= 3} for i in range(1, 7)],
        
        # Table VIP1 - VIP table (4 guests)
        {"name": "VIP John", "table": "VIP1", "seat": 1, "dietary": "allergies:shellfish", "checked_in": True},
        {"name": "VIP Mary", "table": "VIP1", "seat": 2, "dietary": "vegetarian", "checked_in": True},
        {"name": "VIP Robert", "table": "VIP1", "seat": 3, "dietary": "none", "checked_in": False},
        {"name": "VIP Sarah", "table": "VIP1", "seat": 4, "dietary": "halal", "checked_in": False},
    ]
    
    for guest_data in guests_data:
        guest = Guest(
            event_id=event.id,
            name=guest_data["name"],
            table_name=guest_data["table"],
            seat_no=guest_data["seat"],
            dietary=guest_data["dietary"],
            checked_in=guest_data["checked_in"]
        )
        db_session.add(guest)
    
    db_session.commit()
    db_session.refresh(event)
    return event

def test_complex_seating_summary(db_session, complex_event):
    """Test seating summary with complex data"""
    summary = SeatingService.get_seating_summary(
        public_code="LARGE123",
        db=db_session,
        include_names=False
    )
    
    assert summary is not None
    assert summary["total_guests"] == 33  # 11 + 12 + 6 + 4
    assert summary["total_tables"] == 4  # A1, A2, B1, VIP1 (B2 has no guests)
    assert summary["checked_in_guests"] == 17  # 5 + 8 + 3 + 2 - 1 (VIP Sarah not checked in)
    
    # Check individual table stats
    tables = {table["table_name"]: table for table in summary["tables"]}
    
    # A1 table
    assert tables["A1"]["total_guests"] == 11
    assert tables["A1"]["checked_in"] == 5
    assert tables["A1"]["available_seats"] == 1
    
    # A2 table (full)
    assert tables["A2"]["total_guests"] == 12
    assert tables["A2"]["checked_in"] == 8
    assert tables["A2"]["available_seats"] == 0
    
    # VIP1 table
    assert tables["VIP1"]["total_guests"] == 4
    assert tables["VIP1"]["checked_in"] == 2
    assert tables["VIP1"]["available_seats"] == 8

def test_who_sits_with_whom(db_session, complex_event):
    """Test detailed who-sits-with-whom functionality"""
    # Test A1 table guest
    seating_info = SeatingService.get_guest_seating_info(
        public_code="LARGE123",
        guest_name="A1_Guest_5",
        db=db_session
    )
    
    assert seating_info is not None
    assert len(seating_info.table_mates) == 10  # 11 total - 1 (self)
    
    # Check table mate details
    table_mates = seating_info.table_mates
    table_mate_names = [mate["name"] for mate in table_mates]
    assert "A1_Guest_1" in table_mate_names
    assert "A1_Guest_11" in table_mate_names
    assert "A1_Guest_5" not in table_mate_names  # Should not include self
    
    # Check checked-in status is included
    checked_in_mates = [mate for mate in table_mates if mate["checked_in"]]
    not_checked_in_mates = [mate for mate in table_mates if not mate["checked_in"]]
    
    assert len(checked_in_mates) == 4  # Guests 1,2,3,4 (excluding self which is guest 5)
    assert len(not_checked_in_mates) == 6  # Guests 6,7,8,9,10,11

def test_vip_table_seating(db_session, complex_event):
    """Test VIP table specific scenarios"""
    seating_info = SeatingService.get_guest_seating_info(
        public_code="LARGE123",
        guest_name="VIP John",
        db=db_session
    )
    
    assert seating_info is not None
    assert seating_info.table_name == "VIP1"
    assert seating_info.seat_no == 1
    assert seating_info.dietary == "allergies:shellfish"
    assert seating_info.checked_in == True
    
    # Check VIP table mates
    table_mates = seating_info.table_mates
    assert len(table_mates) == 3  # VIP Mary, Robert, Sarah
    
    # Verify specific dietary preferences are preserved
    mary = next((mate for mate in table_mates if mate["name"] == "VIP Mary"), None)
    assert mary is not None
    assert mary["dietary"] == "vegetarian"
    assert mary["checked_in"] == True
    
    sarah = next((mate for mate in table_mates if mate["name"] == "VIP Sarah"), None)
    assert sarah is not None
    assert sarah["dietary"] == "halal"
    assert sarah["checked_in"] == False

def test_table_capacity_edge_cases(db_session, complex_event):
    """Test table capacity validation edge cases"""
    event = complex_event
    
    # A2 is full (12 guests), should not allow more
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="A2",
        exclude_guest_id=None,
        db=db_session
    )
    assert not valid
    
    # A1 has 11 guests, should allow 1 more
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="A1",
        exclude_guest_id=None,
        db=db_session
    )
    assert valid
    
    # B2 has no guests, should allow guests
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="B2",
        exclude_guest_id=None,
        db=db_session
    )
    assert valid
    
    # Test excluding a guest from A2 (should become valid)
    a2_guest = db_session.query(Guest).filter(
        Guest.event_id == event.id,
        Guest.table_name == "A2"
    ).first()
    
    valid = SeatingService.validate_table_capacity(
        event_id=event.id,
        table_name="A2",
        exclude_guest_id=a2_guest.id,
        db=db_session
    )
    assert valid

def test_dietary_preferences_distribution(db_session, complex_event):
    """Test dietary preferences in seating arrangements"""
    summary = SeatingService.get_seating_summary(
        public_code="LARGE123",
        db=db_session,
        include_names=True
    )
    
    # Count dietary preferences across all tables
    dietary_counts = {"none": 0, "vegetarian": 0, "halal": 0, "allergies": 0}
    
    for table in summary["tables"]:
        for guest in table["guests"]:
            dietary = guest["dietary"]
            if dietary == "none":
                dietary_counts["none"] += 1
            elif dietary == "vegetarian":
                dietary_counts["vegetarian"] += 1
            elif dietary == "halal":
                dietary_counts["halal"] += 1
            elif dietary.startswith("allergies:"):
                dietary_counts["allergies"] += 1
    
    # Verify expected dietary distribution
    assert dietary_counts["none"] > 0
    assert dietary_counts["vegetarian"] > 0
    assert dietary_counts["halal"] > 0
    assert dietary_counts["allergies"] > 0

def test_seat_ordering(db_session, complex_event):
    """Test that guests are returned in seat order"""
    guests = SeatingService.get_table_guests(
        event_id=complex_event.id,
        table_name="A1",
        db=db_session
    )
    
    # Verify guests are ordered by seat number
    for i in range(len(guests) - 1):
        assert guests[i]["seat_no"] < guests[i + 1]["seat_no"]
    
    # Verify we have all expected seats
    seat_numbers = [guest["seat_no"] for guest in guests]
    assert seat_numbers == list(range(1, 12))  # 1 through 11

def test_case_insensitive_guest_search(db_session, complex_event):
    """Test case-insensitive guest name search"""
    # Test various case combinations
    test_cases = [
        "vip john",      # lowercase
        "VIP JOHN",      # uppercase
        "Vip John",      # proper case
        "vIP jOHn",      # mixed case
        "vip",           # partial match
        "john"           # partial match
    ]
    
    for search_term in test_cases:
        seating_info = SeatingService.get_guest_seating_info(
            public_code="LARGE123",
            guest_name=search_term,
            db=db_session
        )
        
        assert seating_info is not None
        assert seating_info.guest_name == "VIP John"
        assert seating_info.table_name == "VIP1"
