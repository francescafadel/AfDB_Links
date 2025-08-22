# MapAfrica Project Extractor

A Python CLI tool that reads a CSV containing project identifiers, visits MapAfrica project pages, extracts project information, and writes a new CSV with the extracted data.

## Features

- **CSV Input Processing**: Reads project identifiers from CSV files
- **Multi-language Support**: Extracts content in both English and French
- **Robust Section Extraction**: Finds content under specific headings (h2/h3)
- **Error Handling**: Graceful handling of missing pages and parsing errors
- **Rate Limiting**: Configurable delays to respect server resources
- **Comprehensive Logging**: Real-time progress and status reporting

## Installation

1. **Install dependencies**:
   ```bash
   pip install requests beautifulsoup4 lxml urllib3
   ```

2. **Make the script executable** (optional):
   ```bash
   chmod +x mapafrica_extractor.py
   ```

## Usage

### Basic Usage

```bash
python3 mapafrica_extractor.py --projects input.csv
```

This will:
- Read project identifiers from `input.csv`
- Visit each MapAfrica project page
- Extract project information
- Save results to `mapafrica_output.csv`

### Advanced Usage

```bash
# Custom column name and output file
python3 mapafrica_extractor.py --projects input.csv --id-col ProjectID --out results.csv

# Slower rate limiting for better reliability
python3 mapafrica_extractor.py --projects input.csv --rate-limit 2.0

# Custom timeout and base URL
python3 mapafrica_extractor.py --projects input.csv --timeout 60 --base-url https://mapafrica.afdb.org
```

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--projects` | Path to input CSV file (required) | - |
| `--id-col` | Column name containing project identifiers | `Identifier` |
| `--out` | Output CSV file path | `mapafrica_output.csv` |
| `--rate-limit` | Delay between requests (seconds) | `1.0` |
| `--timeout` | Request timeout (seconds) | `30` |
| `--base-url` | Base URL for MapAfrica | `https://mapafrica.afdb.org` |

## Input CSV Format

Your input CSV should contain a column with project identifiers:

```csv
Identifier,ProjectName,Country
P-Z1-A00-001,Agricultural Development Project,Kenya
P-Z1-A00-002,Rural Infrastructure Project,Nigeria
P-Z1-A00-003,Water Management Project,Ethiopia
```

## Output CSV Format

The tool generates a CSV with the following columns:

| Column | Description | Example Values |
|--------|-------------|----------------|
| `Identifier` | Original project identifier | `P-Z1-A00-001` |
| `project_url` | Constructed MapAfrica URL | `https://mapafrica.afdb.org/project/P-Z1-A00-001` |
| `general_description` | Project general description text | `"This project aims to..."` |
| `objectives` | Project objectives text | `"The main objectives are..."` |
| `beneficiaries` | Beneficiaries information | `"Direct beneficiaries include..."` |
| `status` | Processing status | `ok`, `not_found`, `error` |
| `notes` | Diagnostic information | `"fr locale used; missing sections: beneficiaries"` |

## Extraction Logic

### Target Sections

The tool extracts content from these sections (case-insensitive):

**English:**
- "Project General Description" or "General Description"
- "Project Objectives"
- "Beneficiaries"

**French:**
- "Description générale du projet"
- "Objectifs du projet"
- "Bénéficiaires"

### Content Extraction

1. **Find Headings**: Locates h2/h3 elements matching target section names
2. **Extract Content**: Captures all content until the next heading at the same level
3. **Text Processing**: Joins paragraphs and list items with spaces
4. **Language Detection**: Detects French content and notes it

### URL Construction

The tool constructs project URLs using these patterns:
- `https://mapafrica.afdb.org/project/{identifier}`
- `https://mapafrica.afdb.org/projects/{identifier}`
- `https://mapafrica.afdb.org/project/view/{identifier}`
- `https://mapafrica.afdb.org/en/project/{identifier}`
- `https://mapafrica.afdb.org/fr/project/{identifier}`

## Status Codes

| Status | Description |
|--------|-------------|
| `ok` | Successfully extracted project information |
| `not_found` | Project page not found (404 or similar) |
| `error` | HTTP error or parsing error occurred |

## Examples

### Example 1: Basic Extraction
```bash
python3 mapafrica_extractor.py --projects sample_projects.csv
```

### Example 2: Custom Configuration
```bash
python3 mapafrica_extractor.py \
  --projects projects.csv \
  --id-col ProjectID \
  --out extracted_data.csv \
  --rate-limit 2.0 \
  --timeout 60
```

### Example 3: Different Column Name
```bash
python3 mapafrica_extractor.py \
  --projects data.csv \
  --id-col ID \
  --out results.csv
```

## Error Handling

The tool handles various error scenarios:

- **Missing CSV file**: Clear error message with file path
- **Missing ID column**: Lists available columns and exits
- **Empty identifiers**: Skips rows with empty identifiers
- **Network errors**: Retries with exponential backoff
- **Parsing errors**: Continues processing other projects
- **Missing sections**: Notes which sections were not found

## Logging

The tool provides comprehensive logging:
- **INFO**: Processing progress and successful extractions
- **WARNING**: Missing data or empty identifiers
- **ERROR**: Network failures and parsing errors

## Troubleshooting

### Common Issues

1. **403 Forbidden**: Website blocking automated requests
   - Try increasing `--rate-limit` to 2.0 or higher
   - Check if the website requires authentication

2. **404 Not Found**: Project pages don't exist
   - Verify project identifiers are correct
   - Check URL construction patterns

3. **Timeout Errors**: Slow website responses
   - Increase `--timeout` value
   - Reduce `--rate-limit` to be more patient

4. **Missing Sections**: Content not found on pages
   - Check if section headings match expected names
   - Verify page structure hasn't changed

### Debug Mode

To see more detailed logging, you can modify the logging level in the script:
```python
logging.basicConfig(level=logging.DEBUG, ...)
```

## Dependencies

- `requests`: HTTP library for making requests
- `beautifulsoup4`: HTML parsing library
- `lxml`: XML/HTML parser backend
- `urllib3`: HTTP client library

## License

This tool is provided as-is for educational and research purposes. Please respect the MapAfrica website's terms of service when using this tool.
