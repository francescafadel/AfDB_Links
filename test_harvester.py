#!/usr/bin/env python3
"""
Test script for AfDB Harvester functionality
"""

import sys
import tempfile
import os
from afdb_harvester import AfDBHarvester


def test_harvester_initialization():
    """Test harvester initialization."""
    print("Testing harvester initialization...")
    
    seeds = ["https://www.afdb.org/en/documents"]
    harvester = AfDBHarvester(
        seeds=seeds,
        sector="Agriculture & Agro-industries",
        out_dir="test_outputs",
        max_pages=5,
        rate_limit=1.0
    )
    
    assert harvester.seeds == seeds
    assert harvester.target_sector == "Agriculture & Agro-industries"
    assert harvester.max_pages == 5
    assert harvester.rate_limit == 1.0
    assert harvester.out_dir.name == "test_outputs"
    
    print("✓ Harvester initialization test passed")


def test_sector_filtering():
    """Test sector filtering functionality."""
    print("Testing sector matching...")
    
    seeds = ["https://example.com"]
    harvester = AfDBHarvester(seeds=seeds, out_dir="test_outputs")
    
    # Test sector matching method
    assert harvester._matches_target_sector('Agriculture & Agro-industries') == True
    assert harvester._matches_target_sector('AGRICULTURE & AGRO-INDUSTRIES') == True
    assert harvester._matches_target_sector('  Agriculture & Agro-industries  ') == True
    assert harvester._matches_target_sector('Energy') == False
    assert harvester._matches_target_sector('') == False
    
    print("✓ Sector matching test passed")


def test_csv_writing():
    """Test CSV writing functionality."""
    print("Testing CSV writing...")
    
    seeds = ["https://example.com"]
    harvester = AfDBHarvester(seeds=seeds, out_dir="test_outputs")
    
    test_docs = [
        {
            'source_seed': 'https://example.com',
            'page_num': 1,
            'title': 'Test Document 1',
            'date': '2023-01-01',
            'country': 'Kenya',
            'sector': 'Agriculture & Agro-industries',
            'detail_url': 'https://example.com/doc1',
            'pdf_url': 'https://example.com/doc1.pdf',
            'status': 'linked',
            'notes': 'test document'
        },
        {
            'source_seed': 'https://example.com',
            'page_num': 1,
            'title': 'Test Document 2',
            'date': '2023-01-02',
            'country': 'Nigeria',
            'sector': 'Agriculture & Agro-industries',
            'detail_url': 'https://example.com/doc2',
            'pdf_url': '',
            'status': 'no_pdf',
            'notes': 'no pdf found'
        }
    ]
    
    # Set test results and write manifest
    harvester.all_results = test_docs
    harvester.fresh = True  # Force overwrite for test
    
    try:
        harvester._write_manifest()
        
        # Verify file was created and has content
        manifest_file = harvester.out_dir / "afdb_manifest.csv"
        assert manifest_file.exists()
        
        with open(manifest_file, 'r', encoding='utf-8') as f:
            content = f.read()
            assert 'source_seed,page_num,title,date,country,sector,detail_url,pdf_url,status,notes' in content
            assert 'Test Document 1' in content
            assert 'Test Document 2' in content
            assert 'linked' in content
            assert 'no_pdf' in content
        
        print("✓ CSV writing test passed")
    
    finally:
        # Clean up
        import shutil
        if harvester.out_dir.exists():
            shutil.rmtree(harvester.out_dir)


def test_url_parsing():
    """Test URL parsing and construction."""
    print("Testing URL parsing...")
    
    seeds = ["https://example.com"]
    harvester = AfDBHarvester(seeds=seeds, out_dir="test_outputs")
    
    # Test page number extraction
    assert harvester._extract_page_number("https://example.com?page=5") == 5
    assert harvester._extract_page_number("https://example.com?page=1&other=param") == 1
    assert harvester._extract_page_number("https://example.com") == 0
    
    # Test session creation
    assert harvester.session is not None
    
    print("✓ URL parsing test passed")


def main():
    """Run all tests."""
    print("Running AfDB Harvester tests...\n")
    
    try:
        test_harvester_initialization()
        test_sector_filtering()
        test_csv_writing()
        test_url_parsing()
        
        print("\n🎉 All tests passed!")
        return 0
    
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
