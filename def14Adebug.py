import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import time

# Company information
companies = [
    {"ticker": "BAX", "cik": "0000010456", "name": "Baxter"},
]

# Required headers for SEC API
headers = {
    'User-Agent': 'Your Name your-email@example.com'  # Replace with your info
}

# Keywords to identify director compensation section
compensation_keywords = [
    'director compensation',
    'compensation of directors',
    'non-employee director compensation',
    'board compensation',
    'director remuneration',
    'compensation for directors'
]

csv_data = []

def clean_text(text):
    """Clean text by removing extra whitespace and newlines"""
    if not text:
        return ""
    # Replace newlines, tabs, and multiple spaces with single space
    cleaned = re.sub(r'[\n\r\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def has_name_column(table):
    """Check if table has a 'name' column and return its index"""
    rows = table.find_all('tr')
    if not rows:
        return None
    
    print(f"      Checking table with {len(rows)} rows for name column...")
    
    # Check first few rows for headers - these could be in either th OR td tags
    for row_idx, row in enumerate(rows[:5]):
        # Get all cells (both th and td) directly under this tr
        cells = row.find_all(['th', 'td'], recursive=False)
        
        if len(cells) < 2:  # Need at least 2 columns
            continue
        
        name_col_idx = None
        
        # Debug: show what we found in this row
        cell_preview = []
        for idx, cell in enumerate(cells):
            # Clean the text to handle newlines
            cell_text = clean_text(cell.get_text()).lower()
            cell_preview.append(f"{idx}:{cell_text[:15] if cell_text else '[empty]'}")
        print(f"        Row {row_idx}: {' | '.join(cell_preview[:8])}")
        
        for idx, cell in enumerate(cells):
            # Clean the text to handle newlines
            cell_text = clean_text(cell.get_text()).lower()
            
            # Skip empty cells
            if not cell_text:
                continue
            
            # Check for name column
            if 'name' in cell_text and name_col_idx is None:
                name_col_idx = idx
                print(f"          Found 'name' at column {idx}")
                # Found name column, return immediately
                print(f"        ✓ Row {row_idx} has name column at index {name_col_idx}")
                return name_col_idx
    
    print(f"        ✗ No row found with name column")
    return None

def find_compensation_table(soup, filing_date):
    """Find the director compensation table in the HTML document"""
    
    # Find ALL elements (any tag) in the document
    all_elements = soup.find_all()
    
    print(f"  Searching through {len(all_elements)} total elements...")
    
    matches_found = 0
    
    for element in all_elements:
        # Clean text to handle newlines
        text = clean_text(element.get_text()).lower()
        
        # Check if this element contains compensation keywords
        for keyword in compensation_keywords:
            if keyword in text and len(text) < 200:  # Header shouldn't be too long
                matches_found += 1
                print(f"\n  Match #{matches_found}: Found '{keyword}' in <{element.name}> tag")
                # Show cleaned text
                print(f"    Text: '{clean_text(element.get_text())[:80]}'")
                
                # Look for tables near this element
                current = element
                tables_checked = 0
                for step in range(100):  # Look ahead up to 100 elements
                    current = current.find_next()
                    if current is None:
                        break
                    if current.name == 'table':
                        tables_checked += 1
                        print(f"    Found table #{tables_checked} after {step} steps")
                        
                        # Check if this table has a 'name' column
                        name_col_idx = has_name_column(current)
                        
                        if name_col_idx is not None:
                            print(f"    ✓✓✓ Table has Name column at index {name_col_idx}!")
                            return current, name_col_idx
                        else:
                            print(f"    Continuing search...")
                            
                            # Only check first 5 tables after keyword
                            if tables_checked >= 5:
                                print(f"    Checked {tables_checked} tables, moving to next keyword match")
                                break
                break  # Found keyword match, no need to check other keywords for this element
    
    print(f"\n  Total keyword matches found: {matches_found}")
    return None, None

def extract_names_from_table(table, name_column_index):
    """Extract names from the Name column of the table"""
    names = []
    
    # Find all rows
    rows = table.find_all('tr')
    
    if not rows:
        return names
    
    print(f"\n  Extracting names from table:")
    print(f"    Total rows: {len(rows)}")
    print(f"    Name column index: {name_column_index}")
    
    # Extract names from data rows (skip first row which is likely header)
    for row_idx, row in enumerate(rows[1:], start=1):
        # Get cells directly under this tr (both th and td)
        cells = row.find_all(['td', 'th'], recursive=False)
        
        if len(cells) > name_column_index:
            # Clean text to handle newlines
            name = clean_text(cells[name_column_index].get_text())
            
            # Clean up name and filter out non-name entries
            name_lower = name.lower()
            
            # Skip if it's clearly not a name
            if (name and len(name) > 2 and 
                not name_lower.startswith(('total', '$', '—', 'none', 'fees', 'stock', 'award', 
                                          'option', 'incentive', 'all other', 'name')) and
                not re.match(r'^[\d,\$\.\s\-—]+$', name) and  # Skip numeric entries
                name not in ['—', '&#8212;']):
                
                # Remove footnote markers and HTML entities
                name = re.sub(r'\(\d+\)|\*+|†+|‡+|\[\d+\]|<sup>.*?</sup>', '', name)
                name = re.sub(r'&#\d+;', '', name)  # Remove HTML entities
                name = clean_text(name)  # Final clean to remove any remaining whitespace
                
                if name and len(name) > 2:
                    names.append(name)
                    print(f"    Row {row_idx}: {name}")
    
    return names

for company in companies:
    cik = company['cik']
    ticker = company['ticker']
    name = company['name']
    
    print(f"\n{'='*60}")
    print(f"Processing {name} ({ticker})")
    print(f"{'='*60}")
    
    # Get company submissions
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        filings = data['filings']['recent']
        
        # Filter for DEF 14A filings in 2024-2025
        for i in range(len(filings['form'])):
            form_type = filings['form'][i]
            filing_date = filings['filingDate'][i]
            accession_number = filings['accessionNumber'][i]
            primary_document = filings['primaryDocument'][i]
            # Check if it's DEF 14A and filed in 2022 or 2025
            if form_type == 'DEF 14A' and filing_date.startswith(('2024')):
                year = filing_date[:4]
                print(f"\nFiling Date: {filing_date}")
                print(f"Accession Number: {accession_number}")
                print(f"Primary Document: {primary_document}")
                
                # Construct document URL
                accession_no_clean = accession_number.replace('-', '')
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no_clean}/{primary_document}"
                print(f"Document URL: {doc_url}")
                
                # Fetch the HTML document
                time.sleep(0.1)  # Be respectful to SEC servers
                doc_response = requests.get(doc_url, headers=headers)
                
                if doc_response.status_code == 200:
                    soup = BeautifulSoup(doc_response.content, 'html.parser')
                    
                    # Find director compensation table
                    comp_table, name_col_idx = find_compensation_table(soup, filing_date)
                    
                    if comp_table and name_col_idx is not None:
                        # Extract names
                        director_names = extract_names_from_table(comp_table, name_col_idx)
                        print(f"\n  ✓ Successfully extracted {len(director_names)} directors")
                        
                        # Add to CSV data
                        for director_name in director_names:
                            csv_data.append({
                                'Ticker': ticker,
                                'Year': year,
                                'Director Name': director_name
                            })
                    else:
                        print(f"\n  ✗ Could not find director compensation table with name column")
                else:
                    print(f"  Error fetching document: {doc_response.status_code}")
    else:
        print(f"Error retrieving data: {response.status_code}")
    
    time.sleep(0.1)  # Rate limiting

# Write to CSV
if csv_data:
    filename = f"director_names_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Ticker', 'Year', 'Director Name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\n{'='*60}")
    print(f"Data exported to {filename}")
    print(f"Total director entries: {len(csv_data)}")
else:
    print("\nNo data to export")