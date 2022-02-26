import pandas as pd
from time import sleep
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver

def func(cards):
    data = []
    for card in cards:
        try: info = card.find_element_by_class_name("s-card-container").find_element_by_xpath("./div/div[3]")
        except: 
            try: info = card.find_element_by_class_name("s-card-container").find_element_by_xpath("./div/div[2]")
            except:
                try: info = card.find_element_by_class_name("s-card-container").find_element_by_xpath("./div/div/div[3]")
                except: info = card.find_element_by_class_name("s-card-container").find_element_by_xpath("./div/div/div[2]")
        try: description = info.find_element_by_xpath("./div[1]/h2").text
        except: description = None
        try: rating = info.find_element_by_xpath("./div[2]/div/span").get_attribute("aria-label")
        except: rating = None
        try: votes = info.find_elements_by_xpath("./div[2]/div/span")[1].text
        except: votes = None
        try: offer_price = info.find_element_by_class_name("a-price").text.replace("\n", ".")
        except: offer_price = None
        try: actual_price = info.find_element_by_class_name("a-price").find_element_by_xpath("..//span[@data-a-strike='true']").text
        except: actual_price = offer_price
        
        data.append([description, rating, votes, offer_price, actual_price])
        
    return data

def scrappi(product_name, n_pages):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    
    url = "https://www.amazon.com/s?k="+product_name
    driver.get(url)
    sleep(4)

    cards = driver.find_elements_by_xpath('//div[@data-component-type="s-search-result"]')
    while len(cards) == 0: 
        driver.get(url)
        sleep(4)
    
    max_pages = int(driver.find_element_by_xpath(".//span[@class='s-pagination-strip']/span[last()]").text)
    while n_pages > max_pages or n_pages == 0:
        print(f"Please Enter a Valid Number of Pages Between 1 to {max_pages}:")
        n_pages = int(input())
    
    data = []
    
    while n_pages > 0:
        n_pages -= 1
        data.extend(func(driver.find_elements_by_xpath('//div[@data-component-type="s-search-result"]')))
        driver.find_element_by_class_name("s-pagination-next").click()
        sleep(4)
        
    driver.close()
    return pd.DataFrame(data, columns=["Description", "Rating", "Votes", "Offer Price", "Actual Price"])