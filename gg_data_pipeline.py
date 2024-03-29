import pandas as pd
from datetime import datetime
import time
from tqdm import tqdm
from info import *
import sqldf

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup

import google.generativeai as genai
import psycopg2

############################ CRAWL DATA ############################
# Connect to the web to crawl
def connect_to_web(url):
    ## Set up Edge webdriver options.
    options = webdriver.EdgeOptions()
    options.headless = True # Runs driver without opening a chrome browser.
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    ## Set the path to your webdriver
    service = Service('msedgedriver.exe')

    ## Initiate the browser
    driver = webdriver.Edge(service=service, options=options)
    driver.get(url)
    print(f'Connected to {url}')
    return driver

# Crawl data
## Function to scroll the target div until the end
def scroll_target_div(driver):
    target_div = driver.find_element(By.CLASS_NAME, "fysCi")
    
    # Get the initial scroll height
    last_height = target_div.get_attribute('scrollHeight')
    while True:
        # Scroll to the bottom of the div
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", target_div)

        # Wait for the page to load
        time.sleep(5)

        # Get the current scroll height
        current_height = target_div.get_attribute('scrollHeight')

        # If the scroll height hasn't changed, exit the loop
        if current_height == last_height:
            break

        # Update the last height
        last_height = current_height    

## Function to get all reviews in soup type
def crawl_reviews(driver):
    ### Click to review button
    driver.find_element(By.CSS_SELECTOR, '#yDmH0d > c-wiz.SSPGKf.Czez9d > div > div > div:nth-child(1) > div > div.wkMJlb.YWi3ub > div > div.qZmL0 > div:nth-child(1) > c-wiz:nth-child(5) > section > header > div > div:nth-child(2) > button > i').click()
    time.sleep(2)

    # ### Click to sort button
    driver.find_element(By.CSS_SELECTOR, '#sortBy_1 > div.kW9Bj > i').click()
    time.sleep(2)

    ### Click to newest button
    driver.find_element(By.CSS_SELECTOR, '#yDmH0d > div.VfPpkd-Sx9Kwc.cC1eCc.UDxLd.PzCPDd.HQdjr.VfPpkd-Sx9Kwc-OWXEXe-FNFY6c > div.VfPpkd-wzTsW > div > div > div > div > div.fysCi > div.JPdR6b.e5Emjc.ah7Sve.qjTEB > div > div > span:nth-child(2) > div.uyYuVb.oJeWuf > div.jO7h3c').click()
    time.sleep(2)

    ### Scroll down the specific div element
    print('Scrolling the reviews page')
    scroll_target_div(driver)
    print('Scrolling completed !!!')

    ### Get the page source after clicking the button
    page_source = driver.page_source
    
    ### Parse the page source with Beautiful Soup
    soup = BeautifulSoup(page_source, 'html.parser')
    print('Got source of page !!!')

    ### Close the browser
    driver.quit()
    return soup

## Function to collect data from soup, transform into a pandas df
def get_df(soup):
    ### get list review date
    review_span = soup.find_all("span", class_= 'bp9Aid')
    review_dates = [datetime.strptime(x.text, '%d tháng %m, %Y').strftime('%Y-%m-%d') for x in review_span]

    ### get list review stars
    review_img = soup.find_all("div", class_= 'iXRFPc')
    review_stars = [int(x.get('aria-label').split()[3]) for x in review_img]

    ### get list review content
    review_text = soup.find_all("div", class_= 'h3YV2d')
    review_contents = [x.text.strip() for x in review_text]

    ### Convert to a pandas dataframe
    reviews_dict = []
    print('Creating a dataframe')
    for review_date, review_star, review_content in zip(review_dates, review_stars, review_contents):
        review_dict = {
            "review_date": review_date,
            "review_star": review_star,
            "review_content": review_content,
        }
        reviews_dict.append(review_dict)
    print('Creating completed !')
    gg_reviews = pd.DataFrame(reviews_dict[3:]) # remove 3 first preview reviews
    return gg_reviews

