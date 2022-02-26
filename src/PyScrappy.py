############## ECommereceScrapper ############## 
class ECommerceScrapper():
    
    """

    ECommerece Scrapper: Helps in scrapping data from E-Comm websites
        1. Alibaba
        2. Amazon
        3. Flipkart
        4. Snapdeal

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.ECommerceScrapper()

    """

    ############## Alibaba Scrapper ##############
    def alibaba_scrapper(self, product_name, n_pages):

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
        >>>  obj.alibabal_scrapper('product', 3)
        out: Name   Number of Items   Description   Ratings
            abc    440               product a     3.5
            aec    240               product b     4.5

        """

        import alibaba
        return alibaba.scrappi(product_name, n_pages)


    ############## Amazon Scrapper ##############
    def amazon_scrapper(self, product_name, n_pages):

        """

        Amazon Scrapper: Helps in scrapping amazon data ('Description', 'Rating', 'Votes', 'Offer Price', 'Actual Price').
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
        >>>  obj.amazon_scrapper('product', 3)
        out: Name   Number of Items   Description   Ratings
             abc    440               product a     3.5
             aec    240               product b     4.5

        """

        import amazon
        return amazon.scrappi(product_name, n_pages)


    ############## Flipkart Scrapper ############## 
    def flipkart_scrapper(self, product_name, n_pages):

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
        >>>  obj.flipkart_scrapper("Product Name", 3) 
        out: Name   Price   Original Price  Description Rating
             abc    ₹340    ₹440            Product     4.2
             aec    ₹140    ₹240            Product     4.7

        """

        import flipkart 
        return flipkart.scrappi(product_name, n_pages)


    ############## Snapdeal Scrapper ##############
    def snapdeal_scrapper(self, product_name, n_pages):

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
        >>>  obj.snapdeal_scrapper('product', 3)
        out: Name   Price   Original Price   Number of Ratings
             abc    ₹340    ₹440             40
             aec    ₹140    ₹240             34

        """

        import snapdeal
        return snapdeal.scrappi(product_name, n_pages)

########################################################################################################################

############## FoodScrapper ##############
class FoodScrapper():

    """

    Food Scrapper: Helps in scrapping data from food delivery websites
        1. Swiggy
        2. Zomato

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.FoodScrapper()

    """

    ############## Swiggy Scrapper ##############
    def swiggy_scrapper(self, city, n_pages):

        """

        Swiggy Scrapper: Helps in scrapping swiggy data ('Name', 'Cuisine', 'Price', 'Rating').
        return type: DataFrame

        Parameters
        ------------
        city: Enter the name of desired city were swiggy delivers
            Type: str

        n_pages: Enter the number of pages that you want to scrape
            Type: int

        Note
        ------
        Both the arguments are a compulsion. 

        Example
        ---------
        >>>  obj.swiggy_scrapper('city', 3)
        out: Name   Cuisine     Price           Rating
             abc    indian      ₹123 for two    4.5
             xyz    indian      ₹342 for two    4.3

        """

        import swiggy
        return swiggy.scrappi(city, n_pages)


    ############## Zomato Scrapper ##############
    def zomato_scrapper(self, city, n_pages):

        """

        Zomato Scrapper: Helps in scrapping zomato data ("Name", "Cusine", "Price", "Rating", "Delivery Time", "Review counts").
        return type: DataFrame

        Parameters
        ------------
        city: Enter the name of desired city were zomato delivers
            Type: str

        n_pages: Enter the number of pages that you want to scrape
            Type: int

        Note
        ------
        Both the arguments are a compulsion. 

        Example
        ---------
        >>>  obj.zomato_scrapper('city', 3)
        out: Name   Cuisine     Price           Rating    Delivery Time     Review Count
             abc    indian      ₹123 for two    4.5         45min               3.4K
             xyz    indian      ₹342 for two    4.3         40min               1.2K

        """

        import zomato
        return zomato.scrappi(city, n_pages)

########################################################################################################################

############## Image Scrapper ##############
def image_scrapper(data_name, n_images=10, img_format='jpg', folder_name='images'):

    """

    Image Scrapper: Helps in scrapping images from "Google", "Yahoo", "Bing".
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
        Accepted Values: 'jpg', 'jpeg', 'png', 'gif'
    
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
    return image.scrappi(data_name, n_images, img_format, folder_name)

########################################################################################################################

