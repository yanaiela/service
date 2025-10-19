#!/usr/bin/env python3
"""
Extended debug script to find where references actually start in this specific PDF.
"""

import sys
import pdfplumber
import re
from pathlib import Path

def find_references_in_pdf(pdf_path: str):
    """Find where references start in this specific PDF."""
    print(f"Searching for references in: {pdf_path}")
    print("=" * 60)
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"Total pages: {total_pages}")
            print()
            
            # Look at the last several pages to find references
            start_page = max(0, total_pages - 10)
            
            for page_idx in range(start_page, total_pages):
                page = pdf.pages[page_idx]
                page_text = page.extract_text() or ""
                lines = [line.strip() for line in page_text.split('\n') if line.strip()]
                
                print(f"\n--- PAGE {page_idx + 1} ---")
                
                # Show all lines for the last few pages
                for i, line in enumerate(lines):
                    print(f"{i+1:2d}: {line}")
                
                # Look for reference patterns
                ref_indicators = [
                    'References',
                    'REFERENCES', 
                    'Bibliography',
                    'BIBLIOGRAPHY'
                ]
                
                for line in lines:
                    line_clean = line.strip()
                    if any(indicator in line_clean for indicator in ref_indicators):
                        print(f"\n*** FOUND POTENTIAL REFERENCES MARKER: '{line_clean}' ***")
                
                # Look for citation patterns
                citation_count = 0
                for line in lines:
                    # Common academic citation patterns
                    if (re.search(r'[A-Z][a-z]+.*\(\d{4}\)', line) or  # Author (year)
                        re.search(r'[A-Z][a-z]+.*,\s*\d{4}', line) or    # Author, year
                        re.search(r'^\d+\.\s*[A-Z]', line) or             # 1. Author
                        re.search(r'^\[\d+\]', line)):                    # [1]
                        citation_count += 1
                
                if citation_count > 3:
                    print(f"\n*** PAGE HAS {citation_count} CITATION-LIKE LINES ***")
                
                if page_idx >= start_page + 3:  # Only show a few pages
                    print("\n... (truncated)")
                    break
                    
    except Exception as e:
        print(f"Error analyzing PDF: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python find_references.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"File not found: {pdf_path}")
        sys.exit(1)
    
    find_references_in_pdf(pdf_path)