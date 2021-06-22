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

def scrappi(data, n_images, img_format, folder_name):
        

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