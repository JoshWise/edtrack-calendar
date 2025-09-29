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
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            self.session.close()

    async def scrape_lesson_content(self, url: str, class_id: int) -> pd.DataFrame:
        """
        Scrape lesson content from curriculum websites
        
        Args:
            url: URL to scrape lesson content from
            class_id: Class ID from EdTrack database
            
        Returns:
            DataFrame with lesson data compatible with EdTrack schema
        """
        try:
            # Fetch the webpage
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
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

    async def scrape_school_calendar(self, url: str, school_id: int) -> pd.DataFrame:
        """
        Scrape school calendar from district websites
        
        Args:
            url: URL to scrape calendar from
            school_id: School ID from EdTrack database
            
        Returns:
            DataFrame with calendar data compatible with EdTrack schema
        """
        if not self.browser:
            raise RuntimeError("Scraper not initialized. Use async context manager.")
            
        page = await self.browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for calendar to load
            await page.wait_for_timeout(3000)
            
            # Extract calendar data
            calendar_data = await page.evaluate("""
                () => {
                    const events = [];
                    
                    // Common calendar selectors
                    const calendarSelectors = [
                        '.calendar-event', '.school-day', '.event', 
                        '.calendar-day', '.day-event', '[data-date]',
                        '.calendar-item', '.event-item', '.school-event'
                    ];
                    
                    // Try different calendar formats
                    for (const selector of calendarSelectors) {
                        const elements = document.querySelectorAll(selector);
                        
                        if (elements.length > 0) {
                            elements.forEach(el => {
                                // Extract date from various formats
                                const dateStr = extractDate(el);
                                if (dateStr) {
                                    const title = el.textContent?.trim() || '';
                                    const isSchoolDay = determineSchoolDay(el, title);
                                    const dayType = determineDayType(el, title);
                                    
                                    events.push({
                                        date: dateStr,
                                        title: title,
                                        is_school_day: isSchoolDay,
                                        day_type: dayType,
                                        notes: title
                                    });
                                }
                            });
                            break; // Use first successful selector
                        }
                    }
                    
                    // Helper function to extract date
                    function extractDate(element) {
                        // Try data-date attribute first
                        let dateStr = element.getAttribute('data-date');
                        if (dateStr) return dateStr;
                        
                        // Try nested data-date
                        const nestedDate = element.querySelector('[data-date]');
                        if (nestedDate) return nestedDate.getAttribute('data-date');
                        
                        // Try text content for date patterns
                        const text = element.textContent || '';
                        const datePatterns = [
                            /\\d{1,2}\\/\\d{1,2}\\/\\d{4}/,  // MM/DD/YYYY
                            /\\d{4}-\\d{1,2}-\\d{1,2}/,      // YYYY-MM-DD
                            /\\d{1,2}-\\d{1,2}-\\d{4}/,      // MM-DD-YYYY
                            /\\d{1,2}\\s+\\w+\\s+\\d{4}/     // DD Month YYYY
                        ];
                        
                        for (const pattern of datePatterns) {
                            const match = text.match(pattern);
                            if (match) return match[0];
                        }
                        
                        return null;
                    }
                    
                    // Helper function to determine if it's a school day
                    function determineSchoolDay(element, title) {
                        const noSchoolKeywords = [
                            'no school', 'holiday', 'break', 'vacation',
                            'closed', 'in-service', 'teacher work day',
                            'professional development'
                        ];
                        
                        const className = element.className.toLowerCase();
                        const titleLower = title.toLowerCase();
                        
                        // Check class names
                        if (className.includes('no-school') || 
                            className.includes('holiday') || 
                            className.includes('break')) {
                            return false;
                        }
                        
                        // Check title content
                        for (const keyword of noSchoolKeywords) {
                            if (titleLower.includes(keyword)) {
                                return false;
                            }
                        }
                        
                        return true;
                    }
                    
                    // Helper function to determine day type
                    function determineDayType(element, title) {
                        const className = element.className.toLowerCase();
                        const titleLower = title.toLowerCase();
                        
                        if (titleLower.includes('early') || className.includes('early')) {
                            return 'early_release';
                        } else if (titleLower.includes('holiday') || className.includes('holiday')) {
                            return 'holiday';
                        } else if (!determineSchoolDay(element, title)) {
                            return 'no_school';
                        } else {
                            return 'regular';
                        }
                    }
                    
                    return events;
                }
            """)
            
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
        
        Args:
            url: URL to scrape metadata from
            
        Returns:
            Dictionary with curriculum metadata
        """
        if not self.browser:
            raise RuntimeError("Scraper not initialized. Use async context manager.")
            
        page = await self.browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            metadata = await page.evaluate("""
                () => {
                    return {
                        title: document.title,
                        description: document.querySelector('meta[name="description"]')?.getAttribute('content') || '',
                        curriculum_type: extractCurriculumType(),
                        grade_levels: extractGradeLevels(),
                        subject_areas: extractSubjectAreas(),
                        total_lessons: document.querySelectorAll('.lesson, .assignment, .activity, .module').length,
                        last_updated: extractLastUpdated(),
                        url: window.location.href
                    };
                }
                
                function extractCurriculumType() {
                    const title = document.title.toLowerCase();
                    if (title.includes('pltw')) return 'PLTW';
                    if (title.includes('ap')) return 'AP';
                    if (title.includes('ib')) return 'IB';
                    return 'Custom';
                }
                
                function extractGradeLevels() {
                    const text = document.body.textContent.toLowerCase();
                    const grades = [];
                    const gradePattern = /grade\\s+(\\d+)|(\\d+)th\\s+grade/gi;
                    let match;
                    while ((match = gradePattern.exec(text)) !== null) {
                        grades.push(match[1] || match[2]);
                    }
                    return [...new Set(grades)];
                }
                
                function extractSubjectAreas() {
                    const text = document.body.textContent.toLowerCase();
                    const subjects = [];
                    const subjectKeywords = [
                        'computer science', 'programming', 'coding', 'cybersecurity',
                        'engineering', 'mathematics', 'science', 'technology'
                    ];
                    
                    for (const keyword of subjectKeywords) {
                        if (text.includes(keyword)) {
                            subjects.push(keyword);
                        }
                    }
                    
                    return subjects;
                }
                
                function extractLastUpdated() {
                    // Try to find last updated date
                    const updateSelectors = [
                        '.last-updated', '.updated', '.modified', 
                        '[data-updated]', '.date-modified'
                    ];
                    
                    for (const selector of updateSelectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            return element.textContent.trim();
                        }
                    }
                    
                    return null;
                }
            """)
            
            return metadata
            
        finally:
            await page.close()

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
