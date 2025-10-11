# Advanced Visual Calendar Parser Guide

## 🎨 What is the Visual Parser?

The **Advanced Visual Parser** is an optional feature that uses computer vision and OCR to parse visually complex, color-coded school district calendars.

### **When to Use It**

✅ **Use Visual Parser for:**
- Color-coded district calendars (jade, purple, pink backgrounds)
- Calendars with symbols (stars ★, special markers)
- Scanned PDF calendars with visual markers
- District-specific formats (PIR days, semester markers, orientation days)
- Image-based calendars (PNG, JPG)

❌ **Use Standard Parser for:**
- Text-based CSV, Excel, JSON files
- Simple DOCX with tables
- Text-only PDFs
- Most online calendar URLs

---

## 📦 Installation (Optional)

The visual parser requires additional dependencies that are **NOT required** for standard EdTrack operation.

### **Python Packages**

```bash
cd /Users/wised/Documents/edtrack-calendar
source venv/bin/activate
pip install opencv-python-headless pytesseract pdf2image
```

### **System Dependencies**

#### **macOS (Homebrew)**
```bash
brew install tesseract poppler
```

#### **Ubuntu/Debian Linux**
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

#### **Windows**
1. Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. Install [Poppler](https://blog.alivate.com.au/poppler-windows/)
3. Add both to PATH

---

## 🎯 What It Detects

### **Background Colors**
- **Jade/Cyan-Green** → Teacher orientation days ("N" markers)
- **Purple** → PIR (Professional In-service) days ("P" markers)
- **Pink** → End of semester markers (with stars ★)
- **Yellow** → PIR T-days
- **Brown** → Snow days ("SD" markers)
- **Green** → Vacation days (with star *)

### **Symbols**
- **★** → End of semester (pink background)
- **\*** → Vacation marker (green background)

### **Text Markers (OCR)**
- **"N"** → New teacher orientation
- **"P"** or **"PIR"** → Professional development day
- **"T"** → PIR T-day variant
- **"SD"** → Snow day

### **Complex Logic**
- **First Semester Start:** Detects 2 jade "N" days + 3 purple "P" days → next school day = semester start
- **Second Semester Start:** After pink star end-of-semester → next school day = semester start
- **Weekday Detection:** Mon-Fri without markers = school day

---

## 🔧 How to Use

### **In EdTrack UI**

1. Go to **Calendar Integration** page
2. Navigate to **"📅 Scrape or Upload Calendar Data"**
3. Select **"📁 Upload File"** method
4. Choose your school
5. Upload your calendar PDF/image
6. ✅ **Check the box:** "🎨 Use Advanced Visual Parser"
7. Click **"📁 Upload Calendar File"**

### **What Happens**

```
Without Visual Parser (Default):
  PDF → Text extraction → Parse dates → Basic calendar

With Visual Parser (Opt-in):
  PDF → Image conversion → OCR → Color detection → Symbol detection
    → Complex semester logic → Rich calendar with markers
```

---

## 📊 Output Comparison

### **Standard Parser Output:**
```csv
date,day_type,description
2026-01-16,school_day,Regular School Day
2026-05-29,school_day,Regular School Day
```

### **Visual Parser Output:**
```csv
date,day_type,description,flags
2026-01-16,school_day,End of Semester,end_of_semester
2026-05-29,school_day,End of Semester,end_of_semester
2026-08-25,school_day,First Semester Start,first_semester_start
2026-01-19,school_day,Second Semester Start,second_semester_start
2026-09-01,vacation,Vacation,vacation_marker
2026-10-15,professional_day,PIR Day,PIR
```

---

## ⚙️ Configuration

### **Color Thresholds**

In `calendar_visual_parser.py`, you can tune color detection:

```python
COLOR_THRESHOLDS = {
    'jade':  ((75, 40, 30), (95, 255, 255)),      # HSV range for jade
    'purple': ((125, 40, 30), (155, 255, 255)),   # HSV range for purple
    'pink':  ((150, 30, 180), (180, 255, 255)),   # HSV range for pink
    # ... etc
}
```

**How to Tune:**
1. If colors aren't detected correctly, adjust HSV ranges
2. First number = Hue (color), Second = Saturation, Third = Value (brightness)
3. Lower bound = (H_min, S_min, V_min)
4. Upper bound = (H_max, S_max, V_max)

### **Grid Detection**

If calendar grid isn't detected:
- Increase DPI in `_pdf_to_images()` (default 200)
- Adjust grid detection threshold in `_find_calendar_grid()`
- Ensure calendar has visible grid lines

---

## 🚨 Troubleshooting

### "Missing dependencies"
**Solution:** Install optional packages:
```bash
pip install opencv-python-headless pytesseract pdf2image
```

### "Tesseract not found"
**Solution:** Install Tesseract OCR:
- macOS: `brew install tesseract`
- Linux: `sudo apt-get install tesseract-ocr`
- Windows: Download from GitHub releases

### "Could not detect calendar grid"
**Solutions:**
- Ensure PDF has visible grid lines
- Increase DPI when converting PDF
- Try with a different page/month
- Fall back to standard parser

### "No dates detected"
**Solutions:**
- Check if PDF is scanned clearly
- Ensure numbers are readable
- Try increasing resolution
- Use standard parser for text-based PDFs

### "Colors not detected correctly"
**Solutions:**
- Tune COLOR_THRESHOLDS in `calendar_visual_parser.py`
- Check your PDF's actual color values
- Adjust HSV ranges for your specific scanner/PDF settings

---

## 🎓 District-Specific Features

### **Billings Career Center Calendar**

The visual parser is specifically designed to handle:
1. **Teacher Orientation** (jade background + "N")
2. **PIR Days** (purple background + "P" or yellow + "T")
3. **Semester Markers:**
   - First semester: After 2 jade N + 3 purple P sequence
   - Second semester: After pink star end-of-semester day
4. **Vacation Days** (green star)
5. **Snow Days** (brown background + "SD")

---

## 💡 Best Practices

1. **Try Standard Parser First**
   - Faster and works for most calendars
   - No additional dependencies

2. **Use Visual Parser When:**
   - You see 422 errors with standard parser
   - Calendar has color-coding you need to preserve
   - Need to detect semester start/end automatically
   - Have district-specific visual markers

3. **Fallback is Automatic**
   - If visual parser fails, system uses standard parser
   - No data loss, just less detail

4. **Performance:**
   - Standard parser: < 1 second
   - Visual parser: 5-10 seconds (OCR processing)

---

## 🔬 Technical Details

### **Processing Pipeline**

```
1. PDF → Images (pdf2image @ 200 DPI)
2. Grid Detection (OpenCV contours)
3. Cell Extraction (7 cols × 6 rows)
4. OCR per Cell (pytesseract)
5. Color Classification (HSV analysis)
6. Symbol Detection (visual + OCR)
7. Status Classification (rules-based)
8. Semester Logic (sequence detection)
9. EdTrack Format (standardized output)
```

### **Dependencies**

**Required for Visual Parser:**
- `opencv-python-headless` - Image processing
- `pytesseract` - OCR wrapper
- `pdf2image` - PDF to image conversion
- `tesseract` (system) - OCR engine
- `poppler` (system) - PDF rendering

**Not Required:**
- `playwright` - Only for interactive URLs
- These work independently

---

## 🆘 Support

If visual parser doesn't work:
1. Check error messages in UI
2. Verify dependencies installed: `pip list | grep opencv`
3. Test Tesseract: `tesseract --version`
4. Fall back to standard parser (uncheck the box)
5. Convert PDF to CSV manually if needed

---

## ✅ Quick Start

**Minimal test:**
```bash
# Install dependencies
pip install opencv-python-headless pytesseract pdf2image
brew install tesseract poppler

# Test in Python
python3 << EOF
from calendar_visual_parser import check_visual_parser_available
available, msg = check_visual_parser_available()
print(msg)
EOF
```

Should output: `"Visual parser available"` ✅

---

**The visual parser is completely optional. EdTrack works perfectly without it!**

