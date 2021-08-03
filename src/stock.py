from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from time import sleep
import pandas as pd

########## Stock Analysis ##########
def stock_analysis(stock_code, analysis_type):
    analysis = {
        "earning estimate" : 0, 
        "revenue estimate" : 1,
        "earning history" : 2,
        "EPS trend" : 3,
        "EPS revision" : 4,
        "growth estimate" : 5
    }
    if analysis_type not in analysis.keys(): raise KeyError("Invalid value for 'analysis_type'")
    
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    driver.get("https://in.finance.yahoo.com/quote/"+stock_code+"/analysis?p="+stock_code)
    
    try: tables = driver.find_elements_by_xpath('.//section[@data-test="qsp-analyst"]/table')
    except: raise KeyError("Invalid value for 'stock_code'")

    
    try: df = pd.DataFrame([[data.text for data in row.find_elements_by_xpath('td')] for row in tables[analysis[analysis_type]].find_elements_by_xpath('.//tbody/tr')], columns = [head.text for head in tables[analysis[analysis_type]].find_elements_by_tag_name('th')])
    except: 
        print("Analysis report not Available")
        return None
    return df

########## Stock Profile ##########
def stock_profile(stock_code):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    try:
        url = "https://in.finance.yahoo.com/quote/"+stock_code+"/profile?p="+stock_code
        driver.get(url)
        sleep(3)

        card = driver.find_element_by_xpath('.//div[@id="Main"]')
        executives = pd.DataFrame([[data.text for data in row.find_elements_by_xpath('td')] for row in card.find_elements_by_xpath('.//tbody/tr')], columns = [i.text for i in card.find_elements_by_tag_name('th')])
        description = card.find_element_by_xpath('.//section/section[2]/p').text
        pro_card = card.find_element_by_xpath('.//div[@data-test="qsp-profile"]')
        profile = {}
        profile["Company Name"] = pro_card.find_element_by_xpath('.//h3').text
        profile["Headquater"] = ', '.join(pro_card.find_element_by_xpath('.//p').text.split('\n')[:3])
        profile["Sector"], profile["Industry"], profile["Employees"] = [i.split(': ')[1] for i in pro_card.find_element_by_xpath('.//p[2]').text.split('\n')]
    except: 
        print("Profile details not Available or the 'stock_code' is Invalid")
        return None, None, None
    return [profile, description, executives]


########## Historical Data ##########
def stock_history(stock_code, stock_range, stock_frequency):
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('--headless')
    chrome_options.headless = True
    driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install(), options = chrome_options)
    driver.create_options()
    
    try:
        url = "https://in.finance.yahoo.com/quote/"+stock_code+"/history?p="+stock_code
        driver.get(url)
        sleep(3)

        card = driver.find_element_by_xpath('//section[@data-test="qsp-historical"]/div[1]')
        time_period = card.find_element_by_xpath('.//div[1]/div[@data-test="dropdown"]')
        time_period.click()
        sleep(3)

        if stock_range == "1d": time_period.find_element_by_xpath('.//button[@data-value="1_D"]').click()
        elif stock_range == "5d":time_period.find_element_by_xpath('.//button[@data-value="5_D"]').click()
        elif stock_range == "3m":time_period.find_element_by_xpath('.//button[@data-value="3_M"]').click()
        elif stock_range == "6m":time_period.find_element_by_xpath('.//button[@data-value="6_M"]').click()
        elif stock_range == "1y":time_period.find_element_by_xpath('.//button[@data-value="1_Y"]').click()
        elif stock_range == "5y":time_period.find_element_by_xpath('.//button[@data-value="5_Y"]').click()
        elif stock_range == "max":time_period.find_element_by_xpath('.//button[@data-value="MAX"]').click()
        else: raise KeyError("Invalid value passed for 'stock_range'")
        sleep(3)

        frequency = card.find_element_by_xpath('.//span[@data-test="historicalFrequency-selected"]')
        frequency.click()
        sleep(3)

        if stock_frequency == "Daily": card.find_element_by_xpath('.//div[@data-value="1d"]').click()
        elif stock_frequency == "Weekly": card.find_element_by_xpath('.//div[@data-value="1wk"]').click()
        elif stock_frequency == "Monthly": card.find_element_by_xpath('.//div[@data-value="1mo"]').click()
        else: raise KeyError("Invalid value passed for 'stock_frequency'")
        sleep(3)

        card.find_element_by_xpath('.//div[1]/button[@data-reactid="25"]').click()
        sleep(3)
    except: 
        print("Historical Data Not Available or the 'stock_code' is Invalid")
        return

    try:
        link = driver.find_elements_by_link_text('Download')[0].get_attribute('href')
        driver = webdriver.Chrome(ChromeDriverManager(print_first_line=False).install())
        driver.get(link)
        sleep(5)
        print("CSV Downloaded Successfully")
        driver.close()
    except:
        print("CSV file not Available or the 'stock_code' is Invalid")
        return