import os
import re
import warnings
import pandas as pd
from tqdm import tqdm
from app_info import *

from colorama import Fore
from selenium import webdriver
from colorama import init as colorama_init
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
warnings.filterwarnings('ignore')
colorama_init()

import time


WAIT_TIME = 4 # Default wait time(Seconds) before each bot action.
NUM_OF_CALL = 1000 # From validated input in validation.py
USER = os.getlogin()

# url to google playstore games page
URL = f'https://play.google.com/store/apps/details?id={id}&hl={hl}'

# Windowless mode feature (Chrome) and chrome message handling.
options = webdriver.EdgeOptions()
options.headless = True # Runs driver without opening a chrome browser.
options.add_experimental_option("excludeSwitches", ["enable-logging"])

# Set the path to your webdriver
service = Service('msedgedriver.exe')

# Initiate the browser
driver = webdriver.Edge(service=service, options=options)
driver.get(URL)

reviews_list = []
ratings_list = []
dates_list = []
app_reviews = {}

def scroll_reviews():
    time.sleep(WAIT_TIME)
    buttons = driver.find_elements(by= By.TAG_NAME, value="button")
    buttons[-2].click()
    review_scroll = driver.find_element(by= By.CLASS_NAME, value="VfPpkd-Bz112c-LgbsSe.yHy1rc.eT1oJ.mN1ivc.a8Z62d")
    time.sleep(WAIT_TIME)
    for _ in tqdm(range(NUM_OF_CALL)):
        review_scroll.send_keys(Keys.TAB, Keys.END*2)
        time.sleep(2) #### CHECK HERE INCASE.
        
def collect_data():
    time.sleep(WAIT_TIME)
    reviews = driver.find_elements(by= By.CLASS_NAME, value="h3YV2d") # Locates reviews
    dates = driver.find_elements(by= By.CLASS_NAME, value="bp9Aid")
    ratings = driver.find_elements(by= By.CLASS_NAME, value="iXRFPc")
    time.sleep(WAIT_TIME)
    for (review, date, rating) in zip(reviews, dates, ratings):
        review = review.text
        date = date.text
        rating = rating.get_attribute("aria-label")
        rating = re.findall("\d", rating)
        rating = rating[0]
        
        reviews_list.append(review)
        ratings_list.append(rating)
        dates_list.append(date)
    
    app_reviews['review'] = reviews_list
    app_reviews['rating'] = ratings_list
    app_reviews['date'] = dates_list
    driver.quit()

def export_df():
    app_reviews_df = pd.DataFrame(app_reviews)
    app_reviews_df = app_reviews_df.iloc[1: ,]
    app_reviews_df['date'] = pd.to_datetime(app_reviews_df['date'], format='%d tháng %m, %Y').dt.strftime('%Y-%m-%d')
    time.sleep(2)
    app_reviews_df.to_csv('app_reviews_df.csv', index=False, encoding='utf-8')
    data_rows = "{:,}".format(app_reviews_df.shape[0])
    print("\n"f"{Fore.LIGHTGREEN_EX}{data_rows} rows of data have been saved to downloadas as app_reviews_df.")
    
if __name__ == "__main__":
    scroll_reviews()
    collect_data()
    export_df()
    