#!/usr/bin/env python3
"""
Clean CSV file by removing the methodology row
"""

import csv

def clean_csv(input_file, output_file):
    """Remove the first row (methodology) and keep the rest."""
    with open(input_file, 'r', encoding='utf-8') as infile:
        reader = csv.reader(infile)
        rows = list(reader)
    
    # Remove the first row (methodology)
    cleaned_rows = rows[1:]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerows(cleaned_rows)
    
    print(f"Cleaned CSV saved to: {output_file}")
    print(f"Removed 1 row, kept {len(cleaned_rows)} rows")

if __name__ == "__main__":
    clean_csv("AfDB Final Corpus - Sheet1.csv", "afdb_clean.csv")
