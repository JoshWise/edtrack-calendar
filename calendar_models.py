"""
EdTrack Calendar Module - Database Models

This module extends the main EdTrack schema with calendar functionality.
All models are compatible with the existing EdTrack database schema.
"""

from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, ForeignKey,
    Text, Float, UniqueConstraint, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# Database-agnostic JSON column type (same as main EdTrack)
def JSONColumn():
    """Returns JSONB for PostgreSQL, JSON for SQLite"""
    try:
        from db import engine
        if engine.dialect.name == 'postgresql':
            return JSONB
        else:
            return SQLiteJSON
    except:
        # Fallback to JSONB (PostgreSQL)
        return JSONB

class TimeStamped:
    """Mixin class for created_at and updated_at timestamps"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

# Extended Lesson Model (compatible with main EdTrack)
class Lesson(Base, TimeStamped):
    """Enhanced Lesson model with calendar integration fields"""
    __tablename__ = "lessons"
    
    # Existing EdTrack fields
    lesson_id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.class_id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_number = Column(Integer, nullable=False)
    title = Column(String(300), nullable=False)
    date_planned = Column(Date)  # EXISTING - Perfect for calendar integration!
    date_delivered = Column(Date)  # EXISTING
    status = Column(String(20), default="planned")  # EXISTING
    notes = Column(Text)  # EXISTING
    
    # NEW calendar integration fields
    duration_hours = Column(Float, default=1.0)  # Total lesson duration
    duration_type = Column(String(20))  # sequential, days, hours, blocks
    sequence_number = Column(Integer)  # For (1 of 4) type lessons
    total_sequence = Column(Integer)  # Total parts in sequence
    source_file = Column(String(500))  # Path to uploaded lesson file
    file_type = Column(String(20))  # docx, pdf, txt, web
    parsed_content = Column(Text)  # Extracted lesson content
    
    # Relationships (compatible with main EdTrack)
    # class_rel = relationship("Class", back_populates="lessons")
    
    # EXISTING constraint
    __table_args__ = (UniqueConstraint("class_id", "lesson_number", name="uq_lesson_number_per_class"),)

# School Calendar Models (new)
class SchoolCalendar(Base, TimeStamped):
    """School calendar for academic years"""
    __tablename__ = "school_calendars"
    
    calendar_id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(200), nullable=False)  # "2025-2026 Academic Year"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text)
    
    # Relationships
    # school = relationship("School", back_populates="calendars")
    calendar_days = relationship("CalendarDay", back_populates="calendar", cascade="all, delete-orphan")
    
    __table_args__ = (Index("ix_calendar_school_dates", "school_id", "start_date"),)

class CalendarDay(Base, TimeStamped):
    """Individual calendar days with school day information"""
    __tablename__ = "calendar_days"
    
    day_id = Column(Integer, primary_key=True)
    calendar_id = Column(Integer, ForeignKey("school_calendars.calendar_id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    is_school_day = Column(Boolean, default=True, nullable=False)
    day_type = Column(String(50), default="regular")  # regular, early_release, no_school, holiday
    notes = Column(Text)
    
    # Relationships
    calendar = relationship("SchoolCalendar", back_populates="calendar_days")
    
    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_date"),)

# Enhanced Learning Target Model (compatible with main EdTrack)
class LearningTarget(Base, TimeStamped):
    """Learning targets extracted from lesson content"""
    __tablename__ = "learning_targets"
    
    # Existing EdTrack fields
    target_id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True)
    short_name = Column(String(200), nullable=False)
    description = Column(Text)
    domain = Column(String(100))  # e.g., CS, Cyber
    bloom_level = Column(String(20))
    tags = Column(JSONColumn())  # list/obj as JSON
    ai_model_version = Column(String(50))
    rubric_json = Column(JSONColumn())
    
    # NEW calendar integration fields
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", ondelete="SET NULL"))
    target_order = Column(Integer)  # Order within lesson
    estimated_time = Column(Float)  # Hours to complete
    prerequisite_targets = Column(JSONColumn())  # Array of target IDs
    
    # Relationships (compatible with main EdTrack)
    # lesson = relationship("Lesson", back_populates="learning_targets")

# Lesson Target Mapping (compatible with main EdTrack)
class LessonTarget(Base, TimeStamped):
    """Mapping between lessons and learning targets"""
    __tablename__ = "lesson_targets"
    
    # Existing EdTrack fields
    lesson_target_id = Column(Integer, primary_key=True)
    lesson_id = Column(Integer, ForeignKey("lessons.lesson_id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(Integer, ForeignKey("learning_targets.target_id", ondelete="RESTRICT"), nullable=False, index=True)
    weight = Column(Float, default=1.0)
    required = Column(Boolean, default=True, nullable=False)
    
    # NEW calendar integration fields
    scheduled_date = Column(Date)  # When this target should be covered
    completion_date = Column(Date)  # When this target was completed
    
    __table_args__ = (UniqueConstraint("lesson_id", "target_id", name="uq_lesson_target"),)

# Scraping Session Model (for tracking scraping operations)
class ScrapingSession(Base, TimeStamped):
    """Track scraping operations and their results"""
    __tablename__ = "scraping_sessions"
    
    session_id = Column(Integer, primary_key=True)
    session_type = Column(String(50), nullable=False)  # lesson, calendar, combined
    source_url = Column(String(500), nullable=False)
    school_id = Column(Integer, ForeignKey("schools.school_id", ondelete="SET NULL"))
    class_id = Column(Integer, ForeignKey("classes.class_id", ondelete="SET NULL"))
    status = Column(String(20), default="pending")  # pending, completed, failed
    items_scraped = Column(Integer, default=0)
    items_processed = Column(Integer, default=0)
    error_message = Column(Text)
    results_data = Column(JSONColumn())  # Store scraping results
    
    # Relationships
    # school = relationship("School")
    # class_rel = relationship("Class")

# Curriculum Source Model (for managing curriculum URLs)
class CurriculumSource(Base, TimeStamped):
    """Manage curriculum sources and their configurations"""
    __tablename__ = "curriculum_sources"
    
    source_id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)  # "PLTW Cybersecurity"
    url = Column(String(500), nullable=False)
    source_type = Column(String(50))  # pltw, custom, pdf, docx
    school_id = Column(Integer, ForeignKey("schools.school_id", ondelete="RESTRICT"))
    class_id = Column(Integer, ForeignKey("classes.class_id", ondelete="RESTRICT"))
    is_active = Column(Boolean, default=True)
    scraping_config = Column(JSONColumn())  # Custom scraping configuration
    last_scraped = Column(DateTime(timezone=True))
    
    # Relationships
    # school = relationship("School")
    # class_rel = relationship("Class")

# Export all models for easy importing
__all__ = [
    'Base',
    'TimeStamped',
    'JSONColumn',
    'Lesson',
    'SchoolCalendar',
    'CalendarDay',
    'LearningTarget',
    'LessonTarget',
    'ScrapingSession',
    'CurriculumSource'
]
