#!/usr/bin/env python3
"""
MapAfrica Project Extractor using Selenium to handle Cloudflare protection.

This tool extracts project information from MapAfrica project pages by bypassing
Cloudflare protection using Selenium WebDriver with Chrome headless browser.

Author: Francesca Fadel
Repository: https://github.com/francescafadel/AfDB_Links.git
"""

import csv
import logging
import time
import random
from typing import List, Dict, Optional
from urllib.parse import urljoin
import argparse

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from bs4 import BeautifulSoup
except ImportError:
    print("Selenium not installed. Please install with: pip install selenium")
    exit(1)


class MapAfricaExtractor:
    """
    Extracts project information from MapAfrica project pages using Selenium.
    
    This class handles Cloudflare protection by using a headless Chrome browser
    with rotating user agents and proper session management.
    """
    
    def __init__(self, base_url: str = "https://mapafrica.afdb.org", 
                 rate_limit: float = 2.0, timeout: int = 30):
        """
        Initialize the MapAfrica extractor.
        
        Args:
            base_url: Base URL for MapAfrica platform
            rate_limit: Delay between requests in seconds
            timeout: Page load timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.rate_limit = rate_limit
        self.timeout = timeout
        
        # Target sections to extract (English and French)
        self.target_sections = {
            'general_description': [
                'Project General Description',
                'General Description', 
                'Description générale du projet'
            ],
            'objectives': [
                'Project Objectives',
                'Objectifs du projet'
            ],
            'beneficiaries': [
                'Beneficiaries',
                'Bénéficiaires'
            ]
        }
        
        # User agents to rotate for anti-detection
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
        
        self.driver = None
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('mapafrica_extraction.log')
            ]
        )
        return logging.getLogger(__name__)
    
    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver with anti-detection settings."""
        options = Options()
        
        # Headless mode and anti-detection settings
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=' + random.choice(self.user_agents))
        
        # Additional anti-detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Create driver
        driver = webdriver.Chrome(options=options)
        
        # Execute script to remove webdriver property
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver
    
    def _construct_project_url(self, identifier: str) -> str:
        """
        Construct the MapAfrica project URL using the correct pattern.
        
        Args:
            identifier: Project identifier (e.g., P-ZW-AAG-008)
            
        Returns:
            Complete project URL
        """
        return f"{self.base_url}/en/projects/46002-{identifier}"
    
    def _get_page_content(self, url: str) -> Optional[str]:
        """
        Get page content using Selenium with enhanced debugging.
        
        Args:
            url: URL to fetch
            
        Returns:
            Page HTML content or None if failed
        """
        try:
            self.logger.debug(f"Navigating to: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            if not self._wait_for_page_load():
                return None
            
            # Wait additional time for dynamic content
            time.sleep(3)
            
            # Check if page contains project information
            page_source = self.driver.page_source
            if ("project general description" in page_source.lower() or 
                "project objectives" in page_source.lower() or
                "beneficiaries" in page_source.lower()):
                self.logger.info("Found project content on page")
                return page_source
            else:
                self.logger.warning("Page doesn't appear to contain project information")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting page content for {url}: {e}")
            return None
    
    def _wait_for_page_load(self) -> bool:
        """
        Wait for page to load completely.
        
        Returns:
            True if page loaded successfully, False otherwise
        """
        try:
            WebDriverWait(self.driver, self.timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            return True
        except TimeoutException:
            self.logger.warning("Page load timeout")
            return False
    
    def _find_section_content(self, soup: BeautifulSoup, section_names: List[str]) -> str:
        """
        Find and extract content for a specific section.
        
        Args:
            soup: BeautifulSoup object of the page
            section_names: List of possible section names to search for
            
        Returns:
            Extracted text content for the section
        """
        content = []
        notes = []
        
        # Try to find section by heading
        for section_name in section_names:
            # Look for h2 and h3 headings
            for heading in soup.find_all(['h2', 'h3']):
                if heading.get_text(strip=True).lower() == section_name.lower():
                    heading_level = heading.name
                    
                    # Extract content until next heading of same level
                    section_content = self._extract_content_until_next_heading(
                        heading, heading_level
                    )
                    
                    if section_content:
                        content.append(section_content)
                        notes.append(f"found section: {section_name}")
                        break
            
            if content:
                break
        
        # If no content found, try alternative approaches
        if not content:
            # Look for content in divs with similar text
            for section_name in section_names:
                for div in soup.find_all('div'):
                    if section_name.lower() in div.get_text().lower():
                        text = div.get_text(strip=True)
                        if len(text) > 50:  # Only if substantial content
                            content.append(text)
                            notes.append(f"found in div: {section_name}")
                            break
                if content:
                    break
        
        # Join all found content
        result = ' '.join(content) if content else ''
        
        # Add diagnostic notes
        if not result:
            notes.append(f"section missing: {section_names[0]}")
        
        return result.strip()
    
    def _extract_content_until_next_heading(self, heading, heading_level: str) -> str:
        """
        Extract content from a heading until the next heading of the same level.
        
        Args:
            heading: BeautifulSoup heading element
            heading_level: Level of the heading (h2, h3, etc.)
            
        Returns:
            Extracted text content
        """
        content_parts = []
        current = heading.find_next_sibling()
        
        while current and current.name != heading_level:
            if current.name in ['p', 'div', 'li']:
                text = current.get_text(strip=True)
                if text:
                    content_parts.append(text)
            elif current.name is None and current.string:
                text = current.string.strip()
                if text:
                    content_parts.append(text)
            
            current = current.find_next_sibling()
        
        return ' '.join(content_parts)
    
    def _extract_project_info(self, project_url: str) -> Dict:
        """
        Extract project information from a project page.
        
        Args:
            project_url: URL of the project page
            
        Returns:
            Dictionary containing extracted information
        """
        try:
            # Get page content
            page_source = self._get_page_content(project_url)
            if not page_source:
                return {
                    'project_url': project_url,
                    'general_description': '',
                    'objectives': '',
                    'beneficiaries': '',
                    'status': 'not_found',
                    'notes': 'failed to fetch page'
                }
            
            # Parse HTML
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract each section
            general_description = self._find_section_content(
                soup, self.target_sections['general_description']
            )
            objectives = self._find_section_content(
                soup, self.target_sections['objectives']
            )
            beneficiaries = self._find_section_content(
                soup, self.target_sections['beneficiaries']
            )
            
            # Determine status and notes
            if general_description or objectives or beneficiaries:
                status = 'ok'
                notes = 'sections extracted successfully'
            else:
                status = 'not_found'
                notes = 'no sections found'
            
            return {
                'project_url': project_url,
                'general_description': general_description,
                'objectives': objectives,
                'beneficiaries': beneficiaries,
                'status': status,
                'notes': notes
            }
            
        except Exception as e:
            self.logger.error(f"Error extracting project info from {project_url}: {e}")
            return {
                'project_url': project_url,
                'general_description': '',
                'objectives': '',
                'beneficiaries': '',
                'status': 'error',
                'notes': f'extraction error: {str(e)}'
            }
    
    def process_csv(self, input_file: str, output_file: str, 
                   id_column: str = 'Identifier', max_rows: Optional[int] = None) -> None:
        """
        Process a CSV file containing project identifiers.
        
        Args:
            input_file: Path to input CSV file
            output_file: Path to output CSV file
            id_column: Name of the column containing project identifiers
            max_rows: Maximum number of rows to process (None for all)
        """
        try:
            # Initialize WebDriver
            self.driver = self._create_driver()
            self.logger.info("WebDriver initialized successfully")
            
            results = []
            row_count = 0
            
            # Read input CSV
            with open(input_file, 'r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                
                # Validate ID column exists
                if id_column not in reader.fieldnames:
                    raise ValueError(f"Column '{id_column}' not found in CSV. Available columns: {reader.fieldnames}")
                
                # Process each row
                for row_num, row in enumerate(reader, 1):
                    identifier = row[id_column].strip()
                    
                    if not identifier:
                        self.logger.warning(f"Row {row_num}: Empty identifier, skipping")
                        continue
                    
                    self.logger.info(f"Processing row {row_num}: {identifier}")
                    
                    # Construct project URL
                    project_url = self._construct_project_url(identifier)
                    
                    # Extract project information
                    project_info = self._extract_project_info(project_url)
                    project_info['Identifier'] = identifier
                    
                    results.append(project_info)
                    row_count += 1
                    
                    # Log result
                    self.logger.info(f"Row {row_num}: {project_info['status']} - {project_info['notes']}")
                    
                    # Rate limiting
                    if max_rows and row_count < max_rows:
                        time.sleep(self.rate_limit)
                    elif not max_rows:
                        time.sleep(self.rate_limit)
                    
                    # Check if we've reached max rows
                    if max_rows and row_count >= max_rows:
                        self.logger.info(f"Reached maximum rows limit ({max_rows})")
                        break
            
            # Write output CSV
            self._write_output_csv(results, output_file)
            
            self.logger.info(f"Output written to: {output_file}")
            self.logger.info(f"Processing completed. Processed {row_count} projects.")
            
        except Exception as e:
            self.logger.error(f"Error processing CSV: {e}")
            raise
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Chrome driver closed")
    
    def _write_output_csv(self, results: List[Dict], output_file: str) -> None:
        """
        Write results to output CSV file.
        
        Args:
            results: List of dictionaries containing project information
            output_file: Path to output CSV file
        """
        fieldnames = [
            'Identifier', 'project_url', 'general_description', 
            'objectives', 'beneficiaries', 'status', 'notes'
        ]
        
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        
        self.logger.info(f"Results saved to: {output_file}")


def main():
    """Main function to handle command line arguments and run the extractor."""
    parser = argparse.ArgumentParser(
        description='Extract project information from MapAfrica using Selenium'
    )
    
    parser.add_argument(
        '--projects', 
        required=True,
        help='Path to input CSV file containing project identifiers'
    )
    
    parser.add_argument(
        '--id-col', 
        default='Identifier',
        help='Name of the column containing project identifiers (default: Identifier)'
    )
    
    parser.add_argument(
        '--out', 
        default='mapafrica_output.csv',
        help='Output CSV file path (default: mapafrica_output.csv)'
    )
    
    parser.add_argument(
        '--rate-limit', 
        type=float, 
        default=2.0,
        help='Delay between requests in seconds (default: 2.0)'
    )
    
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=30,
        help='Page load timeout in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--base-url', 
        default='https://mapafrica.afdb.org',
        help='Base URL for MapAfrica (default: https://mapafrica.afdb.org)'
    )
    
    parser.add_argument(
        '--max-rows', 
        type=int, 
        default=None,
        help='Maximum number of rows to process (default: all rows)'
    )
    
    args = parser.parse_args()
    
    # Validate input file exists
    try:
        with open(args.projects, 'r') as f:
            pass
    except FileNotFoundError:
        print(f"Error: Input file '{args.projects}' not found")
        exit(1)
    
    # Create extractor and process
    extractor = MapAfricaExtractor(
        base_url=args.base_url,
        rate_limit=args.rate_limit,
        timeout=args.timeout
    )
    
    try:
        extractor.process_csv(
            input_file=args.projects,
            output_file=args.out,
            id_column=args.id_col,
            max_rows=args.max_rows
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
