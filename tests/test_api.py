"""
Test cases for calendar API functionality
"""

import pytest
from fastapi.testclient import TestClient
from calendar_api import app
import pandas as pd
from datetime import datetime

# Create test client
client = TestClient(app)

class TestCalendarAPI:
    """Test cases for calendar API"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "endpoints" in data
    
    def test_scrape_calendar_request_validation(self):
        """Test calendar scraping request validation"""
        # Test with missing fields
        response = client.post("/scrape-calendar", json={})
        assert response.status_code == 422  # Validation error
        
        # Test with invalid data types
        response = client.post("/scrape-calendar", json={
            "calendar_url": "https://example.com",
            "school_id": "invalid"  # Should be int
        })
        assert response.status_code == 422
    
    def test_scrape_lessons_request_validation(self):
        """Test lesson scraping request validation"""
        # Test with missing fields
        response = client.post("/scrape-lessons", json={})
        assert response.status_code == 422
        
        # Test with invalid data types
        response = client.post("/scrape-lessons", json={
            "lesson_url": "https://example.com",
            "class_id": "invalid"  # Should be int
        })
        assert response.status_code == 422
    
    def test_scrape_and_schedule_request_validation(self):
        """Test combined scraping request validation"""
        # Test with missing fields
        response = client.post("/scrape-and-schedule", json={})
        assert response.status_code == 422
        
        # Test with valid request structure
        valid_request = {
            "lesson_url": "https://example.com/lessons",
            "calendar_url": "https://example.com/calendar",
            "class_id": 1,
            "school_id": 1,
            "hours_per_day": 2
        }
        
        # This will fail due to network issues, but should validate request structure
        response = client.post("/scrape-and-schedule", json=valid_request)
        # Should not be a validation error (422)
        assert response.status_code != 422
    
    def test_curriculum_metadata_request_validation(self):
        """Test curriculum metadata request validation"""
        # Test with missing fields
        response = client.post("/curriculum-metadata", json={})
        assert response.status_code == 422
        
        # Test with valid request structure
        valid_request = {
            "lesson_url": "https://example.com/curriculum",
            "class_id": 1
        }
        
        # This will fail due to network issues, but should validate request structure
        response = client.post("/curriculum-metadata", json=valid_request)
        # Should not be a validation error (422)
        assert response.status_code != 422
    
    def test_process_data_request_validation(self):
        """Test data processing request validation"""
        # Test with missing fields
        response = client.post("/process-data", json={})
        assert response.status_code == 422
        
        # Test with valid request structure
        valid_request = {
            "calendar_data": [
                {
                    "date": "2024-01-15",
                    "is_school_day": True,
                    "day_type": "regular"
                }
            ],
            "lesson_data": [
                {
                    "lesson_number": 1,
                    "title": "Test Lesson",
                    "duration_hours": 1.0
                }
            ],
            "target_data": [
                {
                    "code": "LT-001-01",
                    "short_name": "Test Target",
                    "description": "Test description"
                }
            ],
            "school_id": 1,
            "class_id": 1
        }
        
        # This should process successfully
        response = client.post("/process-data", json=valid_request)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "success"
        assert "data" in data
        assert "summary" in data
    
    def test_api_response_structure(self):
        """Test API response structure"""
        # Test with valid data processing request
        valid_request = {
            "calendar_data": [
                {
                    "date": "2024-01-15",
                    "is_school_day": True,
                    "day_type": "regular"
                }
            ],
            "lesson_data": [
                {
                    "lesson_number": 1,
                    "title": "Test Lesson",
                    "duration_hours": 1.0
                }
            ],
            "target_data": [],
            "school_id": 1,
            "class_id": 1
        }
        
        response = client.post("/process-data", json=valid_request)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check response structure
        assert "status" in data
        assert "message" in data
        assert "data" in data
        assert "summary" in data
        
        # Check data structure
        assert "calendar" in data["data"]
        assert "lessons" in data["data"]
        assert "targets" in data["data"]
        assert "mappings" in data["data"]
        
        # Check summary structure
        assert "total_lessons" in data["summary"]
        assert "total_targets" in data["summary"]
        assert "schedule_valid" in data["summary"]
    
    def test_error_handling(self):
        """Test error handling"""
        # Test with invalid URL (should cause network error)
        response = client.post("/scrape-calendar", json={
            "calendar_url": "https://invalid-url-that-does-not-exist.com",
            "school_id": 1
        })
        
        # Should return 500 error due to network failure
        assert response.status_code == 500
        
        data = response.json()
        assert "detail" in data
        assert "Failed to scrape calendar" in data["detail"]
    
    def test_cors_headers(self):
        """Test CORS headers"""
        response = client.options("/health")
        assert response.status_code == 200
        
        # Check CORS headers
        headers = response.headers
        assert "access-control-allow-origin" in headers
        assert "access-control-allow-methods" in headers
        assert "access-control-allow-headers" in headers
    
    def test_documentation_endpoints(self):
        """Test documentation endpoints"""
        # Test OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200
        
        # Test ReDoc
        response = client.get("/redoc")
        assert response.status_code == 200
        
        # Test OpenAPI JSON
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        data = response.json()
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
