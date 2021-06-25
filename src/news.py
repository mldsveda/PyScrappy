import urllib.request
try:
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.common.keys import Keys
    from selenium import webdriver
except:
    print("<--- Please install the below packages  --->")
    print("--pip install selenium")
    print("--pip install webdriver-manager")
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
import requests
import time
import json
import re
import os 

usr_agent = {
'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
'Accept-Encoding': 'none',
'Accept-Language': 'en-US,en;q=0.8',
'Connection': 'keep-alive',
}

def scrappi(n_pages, genre):
    
    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get('https://inshorts.com/en/read/'+genre)
    
    for _ in range(n_pages):
        driver.find_element_by_tag_name('body').send_keys(Keys.END)
        time.sleep(3)
        driver.find_element_by_id('load-more-btn').click()
        text_field = driver.find_element_by_id('load-more-btn')
        
    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.find_all('div', {"class": "news-card z-depth-1"})
    
    lst = []
    for details in main:
        dictionary={}
        dictionary['Headlines'] = (details.find('a', {"class": "clickable"}).text).replace('\n', '')
        dictionary['Time'] = details.find('span', {"class": "time"}).text
        date = details.find('div', {"class": "news-card-author-time news-card-author-time-in-title"}).find_all('span')
        dictionary['Date'] = date[3].text
        dictionary['News'] = details.find('div', {"itemprop": "articleBody"}).text
        
        lst.append(dictionary)

    df = pd.DataFrame(lst)
    return df