# EdTrack Calendar Module

A specialized module for scraping curriculum content and school calendars, processing them with Pandas, and integrating with the main EdTrack application via API.

## 🎯 Purpose

This module extends EdTrack's functionality by:
- **Scraping lesson content** from curriculum websites using Playwright
- **Processing school calendars** to identify school days and holidays
- **Scheduling lessons** across the academic calendar
- **Extracting learning targets** from lesson content
- **Providing API endpoints** for integration with the main EdTrack application

## 🏗️ Architecture

```
URL Scraping (Playwright) → Pandas Processing → API Endpoints → Main EdTrack
```

## 📊 Schema Compatibility

This module uses the **exact same database schema** as the main EdTrack application:
- Extends existing `Lesson` model with calendar fields
- Adds `SchoolCalendar` and `CalendarDay` models
- Extracts `LearningTarget` data from lesson content
- Maintains all existing relationships and constraints

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Railway account (for deployment)
- Main EdTrack application running

### Installation
```bash
# Clone the repository
git clone https://github.com/JoshWise/edtrack-calendar.git
cd edtrack-calendar

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Running Locally
```bash
# Start the API server
uvicorn calendar_api:app --host 0.0.0.0 --port 8000

# API will be available at http://localhost:8000
```

## 📁 Project Structure

```
edtrack-calendar/
├── calendar_api.py          # FastAPI application
├── calendar_scraper.py      # Playwright web scraping
├── calendar_processor.py    # Pandas data processing
├── calendar_models.py       # Database models (EdTrack compatible)
├── calendar_database.py     # Database operations
├── requirements.txt         # Python dependencies
├── railway.json            # Railway deployment config
├── .gitignore              # Git ignore rules
├── README.md               # This file
└── tests/                  # Test files
    ├── test_scraper.py
    ├── test_processor.py
    └── test_api.py
```

## 🔧 Core Components

### 1. Calendar Scraper (`calendar_scraper.py`)
- **Playwright-based web scraping**
- **Lesson content extraction** from curriculum websites
- **School calendar parsing** from district websites
- **Data validation** and cleaning

### 2. Calendar Processor (`calendar_processor.py`)
- **Pandas-based data processing**
- **Lesson scheduling** across school days
- **Learning target extraction** from lesson content
- **Duration pattern recognition** (sequential, days, hours, blocks)

### 3. Calendar API (`calendar_api.py`)
- **FastAPI endpoints** for external integration
- **Data validation** and error handling
- **JSON responses** compatible with main EdTrack
- **Async processing** for large datasets

### 4. Database Models (`calendar_models.py`)
- **EdTrack-compatible schema**
- **Extended Lesson model** with calendar fields
- **New calendar models** (SchoolCalendar, CalendarDay)
- **Same relationships** as main application

## 🌐 API Endpoints

### Scrape and Schedule Lessons
```http
POST /scrape-and-schedule
Content-Type: application/json

{
    "lesson_url": "https://curriculum.example.com/lessons",
    "calendar_url": "https://school.example.com/calendar",
    "class_id": 1,
    "school_id": 1,
    "hours_per_day": 2
}
```

### Scrape School Calendar Only
```http
POST /scrape-calendar
Content-Type: application/json

{
    "calendar_url": "https://school.example.com/calendar",
    "school_id": 1
}
```

### Scrape Lesson Content Only
```http
POST /scrape-lessons
Content-Type: application/json

{
    "lesson_url": "https://curriculum.example.com/lessons",
    "class_id": 1
}
```

## 🔄 Integration with Main EdTrack

### API Communication
```python
# Example integration from main EdTrack
import requests

def import_calendar_data(calendar_url: str, school_id: int):
    calendar_module_url = "https://edtrack-calendar.railway.app"
    
    response = requests.post(f"{calendar_module_url}/scrape-and-schedule", json={
        "lesson_url": lesson_url,
        "calendar_url": calendar_url,
        "class_id": class_id,
        "school_id": school_id,
        "hours_per_day": 2
    })
    
    if response.status_code == 200:
        data = response.json()
        # Process returned lessons and targets
        return data
    else:
        return {"error": "Failed to scrape calendar data"}
```

## 📊 Data Flow

1. **Scraping Phase:**
   - Playwright scrapes lesson content from curriculum URLs
   - Extracts school calendar data from district websites
   - Returns raw data as Pandas DataFrames

2. **Processing Phase:**
   - Pandas processes scraped data
   - Identifies lesson duration patterns
   - Schedules lessons across school days
   - Extracts learning targets from content

3. **Integration Phase:**
   - API returns processed data as JSON
   - Main EdTrack imports data via API calls
   - Data saved using existing database schema

## 🛠️ Development

### Running Tests
```bash
# Run all tests
pytest tests/

# Run specific test files
pytest tests/test_scraper.py
pytest tests/test_processor.py
pytest tests/test_api.py
```

### Adding New Scrapers
```python
# Add new curriculum website support
class CustomCurriculumScraper(EdTrackCalendarScraper):
    async def scrape_custom_site(self, url: str):
        # Custom scraping logic
        pass
```

## 🚀 Deployment

### Railway Deployment
1. **Connect GitHub repository** to Railway
2. **Add PostgreSQL database** service
3. **Set environment variables** for database connection
4. **Deploy automatically** on git push

### Environment Variables
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
API_KEY=your-secure-api-key
```

## 📈 Monitoring

- **Health checks** at `/health`
- **API documentation** at `/docs`
- **Metrics endpoint** at `/metrics`
- **Railway logs** for debugging

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 Author

JoshWise - [GitHub](https://github.com/JoshWise)

## 🆘 Support

For support and questions:
- Open an issue on GitHub
- Contact the development team
- Check the main EdTrack documentation
