import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import time

compensation_keywords = [
    'director compensation',           
    'compensation of directors',
    'non-employee director compensation',
    'board compensation', 
    'director remuneration',
    'compensation for directors',
    "directors' compensation",
    "director's compensation",
    "directors' compensation",
    "director's compensation",
    "directors&#8217; compensation",
    "director&#8217;s compensation",
    "directors&rsquo; compensation",
    "director&rsquo;s compensation",
]

csv_data = []

headers = {
    'User-Agent': 'Your Name your-email@example.com'
}

def clean_text(text):
    if not text:
        return ""
    cleaned = re.sub(r'[\n\r\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def has_name_column(table):
    rows = table.find_all('tr')
    if not rows:
        return None
    
    print(f"      Checking table with {len(rows)} rows for name column...")
    
    for row_idx, row in enumerate(rows[:5]):
        cells = row.find_all(['th', 'td'], recursive=False)
        
        if len(cells) < 2:
            continue
        
        name_col_idx = None
        
        cell_preview = []
        for idx, cell in enumerate(cells):
            cell_text = clean_text(cell.get_text()).lower()
            cell_preview.append(f"{idx}:{cell_text[:15] if cell_text else '[empty]'}")
        print(f"        Row {row_idx}: {' | '.join(cell_preview[:8])}")
        
        for idx, cell in enumerate(cells):
            cell_text = clean_text(cell.get_text()).lower()
            
            if not cell_text:
                continue
            
            if 'name' in cell_text and name_col_idx is None:
                if any(exclude in cell_text for exclude in ['plan name', 'award name', 'grant name', 'program name']):
                    print(f"          Found 'name' at column {idx} but excluded: '{cell_text}'")
                    continue
                
                name_col_idx = idx
                print(f"          Found 'name' at column {idx}: '{cell_text}'")
                print(f"        ✓ Row {row_idx} has name column at index {name_col_idx}")
                return name_col_idx
    
    print(f"        ✗ No row found with name column")
    return None

def find_compensation_table(soup, filing_date):
    all_elements = soup.find_all()
    
    print(f"  Searching through {len(all_elements)} total elements...")
    
    matches_found = 0
    
    for element in all_elements:
        text = clean_text(element.get_text()).lower()
        
        for keyword in compensation_keywords:
            if keyword in text and len(text) < 200:
                matches_found += 1
                print(f"\n  Match #{matches_found}: Found '{keyword}' in <{element.name}> tag")
                print(f"    Text: '{clean_text(element.get_text())[:80]}'")
                
                current = element
                tables_checked = 0
                for step in range(100):
                    current = current.find_next()
                    if current is None:
                        break
                    if current.name == 'table':
                        tables_checked += 1
                        print(f"    Found table #{tables_checked} after {step} steps")
                        
                        name_col_idx = has_name_column(current)
                        
                        if name_col_idx is not None:
                            print(f"    ✓✓✓ Table has Name column at index {name_col_idx}!")
                            return current, name_col_idx
                        else:
                            print(f"    Continuing search...")
                            
                            if tables_checked >= 5:
                                print(f"    Checked {tables_checked} tables, moving to next keyword match")
                                break
                break
    
    print(f"\n  Total keyword matches found: {matches_found}")
    return None, None

def extract_names_from_table(table, name_column_index):
    names = []
    
    title_keywords = [
        'chief', 'president', 'ceo', 'cfo', 'coo', 'executive',
        'chairman', 'chair', 'vice', 'secretary', 'treasurer',
        'officer', 'controller', 'manager', 'lead', 'head',
        'senior', 'junior', 'assistant', 'emeritus',
        'independent', 'non-employee', 'employee',
        'audit', 'compensation', 'governance', 'nominating',
        'committee', 'retired', 'former', 'founder', 'current', 'and','all'
    ]
    
    rows = table.find_all('tr')
    
    if not rows:
        return names
    
    print(f"\n  Extracting names from table:")
    print(f"    Total rows: {len(rows)}")
    print(f"    Name column index: {name_column_index}")
    
    for row_idx, row in enumerate(rows, start=1):
        cells = row.find_all(['td', 'th'], recursive=False)
        
        if len(cells) > name_column_index:
            name = clean_text(cells[name_column_index].get_text())
            
            name_lower = name.lower()
            
            if (name and len(name) > 2 and 
                not name_lower.startswith(('total', '$', '—', 'none', 'fees', 'stock', 'award', 
                                          'option', 'incentive', 'all other', 'name')) and
                not re.match(r'^[\d,\$\.\s\-—]+$', name) and
                name not in ['—', '&#8212;']):
                
                name = re.sub(r'\(\d+\)|\*+|†+|‡+|\[\d+\]|<sup>.*?</sup>', '', name)
                name = re.sub(r'&#\d+;', '', name)
                name = clean_text(name)
                
                if name and len(name) > 2:
                    name_lower = name.lower()
                    
                    has_title_keyword = any(keyword in name_lower for keyword in title_keywords)
                    
                    if has_title_keyword:
                        earliest_pos = len(name)
                        matched_keyword = None
                        
                        for keyword in title_keywords:
                            pos = name_lower.find(keyword)
                            if pos != -1 and pos < earliest_pos:
                                earliest_pos = pos
                                matched_keyword = keyword
                        
                        if earliest_pos > 0:
                            clean_name = name[:earliest_pos].strip()
                            clean_name = re.sub(r'[,\-—()\s]+$', '', clean_name).strip()
                            
                            if clean_name and len(clean_name) > 2 and not re.match(r'^[\d,\$\.\s\-—]+$', clean_name):
                                print(f"    Row {row_idx}: CLEANED - '{name}' -> '{clean_name}'")
                                names.append(clean_name)
                            else:
                                print(f"    Row {row_idx}: SKIPPED (invalid after cleaning) - {name}")
                        else:
                            print(f"    Row {row_idx}: SKIPPED (title only) - {name}")
                    else:
                        names.append(name)
                        print(f"    Row {row_idx}: {name}")
    
    return names

input_csv = 'def14a_filings_catalog.csv'
indices_to_process = [1847, 423, 1256, 89, 1673, 942, 1501, 267, 1834, 1092, 556, 1429, 703, 1965, 318, 1176, 847, 1612, 475, 1289]

with open(input_csv, 'r', encoding='utf-8') as file:
    reader = csv.DictReader(file)
    rows = list(reader)
    
    for idx in indices_to_process:
        if idx >= len(rows):
            print(f"Index {idx} out of range, skipping")
            continue
        
        row = rows[idx]
        company_name = row['company_name']
        cik = row['cik']
        filing_date = row['filing_date']
        accession_number = row['accession_number']
        sec_url = row['sec_url']
        
        year = filing_date[:4]
        
        print(f"\n{'='*60}")
        print(f"Processing: {company_name} ({filing_date})")
        print(f"{'='*60}")
        
        time.sleep(0.1)
        doc_response = requests.get(sec_url, headers=headers)
        
        if doc_response.status_code == 200:
            soup = BeautifulSoup(doc_response.content, 'html.parser')
            comp_table, name_col_idx = find_compensation_table(soup,filing_date)
            
            if comp_table and name_col_idx is not None:
                director_names = extract_names_from_table(comp_table, name_col_idx)
                print(f"\n  ✓ Successfully extracted {len(director_names)} directors")
                for director_name in director_names:
                    csv_data.append({
                        'Company': company_name,
                        'CIK': cik,
                        'Year': year,
                        'Director Name': director_name
                    })
            else:
                print(f"\n  ✗ Could not find director compensation table with name column")
        else:
            print(f"  Error fetching document: {doc_response.status_code}")

if csv_data:
    filename = f"director_names_new_{datetime.now().strftime('%Y%m%d')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Company', 'CIK', 'Year', 'Director Name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\n{'='*60}")
    print(f"Data exported to {filename}")
    print(f"Total director entries: {len(csv_data)}")
else:
    print("\nNo data to export")