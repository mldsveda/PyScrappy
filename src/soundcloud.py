import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from selenium import webdriver
from bs4 import BeautifulSoup
import time, re

def soundcloud_tracks(track_name, n_pages):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line = False).install(), options = chrome_options)
    driver.create_options()
    driver.get('https://soundcloud.com/search/sounds?q='+track_name)

    for _ in range(n_pages):
        driver.find_element_by_tag_name('body').send_keys(Keys.END)
        time.sleep(3)

    html = driver.page_source
    soup = BeautifulSoup(html, 'html.parser')
    main = soup.find_all("div", {"class": "search"})[0]
    songs = main.find_all('div', {'class': 'sound__content'})
    lst = []
    for song in songs:
        dictionary = {}
        dictionary['Uploader'] = song.find('span', {"class": "soundTitle__usernameText"}).text
        dictionary['Uploader'] = re.sub('[^a-zA-Z]', '', dictionary['Uploader'])
        dictionary['Music Title'] = (song.find('a', {"class": "soundTitle__title sc-link-dark sc-link-secondary"}).text).replace('\n', '')
        dictionary['Time of Upload'] = (song.find('span', {"class": "sc-visuallyhidden"}).text).replace('\n', '')
        dictionary['Plays'] = song.find('span', {"class": "sc-ministats"}).text
        dictionary['Plays'] = re.sub('[^0-9,]', '', dictionary['Plays'])[:-3]
        lst.append(dictionary)

    driver.close()
    return pd.DataFrame(lst)