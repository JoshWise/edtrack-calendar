"""
EdTrack Advanced Visual Calendar Parser

This optional module uses OpenCV and OCR to parse visually complex,
color-coded school district calendars with symbols and special markers.

REQUIRES OPTIONAL DEPENDENCIES:
  pip install opencv-python-headless pytesseract pdf2image

SYSTEM DEPENDENCIES:
  - Tesseract OCR: brew install tesseract (macOS) or apt-get install tesseract-ocr (Linux)
  - Poppler: brew install poppler (macOS) or apt-get install poppler-utils (Linux)
"""

import os
import re
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

# Optional dependencies - graceful failure if not installed
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False


# Color thresholds in HSV (tune for your specific PDF/scanner)
COLOR_THRESHOLDS = {
    'jade':  ((75, 40, 30), (95, 255, 255)),      # cyan-green
    'green_star': ((45, 40, 40), (75, 255, 255)),  # green for vacation
    'purple': ((125, 40, 30), (155, 255, 255)),    # purple for PIR
    'pink':  ((150, 30, 180), (180, 255, 255)),    # magenta/pink for end-of-semester
    'yellow': ((20, 40, 40), (35, 255, 255)),      # yellow for PIR-T
    'brown': ((8, 40, 30), (20, 200, 200)),        # brown for snow days
    'white': ((0, 0, 200), (180, 25, 255)),        # white background
}


