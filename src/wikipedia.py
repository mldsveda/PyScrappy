from urllib.request import urlopen
from bs4 import BeautifulSoup
import re

usr_agent = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
    'Accept-Encoding': 'none',
    'Accept-Language': 'en-US,en;q=0.8',
    'Connection': 'keep-alive',
}

def para(word):
    word=word.replace(' ', '_')
    # Specify url of the web page
    source = urlopen('https://en.wikipedia.org/wiki/'+str(word)).read()
    # Make a soup 
    soup = BeautifulSoup(source,'lxml')

    # Extract the plain text content from paragraphs
    paras = []
    for paragraph in soup.find_all('p'):
        paras.append(str(paragraph.text))
    return paras

def header(word):
    word=word.replace(' ', '_')
    # Specify url of the web page
    source = urlopen('https://en.wikipedia.org/wiki/'+str(word)).read()
    soup = BeautifulSoup(source, "lxml")

    # Extract text from paragraph headers
    heads = []
    for head in soup.find_all('span', attrs={'mw-headline'}):
        heads.append(str(head.text))
    return heads

def text(word):
    word=word.replace(' ', '_')
    # Specify url of the web page
    source = urlopen('https://en.wikipedia.org/wiki/'+str(word)).read()
    soup = BeautifulSoup(source, "lxml")
    
    paras = []
    for paragraph in soup.find_all('p'):
        paras.append(str(paragraph.text))
        
    heads = []
    for head in soup.find_all('span', attrs={'mw-headline'}):
        heads.append(str(head.text))

    # Interleave paragraphs & headers
    text = [val for pair in zip(paras, heads) for val in pair]
    text = ' '.join(text)

    # Drop footnote superscripts in brackets
    text = re.sub(r"\[.*?\]+", '', text)

    # Replace '\n' (a new line) with '' and end the string at $1000.
    text = text.replace('\n', '')[:-11]
    return text