from bs4 import BeautifulSoup
import pandas as pd
import requests

def scrappi(city, n_pages):
    lst_of_urls = []
    for i in range(1, n_pages+1): lst_of_urls.append("https://www.swiggy.com/" + city + '?page=' + str(i))

    def swiggy(soup):
        main = soup.find_all('div', {'class': 'nDVxx'})[0]
        lst = []
        for details in main.find_all('div', {'class': '_3XX_A'}):
            dictionary = {}
            dictionary['Name'] = details.find('div', {"class": "nA6kb"}).text
            dictionary['Cuisine'] = details.find('div', {"class": "_1gURR"}).text
            dictionary['Price'] = details.find('div', {"class": "nVWSi"}).text
            dictionary['Rating'] = details.find('div', {"class": "_9uwBC"}).text
            lst.append(dictionary)
        return lst
    
    x = []
    for i in lst_of_urls:
        try: url = requests.get(i)
        except: raise ValueError("Invalid value passed for 'city'")
        soup = BeautifulSoup(url.text, "lxml")
        x.extend(swiggy(soup))

    return pd.DataFrame(x)