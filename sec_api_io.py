from sec_api import DirectorsBoardMembersApi
from dotenv import load_dotenv
import os
import csv
from datetime import datetime

load_dotenv()
API_KEY = os.getenv("API_KEY")
directorBoardsMembersApi = DirectorsBoardMembersApi(API_KEY)

tickers = ["AMZN", "WMT", "GOOG"]

csv_data = []

for ticker in tickers:
    query = {
        "query": {
            "query_string": {
                "query": f"ticker:{ticker} AND filedAt:[2024-01-01 TO 2024-12-31]",
            }
        },
        "from": "0",
        "size": "1",
        "sort": [{"filedAt": {"order": "desc"}}]
    }
    
    response = directorBoardsMembersApi.get_data(query)
    
    if response['total']['value'] > 0:
        directors = response['data'][0]['directors']
        
        for director in directors:
            csv_data.append({
                'Ticker': ticker,
                'Director Name': director['name']
            })
    else:
        print(f"No data found for {ticker}")

if csv_data:
    filename = f"directors_sec_api_io_{datetime.now().strftime('%Y%m%d')}.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Ticker', 'Director Name']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"Data exported to {filename}")
else:
    print("No data to export")