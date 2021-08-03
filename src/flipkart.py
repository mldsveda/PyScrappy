from bs4 import BeautifulSoup
import pandas as pd
import requests

usr_agent = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
}

def scrappi(product_name, n_pages):

    flip = "https://www.flipkart.com/search?q="+product_name
    url = requests.get(flip)
    soup = BeautifulSoup(url.text,"lxml")
    
    if n_pages == 0:
        Page = soup.find("div",class_="_2MImiq").find("span", class_="").text
        c = Page.split()
        i=((c[3].replace(',','')))
        print("Enter valid number of Pages between 1 and {}".format(i))
        return scrappi(product_name, n_pages=int(input("Enter a Page Number: ")))
        
    initial_url = str(flip)
    lst_of_urls = []
    for i in range(1, n_pages+1):
        x = initial_url + '&page=' + str(i)
        lst_of_urls.append(x)
    
    def rectangle(soup):
        
        lst = []
        cnt = soup.find_all("div", {"class": "_2kHMtA"})
        for i in range(len(cnt)):
            
            try: name = cnt[i].find("div", {"class": "_4rR01T"}).text  
            except: name = "None"

            try: Price = cnt[i].find("div", {"class":"_30jeq3 _1_WHN1"}).text
            except: Price = "None"

            try:
                Priceo = cnt[i].find("div", {"class": "_3I9_wc _27UcVY"}).text.split()
                oprice = Priceo[0]
            except: oprice = "None"
                
            try: Description = cnt[i].find("li", {"class": "rgWa7D"}).text
            except: Description = "None"

            try: rating=cnt[i].find("div",{"class":"_3LWZlK"}).text
            except: rating="None"
                
            lst.append([name, Price, oprice, Description, rating])

        return lst
    
    def Card_Style(soup):

        lst=[]
        cnt = soup.find_all("div", {"class": "_4ddWXP"})
        for i in range(len(cnt)):
            
            try: name = cnt[i].find("a", {"class": "s1Q9rs"}).text
            except: name = "None"

            try: Price = cnt[i].find("div", {"class": "_30jeq3"}).text
            except: Price = "None"

            try:
                Priceo = cnt[i].find("div", {"class": "_3I9_wc"}).text.split()
                oprice = Priceo[0]

            except: oprice = "None"

            try: Description = cnt[i].find("div", {"class": "_3Djpdu"}).text
            except: Description = "None"
                
            try: rating=cnt[i].find("div",{"class":"_3LWZlK"}).text
            except: rating="None"
                
            lst.append([name, Price, oprice, Description, rating])

        return lst
    
    def OtherStyle(soup):

        lst=[]
        cnt = soup.find_all("div", {"class": "_1xHGtK _373qXS"})
        for i in range(len(cnt)):
            
            try: name = cnt[i].find("div", {"class": "_2WkVRV"}).text
            except: name = "None"

            try: Price = cnt[i].find("div", {"class": "_30jeq3"}).text
            except: Price = "None"

            try:
                Priceo = cnt[i].find("div", {"class": "_3I9_wc"}).text.split()
                oprice = Priceo[0]
            except: oprice = "None"

            try: Description = cnt[i].find("a", {"class": "IRpwTa"}).text
            except: Description = "None"
                
            try: rating=cnt[i].find("div",{"class":"_3LWZlK"}).text
            except: rating="None"

            lst.append([name, Price, oprice, Description, rating])
            
        return lst
    
    def flipkart(soup):
        if len(soup.find_all("div",class_="_4ddWXP"))>=1:
            return Card_Style(soup)
        elif len(soup.find_all("div",class_="_2kHMtA"))>=1:
            return rectangle(soup)
        elif len(soup.find_all("div", {"class": "_1xHGtK _373qXS"}))>=1:
            return OtherStyle(soup)

    x = []
    for i in lst_of_urls:
        url = requests.get(i)
        soup = BeautifulSoup(url.text,"lxml")
        abc = flipkart(soup)
        if abc: 
            for j in abc: x.append(j)

    return pd.DataFrame(x, columns =['Name', 'Price', 'Original Price', 'Description', 'Rating'])