############################ RUN SEGMENTATION ############################
def create_model(key):
    genai.configure(api_key=key)
    
    generation_config = {
        "candidate_count": 1,
        "max_output_tokens": 256,
        "temperature": 1.0,
        "top_p": 0.7,
    }

    safety_settings=[
    {
        "category": "HARM_CATEGORY_DANGEROUS",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_NONE",
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE",
    },
    ]

    model = genai.GenerativeModel(
        model_name="gemini-pro",
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    return model

def classify_emotion(model, text):
    response = model.generate_content(f'''Bạn là một nhà phân loại cảm xúc xuất sắc, \
    hãy phân loại content sau thuộc loại gì?. \
    Tôi có đề xuất là:
    - Những comment nào có chứa những từ "hay", "good", "ok" \
    hoặc mang hàm ý tương tự thì cho nó là pos.\
    - Những comment nào có chứa những từ "dở", "tệ", "chán" \
    hoặc mang hàm ý tương tự, chửi rủa thì cho nó là neg. \
    - Còn lại những câu không rõ ràng, spam, thì cho là neu.\
    Chỉ cần trả lời là pos hoặc neg hoặc neu: {text}''')
    time.sleep(3)
    return response.text

def summary_review(model, text):
    response = model.generate_content(f'''Bạn là một nhà tóm tắt ý chính của comment xuất sắc\
    , Hãy phân loại thành một trong các loại sau: 
    - Bào Tiền: Là những comment thường hay chứa những từ "chê việc nạp", "hút máu", "bào" hoặc mang hàm ý tương tự,\
    - Văng ra khỏi game: Là những comment thường hay chứa từ "thoát ra khỏi game", "văng game", "dis" hoặc mang hàm ý tương tự\
    - Chê gameplay: Là những comment thường hay chứa những từ "chê", "game chán", "game dở" hoặc mang hàm ý tương tự\
    - Khen gameplay: Là những comment thường hay chứa những từ "khen", "game hay", "đồ họa đẹp", "cốt truyện cuốn" hoặc mang hàm ý tương tự\
    - Không tải/vào được game: Là những comment thường hay chứa những từ "không vào được", "không tải được", "không đăng nhập được", "tải lâu", "không vào được", "không kết nối được", "tải lại báo lỗi", "tải rồi mà bị đơ"  hoặc mang hàm ý tương tự\
    - Lag, giật, chậm: Là những comment thường hay chứa những từ "lag", "giật", "chậm", "đường truyền không ổn định" hoặc mang hàm ý tương tự\
    - Bug game: Là những comment thường hay chứa những từ "game lỗi", "bug" hoặc mang hàm ý tương tự\
    - Lỗi Nạp: Là những comment thường hay chứa những từ "nạp không được", "nạp mà không nhận", "nạp lỗi", hoặc mang hàm ý tương tự\
    - Nóng, cấu hình cao: Là những comment thường hay chứa những từ "cấu hình cao", "máy nóng", "máy yếu", hoặc mang hàm ý tương tự\
    - Góp ý cho game: Là những comment thường mang hàm ý mong thêm cái gì mới, sửa cái gì đó
    - Khác: Là những comment không thuộc các loại kể trên\
    Chỉ được dùng một trong các phân loại trên, không cần ghi thêm hoặc ghi khác: {text}''')
    time.sleep(5)
    return response.text

def segment_df(model, gg_reviews):
    print('Running the AI segmentation model!')

    print('Classifying the emotion')
    gg_reviews['emotion'] = gg_reviews['review_content'].apply(lambda x: classify_emotion(model, x))
    print('Completed classifying the emotion')

    print('Summarizing reviews')
    gg_reviews['summary_review'] = gg_reviews['review_content'].apply(lambda x: summary_review(model, x))
    print('Completed summarizing reviews')

    print('Completed segmentation!')
    return gg_reviews

############################ AGGREGATE RESULT ############################
def aggregate_df(gg_reviews):
    print('Aggregating the table')
    gg_reviews_agg_query = '''
        SELECT review_date, review_star, emotion, summary_review, COUNT(review_star) AS num_review_star, COUNT(emotion) AS num_emotion, COUNT(summary_review) AS num_summary_review
        FROM gg_reviews
        GROUP BY review_date, review_star, emotion, summary_review
        ORDER BY review_date DESC, review_star DESC
    '''
    gg_reviews_agg = sqldf.run(gg_reviews_agg_query)
    print('Completed Aggregating!')
    return gg_reviews_agg

############################ INGEST TO DATABASE ############################
def ingest_to_db(gg_reviews_agg, game):

    # Kết nối tới PostgreSQL
    conn = psycopg2.connect(
        host=HOST,
        database=DB_NAME,
        user=USER,
        password=PASSWORDS
    )

    # Tạo đối tượng cursor để thực hiện các thao tác với cơ sở dữ liệu
    cur = conn.cursor()

    # Create table if it doesn't exist
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {game}.{game}_gg_reviews_agg (
        review_date DATE,
        review_star VARCHAR(255),
        emotion VARCHAR(255),
        summary_review TEXT,
        num_review_star INT2,
        num_emotion INT2,
        num_summary_review INT2,
        PRIMARY KEY (review_date, review_star, emotion, summary_review)
    )
    """
    cur.execute(create_table_query)
    print('Created table')
    conn.commit()

    print('Ingesting to database')
    for row in gg_reviews_agg.itertuples():
        try:
            cur.execute(
                f"INSERT INTO {game}.{game}_gg_reviews_agg(review_date, review_star, emotion, summary_review, num_review_star, num_emotion, num_summary_review) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (review_date, review_star, emotion, summary_review) DO NOTHING",
                (row.review_date, row.review_star, row.emotion, row.summary_review, row.num_review_star, row.num_emotion, row.num_summary_review)
            )
            # Commit transaction nếu không có lỗi
            conn.commit()
        except Exception as e:
            print("An error occurred:", e)
            # Rollback in case of error
            conn.rollback()

    cur.close()
    conn.close()
    print('Completed ingesting!')

if __name__=="__main__":
    # Number of scrolls
    GAME = 'tlbb2'

    driver = connect_to_web(GG_URL)
    soup = crawl_reviews(driver)
    gg_reviews = get_df(soup)

    model = create_model(GEM_API_KEY)
    gg_reviews = segment_df(model, gg_reviews)

    gg_reviews_agg = aggregate_df(gg_reviews)

    ingest_to_db(gg_reviews_agg, GAME)