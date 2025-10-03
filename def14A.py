import requests
from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import time

companies = [
    {"ticker": "AMZN", "cik": "0001018724", "name": "Amazon"},
    {"ticker": "WMT", "cik": "0000104169", "name": "Walmart"},
    {"ticker": "GOOG", "cik": "0001652044", "name": "Alphabet/Google"}
]

headers = {
    'User-Agent': 'Your Name your-email@example.com'
}

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
    if not text:
        return ""
    cleaned = re.sub(r'[\n\r\t]+', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def has_name_column(table):
    rows = table.find_all('tr')
    if not rows:
        return None
    
    for row in rows[:5]:
        cells = row.find_all(['th', 'td'], recursive=False)
        if len(cells) < 2:
            continue
        
        for idx, cell in enumerate(cells):
            cell_text = clean_text(cell.get_text()).lower()
            if not cell_text:
                continue
            if 'name' in cell_text:
                return idx
    
    return None

def find_compensation_table(soup):
    all_elements = soup.find_all()
    
    for element in all_elements:
        text = clean_text(element.get_text()).lower()
        
        for keyword in compensation_keywords:
            if keyword in text and len(text) < 200:
                current = element
                tables_checked = 0
                for step in range(100):
                    current = current.find_next()
                    if current is None:
                        break
                    if current.name == 'table':
                        tables_checked += 1
                        name_col_idx = has_name_column(current)
                        if name_col_idx is not None:
                            return current, name_col_idx
                        if tables_checked >= 5:
                            break
                break
    
    return None, None

def extract_names_from_table(table, name_column_index):
    names = []
    rows = table.find_all('tr')
    if not rows:
        return names
    
    for row in rows[1:]:
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
                    names.append(name)
    
    return names

for company in companies:
    cik = company['cik']
    ticker = company['ticker']
    name = company['name']
    
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        filings = data['filings']['recent']
        
        for i in range(len(filings['form'])):
            form_type = filings['form'][i]
            filing_date = filings['filingDate'][i]
            accession_number = filings['accessionNumber'][i]
            primary_document = filings['primaryDocument'][i]
            
            if form_type == 'DEF 14A' and filing_date.startswith(('2024', '2025')):
                year = filing_date[:4]
                accession_no_clean = accession_number.replace('-', '')
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession_no_clean}/{primary_document}"
                
                time.sleep(0.1)
                doc_response = requests.get(doc_url, headers=headers)
                
                if doc_response.status_code == 200:
                    soup = BeautifulSoup(doc_response.content, 'html.parser')
                    comp_table, name_col_idx = find_compensation_table(soup)
                    
                    if comp_table and name_col_idx is not None:
                        director_names = extract_names_from_table(comp_table, name_col_idx)
                        for director_name in director_names:
                            csv_data.append({
                                'Ticker': ticker,
                                'Year': year,
                                'Director Name': director_name
                            })
    
    time.sleep(0.1)

if csv_data:
    filename = f"director_names_{datetime.now().strftime('%Y%m%d')}.csv"
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Ticker', 'Year', 'Director Name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Data exported to {filename}")
    print(f"Total director entries: {len(csv_data)}")
else:
    print("No data to export")