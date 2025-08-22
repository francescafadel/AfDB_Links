#!/usr/bin/env python3
"""
Example usage of AfDB Harvester

This script demonstrates how to use the AfDB Harvester programmatically
instead of through the command line interface.
"""

from afdb_harvester import AfDBHarvester


def main():
    """Example usage of the AfDB Harvester."""
    
    print("AfDB Harvester - Example Usage")
    print("=" * 40)
    
    # Create harvester instance with custom settings
    harvester = AfDBHarvester(
        base_url="https://www.afdb.org",
        max_pages=3,  # Limit to 3 pages for demo
        delay=2.0,    # 2 second delay between requests
        timeout=30    # 30 second timeout
    )
    
    print(f"Target sector: {harvester.target_sector}")
    print(f"Max pages: {harvester.max_pages}")
    print(f"Delay: {harvester.delay} seconds")
    print()
    
    # Example URL - you would replace this with the actual AfDB documents URL
    start_url = "https://www.afdb.org/en/documents"
    
    print(f"Starting harvest from: {start_url}")
    print("Note: This is a demo. Replace with actual AfDB documents URL to run.")
    print()
    
    # Uncomment the following lines to actually run the harvester:
    # try:
    #     harvester.harvest(start_url, "example_output.csv")
    #     print("Harvest completed successfully!")
    # except Exception as e:
    #     print(f"Error during harvest: {e}")
    
    print("To run the harvester, uncomment the harvest() call in this script.")
    print("Or use the command line interface:")
    print("  python3 afdb_harvester.py https://www.afdb.org/en/documents --max-pages 3")


if __name__ == "__main__":
    main()
