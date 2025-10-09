"""
EdTrack Calendar Module - Data Processor

This module uses Pandas to process scraped lesson and calendar data,
schedule lessons across school days, and extract learning targets.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import re
# Note: Processor doesn't use database models - just processes DataFrames

class EdTrackCalendarProcessor:
    """Main processor class for calendar and lesson data"""
    
    def __init__(self):
        self.lessons_df = pd.DataFrame()
        self.calendar_df = pd.DataFrame()
        self.targets_df = pd.DataFrame()
    
    def inspect_file_structure(self, df: pd.DataFrame) -> dict:
        """
        Inspect the structure of an uploaded file to help with processing
        
        Args:
            df: DataFrame to inspect
            
        Returns:
            Dictionary with file structure information
        """
        return {
            "columns": list(df.columns),
            "shape": df.shape,
            "dtypes": df.dtypes.to_dict(),
            "sample_data": df.head(3).to_dict('records') if not df.empty else [],
            "has_date_columns": any(col.lower() in ['date', 'day', 'due_date', 'assigned_date', 'created_date'] 
                                  for col in df.columns),
            "suggested_date_columns": [col for col in df.columns 
                                     if col.lower() in ['date', 'day', 'due_date', 'assigned_date', 'created_date']]
        }
        
    def process_calendar_data(self, calendar_df: pd.DataFrame, school_id: int) -> pd.DataFrame:
        """
        Process raw calendar data into standardized format
        
        Args:
            calendar_df: Raw calendar data from scraper
            school_id: School ID from EdTrack database
            
        Returns:
            Processed calendar DataFrame
        """
        if calendar_df.empty:
            return pd.DataFrame()
            
        # Create a copy to avoid modifying original
        processed_df = calendar_df.copy()
        
        # Check if 'date' column exists, if not try common alternatives
        if 'date' not in processed_df.columns:
            date_columns = ['Date', 'DATE', 'calendar_date', 'school_date', 'day', 'due_date', 'assigned_date', 'created_date']
            for col in date_columns:
                if col in processed_df.columns:
                    processed_df['date'] = processed_df[col]
                    break
            else:
                # If no date column found, provide detailed error message
                available_columns = list(processed_df.columns)
                raise ValueError(f"No date column found. Available columns: {available_columns}. Expected date columns: 'date', 'Date', 'DATE', 'calendar_date', 'school_date', 'day', 'due_date', 'assigned_date', 'created_date'")
        
        # Standardize date format
        processed_df['date'] = pd.to_datetime(processed_df['date'], errors='coerce')
        
        # Remove rows with invalid dates
        processed_df = processed_df.dropna(subset=['date'])
        
        if processed_df.empty:
            raise ValueError("No valid dates found in calendar data")
        
        # Add derived columns
        processed_df['year'] = processed_df['date'].dt.year
        processed_df['month'] = processed_df['date'].dt.month
        processed_df['day'] = processed_df['date'].dt.day
        processed_df['weekday'] = processed_df['date'].dt.day_name()
        processed_df['is_weekend'] = processed_df['date'].dt.weekday >= 5
        
        # Determine academic year
        processed_df['academic_year'] = self._get_academic_year(processed_df['date'])
        
        # Determine semester
        processed_df['semester'] = self._get_semester(processed_df['date'])
        
        # Add school_id if not present
        if 'school_id' not in processed_df.columns:
            processed_df['school_id'] = school_id
        
        # Add default school day status if not present
        if 'is_school_day' not in processed_df.columns:
            # Default: weekdays are school days, weekends are not
            processed_df['is_school_day'] = ~processed_df['is_weekend']
        
        # Add default day type if not present
        if 'day_type' not in processed_df.columns:
            processed_df['day_type'] = processed_df.apply(
                lambda row: 'school_day' if row['is_school_day'] else 'weekend', 
                axis=1
            )
        
        # Sort by date
        processed_df = processed_df.sort_values('date')
        
        # Create academic year summary
        academic_years = processed_df['academic_year'].unique()
        
        return processed_df
    
    def process_lessons_for_scheduling(self, lessons_df: pd.DataFrame, calendar_df: pd.DataFrame, 
                                     hours_per_day: int = 1, class_id: int = None) -> pd.DataFrame:
        """
        Process lessons and schedule them across school days
        
        Args:
            lessons_df: Raw lesson data from scraper
            calendar_df: Processed calendar data
            hours_per_day: Number of class hours per day
            class_id: Class ID for scheduling
            
        Returns:
            Scheduled lessons DataFrame
        """
        if lessons_df.empty or calendar_df.empty:
            return pd.DataFrame()
            
        # Filter calendar to school days only
        school_days = calendar_df[calendar_df['is_school_day'] == True].copy()
        school_days = school_days.sort_values('date')
        
        if school_days.empty:
            raise ValueError("No school days found in calendar data")
        
        # Process lessons for scheduling
        scheduled_lessons = []
        current_date_index = 0
        
        for _, lesson in lessons_df.iterrows():
            # Calculate total hours needed for this lesson
            total_hours = lesson.get('duration_hours', 1.0)
            duration_type = lesson.get('duration_type', 'hours')
            
            # Handle different duration types
            if duration_type == 'days':
                # Scale by hours per day
                total_hours = total_hours * hours_per_day
            elif duration_type == 'sequential':
                # Already calculated in scraper
                pass
            # hours and blocks are already in hours
            
            # Break into hour segments
            hour_segments = []
            for hour in range(int(total_hours)):
                segment = {
                    'class_id': class_id or lesson.get('class_id'),
                    'lesson_number': lesson['lesson_number'],
                    'title': lesson['title'],
                    'hour_segment': hour + 1,
                    'total_segments': int(total_hours),
                    'duration_type': duration_type,
                    'sequence_number': lesson.get('sequence_number'),
                    'total_sequence': lesson.get('total_sequence'),
                    'status': 'planned',
                    'notes': lesson.get('notes', ''),
                    'source_file': lesson.get('source_file'),
                    'file_type': lesson.get('file_type'),
                    'parsed_content': lesson.get('parsed_content'),
                    'duration_hours': 1.0  # Each segment is 1 hour
                }
                hour_segments.append(segment)
            
            # Schedule hour segments across school days
            hours_scheduled = 0
            for segment in hour_segments:
                if current_date_index >= len(school_days):
                    # No more school days available
                    break
                    
                current_date = school_days.iloc[current_date_index]['date']
                segment['date_planned'] = current_date
                
                scheduled_lessons.append(segment)
                hours_scheduled += 1
                
                # Move to next day if we've scheduled enough hours for today
                if hours_scheduled >= hours_per_day:
                    current_date_index += 1
                    hours_scheduled = 0
        
        # Convert to DataFrame
        scheduled_df = pd.DataFrame(scheduled_lessons)
        
        if not scheduled_df.empty:
            scheduled_df['created_at'] = datetime.now()
            scheduled_df['updated_at'] = datetime.now()
        
        return scheduled_df
    
    def create_learning_targets_from_lessons(self, lessons_df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract learning targets from lesson content
        
        Args:
            lessons_df: Lesson data with content
            
        Returns:
            Learning targets DataFrame
        """
        if lessons_df.empty:
            return pd.DataFrame()
            
        targets = []
        target_id = 1
        
        for _, lesson in lessons_df.iterrows():
            content = lesson.get('parsed_content', '')
            title = lesson['title']
            lesson_number = lesson['lesson_number']
            
            # Extract objectives/standards from content
            objectives = self._extract_objectives(content)
            
            if not objectives:
                # Create default target from lesson title
                objectives = [f"Complete {title}"]
            
            for obj in objectives:
                target = {
                    'target_id': target_id,
                    'code': f"LT-{lesson_number:03d}-{target_id:02d}",
                    'short_name': obj[:200] if len(obj) > 200 else obj,
                    'description': obj,
                    'domain': self._extract_domain(title, content),
                    'bloom_level': self._extract_bloom_level(obj),
                    'tags': {
                        'lesson_id': lesson.get('lesson_id'),
                        'lesson_number': lesson_number,
                        'source': 'scraped'
                    },
                    'lesson_id': lesson.get('lesson_id'),
                    'target_order': target_id,
                    'estimated_time': 1.0,  # Default to 1 hour per target
                    'prerequisite_targets': [],
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                targets.append(target)
                target_id += 1
        
        return pd.DataFrame(targets)
    
    def create_lesson_target_mappings(self, lessons_df: pd.DataFrame, targets_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create mappings between lessons and learning targets
        
        Args:
            lessons_df: Scheduled lessons DataFrame
            targets_df: Learning targets DataFrame
            
        Returns:
            Lesson-target mappings DataFrame
        """
        if lessons_df.empty or targets_df.empty:
            return pd.DataFrame()
            
        mappings = []
        
        for _, lesson in lessons_df.iterrows():
            lesson_number = lesson['lesson_number']
            lesson_date = lesson.get('date_planned')
            
            # Find targets for this lesson
            lesson_targets = targets_df[targets_df['lesson_id'] == lesson.get('lesson_id')]
            
            for _, target in lesson_targets.iterrows():
                mapping = {
                    'lesson_id': lesson.get('lesson_id'),
                    'target_id': target['target_id'],
                    'weight': 1.0,
                    'required': True,
                    'scheduled_date': lesson_date,
                    'completion_date': None,
                    'created_at': datetime.now(),
                    'updated_at': datetime.now()
                }
                mappings.append(mapping)
        
        return pd.DataFrame(mappings)
    
    def analyze_calendar(self, calendar_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze calendar data and provide insights
        
        Args:
            calendar_df: Processed calendar DataFrame
            
        Returns:
            Dictionary with calendar analysis
        """
        if calendar_df.empty:
            return {}
            
        analysis = {
            'total_days': len(calendar_df),
            'school_days': calendar_df['is_school_day'].sum(),
            'no_school_days': len(calendar_df) - calendar_df['is_school_day'].sum(),
            'academic_years': calendar_df['academic_year'].nunique(),
            'semesters': calendar_df['semester'].value_counts().to_dict(),
            'day_types': calendar_df['day_type'].value_counts().to_dict(),
            'months_covered': sorted(calendar_df['month'].unique()),
            'date_range': {
                'start': calendar_df['date'].min().isoformat(),
                'end': calendar_df['date'].max().isoformat()
            }
        }
        
        # Calculate school days per month
        monthly_school_days = calendar_df.groupby('month')['is_school_day'].sum().to_dict()
        analysis['school_days_per_month'] = monthly_school_days
        
        # Calculate academic year breakdown
        if 'academic_year' in calendar_df.columns:
            year_analysis = {}
            for year in calendar_df['academic_year'].unique():
                year_data = calendar_df[calendar_df['academic_year'] == year]
                year_analysis[year] = {
                    'total_days': len(year_data),
                    'school_days': year_data['is_school_day'].sum(),
                    'start_date': year_data['date'].min().isoformat(),
                    'end_date': year_data['date'].max().isoformat()
                }
            analysis['academic_year_breakdown'] = year_analysis
        
        return analysis
    
    def validate_schedule(self, scheduled_lessons_df: pd.DataFrame, calendar_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate lesson schedule against calendar constraints
        
        Args:
            scheduled_lessons_df: Scheduled lessons DataFrame
            calendar_df: Calendar DataFrame
            
        Returns:
            Validation results dictionary
        """
        if scheduled_lessons_df.empty or calendar_df.empty:
            return {'valid': True, 'warnings': [], 'errors': []}
            
        warnings = []
        errors = []
        
        # Check for lessons scheduled on non-school days
        non_school_days = calendar_df[calendar_df['is_school_day'] == False]['date'].dt.date.tolist()
        scheduled_dates = pd.to_datetime(scheduled_lessons_df['date_planned']).dt.date.tolist()
        
        conflicts = set(scheduled_dates) & set(non_school_days)
        if conflicts:
            errors.append(f"Lessons scheduled on non-school days: {list(conflicts)}")
        
        # Check for lessons scheduled on weekends
        weekend_lessons = scheduled_lessons_df[
            pd.to_datetime(scheduled_lessons_df['date_planned']).dt.weekday >= 5
        ]
        if not weekend_lessons.empty:
            warnings.append(f"Lessons scheduled on weekends: {len(weekend_lessons)}")
        
        # Check for lesson number gaps
        lesson_numbers = sorted(scheduled_lessons_df['lesson_number'].unique())
        expected_numbers = list(range(1, len(lesson_numbers) + 1))
        missing_numbers = set(expected_numbers) - set(lesson_numbers)
        if missing_numbers:
            warnings.append(f"Missing lesson numbers: {sorted(missing_numbers)}")
        
        # Check for duplicate lesson numbers on same date
        duplicates = scheduled_lessons_df.groupby(['date_planned', 'lesson_number']).size()
        duplicate_lessons = duplicates[duplicates > 1]
        if not duplicate_lessons.empty:
            errors.append(f"Duplicate lesson numbers on same date: {len(duplicate_lessons)}")
        
        return {
            'valid': len(errors) == 0,
            'warnings': warnings,
            'errors': errors
        }
    
    def _get_academic_year(self, dates: pd.Series) -> pd.Series:
        """Determine academic year (e.g., 2025-2026)"""
        academic_years = []
        for date in dates:
            if date.month >= 8:  # August onwards
                academic_year = f"{date.year}-{date.year + 1}"
            else:  # January to July
                academic_year = f"{date.year - 1}-{date.year}"
            academic_years.append(academic_year)
        return pd.Series(academic_years)
    
    def _get_semester(self, dates: pd.Series) -> pd.Series:
        """Determine semester based on date"""
        semesters = []
        for date in dates:
            if 8 <= date.month <= 12:  # Fall semester
                semester = "Fall"
            elif 1 <= date.month <= 5:  # Spring semester
                semester = "Spring"
            else:  # Summer
                semester = "Summer"
            semesters.append(semester)
        return pd.Series(semesters)
    
    def _extract_objectives(self, content: str) -> List[str]:
        """Extract learning objectives from lesson content"""
        objectives = []
        
        # Look for common objective patterns
        patterns = [
            r'objective[s]?[:\s]+(.+?)(?:\n|$)',
            r'learning\s+target[s]?[:\s]+(.+?)(?:\n|$)',
            r'students?\s+will[:\s]+(.+?)(?:\n|$)',
            r'standard[s]?[:\s]+(.+?)(?:\n|$)',
            r'goal[s]?[:\s]+(.+?)(?:\n|$)',
            r'outcome[s]?[:\s]+(.+?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)
            objectives.extend(matches)
        
        # Clean and deduplicate objectives
        cleaned_objectives = []
        for obj in objectives:
            obj = obj.strip()
            if obj and obj not in cleaned_objectives:
                cleaned_objectives.append(obj)
        
        return cleaned_objectives
    
    def _extract_domain(self, title: str, content: str = "") -> str:
        """Extract domain from lesson title and content"""
        text = (title + " " + content).lower()
        
        if any(word in text for word in ['cyber', 'security', 'hacking', 'encryption']):
            return 'Cybersecurity'
        elif any(word in text for word in ['program', 'code', 'algorithm', 'function', 'variable']):
            return 'Programming'
        elif any(word in text for word in ['data', 'database', 'sql', 'analysis']):
            return 'Data Science'
        elif any(word in text for word in ['web', 'html', 'css', 'javascript']):
            return 'Web Development'
        elif any(word in text for word in ['robot', 'hardware', 'circuit', 'sensor']):
            return 'Hardware'
        elif any(word in text for word in ['network', 'internet', 'protocol', 'tcp']):
            return 'Networking'
        else:
            return 'Computer Science'
    
    def _extract_bloom_level(self, objective: str) -> str:
        """Extract Bloom's taxonomy level from objective"""
        obj_lower = objective.lower()
        
        # Create level (highest)
        if any(word in obj_lower for word in ['create', 'design', 'develop', 'construct', 'build', 'make']):
            return 'Create'
        # Evaluate level
        elif any(word in obj_lower for word in ['evaluate', 'judge', 'critique', 'assess', 'rate', 'compare']):
            return 'Evaluate'
        # Analyze level
        elif any(word in obj_lower for word in ['analyze', 'compare', 'contrast', 'examine', 'investigate', 'explore']):
            return 'Analyze'
        # Apply level
        elif any(word in obj_lower for word in ['apply', 'use', 'implement', 'demonstrate', 'execute', 'practice']):
            return 'Apply'
        # Understand level
        elif any(word in obj_lower for word in ['understand', 'explain', 'describe', 'summarize', 'interpret', 'classify']):
            return 'Understand'
        # Remember level (lowest)
        else:
            return 'Remember'

# Utility functions for standalone use
def process_lessons_and_calendar(lessons_df: pd.DataFrame, calendar_df: pd.DataFrame, 
                               hours_per_day: int = 1, class_id: int = None) -> Dict[str, pd.DataFrame]:
    """Standalone function to process lessons and calendar data"""
    processor = EdTrackCalendarProcessor()
    
    # Process calendar data
    processed_calendar = processor.process_calendar_data(calendar_df, calendar_df['school_id'].iloc[0] if not calendar_df.empty else 1)
    
    # Schedule lessons
    scheduled_lessons = processor.process_lessons_for_scheduling(lessons_df, processed_calendar, hours_per_day, class_id)
    
    # Extract learning targets
    learning_targets = processor.create_learning_targets_from_lessons(lessons_df)
    
    # Create lesson-target mappings
    lesson_target_mappings = processor.create_lesson_target_mappings(scheduled_lessons, learning_targets)
    
    return {
        'calendar': processed_calendar,
        'lessons': scheduled_lessons,
        'targets': learning_targets,
        'mappings': lesson_target_mappings
    }
