############## Flipkart Scrapper ############## 

def flipkart_scrapper(product_name, n_pages):

    """

    Flipkart Scrapper: Helps in scrapping Flikart data ('Name', 'Price', 'Original Price', 'Description', 'Rating').
    return type: DataFrame

    Parameters
    ------------
    product_name: Enter the name of the desired product, which you want to scrape the data of
        Type: str

    n_pages: Enter the number of pages that you want to scrape
        Type: int

    Note
    ------
    Both the arguments are a compulsion. 
    If n_pages == 0: A prompt will ask you to enter a valid page number and the scrapper will re-run. 
    
    Example
    ---------
    >>>  flipkart_scrapper("Product Name", 3) 
    out: Name   Price   Original Price  Description Rating
         abc    ₹340    ₹440            Product     4.2
         aec    ₹140    ₹240            Product     4.7

    """

    import flipkart 
    return flipkart.scrappi(product_name, n_pages)

############## Snapdeal Scrapper ##############

def snapdeal_scrapper(product_name, n_pages):

    """

    Snapdeal Scrapper: Helps in scrapping Snapdeal data ('Name', 'Price', 'Original Price', 'Number of Ratings').
    return type: DataFrame

    Parameters
    ------------
    product_name: Enter the name of the desired product, which you want to scrape the data of
        Type: str

    n_pages: Enter the number of pages that you want to scrape
        Type: int

    Note
    ------
    Both the arguments are a compulsion. 
    If n_pages == 0: A prompt will ask you to enter a valid page number and the scrapper will re-run.
    
    Example
    ---------
    >>>  snapdeal_scrapper('product', 3)
    out: Name   Price   Original Price   Number of Ratings
         abc    ₹340    ₹440             40
         aec    ₹140    ₹240             34

    """

    import snapdeal
    return snapdeal.scrappi(product_name, n_pages)

############## Alibaba Scrapper ##############

def alibaba_scrapper(product_name, n_pages):

    """

    Alibaba Scrapper: Helps in scrapping Alibaba data ('Name', 'Number of Items', 'Description', 'Ratings').
    return type: DataFrame

    Parameters
    ------------
    product_name: Enter the name of desired product
        Type: str

    n_pages: Enter the number of pages that you want to scrape
        Type: int

    Note
    ------
    Both the arguments are a compulsion. 
    If n_pages == 0: A prompt will ask you to enter a valid page number and the scrapper will re-run.

    Example
    ---------
    >>>  alibabal_scrapper('product', 3)
    out: Name   Number of Items   Description   Ratings
         abc    440               product a     3.5
         aec    240               product b     4.5

    """

    import alibaba
    return alibaba.scrappi(product_name, n_pages)

############## Image Scrapper ##############

def image_scrapper(data_name, n_images=10, img_format='jpg', folder_name='images'):

    """

    Image Scrapper: Helps in scrapping images from "Google", "Yahoo", "Bing".
                    Downloads it to the desired folder.

    Parameters
    ------------
    data_name: Enter the name of object/item whose images you want to scrape/download    
        Type: str

    n_images: Enter the number of imsges you want to scrape of download
        Type: int
        Default: 10

    img_format: Enter the format of the image file
        Type: str
        Default: 'jpg'
        Accepted Values: 'jpg', 'jpeg', 'png', 'svg'
    
    folder_name: Enter the path/folder name where you want to download the images
        Type: str
        Default: 'images'

    Note
    ------
    Make sure the data_name is a valid name, and if you enter the directory make sure its a valid one.
    The scrapper will take some time to work. Wait for the images to get scrapped and downloaded, as it scrapes from all three search engines: Google, Yahoo and Bing. 
    
    Feel free to experiment with different image formats.
     
    Example
    ---------
    >>>  image_scarpper('Apple', 100, 'png', 'Apples')
    out: Starting to download...
         Successfully downloaded 100 images 
    
    """

    import image
    return image.scrappi(data_name, n_images=0, img_format='jpg', folder_name='images')

############## YouTube Scrapper ##############

