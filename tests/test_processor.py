"""
Test cases for calendar processor functionality
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from calendar_processor import EdTrackCalendarProcessor

class TestCalendarProcessor:
    """Test cases for calendar processor"""
    
    def setup_method(self):
        """Set up test data"""
        self.processor = EdTrackCalendarProcessor()
        
        # Create sample lesson data
        self.lessons_data = {
            'class_id': [1, 1, 1],
            'lesson_number': [1, 2, 3],
            'title': ['Lesson 1', 'Lesson 2', 'Lesson 3'],
            'duration_hours': [1.0, 2.0, 1.5],
            'duration_type': ['hours', 'hours', 'days'],
            'parsed_content': ['Content 1', 'Content 2', 'Content 3'],
            'status': ['planned', 'planned', 'planned']
        }
        self.lessons_df = pd.DataFrame(self.lessons_data)
        
        # Create sample calendar data
        self.calendar_data = {
            'school_id': [1, 1, 1, 1, 1],
            'date': [
                datetime(2024, 1, 15),
                datetime(2024, 1, 16),
                datetime(2024, 1, 17),
                datetime(2024, 1, 18),
                datetime(2024, 1, 19)
            ],
            'is_school_day': [True, True, False, True, True],
            'day_type': ['regular', 'regular', 'holiday', 'regular', 'regular']
        }
        self.calendar_df = pd.DataFrame(self.calendar_data)
    
    def test_process_calendar_data(self):
        """Test calendar data processing"""
        processed_df = self.processor.process_calendar_data(self.calendar_df, 1)
        
        # Check required columns
        required_columns = ['date', 'is_school_day', 'day_type']
        for col in required_columns:
            assert col in processed_df.columns
        
        # Check derived columns
        assert 'year' in processed_df.columns
        assert 'month' in processed_df.columns
        assert 'weekday' in processed_df.columns
        assert 'is_weekend' in processed_df.columns
        
        # Check data types
        assert processed_df['is_school_day'].dtype == 'bool'
        assert processed_df['is_weekend'].dtype == 'bool'
    
    def test_process_lessons_for_scheduling(self):
        """Test lesson scheduling"""
        scheduled_df = self.processor.process_lessons_for_scheduling(
            self.lessons_df, self.calendar_df, hours_per_day=1, class_id=1
        )
        
        # Check required columns
        required_columns = ['class_id', 'lesson_number', 'title', 'date_planned']
        for col in required_columns:
            assert col in scheduled_df.columns
        
        # Check that lessons are scheduled
        assert not scheduled_df.empty
        assert 'date_planned' in scheduled_df.columns
        
        # Check that scheduled dates are school days
        scheduled_dates = pd.to_datetime(scheduled_df['date_planned']).dt.date
        school_dates = self.calendar_df[self.calendar_df['is_school_day'] == True]['date'].dt.date
        
        for date in scheduled_dates:
            assert date in school_dates.values
    
    def test_create_learning_targets_from_lessons(self):
        """Test learning target extraction"""
        targets_df = self.processor.create_learning_targets_from_lessons(self.lessons_df)
        
        # Check required columns
        required_columns = ['code', 'short_name', 'description', 'domain']
        for col in required_columns:
            assert col in targets_df.columns
        
        # Check that targets are created
        assert not targets_df.empty
        
        # Check code format
        for code in targets_df['code']:
            assert code.startswith('LT-')
            assert '-' in code
    
    def test_create_lesson_target_mappings(self):
        """Test lesson-target mapping creation"""
        # Create sample targets
        targets_data = {
            'target_id': [1, 2, 3],
            'lesson_id': [1, 1, 2],
            'code': ['LT-001-01', 'LT-001-02', 'LT-002-01'],
            'short_name': ['Target 1', 'Target 2', 'Target 3']
        }
        targets_df = pd.DataFrame(targets_data)
        
        # Create sample scheduled lessons
        scheduled_lessons_data = {
            'lesson_id': [1, 2],
            'class_id': [1, 1],
            'lesson_number': [1, 2],
            'title': ['Lesson 1', 'Lesson 2'],
            'date_planned': [datetime(2024, 1, 15), datetime(2024, 1, 16)]
        }
        scheduled_lessons_df = pd.DataFrame(scheduled_lessons_data)
        
        mappings_df = self.processor.create_lesson_target_mappings(
            scheduled_lessons_df, targets_df
        )
        
        # Check required columns
        required_columns = ['lesson_id', 'target_id', 'weight', 'required']
        for col in required_columns:
            assert col in mappings_df.columns
        
        # Check that mappings are created
        assert not mappings_df.empty
    
    def test_analyze_calendar(self):
        """Test calendar analysis"""
        analysis = self.processor.analyze_calendar(self.calendar_df)
        
        # Check required analysis fields
        required_fields = ['total_days', 'school_days', 'no_school_days']
        for field in required_fields:
            assert field in analysis
        
        # Check calculations
        assert analysis['total_days'] == len(self.calendar_df)
        assert analysis['school_days'] == self.calendar_df['is_school_day'].sum()
        assert analysis['no_school_days'] == len(self.calendar_df) - self.calendar_df['is_school_day'].sum()
    
    def test_validate_schedule(self):
        """Test schedule validation"""
        # Create sample scheduled lessons
        scheduled_lessons_data = {
            'lesson_id': [1, 2],
            'class_id': [1, 1],
            'lesson_number': [1, 2],
            'title': ['Lesson 1', 'Lesson 2'],
            'date_planned': [datetime(2024, 1, 15), datetime(2024, 1, 16)]
        }
        scheduled_lessons_df = pd.DataFrame(scheduled_lessons_data)
        
        validation = self.processor.validate_schedule(scheduled_lessons_df, self.calendar_df)
        
        # Check validation structure
        required_fields = ['valid', 'warnings', 'errors']
        for field in required_fields:
            assert field in validation
        
        # Check that validation is valid for school days
        assert validation['valid'] == True
    
    def test_extract_objectives(self):
        """Test objective extraction"""
        content = """
        Objectives:
        - Students will understand basic programming concepts
        - Students will be able to write simple Python code
        
        Learning Targets:
        - Create variables and assign values
        - Use conditional statements
        """
        
        objectives = self.processor._extract_objectives(content)
        
        # Check that objectives are extracted
        assert len(objectives) > 0
        
        # Check objective content
        for obj in objectives:
            assert len(obj) > 0
            assert isinstance(obj, str)
    
    def test_extract_domain(self):
        """Test domain extraction"""
        # Test cybersecurity domain
        title = "Introduction to Cybersecurity"
        content = "Learn about security protocols and encryption"
        domain = self.processor._extract_domain(title, content)
        assert domain == 'Cybersecurity'
        
        # Test programming domain
        title = "Python Programming Basics"
        content = "Learn variables, functions, and algorithms"
        domain = self.processor._extract_domain(title, content)
        assert domain == 'Programming'
    
    def test_extract_bloom_level(self):
        """Test Bloom's taxonomy level extraction"""
        # Test Create level
        objective = "Students will create a new application"
        level = self.processor._extract_bloom_level(objective)
        assert level == 'Create'
        
        # Test Apply level
        objective = "Students will apply programming concepts"
        level = self.processor._extract_bloom_level(objective)
        assert level == 'Apply'
        
        # Test Remember level (default)
        objective = "Students will learn about computers"
        level = self.processor._extract_bloom_level(objective)
        assert level == 'Remember'
    
    def test_get_academic_year(self):
        """Test academic year calculation"""
        dates = pd.Series([
            datetime(2024, 8, 15),  # Fall semester
            datetime(2024, 12, 15), # Fall semester
            datetime(2025, 1, 15),  # Spring semester
            datetime(2025, 5, 15)   # Spring semester
        ])
        
        academic_years = self.processor._get_academic_year(dates)
        
        # Check academic year format
        for year in academic_years:
            assert '-' in year
            assert len(year.split('-')) == 2
    
    def test_get_semester(self):
        """Test semester calculation"""
        dates = pd.Series([
            datetime(2024, 8, 15),  # Fall
            datetime(2024, 12, 15), # Fall
            datetime(2025, 1, 15),  # Spring
            datetime(2025, 5, 15),  # Spring
            datetime(2025, 6, 15)   # Summer
        ])
        
        semesters = self.processor._get_semester(dates)
        
        # Check semester values
        expected_semesters = ['Fall', 'Fall', 'Spring', 'Spring', 'Summer']
        for i, semester in enumerate(semesters):
            assert semester == expected_semesters[i]