class VisualCalendarParser:
    """Advanced visual parser for color-coded calendars"""
    
    def __init__(self):
        if not OPENCV_AVAILABLE:
            raise ImportError("opencv-python-headless is required for visual parsing. Install with: pip install opencv-python-headless")
        if not TESSERACT_AVAILABLE:
            raise ImportError("pytesseract is required for visual parsing. Install with: pip install pytesseract")
        if not PDF2IMAGE_AVAILABLE:
            raise ImportError("pdf2image is required for PDF parsing. Install with: pip install pdf2image")
    
    def parse_pdf_calendar(self, pdf_path: str, school_id: int, fallback_year: Optional[int] = None) -> pd.DataFrame:
        """
        Parse a color-coded calendar PDF using visual analysis
        
        Args:
            pdf_path: Path to PDF file
            school_id: School ID from EdTrack
            fallback_year: Year to use if not detected in PDF
            
        Returns:
            DataFrame with parsed calendar data
        """
        # Convert PDF to images
        images = self._pdf_to_images(pdf_path)
        
        all_items = []
        for page_idx, img in enumerate(images):
            try:
                items = self._parse_calendar_page(img, fallback_year)
                for item in items:
                    item['page'] = page_idx + 1
                    item['school_id'] = school_id
                all_items.extend(items)
            except Exception as e:
                print(f"Warning: Page {page_idx + 1} parsing failed: {e}")
        
        # Convert to DataFrame
        df = pd.DataFrame(all_items)
        
        # Filter out rows without valid dates
        df = df[df['date'].notna()].copy()
        
        return df
    
    def _pdf_to_images(self, pdf_path: str, dpi: int = 200) -> List[np.ndarray]:
        """Convert PDF pages to OpenCV images"""
        pages = convert_from_path(pdf_path, dpi=dpi)
        images = []
        for page in pages:
            # Convert PIL RGB to OpenCV BGR
            arr = np.array(page)
            images.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
        return images
    
    def _find_calendar_grid(self, img: np.ndarray) -> Tuple[List[List[Tuple]], Tuple]:
        """
        Detect calendar grid cells using contour detection
        Supports both single-month and year-view (multi-month) calendars
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = img.shape[:2]
        
        # Try adaptive threshold approach
        thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 21, 10)
        
        # For year-view calendars, use a different strategy
        # Divide the page into a grid of month sections
        # Typical year calendar: 3 or 4 columns x 3 or 4 rows of months
        
        # Detect if this is a year-view by looking for multiple month patterns
        text_sample = ""
        try:
            import pytesseract
            # Sample middle section to check for multiple months
            sample_area = img[h//4:h//2, w//4:3*w//4]
            text_sample = pytesseract.image_to_string(sample_area)
        except:
            pass
        
        # Count how many month names appear
        import calendar as cal_module
        month_count = sum(1 for month_name in cal_module.month_name[1:] 
                         if month_name.upper() in text_sample.upper())
        
        is_year_view = month_count >= 3  # If 3+ months detected, it's a year view
        
        if is_year_view:
            # Year-view calendar: create a simple grid covering the whole page
            # Divide into smaller sections (assume 3x4 or 4x3 grid for 12 months)
            # For simplicity, create a uniform grid across the page
            cols = 21  # 3 months × 7 days
            rows = 24  # 4 months × 6 weeks
            
            cell_w = w // cols
            cell_h = h // rows
            
            cells = []
            for r in range(rows):
                row_cells = []
                for c in range(cols):
                    cx = c * cell_w
                    cy = r * cell_h
                    padx = max(1, cell_w // 20)
                    pady = max(1, cell_h // 20)
                    row_cells.append((cx + padx, cy + pady, cell_w - 2*padx, cell_h - 2*pady))
                cells.append(row_cells)
            
            return cells, (0, 0, w, h)
        else:
            # Single month calendar - original logic
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (50, 3))
            closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            max_area = 0
            cal_bbox = None
            
            for cnt in contours:
                x, y, wc, hc = cv2.boundingRect(cnt)
                area = wc * hc
                if area > max_area and wc > w * 0.4 and hc > h * 0.4:
                    max_area = area
                    cal_bbox = (x, y, wc, hc)
            
            if cal_bbox is None:
                raise RuntimeError("Could not detect calendar grid. Try increasing DPI or ensure grid lines are visible.")
            
            x, y, wc, hc = cal_bbox
            
            # Split into 7 columns x 6 rows (typical single month)
            cols = 7
            rows = 6
            cell_w = wc // cols
            cell_h = hc // rows
            
            cells = []
            for r in range(rows):
                row_cells = []
                for c in range(cols):
                    cx = x + c * cell_w
                    cy = y + r * cell_h
                    padx = max(2, cell_w // 40)
                    pady = max(2, cell_h // 40)
                    row_cells.append((cx + padx, cy + pady, cell_w - 2*padx, cell_h - 2*pady))
                cells.append(row_cells)
            
            return cells, cal_bbox
    
    def _classify_bg_color(self, cell_img: np.ndarray) -> Optional[str]:
        """Classify cell background color"""
        hsv = cv2.cvtColor(cell_img, cv2.COLOR_BGR2HSV)
        h, w = hsv.shape[:2]
        
        # Sample central region
        cx1, cy1 = int(w * 0.15), int(h * 0.15)
        cx2, cy2 = int(w * 0.85), int(h * 0.85)
        sample = hsv[cy1:cy2, cx1:cx2]
        
        # Check each color
        for name, (low, high) in COLOR_THRESHOLDS.items():
            mask = cv2.inRange(hsv, np.array(low), np.array(high))
            frac = (mask > 0).sum() / mask.size
            if frac > 0.08:  # 8% of cell matches this color
                return name
        
        return None
    
    def _ocr_cell_text(self, cell_img: np.ndarray) -> str:
        """Extract text from cell using OCR"""
        gray = cv2.cvtColor(cell_img, cv2.COLOR_BGR2GRAY)
        
        # Scale up for better OCR
        h, w = gray.shape
        scale = max(1, 2 * 100 // h)
        big = cv2.resize(gray, (w * scale, h * scale), interpolation=cv2.INTER_LINEAR)
        
        # Threshold
        thresh = cv2.adaptiveThreshold(big, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 15, 5)
        
        # OCR config
        config = '--psm 10 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz*★☆'
        raw = pytesseract.image_to_string(thresh, config=config)
        
        # Cleanup
        raw = raw.strip().replace('\n', ' ').replace('\x0c', '').strip()
        return raw
    
    def _extract_day_number(self, text: str) -> Optional[int]:
        """Extract day number from OCR text"""
        match = re.search(r'\b([0-9]{1,2})\b', text)
        if match:
            return int(match.group(1))
        return None
    
    def _detect_star(self, cell_img: np.ndarray, text: str) -> bool:
        """Detect star symbol visually or from OCR"""
        # Check OCR text
        if any(char in text for char in ['*', '★', '☆']):
            return True
        
        # Visual detection: look for yellow/bright area (star symbol)
        hsv = cv2.cvtColor(cell_img, cv2.COLOR_BGR2HSV)
        low, high = COLOR_THRESHOLDS['yellow']
        mask = cv2.inRange(hsv, np.array(low), np.array(high))
        
        if mask.sum() > 20:
            return True
        
        return False
    
    def _extract_month_year_from_header(self, img: np.ndarray, grid_bbox: Tuple) -> Tuple[Optional[int], Optional[int]]:
        """Extract month and year from calendar header"""
        x, y, w, h = grid_bbox
        header_area = img[max(0, y - 120):y, x:x + w]
        
        try:
            header_text = pytesseract.image_to_string(header_area)
            header_text = header_text.strip()
            
            # Find month
            import calendar as cal_module
            month = None
            for month_idx, month_name in enumerate(cal_module.month_name[1:], 1):
                if month_name.lower() in header_text.lower():
                    month = month_idx
                    break
            
            # Find year
            year_match = re.search(r'20\d{2}|\d{4}', header_text)
            year = int(year_match.group(0)) if year_match else None
            
            return month, year
        except Exception:
            return None, None
    
    def _parse_calendar_page(self, img: np.ndarray, fallback_year: Optional[int] = None) -> List[Dict]:
        """Parse a single calendar page"""
        cells, grid_bbox = self._find_calendar_grid(img)
        
        # Extract month/year from header
        month, year = self._extract_month_year_from_header(img, grid_bbox)
        
        if year is None:
            year = fallback_year or datetime.now().year
        if month is None:
            month = 1  # Default to January
        
        parsed_items = []
        day_cells = []
        
        # Process each cell
        for r, row in enumerate(cells):
            for c, bbox in enumerate(row):
                x, y, w, h = bbox
                cell_img = img[y:y+h, x:x+w]
                
                # Extract info
                text = self._ocr_cell_text(cell_img)
                bg_color = self._classify_bg_color(cell_img)
                day_num = self._extract_day_number(text)
                has_star = self._detect_star(cell_img, text)
                
                day_cells.append({
                    'r': r, 'c': c,
                    'text': text,
                    'bg': bg_color,
                    'daynum': day_num,
                    'star': has_star,
                    'img': cell_img
                })
        
        # Assign dates to cells
        for cell in day_cells:
            daynum = cell['daynum']
            
            if daynum is None:
                continue
            
            # Try to create date
            try:
                this_date = datetime(year, month, int(daynum)).date()
            except ValueError:
                # May be from previous/next month
                if cell['r'] == 0 and daynum > 20:
                    # Likely previous month
                    m = month - 1 if month > 1 else 12
                    y = year if month > 1 else year - 1
                    try:
                        this_date = datetime(y, m, daynum).date()
                    except:
                        continue
                else:
                    continue
            
            # Classify status based on visual markers
            status, flags = self._classify_date_status(cell, this_date)
            
            item = {
                'date': this_date.isoformat(),
                'day_of_week': this_date.strftime("%A"),
                'status': status,
                'bg_color': cell['bg'],
                'raw_text': cell['text'],
                'flags': flags,
                'pos': (cell['r'], cell['c'])
            }
            parsed_items.append(item)
        
        # Apply semester logic
        parsed_items = self._apply_semester_logic(parsed_items)
        
        return parsed_items
    
    def _classify_date_status(self, cell: Dict, date: datetime.date) -> Tuple[str, List[str]]:
        """Classify date status based on visual markers"""
        text = cell['text'].upper()
        bg = cell['bg']
        star = cell['star']
        flags = []
        
        # Check for specific markers
        has_P = any(tok in text for tok in ["PIR", "P "])
        has_T = 'T' in text
        has_SD = 'SD' in text
        has_N = 'N' in text
        
        # Determine status
        if star and bg == 'green_star':
            status = "vacation"
            flags.append("vacation_marker")
        elif bg == 'jade' and has_N:
            status = "orientation"
            flags.append("teacher_orientation")
        elif has_P or bg == 'purple':
            status = "PIR"
            flags.append("PIR")
        elif has_T or bg == 'yellow':
            status = "PIR"
            flags.append("PIR_T_day")
        elif has_SD or bg == 'brown':
            status = "snow_day"
            flags.append("snow_day")
        elif bg == 'pink' and star:
            status = "school_day"
            flags.append("end_of_semester")
        else:
            # Weekdays without special markers = school day
            dow = date.weekday()  # 0=Mon, 6=Sun
            if dow < 5:  # Mon-Fri
                status = "school_day"
            else:
                status = "non_school"
        
        return status, flags
    
    def _apply_semester_logic(self, items: List[Dict]) -> List[Dict]:
        """Apply complex semester start/end detection logic"""
        # Sort by date
        items_sorted = [it for it in items if it['date'] is not None]
        items_sorted.sort(key=lambda x: x['date'])
        
        # Find first semester start
        # Pattern: 2 jade "N" days, then 3 purple "P" days, then next school day
        found_first_sem = False
        for i in range(len(items_sorted) - 5):
            seq = items_sorted[i:i+5]
            
            # Check: 2 jade with N
            if (seq[0]['bg_color'] == 'jade' and 'N' in seq[0]['raw_text'] and
                seq[1]['bg_color'] == 'jade' and 'N' in seq[1]['raw_text'] and
                # 3 purple with P
                seq[2]['bg_color'] == 'purple' and 'P' in seq[2]['raw_text'] and
                seq[3]['bg_color'] == 'purple' and 'P' in seq[3]['raw_text'] and
                seq[4]['bg_color'] == 'purple' and 'P' in seq[4]['raw_text']):
                
                # Find next school day after seq[4]
                for j in range(i+5, len(items_sorted)):
                    if items_sorted[j]['status'] == 'school_day':
                        items_sorted[j]['flags'].append('first_semester_start')
                        found_first_sem = True
                        break
                break
        
        # Find second semester start
        # Pattern: pink star (end of semester), then next school day
        end_of_sem_indices = [i for i, it in enumerate(items_sorted) 
                              if 'end_of_semester' in it.get('flags', [])]
        
        if end_of_sem_indices:
            last_eos_idx = end_of_sem_indices[-1]
            # Find next school day
            for j in range(last_eos_idx + 1, len(items_sorted)):
                if items_sorted[j]['status'] == 'school_day':
                    items_sorted[j]['flags'].append('second_semester_start')
                    break
        
        return items_sorted
    
    def to_edtrack_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """Convert parsed data to EdTrack-compatible format"""
        # Ensure date column is datetime
        df['date'] = pd.to_datetime(df['date'])
        
        # Map status to day_type
        df['day_type'] = df['status'].map({
            'school_day': 'school_day',
            'vacation': 'vacation',
            'PIR': 'professional_day',
            'snow_day': 'snow_day',
            'non_school': 'weekend',
            'orientation': 'orientation'
        }).fillna('other')
        
        # Create description
        df['description'] = df.apply(self._create_description, axis=1)
        
        # Select EdTrack columns
        result = df[['date', 'day_type', 'description', 'school_id']].copy()
        
        return result
    
    def _create_description(self, row) -> str:
        """Create human-readable description"""
        desc_parts = []
        
        if 'first_semester_start' in row.get('flags', []):
            desc_parts.append("First Semester Start")
        elif 'second_semester_start' in row.get('flags', []):
            desc_parts.append("Second Semester Start")
        elif 'end_of_semester' in row.get('flags', []):
            desc_parts.append("End of Semester")
        elif 'teacher_orientation' in row.get('flags', []):
            desc_parts.append("Teacher Orientation")
        elif 'PIR' in row.get('flags', []):
            desc_parts.append("PIR Day")
        elif 'PIR_T_day' in row.get('flags', []):
            desc_parts.append("PIR (T-Day)")
        elif 'vacation_marker' in row.get('flags', []):
            desc_parts.append("Vacation")
        elif 'snow_day' in row.get('flags', []):
            desc_parts.append("Snow Day")
        elif row['status'] == 'school_day':
            desc_parts.append("Regular School Day")
        elif row['status'] == 'non_school':
            desc_parts.append("Weekend/Non-School")
        
        # Add raw text if it contains useful info
        if row.get('raw_text') and len(row['raw_text']) > 2:
            raw_clean = row['raw_text'].strip()
            if raw_clean and raw_clean not in desc_parts:
                desc_parts.append(f"({raw_clean})")
        
        return " - ".join(desc_parts) if desc_parts else "School Day"


def check_visual_parser_available() -> Tuple[bool, str]:
    """
    Check if visual parser dependencies are available
    
    Returns:
        Tuple of (available: bool, message: str)
    """
    missing = []
    
    if not OPENCV_AVAILABLE:
        missing.append("opencv-python-headless")
    if not TESSERACT_AVAILABLE:
        missing.append("pytesseract")
    if not PDF2IMAGE_AVAILABLE:
        missing.append("pdf2image")
    
    if missing:
        return False, f"Missing dependencies: {', '.join(missing)}. Install with: pip install {' '.join(missing)}"
    
    # Check for system dependencies
    try:
        pytesseract.get_tesseract_version()
    except:
        return False, "Tesseract OCR not installed. Install with: brew install tesseract (macOS) or apt-get install tesseract-ocr (Linux)"
    
    return True, "Visual parser available"


# Example standalone usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Parse visual calendar PDF')
    parser.add_argument('--input', required=True, help='PDF file path')
    parser.add_argument('--school_id', type=int, default=1, help='School ID')
    parser.add_argument('--fallback_year', type=int, default=None, help='Fallback year if not detected')
    parser.add_argument('--output', default='calendar_output.csv', help='Output CSV file')
    
    args = parser.parse_args()
    
    # Check dependencies
    available, msg = check_visual_parser_available()
    if not available:
        print(f"❌ {msg}")
        exit(1)
    
    print(f"📄 Parsing visual calendar: {args.input}")
    
    vparser = VisualCalendarParser()
    df = vparser.parse_pdf_calendar(args.input, args.school_id, args.fallback_year)
    
    # Convert to EdTrack format
    result = vparser.to_edtrack_format(df)
    
    # Save output
    result.to_csv(args.output, index=False)
    print(f"✅ Saved {len(result)} calendar dates to {args.output}")
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"   School days: {len(result[result['day_type']=='school_day'])}")
    print(f"   Vacations: {len(result[result['day_type']=='vacation'])}")
    print(f"   PIR days: {len(result[result['day_type']=='professional_day'])}")

