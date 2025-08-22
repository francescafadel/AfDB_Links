# AfDB Links - Project Data Extraction Tools

This repository contains Python tools for extracting project information from African Development Bank (AfDB) platforms, specifically designed to handle Cloudflare protection and extract comprehensive project data.

## 🎯 Project Overview

Successfully extracted **1,107 out of 1,109 projects** (99.8% success rate) from the MapAfrica platform, including:
- Project General Description
- Project Objectives  
- Beneficiaries information

## 📁 Repository Contents

### Core Tools
- **`mapafrica_selenium_extractor.py`** - Main extraction tool using Selenium to bypass Cloudflare
- **`mapafrica_extractor.py`** - Original requests-based extractor (limited by Cloudflare)
- **`afdb_harvester.py`** - AfDB documents harvester (limited by Cloudflare)
- **`clean_csv.py`** - Utility to clean input CSV files

### Data Files
- **`afdb_full_extraction.csv`** - Complete extracted dataset (1,107 projects)
- **`afdb_clean.csv`** - Cleaned input data from original corpus
- **`test_success_10.csv`** - Sample extraction results (first 10 projects)

### Documentation
- **`README.md`** - This file
- **`README_mapafrica.md`** - Detailed MapAfrica extractor documentation
- **`requirements.txt`** - Python dependencies

## 🚀 Quick Start

### Prerequisites
```bash
pip install -r requirements.txt
```

### Extract Project Data
```bash
# Process all projects (takes ~2.5 hours)
python3 mapafrica_selenium_extractor.py --projects afdb_clean.csv --out output.csv

# Test with first 10 projects
python3 mapafrica_selenium_extractor.py --projects afdb_clean.csv --out test.csv --max-rows 10
```

## 📊 Results Summary

### Success Metrics
- **Total Projects Processed**: 1,109
- **Successful Extractions**: 1,107 (99.8%)
- **Failed Extractions**: 2 projects
- **Processing Time**: ~2.5 hours
- **Data Quality**: Complete extraction of all three target sections

### Extracted Data Fields
- `Identifier` - Project ID
- `project_url` - MapAfrica project URL
- `general_description` - Project overview and context
- `objectives` - Development and specific objectives
- `beneficiaries` - Direct and indirect beneficiary information
- `status` - Extraction status (ok/not_found/error)
- `notes` - Diagnostic information

## 🔧 Technical Details

### Cloudflare Bypass Strategy
- **Selenium WebDriver** with Chrome headless browser
- **Rotating User-Agents** to mimic real browser behavior
- **Rate Limiting** (8-second intervals) to avoid detection
- **Session Management** with proper headers and cookies

### URL Structure
Projects are accessed using the pattern:
```
https://mapafrica.afdb.org/en/projects/46002-{PROJECT_ID}
```

### Error Handling
- Graceful handling of missing projects
- Comprehensive logging and status tracking
- Automatic retry mechanisms for failed requests

## 📈 Performance

The extraction process demonstrated excellent reliability:
- **99.8% success rate** across 1,109 projects
- **Consistent data quality** with complete section extraction
- **Robust error handling** for edge cases
- **Efficient processing** with minimal manual intervention

## 🤝 Contributing

This project successfully demonstrates automated data extraction from protected web platforms. The tools can be adapted for similar projects requiring:

- Cloudflare bypass techniques
- Large-scale web scraping
- Structured data extraction
- Robust error handling

## 📄 License

This project is for research and educational purposes. Please respect the terms of service of the target websites.

## 🔗 Links

- [MapAfrica Platform](https://mapafrica.afdb.org)
- [African Development Bank](https://www.afdb.org)
- [GitHub Repository](https://github.com/francescafadel/AfDB_Links.git)

---

**Note**: This repository contains the complete working solution that successfully extracted comprehensive project data from the MapAfrica platform, demonstrating effective techniques for handling modern web protection systems.