############## IMDB Scrapper ##############
def imdb_scrapper(genre, n_pages):

    """

    IMDB Scrapper: Helps in scrapping movies from IMDB.
    return type: DataFrame

    Parameters
    ------------
    genre: Enter the genre of the movie
        Type: str

    n_pages: Enter the number of pages that it will scrape at a single run.
        Type: int

    Note
    ------
    both the parameters are compulsory.

    Example
    ---------
    >>>  imdb_scrapper('action', 4)
    out: Title  Year    Certificate     Runtime     Genre   Rating  Description    Stars   Directors   Votes
         asd    2022        UA          49min       action  3.9     about the..     asd     dfgv        23
         scr    2022        15+         89min       action  4.9     about the..     add     dfgv        23
    """

    import imdb
    return imdb.scrappi(genre, n_pages)

########################################################################################################################

############## LinkedIn Scrapper ##############
def linkedin_scrapper(job_title, n_pages):

    """

    LinkedIn Scrapper: Helps in scrapping job related data from LinkedIn (Job Title, Company Name, Location, Salary, Benefits, Date)
    return type: DataFrame

    Parameters
    ------------
    job_title: Enter the job title or type.
        Type: str

    n_pages: Enter the number of pages that it will scrape at a single run.
        Type: int

    Note
    ------
    Both the parameters is a compulsion

    Example
    ---------
    >>>  linkedin_scrapper('python', 1)
    out: Job Title      Company Name    Location    Salary      Benefits                Date
         abc            PyScrappy       US          2300        Actively Hiring +1      1 day ago
         abc            PyScrappy       US          2300        Actively Hiring +1      1 day ago
         ...
         ..

    """
    
    import linkedin
    return linkedin.scrappi(job_title, n_pages)

########################################################################################################################

############## News Scrapper ##############
def news_scrapper(n_pages, genre = str()):

    """

    News Scrapper: Helps in scrapping News (Headlines, Time, Date, News)
    return type: DataFrame

    Parameters
    ------------
    n_pages: Enter the number of pages that it will scrape at a single run.
        Type: int

    genre: Enter the news genre
        Type: str
        Default: str() (None)
        Values accepted: 
        'national', 'business', 'sports', 'world', 'politics', 'technology', 'startup', 'entertainment', 
        'miscellaneous', 'hatke', 'science', 'automobile'

    Note
    ------
    n_pages in a compulsion

    Example
    ---------
    >>>  news_scrapper(3, 'hatke')
    out: Headlines      Time        Date                    News
         New Package    08:19 pm    25 Jun 2021,Sunday      PyScrappy is a new package...
         New Scrapper   08:19 am    25 Jun 2020,Wednesday   PyScrappy is a new Scrapper...

    """
    
    import news
    return news.scrappi(n_pages, genre = genre)

########################################################################################################################

