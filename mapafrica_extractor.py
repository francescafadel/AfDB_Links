#!/usr/bin/env python3
"""
MapAfrica Project Extractor - Original version using requests.

This tool extracts project information from MapAfrica project pages using
HTTP requests. Note: This version is limited by Cloudflare protection.

Author: Francesca Fadel
Repository: https://github.com/francescafadel/AfDB_Links.git
"""

import csv
import logging
import time
import random
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import argparse


class MapAfricaExtractor:
    """
    Extracts project information from MapAfrica project pages using requests.
    
    Note: This version is limited by Cloudflare protection and may not work
    for all projects due to bot detection.
    """
    
    def __init__(self, base_url: str = "https://mapafrica.afdb.org", 
                 rate_limit: float = 1.0, timeout: int = 30):
        """
        Initialize the MapAfrica extractor.
        
        Args:
            base_url: Base URL for MapAfrica platform
            rate_limit: Delay between requests in seconds
            timeout: Request timeout in seconds
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
        
        self.session = self._create_session()
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def _create_session(self) -> requests.Session:
        """Create and configure requests session with retry logic."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = requests.adapters.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers to mimic browser
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        
        return session
    
    def _make_request(self, url: str) -> Optional[requests.Response]:
        """
        Make HTTP request with error handling.
        
        Args:
            url: URL to request
            
        Returns:
            Response object or None if failed
        """
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            return None
    
    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """
        Get BeautifulSoup object from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            BeautifulSoup object or None if failed
        """
        response = self._make_request(url)
        if response:
            return BeautifulSoup(response.content, 'html.parser')
        return None
    
    def _construct_project_url(self, identifier: str) -> str:
        """
        Construct the MapAfrica project URL using the correct pattern.
        
        Args:
            identifier: Project identifier (e.g., P-ZW-AAG-008)
            
        Returns:
            Complete project URL
        """
        return f"{self.base_url}/en/projects/46002-{identifier}"
    
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
                            break
                if content:
                    break
        
        return ' '.join(content).strip()
    
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
                   id_column: str = 'Identifier') -> None:
        """
        Process a CSV file containing project identifiers.
        
        Args:
            input_file: Path to input CSV file
            output_file: Path to output CSV file
            id_column: Name of the column containing project identifiers
        """
        try:
            results = []
            
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
                    
                    # Log result
                    self.logger.info(f"Row {row_num}: {project_info['status']} - {project_info['notes']}")
                    
                    # Rate limiting
                    time.sleep(self.rate_limit)
            
            # Write output CSV
            self._write_output_csv(results, output_file)
            
            self.logger.info(f"Processing completed. Processed {len(results)} projects.")
            
        except Exception as e:
            self.logger.error(f"Error processing CSV: {e}")
            raise
    
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
        description='Extract project information from MapAfrica using requests'
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
        default=1.0,
        help='Delay between requests in seconds (default: 1.0)'
    )
    
    parser.add_argument(
        '--timeout', 
        type=int, 
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--base-url', 
        default='https://mapafrica.afdb.org',
        help='Base URL for MapAfrica (default: https://mapafrica.afdb.org)'
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
            id_column=args.id_col
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
