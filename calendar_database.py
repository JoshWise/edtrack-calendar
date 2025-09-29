"""
EdTrack Calendar Module - Database Operations

This module handles database operations for the calendar module,
compatible with the main EdTrack database schema.
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd
from typing import Optional, List, Dict, Any
import logging

from calendar_models import Base, Lesson, LearningTarget, SchoolCalendar, CalendarDay

logger = logging.getLogger(__name__)

class CalendarDatabase:
    """Database operations for calendar module"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database connection
        
        Args:
            database_url: Database URL, defaults to environment variable
        """
        self.database_url = database_url or os.getenv("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is required")
        
        self.engine = create_engine(self.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self):
        """Create database tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except SQLAlchemyError as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def save_lessons(self, lessons_df: pd.DataFrame) -> List[int]:
        """
        Save lessons to database
        
        Args:
            lessons_df: Lessons DataFrame
            
        Returns:
            List of lesson IDs
        """
        if lessons_df.empty:
            return []
        
        lesson_ids = []
        
        with self.get_session() as session:
            try:
                for _, row in lessons_df.iterrows():
                    lesson = Lesson(
                        class_id=row['class_id'],
                        lesson_number=row['lesson_number'],
                        title=row['title'],
                        date_planned=row.get('date_planned'),
                        date_delivered=row.get('date_delivered'),
                        status=row.get('status', 'planned'),
                        notes=row.get('notes'),
                        duration_hours=row.get('duration_hours', 1.0),
                        duration_type=row.get('duration_type'),
                        sequence_number=row.get('sequence_number'),
                        total_sequence=row.get('total_sequence'),
                        source_file=row.get('source_file'),
                        file_type=row.get('file_type'),
                        parsed_content=row.get('parsed_content')
                    )
                    session.add(lesson)
                    session.flush()  # Get the ID
                    lesson_ids.append(lesson.lesson_id)
                
                session.commit()
                logger.info(f"Saved {len(lesson_ids)} lessons to database")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error saving lessons: {e}")
                raise
        
        return lesson_ids
    
    def save_learning_targets(self, targets_df: pd.DataFrame) -> List[int]:
        """
        Save learning targets to database
        
        Args:
            targets_df: Learning targets DataFrame
            
        Returns:
            List of target IDs
        """
        if targets_df.empty:
            return []
        
        target_ids = []
        
        with self.get_session() as session:
            try:
                for _, row in targets_df.iterrows():
                    target = LearningTarget(
                        code=row['code'],
                        short_name=row['short_name'],
                        description=row.get('description'),
                        domain=row.get('domain'),
                        bloom_level=row.get('bloom_level'),
                        tags=row.get('tags'),
                        ai_model_version=row.get('ai_model_version'),
                        rubric_json=row.get('rubric_json'),
                        lesson_id=row.get('lesson_id'),
                        target_order=row.get('target_order'),
                        estimated_time=row.get('estimated_time'),
                        prerequisite_targets=row.get('prerequisite_targets')
                    )
                    session.add(target)
                    session.flush()  # Get the ID
                    target_ids.append(target.target_id)
                
                session.commit()
                logger.info(f"Saved {len(target_ids)} learning targets to database")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error saving learning targets: {e}")
                raise
        
        return target_ids
    
    def save_calendar(self, calendar_df: pd.DataFrame, school_id: int) -> int:
        """
        Save school calendar to database
        
        Args:
            calendar_df: Calendar DataFrame
            school_id: School ID
            
        Returns:
            Calendar ID
        """
        if calendar_df.empty:
            raise ValueError("No calendar data provided")
        
        with self.get_session() as session:
            try:
                # Create school calendar record
                start_date = calendar_df['date'].min()
                end_date = calendar_df['date'].max()
                academic_year = f"{start_date.year}-{end_date.year}"
                
                school_calendar = SchoolCalendar(
                    school_id=school_id,
                    name=f"{academic_year} Academic Year",
                    start_date=start_date,
                    end_date=end_date,
                    active=True,
                    notes=f"Calendar scraped from external source"
                )
                session.add(school_calendar)
                session.flush()  # Get the ID
                calendar_id = school_calendar.calendar_id
                
                # Save calendar days
                for _, row in calendar_df.iterrows():
                    calendar_day = CalendarDay(
                        calendar_id=calendar_id,
                        date=row['date'],
                        is_school_day=row.get('is_school_day', True),
                        day_type=row.get('day_type', 'regular'),
                        notes=row.get('notes')
                    )
                    session.add(calendar_day)
                
                session.commit()
                logger.info(f"Saved calendar {calendar_id} with {len(calendar_df)} days")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error saving calendar: {e}")
                raise
        
        return calendar_id
    
    def get_lessons_by_class(self, class_id: int) -> pd.DataFrame:
        """
        Get lessons for a specific class
        
        Args:
            class_id: Class ID
            
        Returns:
            Lessons DataFrame
        """
        with self.get_session() as session:
            try:
                query = text("SELECT * FROM lessons WHERE class_id = :class_id ORDER BY lesson_number")
                df = pd.read_sql(query, session.bind, params={"class_id": class_id})
                return df
            except SQLAlchemyError as e:
                logger.error(f"Error getting lessons: {e}")
                raise
    
    def get_calendar_by_school(self, school_id: int) -> pd.DataFrame:
        """
        Get calendar for a specific school
        
        Args:
            school_id: School ID
            
        Returns:
            Calendar DataFrame
        """
        with self.get_session() as session:
            try:
                query = text("""
                    SELECT cd.*, sc.name as calendar_name 
                    FROM calendar_days cd
                    JOIN school_calendars sc ON cd.calendar_id = sc.calendar_id
                    WHERE sc.school_id = :school_id AND sc.active = true
                    ORDER BY cd.date
                """)
                df = pd.read_sql(query, session.bind, params={"school_id": school_id})
                return df
            except SQLAlchemyError as e:
                logger.error(f"Error getting calendar: {e}")
                raise
    
    def get_learning_targets_by_lesson(self, lesson_id: int) -> pd.DataFrame:
        """
        Get learning targets for a specific lesson
        
        Args:
            lesson_id: Lesson ID
            
        Returns:
            Learning targets DataFrame
        """
        with self.get_session() as session:
            try:
                query = text("SELECT * FROM learning_targets WHERE lesson_id = :lesson_id ORDER BY target_order")
                df = pd.read_sql(query, session.bind, params={"lesson_id": lesson_id})
                return df
            except SQLAlchemyError as e:
                logger.error(f"Error getting learning targets: {e}")
                raise
    
    def update_lesson_status(self, lesson_id: int, status: str, date_delivered: Optional[str] = None):
        """
        Update lesson status
        
        Args:
            lesson_id: Lesson ID
            status: New status
            date_delivered: Delivery date (optional)
        """
        with self.get_session() as session:
            try:
                query = text("""
                    UPDATE lessons 
                    SET status = :status, date_delivered = :date_delivered, updated_at = NOW()
                    WHERE lesson_id = :lesson_id
                """)
                session.execute(query, {
                    "lesson_id": lesson_id,
                    "status": status,
                    "date_delivered": date_delivered
                })
                session.commit()
                logger.info(f"Updated lesson {lesson_id} status to {status}")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error updating lesson status: {e}")
                raise
    
    def delete_lesson(self, lesson_id: int):
        """
        Delete a lesson
        
        Args:
            lesson_id: Lesson ID to delete
        """
        with self.get_session() as session:
            try:
                query = text("DELETE FROM lessons WHERE lesson_id = :lesson_id")
                session.execute(query, {"lesson_id": lesson_id})
                session.commit()
                logger.info(f"Deleted lesson {lesson_id}")
                
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error deleting lesson: {e}")
                raise
    
    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get database statistics
        
        Returns:
            Dictionary with database statistics
        """
        with self.get_session() as session:
            try:
                stats = {}
                
                # Count lessons
                result = session.execute(text("SELECT COUNT(*) as count FROM lessons"))
                stats['total_lessons'] = result.scalar()
                
                # Count learning targets
                result = session.execute(text("SELECT COUNT(*) as count FROM learning_targets"))
                stats['total_targets'] = result.scalar()
                
                # Count calendars
                result = session.execute(text("SELECT COUNT(*) as count FROM school_calendars"))
                stats['total_calendars'] = result.scalar()
                
                # Count calendar days
                result = session.execute(text("SELECT COUNT(*) as count FROM calendar_days"))
                stats['total_calendar_days'] = result.scalar()
                
                return stats
                
            except SQLAlchemyError as e:
                logger.error(f"Error getting database stats: {e}")
                raise

# Global database instance
db = None

def get_database() -> CalendarDatabase:
    """Get global database instance"""
    global db
    if db is None:
        db = CalendarDatabase()
    return db

def init_database():
    """Initialize database tables"""
    db = get_database()
    db.create_tables()