def youtube_scrapper(video_sec_url, n_pages):

    """

    YouTube Scrapper: Helps in scrapping YouTube data ('Title', 'Video_url', 'Views', 'Days')
    return type: DataFrame

    Parameters
    ------------
    video_sec_url: Enter the desired YouTube URL (only video section)
        Type: str

    n_pages: The number of pages that it will scrape at a single run
        Type: int

    Note
    ------
    Make sure the url is a valid YouTube url, and please enter the url ending with 'videos', i.e urls only from the video sections are acceptable. The scrapping limit is unlimited.
    
    Example
    ---------
    >>>  youtube_scrapper('https://www.youtube.com/user/youtuber_name/videos', 3)
    out: Title       Video_url                                                Views   Days
         My video    https://www.youtube.com/user/youtuber_name/my_video      1.2m    30 days
         My video2   https://www.youtube.com/user/youtuber_name/my_video2     1m      2 weeks
    
    """

    import youtube
    return youtube.scrappi(video_sec_url, n_pages=3)

############## Wikipedia Scrapper ##############

class WikipediaScrapper():

    """

    Wikipedia Scrapper: Helps in scrapping Wikipedia data
        1. Paragraph
        2. Header
        3. Text

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.wikipedia_scrapper()

    """

############## Wikipedia Paragraph Scrapper ##############

    def para_scrapper(self, word):

        """

        Para Scrapper: Helps in scrapping paragraphs from Wikipedia.

        Parameters
        ------------
        word: Enter the desired keyword
            Type: str

        Note
        ------
        Make sure that the info of the word is available in Wikipedia.
        
        Example
        ---------
        >>>  obj.para_scrapper("Python (programming language)")
        out: ['\n',
             "Python is an interpreted high-level general-purpose programming language.", .....]
        
        """

        import wikipedia
        return wikipedia.para(word)

############## Wikipedia Header Scrapper ##############

    def header_scrapper(self, word):

        """

        Header Scrapper: Helps in scrapping headers from Wikipedia.

        Parameters
        ------------
        word: Enter the desired keyword
            Type: str

        Note
        ------
        Make sure that the info of the word is available in Wikipedia.
        
        Example
        ---------
        >>>  obj.header_scrapper("Python (programming language)")
        out: ['History',
             'Design philosophy and features', ....]
        
        """

        import wikipedia
        return wikipedia.header(word)

############## Wikipedia Text Scrapper ##############

    def text_scrapper(self, word):

        """

        Text Scrapper: Helps in scrapping text from Wikipedia.

        Parameters
        ------------
        word: Enter the desired keyword
            Type: str

        Note
        ------
        Make sure that the info of the word is available in Wikipedia.
        
        Example
        ---------
        >>>  obj.text_scrapper("Python (programming language)")
        out: ' History Python is an interpreted high-level general-purpose programming language..... ' 

        """

        import wikipedia
        return wikipedia.text(word)

############## Instagram Scrapper ##############

class InstagramScrapper():

    """

    Instagram Scrapper: Helps in scrapping instagram data (name, posts, followers, following, bio, captions)
        1. Details and post captions based on Insta handle 
        2. Post captions based on #hashtags

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.instagram_scrapper()

    """

############## Instagram account Scrapper ##############

    def account_scrapper(insta_handle, n_pages):

        """

        Instagram account Scrapper: Helps in scrapping instagram data (name, posts, followers, following, bio, captions)
        return type: DataFrame (for captions)

        Parameters
        ------------
        insta_handle: Enter the desired Insta handle/username
            Type: str

        n_pages: Enter the number of pages that you want to scrape
            Type: int

        Note
        ------
        Make sure the Instagram account is public, after certain number of runs, Instagram will ask you for your Instagram ID and PASSWORD, kindly enter it to continue.
        
        Example
        ---------
        >>>  obj.account_scrapper('Public_account_name', 3)
        out: Name: abc
             Posts: 50
             Followers: 128
             Following: 150
             Bio: Hello World!!

            Captions
            Hello World !!! My first picture.
            Hello World !!! My first program....

        """

        import instagram
        return instagram.account(insta_handle, n_pages)

