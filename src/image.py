from bs4 import BeautifulSoup
import requests
import os 

usr_agent = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
}

def scrappi(data, n_images, img_format, folder_name):
        
    URL = ['https://www.bing.com/images/search?q=', 'https://www.google.com/search?site=&tbm=isch&source=hp&biw=1873&bih=990&q=',
            'https://images.search.yahoo.com/search/images?p=']
    
    def check(folder_name):
        try: 
            os.mkdir(folder_name)
            return folder_name
        except:
            print("Folder Exist with that name!")
            folder_name = input("Enter a new Folder name: \n")
            try: 
                os.mkdir(folder_name)
                return folder_name
            except: return check(folder_name)
            
    folder_name = check(folder_name)

    print('Starting to Download...')

    for i in URL:
        searchurl = i + str(data)
        response = requests.get(searchurl, headers = usr_agent)
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        results = soup.findAll('img', limit = n_images)

        if len(results) != 0:
            for i, image in enumerate(results):
                try: image_link = image["data-srcset"]
                except:
                    try: image_link = image["data-src"]
                    except:
                        try: image_link = image["data-fallback-src"]
                        except:
                            try: image_link = image["src"]
                            except: pass
                    try:
                        r = requests.get(image_link).content
                        try: r = str(r, 'utf-8')
                        except UnicodeDecodeError:
                            with open(f"{folder_name}/images{i+1}.{img_format}", "wb+") as f: f.write(r)
                    except: pass
                    
    return 'Successfully Downloaded ' + str(n_images) + ' images'