import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
import time

def scrappi(city, n_pages):
    if n_pages == 0: raise ValueError("'n_pages' must be greater than 0")
    city = city.replace(' ', '-')
    driver = webdriver.Chrome(ChromeDriverManager().install())
    driver.get("https://www.zomato.com/"+city+"/restaurants")

    for _ in range(n_pages):
        driver.execute_script('window.scrollBy(0, window.innerHeight);')
        time.sleep(4)

    def zomato(card):
        ls = []
        try: name = card.find_element_by_xpath('.//div/a[2]/div/p').text
        except: name = None
        try: cusine = card.find_element_by_xpath('.//div/a[2]/p').text
        except: cusine = None
        try: rating = card.find_element_by_xpath('.//div/a[2]/div[2]/section').get_attribute('value')
        except: rating = None
        try: price, delivery_time = card.find_element_by_xpath('.//div/a[2]/p[2]').text.split('\n')
        except: price, delivery_time = None, None
        try: reviews_count = card.find_element_by_xpath('.//div/a[2]/div[2]/section/div[2]').text[1:-1]
        except: reviews_count = None
        ls.extend([name, cusine, price, rating, delivery_time, reviews_count])
        return ls

    new_ls = []
    try: cards = driver.find_elements_by_class_name('jumbo-tracker')
    except: raise KeyError("Invalid value for 'city'")
    for card in cards:
        new_ls.append(zomato(card))

    driver.close()
    return pd.DataFrame(new_ls, columns = ["Name", "Cusine", "Price", "Rating", "Delivery Time", "Review counts"])