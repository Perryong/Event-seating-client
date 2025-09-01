"""
Tests for Excel validation functionality
"""

import pytest
import pandas as pd
import io
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.db import Base
from app.models import Event, Guest, Table
from app.services.excel_service import ExcelService

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
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
def sample_event(db_session):
    """Create a sample event for testing"""
    event = Event(
        name="Test Wedding",
        date="2024-06-15",
        organizer_email="test@example.com",
        public_code="TEST123"
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event

def create_test_excel(data):
    """Helper function to create Excel bytes from data"""
    df = pd.DataFrame(data)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return buffer.getvalue()

def test_validate_excel_structure_valid():
    """Test Excel structure validation with valid columns"""
    data = {
        'Name': ['John Doe'],
        'Table': ['A1'],
        'Seat No.': [1],
        'Dietary Preference': ['none']
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_excel_structure(df)
    assert valid
    assert len(errors) == 0

def test_validate_excel_structure_missing_columns():
    """Test Excel structure validation with missing columns"""
    data = {
        'Name': ['John Doe'],
        'Table': ['A1']
        # Missing Seat No. and Dietary Preference
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_excel_structure(df)
    assert not valid
    assert len(errors) > 0
    assert 'missing required columns' in errors[0].lower()

def test_validate_excel_structure_case_insensitive():
    """Test Excel structure validation with different cases"""
    data = {
        'NAME': ['John Doe'],
        'table': ['A1'],
        'Seat No.': [1],
        'DIETARY PREFERENCE': ['none']
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_excel_structure(df)
    assert valid
    assert len(errors) == 0

def test_validate_data_constraints_table_size_ok():
    """Test table size validation with acceptable number of guests"""
    data = {
        'Name': [f'Guest {i}' for i in range(1, 13)],  # 12 guests
        'Table': ['A1'] * 12,
        'Seat No.': list(range(1, 13)),
        'Dietary Preference': ['none'] * 12
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_data_constraints(df)
    assert valid
    assert len(errors) == 0

def test_validate_data_constraints_table_size_exceeded():
    """Test table size validation with too many guests"""
    data = {
        'Name': [f'Guest {i}' for i in range(1, 15)],  # 14 guests
        'Table': ['A1'] * 14,
        'Seat No.': list(range(1, 15)),
        'Dietary Preference': ['none'] * 14
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_data_constraints(df)
    assert not valid
    assert len(errors) > 0
    assert 'A1' in errors[0]
    assert '14 guests' in errors[0]

def test_validate_data_constraints_duplicate_seats():
    """Test validation of duplicate seats in same table"""
    data = {
        'Name': ['John Doe', 'Jane Doe'],
        'Table': ['A1', 'A1'],
        'Seat No.': [1, 1],  # Duplicate seat
        'Dietary Preference': ['none', 'vegetarian']
    }
    df = pd.DataFrame(data)
    
    valid, errors = ExcelService.validate_data_constraints(df)
    assert not valid
    assert len(errors) > 0
    assert 'duplicate seat' in errors[0].lower()

def test_process_excel_upload_success(db_session, sample_event):
    """Test successful Excel upload processing"""
    data = {
        'Name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
        'Table': ['A1', 'A1', 'B1'],
        'Seat No.': [1, 2, 1],
        'Dietary Preference': ['none', 'vegetarian', 'halal']
    }
    excel_bytes = create_test_excel(data)
    
    success, errors, count = ExcelService.process_excel_upload(
        excel_bytes, sample_event.id, db_session
    )
    
    assert success
    assert len(errors) == 0
    assert count == 3
    
    # Verify database
    guests = db_session.query(Guest).filter(Guest.event_id == sample_event.id).all()
    assert len(guests) == 3
    
    tables = db_session.query(Table).filter(Table.event_id == sample_event.id).all()
    assert len(tables) == 2  # A1 and B1

def test_process_excel_upload_validation_failure(db_session, sample_event):
    """Test Excel upload with validation errors"""
    data = {
        'Name': [f'Guest {i}' for i in range(1, 15)],  # Too many guests
        'Table': ['A1'] * 14,
        'Seat No.': list(range(1, 15)),
        'Dietary Preference': ['none'] * 14
    }
    excel_bytes = create_test_excel(data)
    
    success, errors, count = ExcelService.process_excel_upload(
        excel_bytes, sample_event.id, db_session
    )
    
    assert not success
    assert len(errors) > 0
    assert count == 0
    
    # Verify no data was inserted
    guests = db_session.query(Guest).filter(Guest.event_id == sample_event.id).all()
    assert len(guests) == 0

def test_create_template():
    """Test Excel template creation"""
    template_bytes = ExcelService.create_template()
    
    assert template_bytes is not None
    assert len(template_bytes) > 0
    
    # Verify template structure
    df = pd.read_excel(io.BytesIO(template_bytes))
    expected_columns = ['Name', 'Table', 'Seat No.', 'Dietary Preference']
    
    for col in expected_columns:
        assert col in df.columns

def test_export_current_data(db_session, sample_event):
    """Test exporting current guest data"""
    # Add some test guests
    guests = [
        Guest(
            event_id=sample_event.id,
            name="John Doe",
            table_name="A1",
            seat_no=1,
            dietary="none",
            checked_in=True
        ),
        Guest(
            event_id=sample_event.id,
            name="Jane Smith",
            table_name="A1",
            seat_no=2,
            dietary="vegetarian",
            checked_in=False
        )
    ]
    
    for guest in guests:
        db_session.add(guest)
    db_session.commit()
    
    # Export data
    excel_bytes = ExcelService.export_current_data(sample_event.id, db_session)
    
    assert excel_bytes is not None
    assert len(excel_bytes) > 0
    
    # Verify exported data
    df = pd.read_excel(io.BytesIO(excel_bytes))
    assert len(df) == 2
    assert 'Checked In' in df.columns
    assert df.iloc[0]['Name'] == 'John Doe'
    assert df.iloc[0]['Checked In'] == 'Yes'
    assert df.iloc[1]['Checked In'] == 'No'
