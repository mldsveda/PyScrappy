import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from time import sleep

def scrappi(hashtag, n_pages):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    driver.get("https://twitter.com/search?q=%23"+hashtag.replace('#', ''))
    sleep(4)

    def twitter(card):
        data_lst = []
        try: name = card.find_element_by_xpath('.//span').text
        except: name = None
        try: twitter_handle = card.find_element_by_xpath('.//span[contains(text(), "@")]').text
        except: twitter_handle = None  
        try: post_time = card.find_element_by_xpath('.//time').get_attribute('datetime')
        except: post_time = None     
        try: tweet = (card.find_element_by_xpath('.//div[2]/div[2]/div[1]').text)+(card.find_element_by_xpath('.//div[2]/div[2]/div[2]').text)
        except: tweet = None     
        try: reply_count = card.find_element_by_xpath('.//div[@data-testid="reply"]').text
        except: reply_count = None     
        try: retweet_count = card.find_element_by_xpath('.//div[@data-testid="retweet"]').text
        except: retweet_count = None     
        try: like_count = card.find_element_by_xpath('.//div[@data-testid="like"]').text
        except: like_count = None 
        
        data_lst.extend([name, twitter_handle, post_time, tweet, reply_count, retweet_count, like_count])
        return data_lst
    
    new_ls = []
    temp_set = set()
    for _ in range(n_pages):
        for card in driver.find_elements_by_xpath('//article[@data-testid="tweet"]'): 
            ls = twitter(card)
            check = ''.join(ls) 
            if check not in temp_set:
                new_ls.append(ls)
                temp_set.add(check)
        driver.execute_script('window.scrollBy(0, window.innerHeight*3);')
        sleep(4)
    
    driver.close()
    return pd.DataFrame(new_ls, columns = ["Name", "Twitter handle", "Post Time", "Tweet", "Reply Count", "Retweet Count", "Like Count"])
