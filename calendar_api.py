"""
EdTrack Calendar Module - FastAPI Application

This module provides REST API endpoints for scraping curriculum content,
processing calendar data, and integrating with the main EdTrack application.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import pandas as pd
import asyncio
from datetime import datetime
import logging

from calendar_scraper import EdTrackCalendarScraper
from calendar_processor import EdTrackCalendarProcessor
from calendar_models import Lesson, LearningTarget, SchoolCalendar, CalendarDay

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="EdTrack Calendar Module",
    description="API for scraping and processing curriculum content and school calendars",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class ScrapeCalendarRequest(BaseModel):
    calendar_url: str = Field(..., description="URL to scrape calendar from")
    school_id: int = Field(..., description="School ID from EdTrack database")

class ScrapeLessonsRequest(BaseModel):
    lesson_url: str = Field(..., description="URL to scrape lesson content from")
    class_id: int = Field(..., description="Class ID from EdTrack database")

class ScrapeAndScheduleRequest(BaseModel):
    lesson_url: str = Field(..., description="URL to scrape lesson content from")
    calendar_url: str = Field(..., description="URL to scrape calendar from")
    class_id: int = Field(..., description="Class ID from EdTrack database")
    school_id: int = Field(..., description="School ID from EdTrack database")
    hours_per_day: int = Field(default=1, description="Number of class hours per day")

class ImportDataRequest(BaseModel):
    calendar_data: List[Dict[str, Any]] = Field(..., description="Calendar data to import")
    lesson_data: List[Dict[str, Any]] = Field(..., description="Lesson data to import")
    target_data: List[Dict[str, Any]] = Field(..., description="Learning target data to import")
    school_id: int = Field(..., description="School ID from EdTrack database")
    class_id: int = Field(..., description="Class ID from EdTrack database")

class APIResponse(BaseModel):
    status: str = Field(..., description="Response status")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    summary: Optional[Dict[str, Any]] = Field(None, description="Summary statistics")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Scrape school calendar only
@app.post("/scrape-calendar", response_model=APIResponse)
async def scrape_calendar(request: ScrapeCalendarRequest):
    """
    Scrape school calendar from a URL
    
    Args:
        request: Calendar scraping request
        
    Returns:
        APIResponse with calendar data
    """
    try:
        logger.info(f"Scraping calendar from: {request.calendar_url}")
        
        async with EdTrackCalendarScraper() as scraper:
            calendar_df = await scraper.scrape_school_calendar(request.calendar_url, request.school_id)
        
        if calendar_df.empty:
            raise HTTPException(status_code=404, detail="No calendar data found")
        
        # Process calendar data
        processor = EdTrackCalendarProcessor()
        processed_calendar = processor.process_calendar_data(calendar_df, request.school_id)
        
        # Analyze calendar
        analysis = processor.analyze_calendar(processed_calendar)
        
        return APIResponse(
            status="success",
            message="Calendar scraped successfully",
            data={
                "calendar": processed_calendar.to_dict('records')
            },
            summary=analysis
        )
        
    except Exception as e:
        logger.error(f"Error scraping calendar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape calendar: {str(e)}")

# Scrape lesson content only
@app.post("/scrape-lessons", response_model=APIResponse)
async def scrape_lessons(request: ScrapeLessonsRequest):
    """
    Scrape lesson content from a URL
    
    Args:
        request: Lesson scraping request
        
    Returns:
        APIResponse with lesson data
    """
    try:
        logger.info(f"Scraping lessons from: {request.lesson_url}")
        
        async with EdTrackCalendarScraper() as scraper:
            lessons_df = await scraper.scrape_lesson_content(request.lesson_url, request.class_id)
        
        if lessons_df.empty:
            raise HTTPException(status_code=404, detail="No lesson data found")
        
        # Extract learning targets
        processor = EdTrackCalendarProcessor()
        targets_df = processor.create_learning_targets_from_lessons(lessons_df)
        
        return APIResponse(
            status="success",
            message="Lessons scraped successfully",
            data={
                "lessons": lessons_df.to_dict('records'),
                "targets": targets_df.to_dict('records')
            },
            summary={
                "total_lessons": len(lessons_df),
                "total_targets": len(targets_df),
                "duration_types": lessons_df['duration_type'].value_counts().to_dict() if 'duration_type' in lessons_df.columns else {}
            }
        )
        
    except Exception as e:
        logger.error(f"Error scraping lessons: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape lessons: {str(e)}")

# Scrape and schedule lessons with calendar
@app.post("/scrape-and-schedule", response_model=APIResponse)
async def scrape_and_schedule(request: ScrapeAndScheduleRequest):
    """
    Scrape lessons and calendar, then schedule lessons across school days
    
    Args:
        request: Combined scraping and scheduling request
        
    Returns:
        APIResponse with scheduled lessons and calendar data
    """
    try:
        logger.info(f"Scraping and scheduling from lesson: {request.lesson_url} and calendar: {request.calendar_url}")
        
        async with EdTrackCalendarScraper() as scraper:
            # Scrape both lesson and calendar data concurrently
            lessons_task = scraper.scrape_lesson_content(request.lesson_url, request.class_id)
            calendar_task = scraper.scrape_school_calendar(request.calendar_url, request.school_id)
            
            lessons_df, calendar_df = await asyncio.gather(lessons_task, calendar_task)
        
        if lessons_df.empty:
            raise HTTPException(status_code=404, detail="No lesson data found")
        if calendar_df.empty:
            raise HTTPException(status_code=404, detail="No calendar data found")
        
        # Process data
        processor = EdTrackCalendarProcessor()
        
        # Process calendar
        processed_calendar = processor.process_calendar_data(calendar_df, request.school_id)
        
        # Schedule lessons
        scheduled_lessons = processor.process_lessons_for_scheduling(
            lessons_df, processed_calendar, request.hours_per_day, request.class_id
        )
        
        # Extract learning targets
        learning_targets = processor.create_learning_targets_from_lessons(lessons_df)
        
        # Create lesson-target mappings
        lesson_target_mappings = processor.create_lesson_target_mappings(scheduled_lessons, learning_targets)
        
        # Validate schedule
        validation = processor.validate_schedule(scheduled_lessons, processed_calendar)
        
        # Analyze calendar
        calendar_analysis = processor.analyze_calendar(processed_calendar)
        
        return APIResponse(
            status="success",
            message="Lessons scraped and scheduled successfully",
            data={
                "calendar": processed_calendar.to_dict('records'),
                "lessons": scheduled_lessons.to_dict('records'),
                "targets": learning_targets.to_dict('records'),
                "mappings": lesson_target_mappings.to_dict('records'),
                "validation": validation
            },
            summary={
                "total_lessons": len(scheduled_lessons),
                "total_targets": len(learning_targets),
                "school_days": calendar_analysis.get('school_days', 0),
                "total_calendar_days": calendar_analysis.get('total_days', 0),
                "schedule_valid": validation.get('valid', False),
                "warnings": validation.get('warnings', []),
                "errors": validation.get('errors', [])
            }
        )
        
    except Exception as e:
        logger.error(f"Error scraping and scheduling: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to scrape and schedule: {str(e)}")

# Get curriculum metadata
@app.post("/curriculum-metadata", response_model=APIResponse)
async def get_curriculum_metadata(request: ScrapeLessonsRequest):
    """
    Get metadata about curriculum content without scraping full lessons
    
    Args:
        request: Lesson scraping request (for URL)
        
    Returns:
        APIResponse with curriculum metadata
    """
    try:
        logger.info(f"Getting curriculum metadata from: {request.lesson_url}")
        
        async with EdTrackCalendarScraper() as scraper:
            metadata = await scraper.scrape_curriculum_metadata(request.lesson_url)
        
        return APIResponse(
            status="success",
            message="Curriculum metadata retrieved successfully",
            data={"metadata": metadata}
        )
        
    except Exception as e:
        logger.error(f"Error getting curriculum metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")

# Process existing data (for testing/debugging)
@app.post("/process-data", response_model=APIResponse)
async def process_existing_data(request: ImportDataRequest):
    """
    Process existing lesson and calendar data
    
    Args:
        request: Data processing request
        
    Returns:
        APIResponse with processed data
    """
    try:
        logger.info("Processing existing data")
        
        # Convert data to DataFrames
        lessons_df = pd.DataFrame(request.lesson_data)
        calendar_df = pd.DataFrame(request.calendar_data)
        
        if lessons_df.empty or calendar_df.empty:
            raise HTTPException(status_code=400, detail="No data provided")
        
        # Process data
        processor = EdTrackCalendarProcessor()
        
        # Process calendar
        processed_calendar = processor.process_calendar_data(calendar_df, request.school_id)
        
        # Schedule lessons
        scheduled_lessons = processor.process_lessons_for_scheduling(
            lessons_df, processed_calendar, hours_per_day=1, class_id=request.class_id
        )
        
        # Extract learning targets
        learning_targets = processor.create_learning_targets_from_lessons(lessons_df)
        
        # Create lesson-target mappings
        lesson_target_mappings = processor.create_lesson_target_mappings(scheduled_lessons, learning_targets)
        
        # Validate schedule
        validation = processor.validate_schedule(scheduled_lessons, processed_calendar)
        
        return APIResponse(
            status="success",
            message="Data processed successfully",
            data={
                "calendar": processed_calendar.to_dict('records'),
                "lessons": scheduled_lessons.to_dict('records'),
                "targets": learning_targets.to_dict('records'),
                "mappings": lesson_target_mappings.to_dict('records'),
                "validation": validation
            },
            summary={
                "total_lessons": len(scheduled_lessons),
                "total_targets": len(learning_targets),
                "schedule_valid": validation.get('valid', False)
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process data: {str(e)}")

# Get API documentation
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "EdTrack Calendar Module API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "scrape_calendar": "POST /scrape-calendar",
            "scrape_lessons": "POST /scrape-lessons",
            "scrape_and_schedule": "POST /scrape-and-schedule",
            "curriculum_metadata": "POST /curriculum-metadata",
            "process_data": "POST /process-data"
        }
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return {"status": "error", "message": "Endpoint not found"}

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return {"status": "error", "message": "Internal server error"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
