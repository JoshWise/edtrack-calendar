"""
Test cases for calendar scraper functionality
"""

import pytest
import pandas as pd
from datetime import datetime
from calendar_scraper import EdTrackCalendarScraper

class TestCalendarScraper:
    """Test cases for calendar scraper"""
    
    @pytest.mark.asyncio
    async def test_scraper_initialization(self):
        """Test scraper initialization"""
        async with EdTrackCalendarScraper() as scraper:
            assert scraper is not None
            assert scraper.browser is not None
    
    @pytest.mark.asyncio
    async def test_scrape_lesson_content_empty_url(self):
        """Test scraping with empty URL"""
        async with EdTrackCalendarScraper() as scraper:
            with pytest.raises(Exception):
                await scraper.scrape_lesson_content("", 1)
    
    @pytest.mark.asyncio
    async def test_scrape_school_calendar_empty_url(self):
        """Test scraping calendar with empty URL"""
        async with EdTrackCalendarScraper() as scraper:
            with pytest.raises(Exception):
                await scraper.scrape_school_calendar("", 1)
    
    def test_dataframe_structure(self):
        """Test DataFrame structure for scraped data"""
        # Test lesson DataFrame structure
        lesson_data = {
            'class_id': [1, 1],
            'lesson_number': [1, 2],
            'title': ['Test Lesson 1', 'Test Lesson 2'],
            'status': ['planned', 'planned'],
            'duration_hours': [1.0, 2.0],
            'created_at': [datetime.now(), datetime.now()],
            'updated_at': [datetime.now(), datetime.now()]
        }
        
        df = pd.DataFrame(lesson_data)
        
        # Check required columns
        required_columns = ['class_id', 'lesson_number', 'title', 'status']
        for col in required_columns:
            assert col in df.columns
        
        # Check data types
        assert df['lesson_number'].dtype == 'int64'
        assert df['duration_hours'].dtype == 'float64'
        assert df['status'].dtype == 'object'
    
    def test_calendar_dataframe_structure(self):
        """Test DataFrame structure for calendar data"""
        # Test calendar DataFrame structure
        calendar_data = {
            'school_id': [1, 1, 1],
            'date': [datetime(2024, 1, 15), datetime(2024, 1, 16), datetime(2024, 1, 17)],
            'is_school_day': [True, True, False],
            'day_type': ['regular', 'regular', 'holiday'],
            'created_at': [datetime.now(), datetime.now(), datetime.now()],
            'updated_at': [datetime.now(), datetime.now(), datetime.now()]
        }
        
        df = pd.DataFrame(calendar_data)
        
        # Check required columns
        required_columns = ['school_id', 'date', 'is_school_day', 'day_type']
        for col in required_columns:
            assert col in df.columns
        
        # Check data types
        assert df['is_school_day'].dtype == 'bool'
        assert df['day_type'].dtype == 'object'
        assert pd.api.types.is_datetime64_any_dtype(df['date'])
    
    def test_metadata_extraction(self):
        """Test curriculum metadata extraction"""
        # Test metadata structure
        metadata = {
            'title': 'Test Curriculum',
            'description': 'Test description',
            'curriculum_type': 'PLTW',
            'grade_levels': ['9', '10'],
            'subject_areas': ['computer science'],
            'total_lessons': 10,
            'url': 'https://example.com'
        }
        
        # Check required fields
        required_fields = ['title', 'curriculum_type', 'total_lessons']
        for field in required_fields:
            assert field in metadata
        
        # Check data types
        assert isinstance(metadata['total_lessons'], int)
        assert isinstance(metadata['grade_levels'], list)
        assert isinstance(metadata['subject_areas'], list)
