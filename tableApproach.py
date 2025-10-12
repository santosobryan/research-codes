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
]




csv_data = []




headers = {
    'User-Agent': 'Your Name your-email@example.com'
}




def clean_text(text):
    """Clean text by removing extra whitespace and newlines"""
    if not text:
        return ""
    cleaned = re.sub(r'[\n\r\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()




def has_name_column(table):
    """Check if table has a 'name' column and return its index"""
    rows = table.find_all('tr')
    if not rows:
        return None
    
    # Check first few rows for headers
    for row_idx, row in enumerate(rows[:5]):
        cells = row.find_all(['th', 'td'], recursive=False)
        
        if len(cells) < 2:
            continue
        
        for idx, cell in enumerate(cells):
            cell_text = clean_text(cell.get_text()).lower()
            
            if not cell_text:
                continue
            
            # Check for name column - accept if 'name' appears anywhere
            if 'name' in cell_text:
                # Skip if it's about plans, awards, or other non-person names
                if any(exclude in cell_text for exclude in ['plan name', 'award name', 'grant name', 'program name']):
                    continue
                
                return idx
    
    return None




def get_text_around_table(table, elements_before=50, elements_after=20):
    """Get text from elements before and after a table"""
    text_before = []
    text_after = []
    
    # Get text before table
    current = table
    for _ in range(elements_before):
        current = current.find_previous()
        if current is None:
            break
        if hasattr(current, 'get_text'):
            text = clean_text(current.get_text())
            if text and len(text) < 200:  # Avoid huge blocks
                text_before.append(text)
    
    # Get text after table
    current = table
    for _ in range(elements_after):
        current = current.find_next()
        if current is None:
            break
        if hasattr(current, 'get_text'):
            text = clean_text(current.get_text())
            if text and len(text) < 200:
                text_after.append(text)
    
    return ' '.join(reversed(text_before)), ' '.join(text_after)




def is_compensation_table(table, text_before, text_after):
    """Check if table is likely a director compensation table"""
    # Normalize apostrophes in context text
    combined_text = (text_before + ' ' + text_after).lower()
    combined_text_normalized = re.sub(r"['`´]", "'", combined_text)
    
    # Check for compensation keywords in surrounding text
    for keyword in compensation_keywords:
        keyword_normalized = re.sub(r"[`´']", "'", keyword).lower()
        if keyword_normalized in combined_text_normalized:
            return True, keyword
    
    return False, None




def has_numeric_columns(table):
    """Check if table has numeric/dollar columns (typical of compensation tables)"""
    rows = table.find_all('tr')
    if len(rows) < 2:
        return False
    
    # Check a few data rows
    for row in rows[1:4]:
        cells = row.find_all(['td', 'th'], recursive=False)
        if len(cells) < 2:
            continue
        
        # Check if any cells contain dollar amounts or numbers
        for cell in cells[1:]:  # Skip first column (usually names)
            text = clean_text(cell.get_text())
            if re.search(r'\$|[\d,]+\.\d{2}|[\d,]{4,}', text):
                return True
    
    return False




def extract_names_from_table(table, name_column_index):
    """Extract names from the Name column of the table"""
    names = []
    
    title_keywords = [
        'chief', 'president', 'ceo', 'cfo', 'coo', 'executive',
        'chairman', 'chair', 'vice', 'secretary', 'treasurer',
        'officer', 'controller', 'manager', 'lead', 'head',
        'senior', 'junior', 'assistant', 'emeritus',
        'independent', 'non-employee', 'employee',
        'audit', 'compensation', 'governance', 'nominating',
        'committee', 'retired', 'former', 'founder', 'current', 'and', 'all'
    ]
    
    rows = table.find_all('tr')
    
    if not rows:
        return names
    
    print(f"      Extracting names from table (Name column: {name_column_index})")
    
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
                        
                        for keyword in title_keywords:
                            pos = name_lower.find(keyword)
                            if pos != -1 and pos < earliest_pos:
                                earliest_pos = pos
                        
                        if earliest_pos > 0:
                            clean_name = name[:earliest_pos].strip()
                            clean_name = re.sub(r'[,\-—()\s]+$', '', clean_name).strip()
                            
                            if clean_name and len(clean_name) > 2 and not re.match(r'^[\d,\$\.\s\-—]+$', clean_name):
                                print(f"        Row {row_idx}: CLEANED - '{name}' -> '{clean_name}'")
                                names.append(clean_name)
                        else:
                            print(f"        Row {row_idx}: SKIPPED (title only) - {name}")
                    else:
                        names.append(name)
                        print(f"        Row {row_idx}: {name}")
    
    return names




def find_compensation_table(soup):
    """Find director compensation table by checking all tables"""
    all_tables = soup.find_all('table')
    
    print(f"  Found {len(all_tables)} total tables in document")
    print(f"  Checking each table for compensation context and structure...")
    
    for table_idx, table in enumerate(all_tables, start=1):
        print(f"\n  Table #{table_idx}:")
        
        # Get surrounding text
        text_before, text_after = get_text_around_table(table)
        
        # Check if it's a compensation table based on context
        is_comp_table, matched_keyword = is_compensation_table(table, text_before, text_after)
        
        if is_comp_table:
            print(f"    ✓ Found keyword '{matched_keyword}' in surrounding text")
            
            # Check if table has name column
            name_col_idx = has_name_column(table)
            
            if name_col_idx is not None:
                print(f"    ✓ Has name column at index {name_col_idx}")
                
                # Check if table has numeric columns (compensation data)
                has_numbers = has_numeric_columns(table)
                
                if has_numbers:
                    print(f"    ✓ Has numeric/dollar columns")
                    print(f"    ✓✓✓ This appears to be the director compensation table!")
                    return table, name_col_idx
                else:
                    print(f"    ✗ No numeric columns found, continuing search...")
            else:
                print(f"    ✗ No name column found, continuing search...")
        else:
            print(f"    ✗ No compensation keywords in surrounding text")
    
    print(f"\n  ✗ No suitable compensation table found")
    return None, None




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
            comp_table, name_col_idx = find_compensation_table(soup)
            
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
                print(f"\n  ✗ Could not find director compensation table")
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