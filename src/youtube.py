try:
    from webdriver_manager.chrome import ChromeDriverManager
except: raise ImportError("'webdriver-manager' package not installed")
try:
    from selenium.webdriver.common.keys import Keys
    from selenium import webdriver
except: raise ImportError("'selenium' package not installed")
from bs4 import BeautifulSoup
import pandas as pd
import time

usr_agent = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
}

def scrappi(url, n_pages):

    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager().install(), options = chrome_options)
    driver.create_options()
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

    return pd.DataFrame(lst)