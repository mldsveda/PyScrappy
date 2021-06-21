#!/usr/bin/env python
# coding: utf-8

# In[27]:


#!/usr/bin/env python
# coding: utf-8

# Importing Modules
# from bs4 import BeautifulSoup
# import pandas as pd
# from selenium import webdriver
# import time

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


# Checking the Container Style
# soupConv(url)


usr_agent = {
'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
'Accept-Encoding': 'none',
'Accept-Language': 'en-US,en;q=0.8',
'Connection': 'keep-alive',
}

#folder_name = 'images'

class Scrappy:

    def flipkart_scrapper(self, n_pages):

        # Url input
        url=str(input("Enter the desired Fipkart URL: \n"))
        urls=requests.get(url)

        initial_url =str(url)
        lst_of_urls = []
        for i in range(0, n_pages):
            x = initial_url + '&page=' + str(i)
            lst_of_urls.append(x)
        #print(lst_of_urls)

        def flipkart(soup):
            #x = "Same"
            lst = []
            urls = requests.get(url)
            soup = BeautifulSoup(urls.text,"lxml")
            Main = soup.find_all("div",class_="_13oc-S")
            try:
                # For Card Style
                if len(Main[0].find("div",class_="_4ddWXP"))>=1:
                    #print("Card Style Container\n")
                    cnt=soup.find_all("div",{"class":"_4ddWXP"})
                    #print(len(cnt))
                    #ad=soup.find("div",{"class":"_2tfzpE"})
                    for i in range(len(cnt)):
                        try:
                            name = cnt[i].find("a",{"class":"s1Q9rs"}).text
                            # Capitalizing the First letter
                            name = name.capitalize()
                            # Discounted Price
                            Price = cnt[i].find("div",{"class":"_30jeq3"}).text
                            # Removing the ₹
                            #Price = re.sub('[₹]', '', Price)
                            # Original Price
                            Priceo = cnt[i].find("div",{"class":"_3I9_wc"}).text.split()
                            oprice = Priceo[0]
                            # Removing the ₹
                            #oprice = re.sub('[₹]', '', oprice)
                            # Description of the Product
                            Description = cnt[i].find("div",{"class":"_3Djpdu"}).text
                            # Appending in a list
                            lst.append([name, Price, oprice, Description])
                        except:
                            lst.append([name, Price, oprice, Description])
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
                            Description=cnt[i].find("li",{"class":"rgWa7D"}).text
                            # Appending in a list and making it 2D
                            lst.append([name, Price, oprice, Description])
                        except:
                            #lst.append(x)
                            pass
                            #print("Not Exist")
            return lst

        x = []
        for i in lst_of_urls:
            abc = flipkart(i)
            for j in abc:
                x.append(j)

        df = pd.DataFrame(x, columns =['Name', 'Price', 'Original Price', 'Description'])
        return df

    def snapdeal_scrapper(self, n_pages):

        # Url input
        url=str(input("Enter the desired Snapdeal URL: \n"))
        urls=requests.get(url)

        initial_url =str(url)
        lst_of_urls = []
        for i in range(0, n_pages):
            x = initial_url + '&page=' + str(i)
            lst_of_urls.append(x)
        #print(lst_of_urls)

        def snapdeal(soup):
            #x = "Same"
            lst = []
            urls = requests.get(url)
            soup = BeautifulSoup(urls.text,"lxml")
            Main = soup.find_all("div", class_ = "product-tuple-description")
            try:
                # For Card Style
                    #print("Card Style Container\n")
                    cnt = soup.find_all("div",{"class":"product-tuple-description"})
                    #print(len(cnt))
                    #ad=soup.find("div",{"class":"_2tfzpE"})
                    for i in range(len(Main)):
                        try:
                            name = Main[i].find("p",{"class":"product-title"}).text
                            # Capitalizing the First letter
                            name = name.capitalize()
                            # Discounted Price
                            Price = Main[i].find("span",{"class":"lfloat product-price"}).text
                            # Removing the ₹
                            #Price = re.sub('[₹]', '', Price)
                            # Original Price
                            Priceo = Main[i].find("span",{"class":"lfloat product-desc-price strike"}).text
                            oprice = Priceo
                            # Removing the ₹
                            #oprice = re.sub('[₹]', '', oprice)
                            # Description of the Product
                            #Description = cnt[i].find("div",{"class":"_3Djpdu"}).text
                            # Appending in a list
                            lst.append([name, oprice, Price])
                        except:
                            lst.append([name, oprice, Price])
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
                            Priceo=cnt[i].find("div",{"class":"_3I9_wc _27UcVY"}).text
                            oprice=Priceo
                            # Removing the ₹
                            #oprice = re.sub('[₹]', '', oprice)
                            # Description of the Product
                            #Description=cnt[i].find("li",{"class":"rgWa7D"}).text
                            # Appending in a list and making it 2D
                            lst.append([name, Price, oprice])
                        except:
                            #lst.append(x)
                            pass
                            #print("Not Exist")
            return lst

        x = []
        for i in lst_of_urls:
            abc = snapdeal(i)
            for j in abc:
                x.append(j)
                
        df = pd.DataFrame(x, columns = ['Name', 'Original Price', 'Discounted Price'])
        return df

    def alibaba_scrapper(self, n_pages):

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
    
    def image_scrapper(self, data ,n_images=0, img_format='jpg', folder_name='images'):
        
        #n_images = int(input('Enter the Number of Images: '))

        URL = ['https://www.bing.com/images/search?q=', 'https://www.google.com/search?site=&tbm=isch&source=hp&biw=1873&bih=990&q=',
              'https://images.search.yahoo.com/search/images?p=']

        try:
            #folder_name = input("Enter Folder Name:- ")
            # folder creation
            os.mkdir(folder_name)

        # if folder exists with that name, ask another name
        except:
            print("Folder Exist with that name!")
            new = input("Enter a new Folder name: \n")
            os.mkdir(new)

        print('Starting to Download...')

        # get url query string
        for i in URL:
            searchurl = i + str(data)
            #print(searchurl)

            # request url, without usr_agent the permission gets denied
            response = requests.get(searchurl, headers = usr_agent)
            html = response.text

            # find all divs where class='rg_meta'
            soup = BeautifulSoup(html, 'html.parser')
            results = soup.findAll('img', limit = n_images)

            #print('Starting to Download...')

            if len(results) != 0:
                for i, image in enumerate(results):

                    # first we will search for "data-srcset" in img tag
                    try:
                        # In image tag ,searching for "data-srcset"
                        image_link = image["data-srcset"]

                    # then we will search for "data-src" in img
                    # tag and so on..
                    except:
                        try:
                            # In image tag ,searching for "data-src"
                            image_link = image["data-src"]
                        except:
                            try:
                                # In image tag ,searching for "data-fallback-src"
                                image_link = image["data-fallback-src"]
                            except:
                                try:
                                    # In image tag ,searching for "src"
                                    image_link = image["src"]

                                # if no Source URL found
                                except:
                                    pass
                        # After getting Image Source URL
                        # We will try to get the content of image
                        try:
                            r = requests.get(image_link).content
                            try:
                                # possibility of decode
                                r = str(r, 'utf-8')

                            except UnicodeDecodeError:
                                # After checking above condition, Image Download start
                                with open(f"{folder_name}/images{i+1}.{img_format}", "wb+") as f:
                                    f.write(r)
                        except:
                            pass

            #print(f'Downloaded {image_link} images')

        return 'Successfully Downloaded ' + str(n_images) + ' images'
    
    class wikipedia_scrapper:

    #     url = "https://en.wikipedia.org/wiki/"+text
    #     page = urllib.request.urlopen(url)
    #     soup = BeautifulSoup(page, "lxml")

        def para(self):
            
            from urllib.request import urlopen
            # Specify url of the web page
            source = urlopen('https://en.wikipedia.org/wiki/'+str(self)).read()
            # Make a soup 
            soup = BeautifulSoup(source,'lxml')

            # Extract the plain text content from paragraphs
            paras = []
            for paragraph in soup.find_all('p'):
                paras.append(str(paragraph.text))

            return paras

        def header(self):

            from urllib.request import urlopen
            # Specify url of the web page
            source = urlopen('https://en.wikipedia.org/wiki/'+str(self)).read()
            soup = BeautifulSoup(source, "lxml")

            # Extract text from paragraph headers
            heads = []
            for head in soup.find_all('span', attrs={'mw-headline'}):
                heads.append(str(head.text))

            return heads

        def text(self):

            from urllib.request import urlopen
            # Specify url of the web page
            source = urlopen('https://en.wikipedia.org/wiki/'+str(self)).read()
            soup = BeautifulSoup(source, "lxml")
            
            paras = []
            for paragraph in soup.find_all('p'):
                paras.append(str(paragraph.text))
                
            heads = []
            for head in soup.find_all('span', attrs={'mw-headline'}):
                heads.append(str(head.text))

            # Interleave paragraphs & headers
            text = [val for pair in zip(paras, heads) for val in pair]
            text = ' '.join(text)

            # Drop footnote superscripts in brackets
            text = re.sub(r"\[.*?\]+", '', text)

            # Replace '\n' (a new line) with '' and end the string at $1000.
            text = text.replace('\n', '')[:-11]
            return text
        
    def youtube_scrapper(self, url, n_pages=5):

        driver = webdriver.Chrome(ChromeDriverManager().install())

        driver.get(url)

        for _ in range(n_pages):
            driver.find_element_by_tag_name('body').send_keys(Keys.END)
            time.sleep(3)

        html = driver.page_source
        soup = BeautifulSoup(html, 'html.parser')
        videos = soup.find_all("div", {"id": "dismissible"})
        lst = []

        for video in videos:
            dictionary = {}
            dictionary['Title'] = video.find("a", {"id": "video-title"}).text
            dictionary['Video_url'] = "https://www.youtube.com/" + video.find("a", {"id": "video-title"})['href']
            meta = video.find("div", {"id": "metadata-line"}).find_all('span')
            dictionary['Views'] = meta[0].text
            dictionary['Days'] = meta[1].text

            lst.append(dictionary)

        df = pd.DataFrame(lst)
        return df
