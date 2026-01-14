import pandas as pd
import re
import string

def clean_company_name(text):
    if pd.isna(text):
        return text
    text = str(text).strip()

    suffixes = [
        r'\b(inc\.?|incorporated)\b',
        r'\b(corp\.?|corporation)\b', 
        r'\b(co\.?|company)\b',
        r'\b(ltd\.?|limited)\b',
        r'\b(llc)\b',
        r'\b(lp)\b',
        r'\b(llp)\b',
        r'\b(pllc)\b',
        r'\b(pa)\b',
        r'\b(pc)\b',
        r'\b(dba)\b',
        r'\b(and associates)\b',
        r'\b(& associates)\b',
        r'\b(associates)\b'
    ]
    
    for suffix in suffixes:
        text = re.sub(suffix, '', text, flags=re.IGNORECASE)
    
    text = re.sub(f'[{re.escape(string.punctuation)}]', '', text)
    
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

file1 = pd.read_excel("India_BSE NSE_Ownership_FamilyStatus.xlsx")
file2 = pd.read_excel("Compustat Global_India BSE NSE_Active_Firm_Controls_updated.xlsx")
file3 = pd.read_excel("Compustat Global_India BSE NSE_Active_Firm.xlsx")

file1["Firmname_adj"] = file1["Company_Name"].str.title()
file1['Firmname_adj'] = file1['Firmname_adj'].apply(clean_company_name)

file2["Firmname_adj"] = file2["conm"].str.title()
file2['Firmname_adj'] = file2['Firmname_adj'].apply(clean_company_name)


file3_merged = file3.merge(
    file1[["Firmname_adj", "Family_firm"]],
    on="Firmname_adj",
    how="left"
)

file2_merged = file2.merge(
    file3_merged[["Firmname_adj", "Family_firm"]],
    on="Firmname_adj",
    how="left"
)

file2_merged.to_excel("Compustat_Global_India_BSE_NSE_Active_Firm_Controls_Merged.xlsx", index=False)