############## Social Media Scrapper ##############
class SocialMediaScrapper():

    """

    Social Media Scrapper: Helps in scrapping data from social media platforms 
        1. Instagram
        2. Twitter
        3. YouTube

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.SocialMediaScrapper()

    """

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
        >>> obj2 = obj.InstagramScrapper()

        """

        ############## Instagram account Scrapper ##############
        def account_scrapper(self, insta_handle, n_pages):

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
            >>>  obj2.account_scrapper('Public_account_name', 3)
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
        def hashtag_scrapper(self, hashtag, n_posts):

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
            >>>  obj2.hashtag_scrapper('#python', 3)
            out: Captions
                Hello World !!! My first picture. #python
                Hello World !!! My first program. #python
                This is scrapping package. #python

            """

            import instagram
            return instagram.hashtag(hashtag, n_posts)


    ############## Twitter Scrapper ##############
    def twitter_scrapper(self, hashtag, n_pages):

        """

        Twitter Scrapper: Helps in scrapping data from Twitter ("Name", "Twitter handle", "Post Time", "Tweet", "Reply Count", "Retweet Count", "Like Count")
        return type: DataFrame

        Parameters
        ------------
        hashtag: Enter the desired hashtag
            Type: str

        n_pages: Enter the number of pages that you want to scrape
            Type: int

        Note
        ------
        Both the arguments are a compulsion

        Example
        ---------
        >>>  obj.twitter_scrapper('#python', 3)
        out: Name   Twitter handle  Post Time   Tweet       Reply Count     Retweet Count   Like Count
             asd    @ksnkj          3:49:36     this is ...     102           230            1.2k
             fsd    @ksdtj          6:49:36     it is a ...     12            30             1k

        """

        import twitter
        return twitter.scrappi(hashtag, n_pages)


    ############## YouTube Scrapper ##############
    def youtube_scrapper(self, video_sec_url, n_pages):

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
        >>>  obj.youtube_scrapper('https://www.youtube.com/user/youtuber_name/videos', 3)
        out: Title       Video_url                                                Views   Days
             My video    https://www.youtube.com/user/youtuber_name/my_video      1.2m    30 days
             My video2   https://www.youtube.com/user/youtuber_name/my_video2     1m      2 weeks
        
        """

        import youtube
        return youtube.scrappi(video_sec_url, n_pages)

########################################################################################################################

############## Song Scrapper ##############
class SongScrapper():
    
    """

    Song Scrapper: Helps in scrapping songs related data
        1. Soundcloud

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.SongScrapper()

    """    

    ############## Soundcloud Scrapper ##############
    def soundcloud_scrapper(self, track_name, n_pages):

        """

        Soundcloud Scrapper: Helps in scrapping data from soundcloud ('Uploader', 'Music Title', 'Time of Upload', 'Plays')
        return type: DataFrame

        Parameters
        ------------
        track_name: Enter the name of desired track/song/music
            Type: str

        n_pages: The number of pages that it will scrape at a single run
            Type: int

        Note
        ------
        Make sure to enter a valid name
        
        Example
        ---------
        >>>  obj.soundcloud_scrapper('music track', 3)
        out: Uploader       Music Title     Time of Upload      Plays
             name1          music           3:34:76             234
             name2          music           5:6:34              445

        """

        import soundcloud
        return soundcloud.soundcloud_tracks(track_name, n_pages)


    ############## Spotify Scrapper ##############
    def spotify_scrapper(self, track_name, n_pages):

        """

        Spotify Scrapper: Helps in scrapping data from spotify ('Id', 'Title', 'Singers', 'Album', 'Duration')
        return type: DataFrame

        Parameters
        ------------
        track_name: Enter the name of desired track/song/music/artist/bodcast
            Type: str

        n_pages: The number of pages that it will scrape at a single run
            Type: int

        Note
        ------
        Make sure to enter a valid name
        
        Example
        ---------
        >>>  obj.spotify_scrapper('pop', 3)
        out: Id     Title   Singers     Album   Duration
             1      abc     abc         abc     2:30
             2      def     def         def     2:30

        """

        import spotify
        return spotify.scrappi(track_name, n_pages)

########################################################################################################################

############## stock Scrapper ##############
class StockScrapper():

    """

    Stock Scrapper: Helps in scrapping stock data
        1. Analysis data of the stock
        2. Historical data of the stock
        3. Profile data of the stock

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.StockScrapper()

    """

    ############## Analysis data scrapper ##############
    def analysis_data_scrapper(self, stock_code, analysis_type):

        """

        Analysis data scrapper: Helps in scrapping the Analytical data of the stock
        return type: DataFrame

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        analysis_type: Enter the name of the analysis type of the stock
            Type: str
            Accepted values: "earning estimate", "revenue estimate", "earning history", "EPS trend", "EPS revision", "growth estimate"

        Note
        ------
        Make sure you enter a valid stock code.
        
        Example
        ---------
        >>>  obj.analysis_data_scrapper('STOCK_CODE', 'earning estimates') 

        """

        import stock
        return stock.stock_analysis(stock_code, analysis_type)


    ############## Historical data scrapper ##############
    def historical_data_scrapper(self, stock_code, time_period, frequency):

        """

        Historical data scrapper: Helps in scrapping the Historical data of the stock ('Date', 'Open', 'High', 'Low', 'Close', 'Adjusted Close', 'Volume')
        return type: CSV file

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        time_period: Enter the range/time period of the stock
            Type: str
            Accepted values: '1d', '5d', '3m', '6m', '1y', '5y', 'max'

        frequency: Enter the time period interval of the data
            Type: str
            Accepted values: 'Daily', 'Weekly', 'Monthly'

        Note
        ------
        Make sure you enter a valid stock code, time period and time interval 
        
        Example
        ---------
        >>>  obj.historical_data_scrapper('STOCK_CODE', '1y', 'Daily')

        """

        import stock
        return stock.stock_history(stock_code, time_period, frequency)


    ############## Profile details scrapper ##############
    def profile_data_scrapper(self, stock_code):

        """

        Profile data scrapper: Helps in scrapping the Profile data of the stock (profile, description, executives)
        return type: [dict, str, DataFrame]

        Parameters
        ------------
        stock_code: Enter the desired stock code
            Type: str

        Note
        ------
        Make sure you enter a valid stock code.
        Make sure to store the result in three variable as list spreading
        
        Example
        ---------
        >>>  profile, description, executives = obj.profile_data_scrapper('STOCK_CODE')

        """

        import stock
        return stock.stock_profile(stock_code)

########################################################################################################################

############## Wikipedia Scrapper ##############
class WikipediaScrapper():

    """

    Wikipedia Scrapper: Helps in scrapping Wikipedia data
        1. Header
        2. Paragraph
        3. Text

    Type: class

    Note
    ------
    Create an object of this class to procced further.

    Example
    ---------
    >>> obj = PyScrappy.WikipediaScrapper()

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

########################################################################################################################