import pandas as pd
from time import sleep
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver

def func(post):
    try: title = post.find_element_by_class_name("base-search-card__title").text
    except: title = None
    try: company = post.find_element_by_class_name("base-search-card__subtitle").text
    except: company = None
    try: location = post.find_element_by_class_name("job-search-card__location").text
    except: location = None
    try: salary = post.find_element_by_class_name("job-search-card__salary-info").text
    except: salary = "Not disclosed"
    try: benefits = post.find_element_by_class_name("job-search-card__benefits").text
    except: benefits = None
    try: date = post.find_element_by_class_name("job-search-card__listdate").text
    except: date = None
    
    return [title, company, location, salary, benefits, date]

def scrappi(job_title, n_pages):
    while n_pages <= 0:
        print("'n_pages' must be greater then 0")
        n_pages = int(input("Enter 'n_pages' greater then 0: "))
        
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    
    driver.get("https://www.linkedin.com/jobs/search/?keywords="+job_title)
    sleep(4)
    
    for i in range(n_pages-1):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        sleep(4)
        try: driver.find_element_by_class_name("infinite-scroller__show-more-button").click()
        except: pass
        
    data = []
    for post in driver.find_elements_by_xpath(".//ul[@class='jobs-search__results-list']/li"):
        data.append(func(post))
        
    driver.close()
    return pd.DataFrame(data, columns=["Job Title", "Company Name", "Location", "Salary", "Benefits", "Date"])