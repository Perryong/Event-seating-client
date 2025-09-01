"""
Table model
"""

from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.core.db import Base

class Table(Base):
    __tablename__ = "tables"
    
    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    table_name = Column(String(100), nullable=False)
    
    # Relationships
    event = relationship("Event", back_populates="tables")
    
    # Composite unique constraint will be handled at application level
    __table_args__ = ()
