import pandas as pd
from time import sleep
from urllib.request import urlopen
from bs4 import BeautifulSoup

def scrappi(genre, n_pages):
    source = urlopen(f"https://www.imdb.com/search/title/?genres={genre}").read()
    data = {
        "title" : [],
        "year" : [],
        "certificate" : [],
        "runtime" : [],
        "genre" : [],
        "rating" : [],
        "description" : [],
        "stars" : [],
        "directors" : [],
        "votes" : []
    }
    
    for i in range(n_pages):
        soup = BeautifulSoup(source,'lxml') 
        cards = soup.find_all("div", {"class":"lister-item-content"})
        for card in cards:
            try: data["title"].append(card.find("h3", {"class":"lister-item-header"}).find("a").text)
            except: data["title"].append(None)
            try: data["year"].append(card.find("h3", {"class":"lister-item-header"}).find_all("span")[-1].text[1:-1])
            except: data["year"].append(None)
            try: data["certificate"].append(card.find("span", {"class":"certificate"}).text)
            except: data["certificate"].append(None)
            try: data["runtime"].append(card.find("span", {"class":"runtime"}).text)
            except: data["runtime"].append(None)
            try: data["genre"].append((card.find("span", {"class":"genre"}).text).strip())
            except: data["genre"].append(None)
            try: data["rating"].append((card.find("div", {"class":"ratings-imdb-rating"}).text).strip())
            except: data["rating"].append(None)
            try: data["description"].append((card.find_all("p", {"class":"text-muted"})[-1].text).strip())
            except: data["description"].append(None)
            casts = card.find("p", {"class":""}).text.split("|")
            star, director = None, None
            for cast in casts:
                temp = cast.strip().replace("\n", "").replace(":", ",").split(",")
                if temp[0] in ["Star", "Stars"]: star = ', '.join(temp[1:])
                elif temp[0] in ["Director", "Directors"]: director = ', '.join(temp[1:])
            data["stars"].append(star)
            data["directors"].append(director)
            try: data["votes"].append(card.find("span", {"name":"nv"}).text)
            except: data["votes"].append(None)
        try:
            source = urlopen("https://www.imdb.com"+soup.find("a", {"class":"lister-page-next next-page"}).attrs['href']).read()
        except:
            break

    return pd.DataFrame(data)