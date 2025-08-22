#!/usr/bin/env python3
"""
CSV Cleaning Utility for AfDB Data Processing.

This script removes the methodology row from the AfDB Final Corpus CSV file
and prepares it for processing by the MapAfrica extractor.

Author: Francesca Fadel
Repository: https://github.com/francescafadel/AfDB_Links.git
"""

import csv
import sys


def clean_csv(input_file: str, output_file: str) -> None:
    """
    Remove the first row (methodology) from CSV and keep the rest.
    
    Args:
        input_file: Path to input CSV file
        output_file: Path to output CSV file
    """
    try:
        # Read input file
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.reader(infile)
            rows = list(reader)
        
        if not rows:
            print("Error: Input file is empty")
            return
        
        # Remove the first row (methodology)
        cleaned_rows = rows[1:]
        
        # Write cleaned data
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.writer(outfile)
            writer.writerows(cleaned_rows)
        
        print(f"✅ Cleaned CSV saved to: {output_file}")
        print(f"📊 Removed 1 row, kept {len(cleaned_rows)} rows")
        
    except FileNotFoundError:
        print(f"❌ Error: Input file '{input_file}' not found")
    except Exception as e:
        print(f"❌ Error processing CSV: {e}")


def main():
    """Main function to handle command line execution."""
    if len(sys.argv) != 3:
        print("Usage: python3 clean_csv.py <input_file> <output_file>")
        print("Example: python3 clean_csv.py 'AfDB Final Corpus - Sheet1.csv' afdb_clean.csv")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    clean_csv(input_file, output_file)


if __name__ == "__main__":
    # Default behavior: clean the AfDB Final Corpus file
    clean_csv("AfDB Final Corpus - Sheet1.csv", "afdb_clean.csv")