############## Instagram hashtag Scrapper ##############

    def hashtag_scrapper(hashtag, n_posts):

        """

        Instagram hashtag Scrapper: Helps in scrapping instagram data (captions)
        return type: DataFrame

        Parameters
        ------------
        hashtag: Enter the desired hashtag
            Type: str

        n_posts: Enter the number of posts that you want to scrape
            Type: int

        Note
        ------
        After certain number of runs, Instagram will ask you for your Instagram ID and PASSWORD, kindly enter it to continue.
        
        Example
        ---------
        >>>  obj.hashtag_scrapper('#python', 3)
        out: Captions
             Hello World !!! My first picture. #python
             Hello World !!! My first program. #python
             This is scrapping package. #python

        """

        import instagram
        return instagram.hashtag(hashtag, n_posts)

############## News Scrapper ##############

def news_scrapper(n_pages, genre=''):

    """

    News Scrapper: Helps in scrapping News (Headlines, Time, Date, News)
    return type: DataFrame

    Parameters
    ------------
    n_pages: Enter the number of pages that it will scrape at a single run.
        Type: int

    genre: Enter the news genre
        Type: str
        Default: '' (None)
        Values accepted: 
        'national', 'business', 'sports', 'world', 'politics', 'technology', 'startup', 'entertainment', 
        'miscellaneous', 'hatke', 'science', 'automobile'

    Note
    ------
    Kindly press on the LOAD MORE button once the chrome web-driver pops up, for a seamless process of scrapping 
    
    Example
    ---------
    >>>  news_scrapper(3, 'hatke')
    out: Headlines      Time        Date                    News
         New Package    08:19 pm    25 Jun 2021,Sunday      PyScrappy is a new package...
         New Scrapper   08:19 am    25 Jun 2020,Wednesday   PyScrappy is a new Scrapper...

    """

    import news
    return news.scrappi(n_pages, genre)

############## stock Scrapper ##############

class StockScrapper():

    """

    Stock Scrapper: Helps in scrapping stock data
        1. Financial data of the stock
        2. Profile data of the stock
        3. Historical data of the stock

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.StockScrapper()

    """

############## Financial details scrapper ##############

    def financial_data_scrapper(stock_code):

        """

        Financial data scrapper: Helps in scrapping the financial data of the stock
        return type: list

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        Note
        ------
        Make sure you enter a valid stock code.
        
        Example
        ---------
        >>>  x = obj.financial_data_scrapper('STOCK_CODE')
        >>>  print(x)
        out: [{'researchDevelopment': 18752000000,
                'incomeBeforeTax': 67091000000,
                'netIncome': 57411000000,
                'sellingGeneralAdministrative': 19916000000, 
                ..............................
                .......................
                ..................
             ]

        """

        import stock
        return stock.stock_financial(stock_code)

############## Profile details scrapper ##############

    def profile_data_scrapper(stock_code):

        """

        Profile data scrapper: Helps in scrapping the Profile data of the stock
        return type: None

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        Note
        ------
        Make sure you enter a valid stock code.
        
        Example
        ---------
        >>>  obj.profile_data_scrapper('STOCK_CODE')
        out: About the Company Officers:
             ------------------------------
             Python
             Programing language
             ..........
             About the Company:
             ----------------------
             Python is an interpreted high-level general-purpose programming language..........

        """

        import stock
        return stock.stock_profile(stock_code)

############## Profile details scrapper ##############

    def historical_data_scrapper(stock_code, stock_range, stock_interval):

        """

        Historical data scrapper: Helps in scrapping the Historical data of the stock ('Date', 'Open', 'High', 'Low', 'Close', 'Adjusted Close', 'Volume')
        return type: Dataframe

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        stock_range: Enter the range/time period of the stock
            Type: str
            Accepted values: '1d', '5d', '1wk', '3wk', '3mo', '6mo', '1y', '5y', 'Max' (or any value in 'd', 'wk', 'mo', 'y' format) 

        stock_interval: Enter the time period interval of the data
            Type: str
            Accepted values: 'Daily', 'Weekly', 'Monthly'

        Note
        ------
        Make sure you enter a valid stock code, time period and time interval 
        
        Example
        ---------
        >>>  obj.historical_data_scrapper('STOCK_CODE', '1y', '1d')
        out: Date       Open    High    Low     Close   Adjusted Close  Volume
             2021-03-12 123.30  132.4   110.7   120.23  120.1           13247543
             2021-07-12 123.30  132.4   110.7   120.23  120.1           132473435
        """

        import stock
        return stock.stock_history(stock_code, stock_range, stock_interval)