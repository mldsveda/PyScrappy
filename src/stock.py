import re
import json
import csv
from io import StringIO
from bs4 import BeautifulSoup
import requests
import pandas as pd

def stock_financial(stock_code):    
    url_financials = 'https://finance.yahoo.com/quote/'+stock_code+'/financials?p='+stock_code
    response = requests.get(url_financials)
    soup = BeautifulSoup(response.text, 'html.parser')
    pattern = re.compile(r'\s--\sData\s--\s')
    script_data = soup.find('script', text=pattern).contents[0]
    start = script_data.find("context")-2
    json_data = json.loads(script_data[start:-12])
    
    # income statement
    annual_is = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['incomeStatementHistory']['incomeStatementHistory']
    quarterly_is = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['incomeStatementHistoryQuarterly']['incomeStatementHistory']

    # cash flow statement
    annual_cf = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['cashflowStatementHistory']['cashflowStatements']
    quarterly_cf = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['cashflowStatementHistoryQuarterly']['cashflowStatements']

    # balance sheet
    annual_bs = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['balanceSheetHistory']['balanceSheetStatements']
    quarterly_bs = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['balanceSheetHistoryQuarterly']['balanceSheetStatements']
    
    annual_is_stmts = []
    quarterly_is_stmts = []
    # consolidate annual
    for s in annual_is:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        annual_is_stmts.append(statement)

    # consolidate quaterly
    for s in quarterly_is:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        quarterly_is_stmts.append(statement)
        
        
    annual_cf_stmts = []
    quarterly_cf_stmts = []
    # annual
    for s in annual_cf:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        annual_cf_stmts.append(statement)

    # quarterly
    for s in quarterly_cf:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        quarterly_cf_stmts.append(statement)
        
    annual_bs_stmts = []
    quarterly_bs_stmts = []

    # annual
    for s in annual_bs:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        annual_bs_stmts.append(statement)

    # quarterly
    for s in quarterly_bs:
        statement = {}
        for key, val in s.items():
            try: statement[key] = val['raw']
            except TypeError: continue
            except KeyError: continue
        quarterly_bs_stmts.append(statement)
        
    return annual_is_stmts, quarterly_is_stmts, annual_cf_stmts, quarterly_cf_stmts, annual_bs_stmts, quarterly_bs_stmts

# Stock Profile
def stock_profile(stock_code):
    url_profile = 'https://finance.yahoo.com/quote/'+stock_code+'/profile?p='+stock_code
    response = requests.get(url_profile)
    soup = BeautifulSoup(response.text, 'html.parser')
    pattern = re.compile(r'\s--\sData\s--\s')
    script_data = soup.find('script', text=pattern).contents[0]
    start = script_data.find("context")-2
    json_data = json.loads(script_data[start:-12])
    company_officers = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['assetProfile']['companyOfficers']
    print('About the Company Officers:')
    print('------------------------------')
    for i in company_officers: 
        print('Name: ', i['name'])
        if 'age' in i.keys(): print('Age: ', i['age'])
        print('Designation: ', i['title'])
        print()
    print('\n')
    print('About the Company:')
    print('----------------------')
    # business description
    business_description = json_data['context']['dispatcher']['stores']['QuoteSummaryStore']['assetProfile']['longBusinessSummary']
    print(business_description)

# Historical Data
def stock_history(stock_code, stock_range, stock_interval):
    if stock_range=='Max': stock_range='200000y'
    if stock_interval=='Daily': stock_interval='1d'
    if stock_interval=='Weekly': stock_interval='1wk'
    if stock_interval=='Monthly': stock_interval='1mo'
    stock_url = 'https://query1.finance.yahoo.com/v7/finance/download/'+stock_code+'?'
    params = {
        'range': stock_range,
        'interval': stock_interval,
        'events':'history'
    }
    response = requests.get(stock_url, params = params)
    file = StringIO(response.text)
    reader = csv.reader(file)
    data = list(reader)
    df = pd.DataFrame(data[1:], columns = ['Date', 'Open', 'High', 'Low', 'Close','Adjusted Close', 'Volume'])
    return df