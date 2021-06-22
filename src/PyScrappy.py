
def flipkart_scrapper(n_pages):

    """

    Flipkart Scrapper: Helps in scrapping Flikart data ('Name', 'Price', 'Original Price', 'Description').
    return type: DataFrame

    Parameters
    ------------
    n_pages: The number of pages that it will scrape at a single run
        Type: int

    Note
    ------
    A prompt will ask you to enter a "Flipkart" url. Make sure you add a valid one.
    Currently supports card and rectangular style.
    
    Example
    ---------
    >>>  flipkart_scrapper(3)
    out: Enter the desired Fipkart URL: https://www.flipkart.com/skjngvd?cSJNdvk=sdv
         Name   Price   Original Price  Description
         abc    ₹340    ₹440            Product
         aec    ₹140    ₹240            Product

    """

    import flipkart 
    return flipkart.scrappi(n_pages)

def snapdeal_scrapper(n_pages):

    """

    Snapdeal Scrapper: Helps in scrapping Snapdeal data ('Name', 'Original Price', 'Discounted Price').
    return type: DataFrame

    Parameters
    ------------
    n_pages: The number of pages that it will scrape at a single run
        Type: int

    Note
    ------
    A prompt will ask you to enter a "Snapdeal" url. Make sure you add a valid one.
    
    Example
    ---------
    >>>  snapdeal_scrapper(3)
    out: Enter the desired Snapdeal URL: https://www.snapdeal.com/skjngvd?cSJNdvk=sdv
         Name   Original Price   Discounted Price
         abc    ₹440             ₹340
         aec    ₹240             ₹140

    """

    import snapdeal
    return snapdeal.scrappi(n_pages)

def alibaba_scrapper(n_pages):

    """

    Alibaba Scrapper: Helps in scrapping Alibaba data ('Name', 'Number of Items').
    return type: DataFrame

    Parameters
    ------------
    n_pages: The number of pages that it will scrape at a single run
        Type: int

    Note
    ------
    A prompt will ask you to enter a "Alibaba" url. Make sure you add a valid one.
    
    Example
    ---------
    >>>  alibabal_scrapper(3)
    out: Enter the desired Alibaba URL: https://www.alibaba.com/skjngvd?cSJNdvk=sdv
         Name   Number of Items
         abc    440             
         aec    240             

    """

    import alibaba
    return alibaba.scrappi(n_pages)

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

class wikipedia_scrapper():

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

def instagram_scrapper(url, n_pages):

    """

    Instagram Scrapper: Helps in scrapping instagram data (name, posts, followers, following, bio, captions)
    return type: DataFrame (for captions)

    Parameters
    ------------
    url: Enter the desired profile URL (Public Profile)
        Type: str

    n_pages: The number of pages that it will scrape at a single run.
        Type: int

    Note
    ------
    Make sure the Instagram account is public, after certain number of runs, Instagram will ask you for your Instagram ID and PASSWORD, kindly enter it to continue.
    
    Example
    ---------
    >>>  instagram_scrapper('https://www.instagram.com/Public_account_name', 3)
    out: Name: abc
         Posts: 50
         Followers: 128
         Following: 150
         Bio: Hello World!!

         Captions
         Hello World !!! My first picture.

    """

    import instagram
    return instagram.insta_details(url, n_pages)