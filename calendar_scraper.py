"""
EdTrack Calendar Module - Web Scraper

This module uses Playwright to scrape lesson content and school calendars
from various educational websites, returning data in EdTrack-compatible format.
"""

import pandas as pd
import asyncio
from playwright.async_api import async_playwright
from datetime import datetime, timedelta
import re
import json
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

class EdTrackCalendarScraper:
    """Main scraper class for extracting lesson and calendar data"""
    
    def __init__(self):
        self.browser = None
        self.page = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=True)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

    async def scrape_lesson_content(self, url: str, class_id: int) -> pd.DataFrame:
        """
        Scrape lesson content from curriculum websites
        
        Args:
            url: URL to scrape lesson content from
            class_id: Class ID from EdTrack database
            
        Returns:
            DataFrame with lesson data compatible with EdTrack schema
        """
        if not self.browser:
            raise RuntimeError("Scraper not initialized. Use async context manager.")
            
        page = await self.browser.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Wait for content to load
            await page.wait_for_timeout(2000)
            
            # Extract lesson data based on common curriculum website patterns
            lessons_data = await page.evaluate("""
                () => {
                    const lessons = [];
                    let lessonNumber = 1;
                    
                    // Common lesson selectors for educational websites
                    const lessonSelectors = [
                        '.lesson', '.assignment', '.activity', '.module', 
                        '.chapter', '.unit', '.topic', '[data-lesson]',
                        '.course-item', '.curriculum-item', '.lesson-item'
                    ];
                    
                    // Try each selector pattern
                    for (const selector of lessonSelectors) {
                        const elements = document.querySelectorAll(selector);
                        
                        if (elements.length > 0) {
                            elements.forEach((el, index) => {
                                const title = el.querySelector('h1, h2, h3, h4, .title, .name, .lesson-title')?.textContent?.trim() || 
                                           el.textContent?.trim().split('\\n')[0] || 
                                           `Lesson ${lessonNumber}`;
                                
                                const content = el.textContent?.trim() || '';
                                const description = el.querySelector('.description, .summary, .overview')?.textContent?.trim() || '';
                                
                                // Extract duration information
                                const durationInfo = extractDurationInfo(content + ' ' + description);
                                
                                // Extract objectives/standards
                                const objectives = extractObjectives(content + ' ' + description);
                                
                                lessons.push({
                                    lesson_number: lessonNumber,
                                    title: title,
                                    description: description,
                                    content: content,
                                    duration_hours: durationInfo.duration_hours,
                                    duration_type: durationInfo.duration_type,
                                    sequence_number: durationInfo.sequence_number,
                                    total_sequence: durationInfo.total_sequence,
                                    objectives: objectives,
                                    source_url: window.location.href,
                                    element_selector: selector
                                });
                                
                                lessonNumber++;
                            });
                            break; // Use first successful selector
                        }
                    }
                    
                    // Helper function to extract duration information
                    function extractDurationInfo(text) {
                        const durationPatterns = [
                            // Sequential patterns: (1 of 4), (2 of 4), etc.
                            /(\\d+)\\s+of\\s+(\\d+)/gi,
                            // Days: (2 days), (3 days), etc.
                            /(\\d+)\\s+days?/gi,
                            // Hours: (2 hours), (3 hours), etc.
                            /(\\d+)\\s+hours?/gi,
                            // Blocks: (4 blocks), (2 blocks), etc.
                            /(\\d+)\\s+blocks?/gi,
                            // Generic numbers: (2), (3), etc.
                            /\\((\\d+)\\)/g
                        ];
                        
                        for (const pattern of durationPatterns) {
                            const match = pattern.exec(text);
                            if (match) {
                                const number = parseInt(match[1]);
                                const fullMatch = match[0].toLowerCase();
                                
                                if (fullMatch.includes('of')) {
                                    return {
                                        duration_hours: parseInt(match[2]) * 1.0,
                                        duration_type: 'sequential',
                                        sequence_number: number,
                                        total_sequence: parseInt(match[2])
                                    };
                                } else if (fullMatch.includes('day')) {
                                    return {
                                        duration_hours: number * 1.0,
                                        duration_type: 'days',
                                        sequence_number: null,
                                        total_sequence: null
                                    };
                                } else if (fullMatch.includes('hour')) {
                                    return {
                                        duration_hours: number,
                                        duration_type: 'hours',
                                        sequence_number: null,
                                        total_sequence: null
                                    };
                                } else if (fullMatch.includes('block')) {
                                    return {
                                        duration_hours: number,
                                        duration_type: 'blocks',
                                        sequence_number: null,
                                        total_sequence: null
                                    };
                                } else {
                                    return {
                                        duration_hours: number,
                                        duration_type: 'hours',
                                        sequence_number: null,
                                        total_sequence: null
                                    };
                                }
                            }
                        }
                        
                        // Default to 1 hour
                        return {
                            duration_hours: 1.0,
                            duration_type: 'hours',
                            sequence_number: null,
                            total_sequence: null
                        };
                    }
                    
                    // Helper function to extract objectives
                    function extractObjectives(text) {
                        const objectives = [];
                        const patterns = [
                            /objective[s]?[:\s]+(.+?)(?:\n|$)/gi,
                            /learning\s+target[s]?[:\s]+(.+?)(?:\n|$)/gi,
                            /students?\s+will[:\s]+(.+?)(?:\n|$)/gi,
                            /standard[s]?[:\s]+(.+?)(?:\n|$)/gi,
                            /goal[s]?[:\s]+(.+?)(?:\n|$)/gi
                        ];
                        
                        for (const pattern of patterns) {
                            let match;
                            while ((match = pattern.exec(text)) !== null) {
                                objectives.push(match[1].trim());
                            }
                        }
                        
                        return objectives;
                    }
                    
                    return lessons;
                }
            """)
            
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
            
        finally:
            await page.close()

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
