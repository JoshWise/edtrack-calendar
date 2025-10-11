"""
EdTrack Calendar Module - Web Scraper

This module uses Playwright to scrape lesson content and school calendars
from various educational websites, returning data in EdTrack-compatible format.
"""

import pandas as pd
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

class EdTrackCalendarScraper:
    """Main scraper class for extracting lesson and calendar data"""
    
    def __init__(self, use_playwright: bool = False):
        """
        Initialize scraper
        
        Args:
            use_playwright: If True, try to use Playwright for JavaScript-heavy sites
                          If False (default), use requests/BeautifulSoup for static content
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.use_playwright = use_playwright
        self.playwright = None
        self.browser = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Only initialize Playwright if explicitly requested
        if self.use_playwright:
            try:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.chromium.launch(headless=True)
            except ImportError:
                print("Warning: Playwright not installed. Falling back to requests/BeautifulSoup.")
                self.use_playwright = False
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        if self.session:
            self.session.close()
    
    def _needs_javascript(self, url: str) -> bool:
        """
        Determine if a URL likely needs JavaScript/Playwright
        
        Args:
            url: URL to check
            
        Returns:
            True if Playwright is recommended, False if static scraping is sufficient
        """
        # URLs that typically need JavaScript
        js_indicators = [
            'classroom.google.com',
            'canvas.instructure.com',
            'blackboard.com',
            'schoology.com',
            'classroom.pltw.org',  # PLTW uses JavaScript
            'app.',  # Most app. subdomains are SPAs
            'portal.',  # Portals often require JS
        ]
        
        url_lower = url.lower()
        return any(indicator in url_lower for indicator in js_indicators)
    
    async def _scrape_with_method(self, url: str, prefer_playwright: bool = False):
        """
        Intelligently choose scraping method based on URL
        
        Args:
            url: URL to scrape
            prefer_playwright: Override to force Playwright
            
        Returns:
            Tuple of (content, method_used)
        """
        # Determine best method
        needs_js = self._needs_javascript(url) or prefer_playwright
        
        if needs_js and self.use_playwright and self.browser:
            # Use Playwright for JavaScript-heavy sites
            try:
                page = await self.browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=30000)
                content = await page.content()
                await page.close()
                return (content, 'playwright')
            except Exception as e:
                print(f"Playwright failed, falling back to requests: {e}")
                # Fall through to requests method
        
        # Use requests/BeautifulSoup for static content (default and fallback)
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return (response.content, 'requests')
        except Exception as e:
            raise Exception(f"Failed to fetch URL with both methods: {e}")

    async def scrape_lesson_content(self, url: str, class_id: int) -> pd.DataFrame:
        """
        Scrape lesson content from curriculum websites
        Uses intelligent method selection (requests or Playwright based on URL)
        
        Args:
            url: URL to scrape lesson content from
            class_id: Class ID from EdTrack database
            
        Returns:
            DataFrame with lesson data compatible with EdTrack schema
        """
        try:
            # Intelligently fetch the webpage
            content, method = await self._scrape_with_method(url)
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            lessons_data = []
            lesson_number = 1
            
            # Common lesson selectors for educational websites
            lesson_selectors = [
                '.lesson', '.assignment', '.activity', '.module', 
                '.chapter', '.unit', '.topic', '[data-lesson]',
                '.course-item', '.curriculum-item', '.lesson-item'
            ]
            
            # Try each selector pattern
            for selector in lesson_selectors:
                elements = soup.select(selector)
                
                if elements:
                    for element in elements:
                        # Extract title
                        title_elem = element.find(['h1', 'h2', 'h3', 'h4', '.title', '.name', '.lesson-title'])
                        title = title_elem.get_text().strip() if title_elem else element.get_text().strip().split('\n')[0]
                        
                        if not title:
                            title = f"Lesson {lesson_number}"
                        
                        # Extract content
                        content = element.get_text().strip()
                        
                        # Extract description
                        desc_elem = element.find(['.description', '.summary', '.overview'])
                        description = desc_elem.get_text().strip() if desc_elem else ''
                        
                        # Extract duration information
                        duration_info = self._extract_duration_info(content + ' ' + description)
                        
                        # Extract objectives
                        objectives = self._extract_objectives(content + ' ' + description)
                        
                        lessons_data.append({
                            'lesson_number': lesson_number,
                            'title': title,
                            'description': description,
                            'content': content,
                            'duration_hours': duration_info['duration_hours'],
                            'duration_type': duration_info['duration_type'],
                            'sequence_number': duration_info['sequence_number'],
                            'total_sequence': duration_info['total_sequence'],
                            'objectives': objectives,
                            'source_url': url,
                            'element_selector': selector
                        })
                        
                        lesson_number += 1
                    
                    break  # Use first successful selector
            
            # Convert to DataFrame with EdTrack-compatible schema
            if not lessons_data:
                return pd.DataFrame()
                
            df = pd.DataFrame(lessons_data)
            
            # Add EdTrack-compatible fields
            df['class_id'] = class_id
            df['status'] = 'planned'
            df['file_type'] = 'web'
            df['parsed_content'] = df['content']
            df['source_file'] = df['source_url']
            df['created_at'] = datetime.now()
            df['updated_at'] = datetime.now()
            
            # Rename columns to match EdTrack schema
            df = df.rename(columns={
                'content': 'notes',
                'source_url': 'source_file'
            })
            
            # Clean up DataFrame
            df = df.drop(columns=['description', 'element_selector'], errors='ignore')
            
            return df
            
        except Exception as e:
            print(f"Error scraping lesson content: {e}")
            return pd.DataFrame()
    
    def _extract_duration_info(self, text: str) -> dict:
        """Extract duration information from text"""
        duration_patterns = [
            # Sequential patterns: (1 of 4), (2 of 4), etc.
            r'(\d+)\s+of\s+(\d+)',
            # Days: (2 days), (3 days), etc.
            r'(\d+)\s+days?',
            # Hours: (2 hours), (3 hours), etc.
            r'(\d+)\s+hours?',
            # Blocks: (4 blocks), (2 blocks), etc.
            r'(\d+)\s+blocks?',
            # Generic numbers: (2), (3), etc.
            r'\((\d+)\)'
        ]
        
        for pattern in duration_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                number = int(match.group(1))
                full_match = match.group(0).lower()
                
                if 'of' in full_match:
                    total = int(match.group(2))
                    return {
                        'duration_hours': total * 1.0,
                        'duration_type': 'sequential',
                        'sequence_number': number,
                        'total_sequence': total
                    }
                elif 'day' in full_match:
                    return {
                        'duration_hours': number * 1.0,
                        'duration_type': 'days',
                        'sequence_number': None,
                        'total_sequence': None
                    }
                elif 'hour' in full_match:
                    return {
                        'duration_hours': number,
                        'duration_type': 'hours',
                        'sequence_number': None,
                        'total_sequence': None
                    }
                elif 'block' in full_match:
                    return {
                        'duration_hours': number,
                        'duration_type': 'blocks',
                        'sequence_number': None,
                        'total_sequence': None
                    }
                else:
                    return {
                        'duration_hours': number,
                        'duration_type': 'hours',
                        'sequence_number': None,
                        'total_sequence': None
                    }
        
        # Default to 1 hour
        return {
            'duration_hours': 1.0,
            'duration_type': 'hours',
            'sequence_number': None,
            'total_sequence': None
        }
    
    def _extract_objectives(self, text: str) -> list:
        """Extract objectives from text"""
        objectives = []
        patterns = [
            r'objective[s]?[:\s]+(.+?)(?:\n|$)',
            r'learning\s+target[s]?[:\s]+(.+?)(?:\n|$)',
            r'students?\s+will[:\s]+(.+?)(?:\n|$)',
            r'standard[s]?[:\s]+(.+?)(?:\n|$)',
            r'goal[s]?[:\s]+(.+?)(?:\n|$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            objectives.extend(matches)
        
        return [obj.strip() for obj in objectives if obj.strip()]
    
    def _extract_date_from_element(self, element) -> Optional[str]:
        """Extract date from an HTML element"""
        # Try data-date attribute first
        date_str = element.get('data-date')
        if date_str:
            return date_str
        
        # Try nested data-date
        nested_date = element.select_one('[data-date]')
        if nested_date:
            return nested_date.get('data-date')
        
        # Try text content for date patterns
        text = element.get_text()
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2}-\d{1,2}-\d{4}',  # MM-DD-YYYY
            r'\d{1,2}\s+\w+\s+\d{4}'   # DD Month YYYY
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        
        return None
    
    def _determine_school_day(self, element, title: str) -> bool:
        """Determine if an event is a school day"""
        no_school_keywords = [
            'no school', 'holiday', 'break', 'vacation',
            'closed', 'in-service', 'teacher work day',
            'professional development'
        ]
        
        # Get element classes
        class_name = ' '.join(element.get('class', [])).lower()
        title_lower = title.lower()
        
        # Check class names
        if 'no-school' in class_name or 'holiday' in class_name or 'break' in class_name:
            return False
        
        # Check title content
        for keyword in no_school_keywords:
            if keyword in title_lower:
                return False
        
        return True
    
    def _determine_day_type(self, element, title: str) -> str:
        """Determine the type of day"""
        class_name = ' '.join(element.get('class', [])).lower()
        title_lower = title.lower()
        
        if 'early' in title_lower or 'early' in class_name:
            return 'early_release'
        elif 'holiday' in title_lower or 'holiday' in class_name:
            return 'holiday'
        elif not self._determine_school_day(element, title):
            return 'no_school'
        else:
            return 'regular'

    async def scrape_school_calendar(self, url: str, school_id: int) -> pd.DataFrame:
        """
        Scrape school calendar from district websites
        Uses intelligent method selection (requests or Playwright based on URL)
        
        Args:
            url: URL to scrape calendar from
            school_id: School ID from EdTrack database
            
        Returns:
            DataFrame with calendar data compatible with EdTrack schema
        """
        try:
            # Intelligently fetch the webpage
            content, method = await self._scrape_with_method(url)
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            calendar_data = []
            
            # Common calendar selectors
            calendar_selectors = [
                '.calendar-event', '.school-day', '.event', 
                '.calendar-day', '.day-event', '[data-date]',
                '.calendar-item', '.event-item', '.school-event'
            ]
            
            # Try each selector pattern
            for selector in calendar_selectors:
                elements = soup.select(selector)
                
                if elements:
                    for element in elements:
                        # Extract date
                        date_str = self._extract_date_from_element(element)
                        if date_str:
                            title = element.get_text().strip()
                            is_school_day = self._determine_school_day(element, title)
                            day_type = self._determine_day_type(element, title)
                            
                            calendar_data.append({
                                'date': date_str,
                                'title': title,
                                'is_school_day': is_school_day,
                                'day_type': day_type,
                                'notes': title
                            })
                    break  # Use first successful selector
            
            # Convert to DataFrame with EdTrack-compatible schema
            if not calendar_data:
                return pd.DataFrame()
                
            df = pd.DataFrame(calendar_data)
            
            # Add EdTrack-compatible fields
            df['school_id'] = school_id
            df['created_at'] = datetime.now()
            df['updated_at'] = datetime.now()
            
            # Convert date column to datetime
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Remove rows with invalid dates
            df = df.dropna(subset=['date'])
            
            return df
            
        finally:
            await page.close()

    async def scrape_curriculum_metadata(self, url: str) -> Dict[str, Any]:
        """
        Scrape metadata about curriculum content
        Uses intelligent method selection (requests or Playwright based on URL)
        
        Args:
            url: URL to scrape metadata from
            
        Returns:
            Dictionary with curriculum metadata
        """
        try:
            # Intelligently fetch the webpage
            content, method = await self._scrape_with_method(url)
            
            # Parse HTML
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract metadata using BeautifulSoup
            title = soup.title.string if soup.title else ''
            description_tag = soup.find('meta', attrs={'name': 'description'})
            description = description_tag.get('content', '') if description_tag else ''
            
            # Extract curriculum type
            title_lower = title.lower()
            if 'pltw' in title_lower:
                curriculum_type = 'PLTW'
            elif 'ap' in title_lower:
                curriculum_type = 'AP'
            elif 'ib' in title_lower:
                curriculum_type = 'IB'
            else:
                curriculum_type = 'Custom'
            
            # Extract grade levels
            body_text = soup.get_text().lower()
            grade_pattern = r'grade\s+(\d+)|(\d+)th\s+grade'
            grade_matches = re.findall(grade_pattern, body_text, re.IGNORECASE)
            grade_levels = list(set([m[0] or m[1] for m in grade_matches if m[0] or m[1]]))
            
            # Extract subject areas
            subject_keywords = [
                'computer science', 'programming', 'coding', 'cybersecurity',
                'engineering', 'mathematics', 'science', 'technology'
            ]
            subject_areas = [kw for kw in subject_keywords if kw in body_text]
            
            # Count total lessons
            lesson_selectors = ['.lesson', '.assignment', '.activity', '.module']
            total_lessons = sum(len(soup.select(sel)) for sel in lesson_selectors)
            
            # Try to find last updated date
            update_selectors = ['.last-updated', '.updated', '.modified', '[data-updated]', '.date-modified']
            last_updated = None
            for selector in update_selectors:
                element = soup.select_one(selector)
                if element:
                    last_updated = element.get_text().strip()
                    break
            
            metadata = {
                'title': title,
                'description': description,
                'curriculum_type': curriculum_type,
                'grade_levels': grade_levels,
                'subject_areas': subject_areas,
                'total_lessons': total_lessons,
                'last_updated': last_updated,
                'url': url
            }
            
            return metadata
            
        except Exception as e:
            return {
                'title': '',
                'description': '',
                'curriculum_type': 'Unknown',
                'grade_levels': [],
                'subject_areas': [],
                'total_lessons': 0,
                'last_updated': None,
                'url': url,
                'error': str(e)
            }

# Utility functions for standalone use
async def scrape_lesson_content(url: str, class_id: int) -> pd.DataFrame:
    """Standalone function to scrape lesson content"""
    async with EdTrackCalendarScraper() as scraper:
        return await scraper.scrape_lesson_content(url, class_id)

async def scrape_school_calendar(url: str, school_id: int) -> pd.DataFrame:
    """Standalone function to scrape school calendar"""
    async with EdTrackCalendarScraper() as scraper:
        return await scraper.scrape_school_calendar(url, school_id)

async def scrape_curriculum_metadata(url: str) -> Dict[str, Any]:
    """Standalone function to scrape curriculum metadata"""
    async with EdTrackCalendarScraper() as scraper:
        return await scraper.scrape_curriculum_metadata(url)
