import pandas as pd
from datetime import datetime
import time
from tqdm import tqdm
from info import *
import sqldf
from itertools import zip_longest


from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
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
    driver.refresh()
    
    ## Insert username and password infomation
    ### Wait until the class of the body tag changes
    WebDriverWait(driver, 10).until(
        lambda d: "tb-default-theme idms-login login-page login-type-asc page-ready" in d.find_element(By.TAG_NAME, "body").get_attribute("class")
    )

    ### Wait until the iframe appears
    iframe = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "iframe")))

    ### Switch to the iframe containing the user info input fields
    driver.switch_to.frame(iframe)

    ### Enter user info
    driver.find_element(By.ID, "account_name_text_field").send_keys('hauct@vng.com.vn')
    driver.find_element(By.XPATH, '/html/body/div[3]/apple-auth/div/div[1]/div/sign-in/div/div[1]/button[1]/i').click()
    time.sleep(2)

    driver.find_element(By.ID, "password_text_field").send_keys('Haudau156')
    driver.find_element(By.XPATH, '/html/body/div[3]/apple-auth/div/div[1]/div/sign-in/div/div[1]/button[1]/i').click()
    time.sleep(60)

    ### Return to the main content and return the driver
    driver.switch_to.default_content()
    print(f'Connected to {url}')
    return driver

# Crawl data
## Function to scroll the target div until the end
def scroll_target_div(driver):
    target_div = driver.find_element(By.CSS_SELECTOR, '#main-ui-view > div.flexcol.ng-scope > div.pane-layout.ng-scope > div.pane-layout-content.ng-scope > div.pane-layout-content-wrapper.arrtwodeetwo.ng-scope')

    # Get the initial scroll height
    last_height = target_div.get_attribute('scrollHeight')

    while True:
        # Scroll to the bottom of the div
        driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', target_div)

        # Wait for the page to load
        time.sleep(3)

        # Get the current scroll height
        current_height = target_div.get_attribute('scrollHeight')

        # If the scroll height hasn't changed, exit the loop
        if current_height == last_height:
            break

        # Update the last height
        last_height = current_height
        
## Function to get all reviews in soup type
def crawl_reviews(driver):
    ### Thay đổi sang frame chứa review và comment
    iframe = driver.find_element(By.XPATH, '/html/body/div[2]/div/div[2]/div/main/div/div/div/div/div[1]/div[2]/div/div/div/div[2]/iframe')
    driver.switch_to.frame(iframe)

    ### Chọn qua country "VN"
    driver.find_element(By.XPATH, '/html/body/div[1]/div[5]/div[5]/div[2]/div[2]/div[3]/div[1]/div[3]/section/div[1]/div[1]/a/span[2]').click()
    driver.find_element(By.XPATH, '/html/body/div[1]/div[5]/div[5]/div[2]/div[2]/div[3]/div[1]/div[3]/section/div[1]/div[1]/div/ul/li[146]').click()

    ### Sroll tới cuối cùng để view toàn bộ comment
    scroll_target_div(driver)

    ### Lấy ra soup
    page_source = driver.page_source
    soup = BeautifulSoup(page_source, 'html.parser')
    print('Got source of page !!!')

    ### Close the browser
    driver.quit()
    return soup

## Function to collect data from soup, transform into a pandas df
### Supportively transform functions
def get_list_contents(soup):
    texts = [div.get_text() for div in soup.find_all('div', {'class': 'ng-binding', 'ng-bind': 'review.value.review'})]
    return texts

def get_list_stars(soup):
    texts = []
    for i in range(1, 6):
        class_name = f'stars alt count-{i}-0'
        ng_bind_value = str(i)
        divs = soup.find_all('div', {'class': class_name, 'ng-bind': ng_bind_value})
        for div in divs:
            texts.append(div.get_text())
    return texts

def app_convert_datetime(text):
    text = text.split('–')[1].strip(' ')
    text = datetime.strptime(text, '%b %d, %Y').strftime('%Y-%m-%d')
    return text

def get_list_dates(soup):
    text = [app_convert_datetime(span.get_text()) for span in soup.find_all('span', {'class': 'ng-binding ng-scope', 'ng-bind': "l10n.interpolate('ITC.apps.r2d2.universal.activity.ratings.review.meta', {USER: review.value.nickname, DATE: ITC.time.showAbbreviatedDate(review.value.lastModified)})", 'ng-if': "!review.value.edited"})]
    return text

### main function
def get_df(soup):
    review_dates = get_list_dates(soup)
    review_stars = get_list_stars(soup)
    review_contents = get_list_contents(soup)

    ### Convert to a pandas dataframe
    reviews_dict = []
    print('Creating a dataframe')

    for review_date, review_star, review_content in zip_longest(review_dates, review_stars, review_contents):
        row = {
            "review_date": review_date,
            "review_star": review_star,
            "review_content": review_content
        }
        reviews_dict.append(row)
    print('Creating completed !')

    app_reviews = pd.DataFrame(reviews_dict)
    return app_reviews

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
    return response.text

def segment_df(model, app_reviews):
    print('Running the AI segmentation model!')

    print('Classifying the emotion')
    app_reviews['emotion'] = app_reviews['review_content'].apply(lambda x: classify_emotion(model, x))
    print('Completed classifying the emotion')

    print('Summarizing reviews')
    app_reviews['summary_review'] = app_reviews['review_content'].apply(lambda x: summary_review(model, x))
    print('Completed summarizing reviews')

    print('Completed segmentation!')
    return app_reviews

############################ AGGREGATE RESULT ############################
def aggregate_df(app_reviews):
    print('Aggregating the table')
    app_reviews_agg_query = '''
        SELECT review_date, review_star, emotion, summary_review, COUNT(review_star) AS num_review_star, COUNT(emotion) AS num_emotion, COUNT(summary_review) AS num_summary_review
        FROM app_reviews
        GROUP BY review_date, review_star, emotion, summary_review
        ORDER BY review_date DESC, review_star DESC
    '''
    app_reviews_agg = sqldf.run(app_reviews_agg_query)
    print('Completed Aggregating!')
    return app_reviews_agg

############################ INGEST TO DATABASE ############################
def ingest_to_db(app_reviews_agg, game):
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host=HOST,
        database=DB_NAME,
        user=USER,
        password=PASSWORDS
    )

    # Create a cursor object to interact with the database
    cur = conn.cursor()

    # Create table if it doesn't exist
    create_table_query = f"""
    CREATE TABLE IF NOT EXISTS {game}.{game}_app_reviews_agg (
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
    for row in app_reviews_agg.itertuples():
        try:
            cur.execute(
                f"INSERT INTO {game}.{game}_app_reviews_agg(review_date, review_star, emotion, summary_review, num_review_star, num_emotion, num_summary_review) VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (review_date, review_star, emotion, summary_review) DO NOTHING",
                (row.review_date, row.review_star, row.emotion, row.summary_review, row.num_review_star, row.num_emotion, row.num_summary_review)
            )
            # Commit transaction if no error occurs
            conn.commit()
        except Exception as e:
            print("An error occurred:", e)
            # Rollback in case of error
            conn.rollback()

    cur.close()
    conn.close()
    print('Completed ingesting!')

if __name__=="__main__":
    GAME = 'tlbb2'

    driver = connect_to_web(APP_URL)
    soup = crawl_reviews(driver)
    app_reviews = get_df(soup)

    model = create_model(GEM_API_KEY)
    app_reviews = segment_df(model, app_reviews)

    app_reviews_agg = aggregate_df(app_reviews)

    ingest_to_db(app_reviews_agg, GAME)