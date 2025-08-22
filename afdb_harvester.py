#!/usr/bin/env python3
"""
AfDB Document Harvester - Production CLI

A production-ready CLI tool to crawl AfDB Documents listings for the Agriculture & Agro-industries sector,
with multi-seed support, robust pagination, and comprehensive PDF URL resolution.
"""

import argparse
import csv
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class AfDBHarvester:
    """Production-ready AfDB document harvester with multi-seed support."""
    
    def __init__(self, seeds: List[str], sector: str = "Agriculture & Agro-industries", 
                 out_dir: str = "outputs", max_pages: int = 25, rate_limit: float = 1.0,
                 user_agent: str = None, log_file: str = None, fresh: bool = False):
        self.seeds = seeds
        self.target_sector = sector
        self.out_dir = Path(out_dir)
        self.max_pages = max_pages
        self.rate_limit = rate_limit
        self.fresh = fresh
        self.timeout = 30
        
        # Create output directory
        self.out_dir.mkdir(exist_ok=True)
        
        # Setup session
        self.session = self._create_session(user_agent)
        
        # Track processed URLs for deduplication
        self.processed_detail_urls: Set[str] = set()
        self.all_results: List[Dict] = []
        
        # Setup logging
        self._setup_logging(log_file)
        self.logger = logging.getLogger(__name__)
    
    def _setup_logging(self, log_file: str = None) -> None:
        """Setup logging configuration."""
        log_path = log_file or self.out_dir / "afdb_harvester.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(log_path)
            ]
        )
    
    def _create_session(self, user_agent: str = None) -> requests.Session:
        """Create a requests session with retry logic and headers."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set headers
        default_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        session.headers.update({
            'User-Agent': user_agent or default_ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        return session
    
    def _make_request(self, url: str, method: str = 'GET') -> Optional[requests.Response]:
        """Make a request with error handling and logging."""
        try:
            self.logger.debug(f"Requesting: {url}")
            if method.upper() == 'HEAD':
                response = self.session.head(url, timeout=self.timeout, allow_redirects=True)
            else:
                response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch {url}: {e}")
            return None
    
    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Get BeautifulSoup object from URL."""
        response = self._make_request(url)
        if response:
            return BeautifulSoup(response.content, 'html.parser')
        return None
    
    def _extract_document_cards(self, soup: BeautifulSoup, source_seed: str, page_num: int) -> List[Dict]:
        """Extract document cards from a listing page."""
        documents = []
        
        # Look for common document card selectors
        card_selectors = [
            '.views-row',  # Common Drupal pattern
            '.document-card',
            '.search-result',
            '.result-item',
            '.document-item',
            'article',
            '.card',
            '[class*="document"]',
            '[class*="result"]'
        ]
        
        cards = []
        for selector in card_selectors:
            cards = soup.select(selector)
            if cards:
                self.logger.info(f"Found {len(cards)} cards using selector: {selector}")
                break
        
        if not cards:
            # Fallback: look for any div that might contain document info
            cards = soup.find_all('div', class_=re.compile(r'document|result|card|item|view', re.I))
            self.logger.info(f"Fallback: Found {len(cards)} potential cards")
        
        for card in cards:
            doc_info = self._extract_card_info(card, source_seed, page_num)
            if doc_info:
                documents.append(doc_info)
        
        return documents
    
    def _extract_card_info(self, card, source_seed: str, page_num: int) -> Optional[Dict]:
        """Extract information from a single document card."""
        try:
            # Extract title
            title = ""
            title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.document-title', '[class*="title"]', 'a']
            for selector in title_selectors:
                title_elem = card.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title:  # Only break if we found non-empty title
                        break
            
            # Extract detail URL
            detail_url = ""
            link_selectors = ['a', '.link', '[class*="link"]']
            for selector in link_selectors:
                link_elem = card.select_one(selector)
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/'):
                        detail_url = urljoin('https://www.afdb.org', href)
                    elif href.startswith('http'):
                        detail_url = href
                    else:
                        detail_url = urljoin('https://www.afdb.org', '/' + href)
                    break
            
            # Extract date
            date = ""
            date_selectors = ['.date', '.published', '[class*="date"]', 'time', '.field-content']
            for selector in date_selectors:
                date_elem = card.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    # Look for date patterns
                    if re.search(r'\d{4}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4}', date_text):
                        date = date_text
                        break
            
            # Extract country
            country = ""
            country_selectors = ['.country', '.location', '[class*="country"]', '[class*="location"]', '.field-content']
            for selector in country_selectors:
                country_elem = card.select_one(selector)
                if country_elem:
                    country = country_elem.get_text(strip=True)
                    if country and not re.search(r'\d{4}', country):  # Avoid dates
                        break
            
            # Extract sector from card
            sector = ""
            sector_selectors = ['.sector', '.category', '[class*="sector"]', '[class*="category"]', '.field-content']
            for selector in sector_selectors:
                sector_elem = card.select_one(selector)
                if sector_elem:
                    sector_text = sector_elem.get_text(strip=True)
                    if 'agriculture' in sector_text.lower() or 'agro' in sector_text.lower():
                        sector = sector_text
                        break
            
            if title and detail_url:
                return {
                    'source_seed': source_seed,
                    'page_num': page_num,
                    'title': title,
                    'date': date,
                    'country': country,
                    'sector': sector,
                    'detail_url': detail_url,
                    'sector_source': 'card' if sector else 'unknown'
                }
        
        except Exception as e:
            self.logger.warning(f"Error extracting card info: {e}")
        
        return None
    
    def _check_sector_on_detail_page(self, detail_url: str) -> Tuple[str, str]:
        """Check sector on detail page. Returns (sector, notes)."""
        soup = self._get_soup(detail_url)
        if not soup:
            return "", "failed to fetch detail page"
        
        # Look for sector information on detail page
        sector_selectors = [
            '.field-name-field-sector .field-item',
            '.field-name-field-category .field-item',
            '.sector',
            '.category',
            '[class*="sector"]',
            '[class*="category"]'
        ]
        
        for selector in sector_selectors:
            sector_elem = soup.select_one(selector)
            if sector_elem:
                sector = sector_elem.get_text(strip=True)
                if sector:
                    return sector, "sector from detail page"
        
        return "", "no sector found on detail page"
    
    def _matches_target_sector(self, sector: str) -> bool:
        """Check if sector matches target sector (case-insensitive, trimmed)."""
        if not sector:
            return False
        return sector.strip().lower() == self.target_sector.strip().lower()
    
    def _process_document(self, doc: Dict) -> Optional[Dict]:
        """Process a single document: check sector and resolve PDF URL."""
        detail_url = doc['detail_url']
        
        # Skip if already processed (deduplication)
        if detail_url in self.processed_detail_urls:
            self.logger.debug(f"Skipping duplicate: {detail_url}")
            return None
        
        self.processed_detail_urls.add(detail_url)
        
        # Check sector enforcement
        sector = doc.get('sector', '')
        notes = []
        
        if sector and self._matches_target_sector(sector):
            # Sector found on card and matches
            final_sector = sector
            notes.append("sector from card")
        elif not sector:
            # No sector on card, check detail page
            final_sector, detail_notes = self._check_sector_on_detail_page(detail_url)
            notes.append(detail_notes)
            
            if not self._matches_target_sector(final_sector):
                self.logger.debug(f"Skipping {detail_url} - sector '{final_sector}' does not match target")
                return None
        else:
            # Sector on card but doesn't match
            self.logger.debug(f"Skipping {detail_url} - sector '{sector}' does not match target")
            return None
        
        # Resolve PDF URL
        pdf_url, pdf_notes = self._resolve_pdf_url(detail_url)
        if pdf_notes:
            notes.append(pdf_notes)
        
        # Build result
        result = {
            'source_seed': doc['source_seed'],
            'page_num': doc['page_num'],
            'title': doc['title'],
            'date': doc['date'],
            'country': doc['country'],
            'sector': final_sector,
            'detail_url': detail_url,
            'pdf_url': pdf_url,
            'status': 'linked' if pdf_url else 'no_pdf',
            'notes': '; '.join(notes) if notes else ''
        }
        
        self.logger.info(f"Processed: {doc['title'][:50]}... -> {result['status']}")
        return result
    
    def _resolve_pdf_url(self, detail_url: str) -> Tuple[str, str]:
        """Resolve PDF URL from document detail page. Returns (pdf_url, notes)."""
        soup = self._get_soup(detail_url)
        if not soup:
            return "", "failed to fetch detail page"
        
        # Look for direct PDF links
        pdf_links = soup.select('a[href$=".pdf"]')
        
        for link in pdf_links:
            href = link.get('href', '')
            if href:
                if href.startswith('/'):
                    pdf_url = urljoin('https://www.afdb.org', href)
                elif href.startswith('http'):
                    pdf_url = href
                else:
                    pdf_url = urljoin('https://www.afdb.org', '/' + href)
                
                # Validate PDF URL (check if it's in expected paths)
                if ('/sites/default/files/documents/' in pdf_url or 
                    pdf_url.startswith('http') and '.pdf' in pdf_url):
                    
                    # Follow redirects to get final URL
                    final_url, redirect_count = self._follow_redirects(pdf_url)
                    notes = f"redirects={redirect_count}" if redirect_count > 0 else ""
                    
                    self.logger.debug(f"Found PDF: {final_url}")
                    return final_url, notes
        
        # Look for other PDF-related selectors
        other_selectors = [
            'a[href*=".pdf"]',
            '.file-link a',
            '.field-name-field-file a',
            '[class*="pdf"] a',
            'a[download*=".pdf"]'
        ]
        
        for selector in other_selectors:
            links = soup.select(selector)
            for link in links:
                href = link.get('href', '')
                if href and '.pdf' in href.lower():
                    if href.startswith('/'):
                        pdf_url = urljoin('https://www.afdb.org', href)
                    elif href.startswith('http'):
                        pdf_url = href
                    else:
                        pdf_url = urljoin('https://www.afdb.org', '/' + href)
                    
                    final_url, redirect_count = self._follow_redirects(pdf_url)
                    notes = f"redirects={redirect_count}" if redirect_count > 0 else ""
                    
                    self.logger.debug(f"Found PDF: {final_url}")
                    return final_url, notes
        
        return "", "no pdf found"
    
    def _follow_redirects(self, url: str) -> Tuple[str, int]:
        """Follow redirects to get final URL. Returns (final_url, redirect_count)."""
        try:
            response = self._make_request(url, method='HEAD')
            if response:
                redirect_count = len(response.history)
                return response.url, redirect_count
        except Exception as e:
            self.logger.warning(f"Error following redirects for {url}: {e}")
        
        return url, 0
    
    def _get_next_page_url(self, soup: BeautifulSoup, current_url: str) -> Optional[str]:
        """Get the next page URL using robust pagination strategies."""
        
        # Strategy 1: If current URL has ?page=N, increment N
        parsed = urlparse(current_url)
        query_params = parse_qs(parsed.query)
        
        if 'page' in query_params:
            try:
                current_page = int(query_params['page'][0])
                next_page = current_page + 1
                
                # Reconstruct URL with incremented page
                new_params = dict(query_params)
                new_params['page'] = [str(next_page)]
                new_query = '&'.join([f"{k}={v[0]}" for k, v in new_params.items()])
                next_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"
                
                self.logger.debug(f"Constructed next page URL: {next_url}")
                return next_url
            except (ValueError, IndexError):
                pass
        
        # Strategy 2: Look for "next" anchor using specific selectors
        next_selectors = [
            'nav a[rel="next"]',
            'nav .pager__item--next a',
            '.pagination a[rel="next"]',
            '[aria-label*="Next" i]'
        ]
        
        for selector in next_selectors:
            next_links = soup.select(selector)
            for next_link in next_links:
                href = next_link.get('href')
                if href:
                    if href.startswith('/'):
                        next_url = urljoin('https://www.afdb.org', href)
                    elif href.startswith('http'):
                        next_url = href
                    else:
                        next_url = urljoin('https://www.afdb.org', '/' + href)
                    
                    self.logger.debug(f"Found next page link: {next_url}")
                    return next_url
        
        # Strategy 3: Look for pagination with page numbers
        page_links = soup.select('.pagination a, .pager a, nav a')
        current_page_num = self._extract_page_number(current_url)
        
        for link in page_links:
            href = link.get('href', '')
            if href:
                link_page_num = self._extract_page_number(href)
                if link_page_num == current_page_num + 1:
                    if href.startswith('/'):
                        next_url = urljoin('https://www.afdb.org', href)
                    elif href.startswith('http'):
                        next_url = href
                    else:
                        next_url = urljoin('https://www.afdb.org', '/' + href)
                    
                    self.logger.debug(f"Found sequential page link: {next_url}")
                    return next_url
        
        return None
    
    def _extract_page_number(self, url: str) -> int:
        """Extract page number from URL."""
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        if 'page' in query_params:
            try:
                return int(query_params['page'][0])
            except (ValueError, IndexError):
                pass
        
        return 0
    
    def harvest_seed(self, seed_url: str) -> List[Dict]:
        """Harvest documents from a single seed URL."""
        self.logger.info(f"Processing seed: {seed_url}")
        
        current_url = seed_url
        page_count = 0
        seed_results = []
        
        while current_url and page_count < self.max_pages:
            page_count += 1
            self.logger.info(f"Processing page {page_count} of {seed_url}")
            
            soup = self._get_soup(current_url)
            if not soup:
                self.logger.error(f"Failed to fetch page {page_count}")
                break
            
            # Extract document cards
            documents = self._extract_document_cards(soup, seed_url, page_count)
            if not documents:
                self.logger.warning(f"No documents found on page {page_count} - stopping pagination")
                break
            
            self.logger.info(f"Found {len(documents)} documents on page {page_count}")
            
            # Process each document
            for doc in documents:
                try:
                    result = self._process_document(doc)
                    if result:
                        seed_results.append(result)
                    
                    # Rate limiting
                    time.sleep(self.rate_limit)
                except Exception as e:
                    self.logger.error(f"Error processing document {doc.get('title', 'Unknown')}: {e}")
                    # Add error record
                    error_result = {
                        'source_seed': seed_url,
                        'page_num': page_count,
                        'title': doc.get('title', 'Unknown'),
                        'date': doc.get('date', ''),
                        'country': doc.get('country', ''),
                        'sector': '',
                        'detail_url': doc.get('detail_url', ''),
                        'pdf_url': '',
                        'status': 'error',
                        'notes': f'processing error: {str(e)}'
                    }
                    seed_results.append(error_result)
            
            # Get next page
            next_url = self._get_next_page_url(soup, current_url)
            if not next_url:
                self.logger.info(f"No more pages found for {seed_url}")
                break
                
            current_url = next_url
            
            # Rate limiting between pages
            time.sleep(self.rate_limit)
        
        self.logger.info(f"Completed seed {seed_url}: {len(seed_results)} agriculture documents")
        return seed_results
    
    def harvest_all_seeds(self) -> None:
        """Process all seeds and write consolidated manifest."""
        self.logger.info(f"Starting harvest of {len(self.seeds)} seeds")
        self.logger.info(f"Target sector: {self.target_sector}")
        self.logger.info(f"Max pages per seed: {self.max_pages}")
        
        for seed_url in self.seeds:
            try:
                seed_results = self.harvest_seed(seed_url)
                self.all_results.extend(seed_results)
            except Exception as e:
                self.logger.error(f"Failed to process seed {seed_url}: {e}")
        
        # Write consolidated results
        self._write_manifest()
        
        self.logger.info(f"Harvest completed. Total documents: {len(self.all_results)}")
        self.logger.info(f"Unique detail URLs processed: {len(self.processed_detail_urls)}")
    
    def _write_manifest(self) -> None:
        """Write consolidated manifest CSV."""
        if not self.all_results:
            self.logger.warning("No results to write")
            return
        
        output_file = self.out_dir / "afdb_manifest.csv"
        
        fieldnames = [
            'source_seed', 'page_num', 'title', 'date', 'country', 
            'sector', 'detail_url', 'pdf_url', 'status', 'notes'
        ]
        
        mode = 'w' if self.fresh else 'a'
        write_header = self.fresh or not output_file.exists()
        
        with open(output_file, mode, newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if write_header:
                writer.writeheader()
            writer.writerows(self.all_results)
        
        self.logger.info(f"Manifest written to: {output_file}")
        self.logger.info(f"Mode: {'overwrite' if self.fresh else 'append'}")
        self.logger.info(f"Records written: {len(self.all_results)}")


def main():
    """Production CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Production AfDB Document Harvester - Multi-seed crawler for Agriculture & Agro-industries sector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with auto-seeds
  python afdb_harvester.py --auto-seeds
  
  # Custom seeds
  python afdb_harvester.py --seeds "https://www.afdb.org/en/documents,https://www.afdb.org/en/documents/category/projects-operations"
  
  # Backward compatible with single URL
  python afdb_harvester.py --url https://www.afdb.org/en/documents
  
  # Custom configuration
  python afdb_harvester.py --auto-seeds --sector "Energy" --max-pages 10 --rate-limit 2.0 --fresh
        """
    )
    
    # Multi-seed support
    parser.add_argument(
        '--seeds',
        help='Comma-separated list of seed URLs to crawl'
    )
    
    parser.add_argument(
        '--url',
        help='Single URL for backward compatibility (use --seeds for multiple URLs)'
    )
    
    parser.add_argument(
        '--auto-seeds',
        action='store_true',
        help='Use default seed URLs if --seeds not provided'
    )
    
    # Core configuration
    parser.add_argument(
        '--sector',
        default='Agriculture & Agro-industries',
        help='Target sector to filter (default: "Agriculture & Agro-industries")'
    )
    
    parser.add_argument(
        '--out-dir',
        default='outputs',
        help='Output directory (default: outputs)'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=25,
        help='Maximum pages per seed (default: 25)'
    )
    
    parser.add_argument(
        '--rate-limit',
        type=float,
        default=1.0,
        help='Rate limit between requests in seconds (default: 1.0)'
    )
    
    # Optional configuration
    parser.add_argument(
        '--user-agent',
        help='Custom User-Agent header'
    )
    
    parser.add_argument(
        '--log-file',
        help='Custom log file path (default: {out-dir}/afdb_harvester.log)'
    )
    
    parser.add_argument(
        '--fresh',
        action='store_true',
        help='Overwrite existing manifest (default: append mode)'
    )
    
    args = parser.parse_args()
    
    # Determine seeds
    seeds = []
    
    if args.seeds:
        seeds = [url.strip() for url in args.seeds.split(',') if url.strip()]
    elif args.url:
        seeds = [args.url]
    elif args.auto_seeds:
        seeds = [
            'https://www.afdb.org/en/documents',
            'https://www.afdb.org/en/documents/category/projects-operations'
        ]
    else:
        print("Error: Must provide --seeds, --url, or --auto-seeds")
        sys.exit(1)
    
    # Validate seeds
    for seed in seeds:
        if not seed.startswith('http'):
            print(f"Error: Invalid URL '{seed}' - must start with http:// or https://")
            sys.exit(1)
    
    print(f"Production AfDB Harvester")
    print(f"Seeds: {len(seeds)}")
    for i, seed in enumerate(seeds, 1):
        print(f"  {i}. {seed}")
    print(f"Target sector: {args.sector}")
    print(f"Max pages per seed: {args.max_pages}")
    print(f"Output directory: {args.out_dir}")
    print(f"Mode: {'fresh' if args.fresh else 'append'}")
    print()
    
    # Create harvester
    try:
        harvester = AfDBHarvester(
            seeds=seeds,
            sector=args.sector,
            out_dir=args.out_dir,
            max_pages=args.max_pages,
            rate_limit=args.rate_limit,
            user_agent=args.user_agent,
            log_file=args.log_file,
            fresh=args.fresh
        )
        
        # Start harvest
        harvester.harvest_all_seeds()
        
    except KeyboardInterrupt:
        print("\nHarvest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Error during harvest: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
