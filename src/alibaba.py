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
        ali = "https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&CatId=&SearchText="+product_name
        url = requests.get(ali)
        soup = BeautifulSoup(url.text,"lxml")
        
        if n_pages == 0:
            print("Enter a valid number of Pages")
            return scrappi(product_name, n_pages=int(input("Enter a Page Number: ")))
            
        initial_url = str(ali)
        lst_of_urls = []
        for i in range(1, n_pages+1):
            x = initial_url + '&page=' + str(i)
            lst_of_urls.append(x)
        
        def Card_Style(soup):

            lst=[]
            cnt = soup.find_all("div", {"class": "m-gallery-product-item-v2"})
            for i in range(len(cnt)):
                
                try: name = cnt[i].find("p", {"class": "elements-title-normal__content"}).text
                except: name = "None"

                try: 
                    Price = cnt[i].find("p", {"class": "elements-offer-price-normal medium"})['title']
                    Price = '$' + str(Price).replace('$', '')
                except: Price = "None"

                try: n_item = cnt[i].find("span", {"class": "element-offer-minorder-normal__value"}).text
                except: n_item = "None"

                try: Description = cnt[i].find("div", {"class": "offer-tag-list"}).text
                except: Description = "None"
                    
                try: rating = cnt[i].find("span",{"class":"seb-supplier-review__score"}).text
                except: rating = "None"
                    
                lst.append([name, Price, n_item, Description, rating])

            return lst
        
        def alibaba(soup):
            if len(soup.find_all("div",class_="m-gallery-product-item-v2"))>=1: return Card_Style(soup)

        x = []
        for i in lst_of_urls:
            url = requests.get(i)
            soup = BeautifulSoup(url.text,"lxml")
            abc = alibaba(soup)
            if abc:
                for j in abc: x.append(j)

        return pd.DataFrame(x, columns =['Name', 'Price', 'Number of Items', 'Description', 'Ratings'])