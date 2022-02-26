import pandas as pd
from time import sleep
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver

def func(last, tracks):
    data = []
    for track in tracks:
        try:
            temp = (track.find_element_by_xpath("./div[@data-testid='tracklist-row']").text).split("\n")
            if last < int(temp[0]):
                if 'E' in temp: temp.remove('E')
                data.append(temp)
        except: pass
    return data

def scrappi(track_type, n_pages):
    while n_pages<= 0:
        n_pages = int(input("Enter a valid 'n_pages', greater than 0: "))
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()

    driver.get(f"https://open.spotify.com/search/{track_type}/tracks")
    sleep(4)
    
    data = []
    last = 0
    for i in range(n_pages):
        main = driver.find_element_by_xpath(".//div[@data-testid='track-list']/div[2]/div[2]")
        data.extend(func(last, main.find_elements_by_xpath("./div")))
        last = int(data[-1][0])
        try:
            scroll = main.find_element_by_xpath("./div[last()]").location_once_scrolled_into_view
            sleep(4)
        except:
            try:
                scroll = main.find_element_by_xpath("./div[last()]").location_once_scrolled_into_view
                sleep(8)
            except:
                pass

    return pd.DataFrame(data, columns=["Id", "Title", "Singers", "Album", "Duration"])