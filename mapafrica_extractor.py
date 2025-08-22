#!/usr/bin/env python3
"""
MapAfrica Project Extractor - Enhanced version to handle Cloudflare protection
Extracts project information from MapAfrica project pages
"""

import csv
import logging
import random
import time
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import argparse

class MapAfricaExtractor:
    def __init__(self, base_url: str = "https://mapafrica.afdb.org", rate_limit: float = 2.0, timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.rate_limit = rate_limit
        self.timeout = timeout
        
        # Target sections to extract (English and French)
        self.target_sections = {
            'general_description': [
                'Project General Description', 'General Description', 'Description générale du projet',
                'Project Description', 'Description du projet'
            ],
            'objectives': [
                'Project Objectives', 'Objectives', 'Objectifs du projet', 'Objectifs'
            ],
            'beneficiaries': [
                'Beneficiaries', 'Bénéficiaires', 'Target Beneficiaries', 'Bénéficiaires cibles'
            ]
        }
        
        # Rotating user agents to appear more like real browsers
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.session = self._create_session()
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('mapafrica_extractor.log')
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _create_session(self) -> requests.Session:
        """Create a session with enhanced anti-detection capabilities"""
        session = requests.Session()
        
        # Configure retry strategy
        from urllib3.util.retry import Retry
        from requests.adapters import HTTPAdapter
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set a random user agent
        session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        })
        
        return session
    
    def _rotate_user_agent(self):
        """Rotate to a different user agent"""
        new_agent = random.choice(self.user_agents)
        self.session.headers.update({'User-Agent': new_agent})
        self.logger.debug(f"Rotated to user agent: {new_agent[:50]}...")
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """Make a request with enhanced anti-detection"""
        try:
            # Rotate user agent occasionally
            if random.random() < 0.3:
                self._rotate_user_agent()
            
            # Add some randomization to the request
            headers = self.session.headers.copy()
            headers.update({
                'Referer': self.base_url,
                'X-Requested-With': 'XMLHttpRequest'
            })
            
            response = self.session.get(
                url, 
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            
            # Check if we got blocked
            if response.status_code == 403:
                self.logger.warning(f"403 Forbidden - likely blocked by Cloudflare for {url}")
                return None
            elif response.status_code == 429:
                self.logger.warning(f"429 Too Many Requests - rate limited for {url}")
                time.sleep(self.rate_limit * 2)  # Wait longer
                return None
            elif response.status_code != 200:
                self.logger.error(f"HTTP {response.status_code} for {url}")
                return None
            
            return response
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None
    
    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Get BeautifulSoup object from URL"""
        response = self._make_request(url)
        if not response:
            return None
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            return soup
        except Exception as e:
            self.logger.error(f"Failed to parse HTML for {url}: {e}")
            return None
    
    def _construct_project_url(self, identifier: str) -> str:
        """Construct potential MapAfrica project URLs"""
        # Try different URL patterns
        patterns = [
            f"{self.base_url}/project/{identifier}",
            f"{self.base_url}/projects/{identifier}",
            f"{self.base_url}/en/project/{identifier}",
            f"{self.base_url}/fr/project/{identifier}"
        ]
        return patterns[0]  # Start with the most likely pattern
    
    def _find_section_content(self, soup: BeautifulSoup, section_names: List[str]) -> tuple:
        """Find section content by heading names"""
        content = ""
        locale_notes = []
        
        # Look for h2 and h3 headings
        for heading_level in ['h2', 'h3']:
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
        """Extract project information from the project page"""
        soup = self._get_soup(project_url)
        
        if not soup:
            return {
                'project_url': project_url,
                'general_description': '',
                'objectives': '',
                'beneficiaries': '',
                'status': 'not_found',
                'notes': 'failed to fetch page'
            }
        
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
        else:
            status = 'no_content'
            notes = 'no target sections found' if not notes else notes
        
        return {
            'project_url': project_url,
            'general_description': general_desc,
            'objectives': objectives,
            'beneficiaries': beneficiaries,
            'status': status,
            'notes': notes
        }
    
    def process_csv(self, input_file: str, output_file: str, id_column: str = 'Identifier', max_rows: int = None) -> None:
        """Process CSV file and extract project information"""
        self.logger.info(f"Processing CSV: {input_file}")
        self.logger.info(f"ID column: {id_column}")
        self.logger.info(f"Output file: {output_file}")
        if max_rows:
            self.logger.info(f"Processing first {max_rows} rows only")
        
        results = []
        row_count = 0
        
        try:
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
                    
                    # Construct project URL
                    project_url = self._construct_project_url(identifier)
                    
                    # Extract project information
                    project_info = self._extract_project_info(project_url)
                    
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
    parser = argparse.ArgumentParser(description='Extract project information from MapAfrica')
    parser.add_argument('--projects', required=True, help='Input CSV file with project identifiers')
    parser.add_argument('--id-col', default='Identifier', help='Column name containing project identifiers (default: Identifier)')
    parser.add_argument('--out', default='mapafrica_output.csv', help='Output CSV file (default: mapafrica_output.csv)')
    parser.add_argument('--rate-limit', type=float, default=2.0, help='Rate limit in seconds between requests (default: 2.0)')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds (default: 30)')
    parser.add_argument('--base-url', default='https://mapafrica.afdb.org', help='Base URL for MapAfrica (default: https://mapafrica.afdb.org)')
    parser.add_argument('--max-rows', type=int, help='Maximum number of rows to process (for testing)')
    
    args = parser.parse_args()
    
    # Validate input file
    if not args.projects:
        print("Error: --projects argument is required")
        return
    
    try:
        extractor = MapAfricaExtractor(
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
