"""
Event model
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship

from app.core.db import Base

class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    date = Column(DateTime, nullable=False)
    organizer_email = Column(String(255), nullable=False)
    public_code = Column(String(50), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    tables = relationship("Table", back_populates="event", cascade="all, delete-orphan")
    guests = relationship("Guest", back_populates="event", cascade="all, delete-orphan")
