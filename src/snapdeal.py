from bs4 import BeautifulSoup
import pandas as pd
import requests

usr_agent = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,/;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
}

def scrappi(product_name, n_pages):

        snap = "https://www.snapdeal.com/search?keyword="+product_name
        url = requests.get(snap)
        soup = BeautifulSoup(url.text,"lxml")
        
        if n_pages == 0:
            print("Enter a valid number of Pages")
            return scrappi(product_name, n_pages=int(input("Enter a Page Number: ")))
            
        initial_url = str(snap)
        lst_of_urls = []
        for i in range(1, n_pages+1):
            x = initial_url + '&page=' + str(i)
            lst_of_urls.append(x)
        
        def Card_Style(soup):

            lst=[]
            cnt = soup.find_all("div", {"class": "product-tuple-description"})
            for i in range(len(cnt)):
                
                try: name = cnt[i].find("p", {"class": "product-title"}).text
                except: name = "None"

                try: Price = cnt[i].find("span", {"class": "lfloat product-price"}).text
                except: Price = "None"

                try: original = cnt[i].find("span", {"class": "lfloat product-desc-price strike"}).text
                except: original = "None"
                    
                try: rating = cnt[i].find("p",{"class":"product-rating-count"}).text
                except: rating = "None"
                    
                lst.append([name, Price, original, rating])

            return lst
        
        def snapdeal(soup):
            if len(soup.find_all("div",class_="product-tuple-description"))>=1:
                return Card_Style(soup)

        x = []
        for i in lst_of_urls:
            url = requests.get(i)
            soup = BeautifulSoup(url.text,"lxml")
            abc = snapdeal(soup)
            for j in abc: x.append(j)

        return pd.DataFrame(x, columns =['Name', 'Price', 'Original Price', 'Number of Ratings'])