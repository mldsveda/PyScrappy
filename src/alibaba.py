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

def scrappi(n_pages):

    # Url input
    url=str(input("Enter the desired Alibaba URL: \n"))
    urls=requests.get(url)

    initial_url =str(url)
    lst_of_urls = []
    for i in range(0, n_pages):
        x = initial_url + '&page=' + str(i)
        lst_of_urls.append(x)
    #print(lst_of_urls)

    def alibaba(soup):
        #x = "Same"
        lst = []
        urls=requests.get(url)
        soup=BeautifulSoup(urls.text,"lxml")
        Main=soup.find_all("div",class_="app-organic-search__list")
        try:
            # For Card Style
            if len(Main[0].find("div",class_="m-gallery-product-item-v2"))>=1:
                #print("Card Style Container\n")
                cnt=soup.find_all("div",{"class":"m-gallery-product-item-v2"})
                #print(len(cnt))
                #ad=soup.find("div",{"class":"_2tfzpE"})
                for i in range(len(cnt)):
                    try:
                        name = cnt[i].find("p",{"class":"elements-title-normal__content"}).text
                        # Capitalizing the First letter
                        name = name.capitalize()
                        # Discounted Price
                        #Price = cnt[i].find("span",{"class":"elements-offer-price-normal__price"}).text
                        # Removing the ₹
                        #Price = re.sub('[₹]', '', Price)
                        # Original Price
                        Priceo = cnt[i].find("span",{"class":"element-offer-minorder-normal__value"}).text
                        oprice = Priceo[0]
                        # Removing the ₹
                        #oprice = re.sub('[₹]', '', oprice)
                        # Description of the Product
                        #Description = cnt[i].find("div",{"class":"_3Djpdu"}).text
                        # Appending in a list
                        lst.append([name, oprice])
                    except:
                        lst.append([name, oprice])
                        #pass
                        #print("Not Exist")
        except:
            # For Rectangle Style
            if len(Main[0].find("div",class_="_2kHMtA"))>=1:
                #print("Rectangular Style Container\n")
                cnt=soup.find_all("div",{"class":"_2kHMtA"})
                ad=soup.find("div",{"class":"_2tfzpE"})
                for i in range(len(cnt)):
                    try:
                        name=cnt[i].find("div",{"class":"_4rR01T"}).text
                        # Capitalizing the First letter
                        name = name.capitalize()
                        # Discounted Price
                        Price = cnt[i].find("div",{"class":"_30jeq3 _1_WHN1"}).text
                        # Removing the ₹
                        #Price = re.sub('[₹]', '', Price)
                        # Original Price
                        Priceo=cnt[i].find("div",{"class":"_3I9_wc _27UcVY"}).text.split()
                        oprice=Priceo[0]
                        # Removing the ₹
                        #oprice = re.sub('[₹]', '', oprice)
                        # Description of the Product
#                         Description=cnt[i].find("li",{"class":"rgWa7D"}).text
                        # Appending in a list and making it 2D
                        lst.append([name, Price, oprice])
                    except:
                        #lst.append(x)
                        pass
                        #print("Not Exist")
        return lst

    x = []
    for i in lst_of_urls:
        abc = alibaba(i)
        for j in abc:
            x.append(j)

    df = pd.DataFrame(x, columns = ['Name', 'Number of Items'])
    return df