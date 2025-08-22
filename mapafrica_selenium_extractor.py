#!/usr/bin/env python3
"""
MapAfrica Project Extractor using Selenium to handle Cloudflare protection
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

class MapAfricaSeleniumExtractor:
    def __init__(self, base_url: str = "https://mapafrica.afdb.org", rate_limit: float = 5.0, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.rate_limit = rate_limit
        self.timeout = timeout
        
        # Target sections to extract (English and French)
        self.target_sections = {
            'general_description': [
                'Project General Description', 'General Description', 'Description générale du projet',
                'Project Description', 'Description du projet', 'Description'
            ],
            'objectives': [
                'Project Objectives', 'Objectives', 'Objectifs du projet', 'Objectifs'
            ],
            'beneficiaries': [
                'Beneficiaries', 'Bénéficiaires', 'Target Beneficiaries', 'Bénéficiaires cibles'
            ]
        }
        
        self.driver = None
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('mapafrica_selenium_extractor.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _setup_driver(self):
        """Setup Chrome driver with anti-detection options"""
        chrome_options = Options()
        
        # Anti-detection options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Random user agent
        user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        chrome_options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        # Window size
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Headless mode (comment out for debugging)
        chrome_options.add_argument('--headless')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.logger.info("Chrome driver initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome driver: {e}")
            raise
    
    def _construct_project_urls(self, identifier: str) -> List[str]:
        """Construct MapAfrica project URLs with the correct pattern"""
        # The correct pattern is: https://mapafrica.afdb.org/en/projects/46002-{IDENTIFIER}
        patterns = [
            f"{self.base_url}/en/projects/46002-{identifier}",
            # Fallback patterns in case the main one doesn't work
            f"{self.base_url}/en/projects/{identifier}",
            f"{self.base_url}/projects/46002-{identifier}",
            f"{self.base_url}/projects/{identifier}"
        ]
        return patterns
    
    def _wait_for_page_load(self, timeout: int = 30):
        """Wait for page to load and handle Cloudflare challenges"""
        try:
            # Wait for page to load
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            
            # Check if we're on a Cloudflare challenge page
            if "Just a moment" in self.driver.title or "challenge" in self.driver.page_source.lower():
                self.logger.info("Detected Cloudflare challenge, waiting...")
                time.sleep(10)  # Wait for challenge to complete
                
                # Wait again for the actual page to load
                WebDriverWait(self.driver, timeout).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
            
            return True
        except TimeoutException:
            self.logger.warning("Page load timeout")
            return False
    
    def _get_page_content(self, url: str) -> Optional[str]:
        """Get page content using Selenium"""
        try:
            self.logger.debug(f"Navigating to: {url}")
            self.driver.get(url)
            
            if not self._wait_for_page_load():
                return None
            
            # Wait a bit more for dynamic content
            time.sleep(3)
            
            # Check if page contains project information
            page_source = self.driver.page_source
            
            # Debug: Log a snippet of the page content
            page_snippet = page_source[:1000].lower()
            self.logger.debug(f"Page snippet: {page_snippet[:200]}...")
            
            if "project general description" in page_source.lower() or "project objectives" in page_source.lower():
                self.logger.info("Found project content on page")
                return page_source
            elif "project" in page_source.lower() and "description" in page_source.lower():
                self.logger.info("Found project-related content, proceeding with extraction")
                return page_source
            else:
                self.logger.warning("Page doesn't appear to contain project information")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting page content for {url}: {e}")
            return None
    
    def _find_section_content(self, soup: BeautifulSoup, section_names: List[str]) -> tuple:
        """Find section content by heading names"""
        content = ""
        locale_notes = []
        
        # Look for h1, h2, h3, h4 headings
        for heading_level in ['h1', 'h2', 'h3', 'h4']:
            headings = soup.find_all(heading_level)
            
            for heading in headings:
                heading_text = heading.get_text(strip=True).lower()
                
                # Check if this heading matches any of our target sections
                for section_name in section_names:
                    if section_name.lower() in heading_text:
                        # Extract content until next heading of same level
                        section_content = self._extract_content_until_next_heading(heading, heading_level)
                        if section_content:
                            content = section_content
                            # Detect if French locale is used
                            if any(fr_name.lower() in heading_text for fr_name in ['générale', 'objectifs', 'bénéficiaires']):
                                locale_notes.append("fr locale detected")
                            break
                
                if content:
                    break
            
            if content:
                break
        
        return content, locale_notes
    
    def _extract_content_until_next_heading(self, heading, heading_level: str) -> str:
        """Extract content from heading until next heading of same level"""
        content_parts = []
        current = heading.find_next_sibling()
        
        while current and current.name != heading_level:
            if current.name in ['p', 'div', 'li', 'span']:
                text = current.get_text(strip=True)
                if text:
                    content_parts.append(text)
            elif current.name is None and current.string:
                text = current.string.strip()
                if text:
                    content_parts.append(text)
            
            current = current.find_next_sibling()
        
        return ' '.join(content_parts)
    
    def _extract_project_info(self, identifier: str) -> Dict:
        """Extract project information by trying multiple URL patterns"""
        urls_to_try = self._construct_project_urls(identifier)
        
        for url in urls_to_try:
            self.logger.debug(f"Trying URL: {url}")
            page_content = self._get_page_content(url)
            
            if page_content:
                soup = BeautifulSoup(page_content, 'html.parser')
                
                # Extract each section
                general_desc, desc_notes = self._find_section_content(soup, self.target_sections['general_description'])
                objectives, obj_notes = self._find_section_content(soup, self.target_sections['objectives'])
                beneficiaries, ben_notes = self._find_section_content(soup, self.target_sections['beneficiaries'])
                
                # Combine notes
                all_notes = desc_notes + obj_notes + ben_notes
                notes = '; '.join(all_notes) if all_notes else ''
                
                # Determine status
                if general_desc or objectives or beneficiaries:
                    status = 'ok'
                    if not notes:
                        notes = 'sections extracted successfully'
                    notes += f'; working URL: {url}'
                    
                    return {
                        'project_url': url,
                        'general_description': general_desc,
                        'objectives': objectives,
                        'beneficiaries': beneficiaries,
                        'status': status,
                        'notes': notes
                    }
        
        # If we get here, no URL worked
        return {
            'project_url': urls_to_try[0],  # Return first attempted URL
            'general_description': '',
            'objectives': '',
            'beneficiaries': '',
            'status': 'not_found',
            'notes': 'no working URL found'
        }
    
    def process_csv(self, input_file: str, output_file: str, id_column: str = 'Identifier', max_rows: int = None) -> None:
        """Process CSV file and extract project information"""
        self.logger.info(f"Processing CSV: {input_file}")
        self.logger.info(f"ID column: {id_column}")
        self.logger.info(f"Output file: {output_file}")
        if max_rows:
            self.logger.info(f"Processing first {max_rows} rows only")
        
        try:
            self._setup_driver()
            
            results = []
            row_count = 0
            
            with open(input_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                
                # Validate ID column exists
                if id_column not in reader.fieldnames:
                    available_columns = ', '.join(reader.fieldnames) if reader.fieldnames else 'none'
                    raise ValueError(f"Column '{id_column}' not found in CSV. Available columns: {available_columns}")
                
                for row_num, row in enumerate(reader, 1):
                    if max_rows and row_count >= max_rows:
                        break
                    
                    identifier = row[id_column].strip()
                    if not identifier:
                        continue
                    
                    self.logger.info(f"Processing row {row_num}: {identifier}")
                    
                    # Extract project information
                    project_info = self._extract_project_info(identifier)
                    
                    # Add identifier to result
                    result = {
                        'Identifier': identifier,
                        **project_info
                    }
                    
                    results.append(result)
                    row_count += 1
                    
                    # Log status
                    status = project_info['status']
                    notes = project_info['notes']
                    self.logger.info(f"Row {row_num}: {status} - {notes}")
                    
                    # Rate limiting
                    if max_rows and row_count < max_rows:
                        time.sleep(self.rate_limit)
            
            # Write results
            self._write_output_csv(results, output_file)
            
            self.logger.info(f"Output written to: {output_file}")
            self.logger.info(f"Processing completed. Processed {len(results)} projects.")
            self.logger.info(f"Results saved to: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Error processing CSV: {e}")
            raise
        finally:
            if self.driver:
                self.driver.quit()
                self.logger.info("Chrome driver closed")
    
    def _write_output_csv(self, results: List[Dict], output_file: str) -> None:
        """Write results to CSV file"""
        if not results:
            return
        
        fieldnames = ['Identifier', 'project_url', 'general_description', 'objectives', 'beneficiaries', 'status', 'notes']
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

def main():
    parser = argparse.ArgumentParser(description='Extract project information from MapAfrica using Selenium')
    parser.add_argument('--projects', required=True, help='Input CSV file with project identifiers')
    parser.add_argument('--id-col', default='Identifier', help='Column name containing project identifiers (default: Identifier)')
    parser.add_argument('--out', default='mapafrica_selenium_output.csv', help='Output CSV file (default: mapafrica_selenium_output.csv)')
    parser.add_argument('--rate-limit', type=float, default=5.0, help='Rate limit in seconds between requests (default: 5.0)')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('--base-url', default='https://mapafrica.afdb.org', help='Base URL for MapAfrica (default: https://mapafrica.afdb.org)')
    parser.add_argument('--max-rows', type=int, help='Maximum number of rows to process (for testing)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.projects:
        print("Error: --projects argument is required")
        return
    
    try:
        extractor = MapAfricaSeleniumExtractor(
            base_url=args.base_url,
            rate_limit=args.rate_limit,
            timeout=args.timeout
        )
        
        extractor.process_csv(
            input_file=args.projects,
            output_file=args.out,
            id_column=args.id_col,
            max_rows=args.max_rows
        )
        
    except Exception as e:
        print(f"Error: {e}")
        return

if __name__ == "__main__":
    main()
